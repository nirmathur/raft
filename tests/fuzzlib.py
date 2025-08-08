#!/usr/bin/env python3
"""
Fuzz testing helper library for RAFT.
Provides generators for charter pattern injection, signature-mismatch detection,
multi-hunk line tracking, and cache fall-back paths.
"""

import random
import re
import string
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class FuzzTest:
    """Represents a single fuzz test case."""

    name: str
    diff: str
    expected_result: bool
    test_type: str
    metadata: Dict = None


def generate_random_string(length: int = 10) -> str:
    """Generate a random string for fuzz testing."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_charter_pattern_injection_tests() -> List[FuzzTest]:
    """Generate tests that inject forbidden patterns from charter."""
    charter_patterns = [
        r"\beval\b",
        r"\bexec\b",
        r"\bos\.system\b",
        r"\bsubprocess\b",
        r"\b__import__\b",
    ]

    tests = []
    for pattern in charter_patterns:
        # Extract the pattern name for test naming
        pattern_name = pattern.replace(r"\b", "").replace("\\", "")

        # Test 1: Direct injection
        test_name = f"charter_injection_{pattern_name}_direct"
        diff = f"""
+ def {generate_random_string()}():
+     {pattern_name}('rm -rf /')
"""
        tests.append(
            FuzzTest(
                name=test_name,
                diff=diff,
                expected_result=False,  # Should be caught
                test_type="charter_injection",
                metadata={"pattern": pattern, "injection_type": "direct"},
            )
        )

        # Test 2: Indirect injection via string concatenation
        test_name = f"charter_injection_{pattern_name}_indirect"
        diff = f"""
+ def {generate_random_string()}():
+     cmd = '{pattern_name}'
+     cmd += '("rm -rf /")'
+     eval(cmd)
"""
        tests.append(
            FuzzTest(
                name=test_name,
                diff=diff,
                expected_result=False,  # Should be caught
                test_type="charter_injection",
                metadata={"pattern": pattern, "injection_type": "indirect"},
            )
        )

        # Test 3: Nested injection
        test_name = f"charter_injection_{pattern_name}_nested"
        diff = f"""
+ def {generate_random_string()}():
+     def inner():
+         {pattern_name}('rm -rf /')
+     inner()
"""
        tests.append(
            FuzzTest(
                name=test_name,
                diff=diff,
                expected_result=False,  # Should be caught
                test_type="charter_injection",
                metadata={"pattern": pattern, "injection_type": "nested"},
            )
        )

    return tests


def generate_signature_mismatch_tests() -> List[FuzzTest]:
    """Generate tests that change function signatures to trigger signature-mismatch detection."""

    tests = []

    # Test 1: Change argument name
    test_name = "signature_mismatch_arg_name_change"
    diff = """
- def process_data(data, config):
+ def process_data(data, new_config):
     return data.upper()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should trigger signature mismatch
            test_type="signature_mismatch",
            metadata={
                "change_type": "arg_name",
                "old_arg": "config",
                "new_arg": "new_config",
            },
        )
    )

    # Test 2: Add argument
    test_name = "signature_mismatch_add_arg"
    diff = """
- def process_data(data):
+ def process_data(data, extra_param=None):
     return data.upper()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should trigger signature mismatch
            test_type="signature_mismatch",
            metadata={"change_type": "add_arg", "new_arg": "extra_param"},
        )
    )

    # Test 3: Remove argument
    test_name = "signature_mismatch_remove_arg"
    diff = """
- def process_data(data, config, debug=False):
+ def process_data(data, config):
     return data.upper()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should trigger signature mismatch
            test_type="signature_mismatch",
            metadata={"change_type": "remove_arg", "removed_arg": "debug"},
        )
    )

    # Test 4: Change argument order
    test_name = "signature_mismatch_arg_order_change"
    diff = """
- def process_data(data, config, debug=False):
+ def process_data(config, data, debug=False):
     return data.upper()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should trigger signature mismatch
            test_type="signature_mismatch",
            metadata={
                "change_type": "arg_order",
                "old_order": ["data", "config", "debug"],
                "new_order": ["config", "data", "debug"],
            },
        )
    )

    # Test 5: Change return type annotation (currently not detected by RAFT)
    test_name = "signature_mismatch_return_type_change"
    diff = """
- def process_data(data: str) -> str:
+ def process_data(data: str) -> bytes:
     return data.upper().encode()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=True,  # Currently passes as RAFT doesn't check return types
            test_type="signature_mismatch",
            metadata={
                "change_type": "return_type",
                "old_return": "str",
                "new_return": "bytes",
                "note": "RAFT currently only checks args, not return types",
            },
        )
    )

    return tests


def generate_multi_hunk_tests() -> List[FuzzTest]:
    """Generate tests with multi-hunk diffs to test line number tracking."""

    tests = []

    # Test 1: Multi-hunk with line number preservation
    test_name = "multi_hunk_line_tracking"
    diff = """
@@ -10,6 +10,7 @@
 def process_data(data):
     result = []
     for item in data:
+        # Add validation
         if item > 0:
             result.append(item)
     return result
@@ -25,8 +26,9 @@
 def validate_input(input_data):
     if not input_data:
         return False
+    # Add type checking
     if not isinstance(input_data, list):
         return False
     return True
@@ -40,6 +42,7 @@
 def main():
     data = [1, 2, 3, 4, 5]
+    # Add logging
     print("Processing data...")
     result = process_data(data)
     return result
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=True,  # Should be safe
            test_type="multi_hunk",
            metadata={"hunks": 3, "line_changes": [11, 29, 45]},
        )
    )

    # Test 2: Multi-hunk with forbidden pattern in second hunk
    test_name = "multi_hunk_with_forbidden_pattern"
    diff = """
@@ -10,6 +10,7 @@
 def process_data(data):
     result = []
     for item in data:
+        # Add validation
         if item > 0:
             result.append(item)
     return result
@@ -25,8 +26,9 @@
 def validate_input(input_data):
     if not input_data:
         return False
+    eval('rm -rf /')  # Forbidden pattern
     if not isinstance(input_data, list):
         return False
     return True
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should be caught
            test_type="multi_hunk",
            metadata={"hunks": 2, "forbidden_pattern": "eval", "hunk_with_pattern": 2},
        )
    )

    # Test 3: Multi-hunk with signature change
    test_name = "multi_hunk_signature_change"
    diff = """
@@ -10,6 +10,7 @@
 def process_data(data):
     result = []
     for item in data:
+        # Add validation
         if item > 0:
             result.append(item)
     return result
@@ -25,8 +26,9 @@
-def validate_input(input_data):
+def validate_input(input_data, strict=False):
     if not input_data:
         return False
+    # Add type checking
     if not isinstance(input_data, list):
         return False
     return True
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=diff,
            expected_result=False,  # Should trigger signature mismatch
            test_type="multi_hunk",
            metadata={"hunks": 2, "signature_change": True, "added_arg": "strict"},
        )
    )

    return tests


def generate_cache_fallback_tests() -> List[FuzzTest]:
    """Generate tests to exercise cache fall-back paths."""

    tests = []

    # Test 1: Large diff that might exceed cache
    test_name = "cache_fallback_large_diff"
    large_diff = ""
    for i in range(100):
        large_diff += f"""
@@ -{i*10},6 +{i*10},7 @@
 def function_{i}(data):
     result = []
     for item in data:
+        # Large diff line {i}
         if item > 0:
             result.append(item)
     return result
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=large_diff,
            expected_result=True,  # Should be safe
            test_type="cache_fallback",
            metadata={"size": "large", "lines": 1000},
        )
    )

    # Test 2: Complex nested structures
    test_name = "cache_fallback_complex_nesting"
    complex_diff = """
@@ -1,20 +1,25 @@
 class ComplexProcessor:
     def __init__(self, config):
         self.config = config
+        # Add validation
         self.validate_config()
     
     def validate_config(self):
         if not self.config:
             raise ValueError("Config required")
+        # Add type checking
         if not isinstance(self.config, dict):
             raise TypeError("Config must be dict")
     
     def process(self, data):
         result = []
         for item in data:
+            # Add complex processing
             processed = self._process_item(item)
             if processed:
                 result.append(processed)
         return result
     
     def _process_item(self, item):
+        # Add validation
         if not item:
             return None
         return item.upper()
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=complex_diff,
            expected_result=True,  # Should be safe
            test_type="cache_fallback",
            metadata={"complexity": "high", "nesting_levels": 3},
        )
    )

    # Test 3: Unicode and special characters
    test_name = "cache_fallback_unicode_special_chars"
    unicode_diff = """
@@ -1,10 +1,12 @@
 def process_unicode_data(data):
     result = []
     for item in data:
+        # Unicode comment: 测试数据
         if item:
+            # Special chars: !@#$%^&*()
             processed = item.upper()
             result.append(processed)
     return result
"""
    tests.append(
        FuzzTest(
            name=test_name,
            diff=unicode_diff,
            expected_result=True,  # Should be safe
            test_type="cache_fallback",
            metadata={"unicode": True, "special_chars": True},
        )
    )

    return tests


def generate_all_fuzz_tests() -> List[FuzzTest]:
    """Generate all types of fuzz tests."""
    all_tests = []

    # Charter pattern injection tests
    all_tests.extend(generate_charter_pattern_injection_tests())

    # Signature mismatch tests
    all_tests.extend(generate_signature_mismatch_tests())

    # Multi-hunk tests
    all_tests.extend(generate_multi_hunk_tests())

    # Cache fallback tests
    all_tests.extend(generate_cache_fallback_tests())

    return all_tests


def measure_test_latency(test_func, *args, **kwargs) -> float:
    """Measure the latency of a test function."""
    import time

    start_time = time.time()
    result = test_func(*args, **kwargs)
    end_time = time.time()
    return end_time - start_time


def calculate_p95_latency(latencies: List[float]) -> float:
    """Calculate the 95th percentile latency."""
    if not latencies:
        return 0.0
    sorted_latencies = sorted(latencies)
    index = int(0.95 * len(sorted_latencies))
    return sorted_latencies[index]


def run_fuzz_test_suite(test_count: int = 100) -> Dict:
    """Run the complete fuzz test suite and return results."""
    import hashlib
    import pathlib

    from agent.core.diff_builder import build_smt_diff
    from agent.core.smt_verifier import verify

    CHARTER_HASH = hashlib.sha256(pathlib.Path("charter.md").read_bytes()).hexdigest()

    all_tests = generate_all_fuzz_tests()
    results = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "latencies": [],
        "test_types": {},
        "errors": [],
    }

    # Run tests
    for i in range(min(test_count, len(all_tests))):
        test = all_tests[i % len(all_tests)]  # Cycle through tests
        results["total_tests"] += 1

        try:
            # Measure latency
            latency = measure_test_latency(lambda: build_smt_diff(test.diff))
            results["latencies"].append(latency)

            # Build SMT and verify
            smt_diff = build_smt_diff(test.diff)
            actual_result = verify(smt_diff, CHARTER_HASH)

            # Check if result matches expectation
            if actual_result == test.expected_result:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "test_name": test.name,
                        "expected": test.expected_result,
                        "actual": actual_result,
                        "test_type": test.test_type,
                    }
                )

            # Track test types
            if test.test_type not in results["test_types"]:
                results["test_types"][test.test_type] = {"passed": 0, "failed": 0}

            if actual_result == test.expected_result:
                results["test_types"][test.test_type]["passed"] += 1
            else:
                results["test_types"][test.test_type]["failed"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(
                {"test_name": test.name, "error": str(e), "test_type": test.test_type}
            )

    # Calculate P95 latency
    results["p95_latency"] = calculate_p95_latency(results["latencies"])
    results["avg_latency"] = (
        sum(results["latencies"]) / len(results["latencies"])
        if results["latencies"]
        else 0
    )

    return results

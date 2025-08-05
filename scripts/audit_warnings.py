#!/usr/bin/env python
"""
Audit script to analyze warning patterns from RAFT fuzz tests.

This script:
1. Analyzes the warning rate and pattern distribution
2. Spot-checks diffs that triggered warnings
3. Validates SMT translation correctness
4. Provides detailed metrics and edge case analysis
"""

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from agent.core.diff_builder import FORBIDDEN, build_smt_diff

# Set random seed once at module level
random.seed(42)


def analyze_warning_patterns(log_file: str = "logs/fuzz_report.jsonl") -> Dict:
    """Analyze warning patterns from fuzz test results."""

    # Read the fuzz report
    with open(log_file, "r") as f:
        results = [json.loads(line) for line in f]

    # Count patterns
    pattern_counts = Counter()
    benign_warnings = 0
    malicious_warnings = 0

    # Re-run the fuzz logic to capture warnings
    for result in results:
        idx = result["idx"]
        benign = result["benign"]

        # Reconstruct the original diff
        if benign:
            diff = f"+ {generate_random_word()} \n"
        else:
            # Use the same FORBIDDEN list as the original script
            forbidden_tokens = ["subprocess", "os.system", "eval(", "exec("]
            token = forbidden_tokens[idx % len(forbidden_tokens)]  # Deterministic
            diff = f"+ {generate_random_word()} {token}\n"

        # Check which patterns would trigger warnings
        for pattern in FORBIDDEN:
            if re.search(pattern, diff):
                pattern_counts[pattern] += 1
                if benign:
                    benign_warnings += 1
                else:
                    malicious_warnings += 1

    return {
        "total_tests": len(results),
        "pattern_counts": dict(pattern_counts),
        "benign_warnings": benign_warnings,
        "malicious_warnings": malicious_warnings,
        "warning_rate": (benign_warnings + malicious_warnings) / len(results),
    }


def generate_random_word(k=10):
    """Generate deterministic random word for reproducible analysis."""
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(k))


def spot_check_edge_cases() -> List[Dict]:
    """Spot-check edge cases and validate SMT translation."""

    edge_cases = [
        # Test case 1: Exact forbidden pattern
        {
            "diff": "+ import subprocess\n",
            "expected": False,
            "description": "Direct subprocess import",
        },
        # Test case 2: Pattern in comment
        {
            "diff": "+ # This uses subprocess\n",
            "expected": False,
            "description": "Subprocess in comment",
        },
        # Test case 3: Pattern in string
        {
            "diff": '+ print("subprocess module")\n',
            "expected": False,
            "description": "Subprocess in string",
        },
        # Test case 4: Partial match
        {
            "diff": "+ mysubprocess = None\n",
            "expected": True,
            "description": "Partial subprocess match",
        },
        # Test case 5: Multiple patterns
        {
            "diff": "+ eval('os.system(\"ls\")')\n",
            "expected": False,
            "description": "Multiple forbidden patterns",
        },
        # Test case 6: Whitespace variations
        {
            "diff": "+ eval ( 'test' )\n",
            "expected": False,
            "description": "Whitespace in eval",
        },
        # Test case 7: Import variations
        {
            "diff": "+ from os import system\n",
            "expected": False,
            "description": "Import system from os",
        },
    ]

    results = []
    for case in edge_cases:
        smt_result = build_smt_diff(case["diff"])
        is_safe = smt_result == "(assert true)"
        results.append(
            {
                "case": case["description"],
                "diff": case["diff"].strip(),
                "expected_safe": case["expected"],
                "actual_safe": is_safe,
                "smt_output": smt_result,
                "correct": is_safe == case["expected"],
            }
        )

    return results


def validate_smt_translation() -> Dict:
    """Validate that SMT translation is working correctly."""

    # Test benign cases
    benign_cases = [
        "+ print('hello world')\n",
        "+ x = 1 + 2\n",
        "+ def my_function():\n",
        "+ import json\n",
        "+ # This is a comment\n",
    ]

    # Test malicious cases
    malicious_cases = [
        "+ import subprocess\n",
        "+ eval('print(1)')\n",
        "+ exec('x=1')\n",
        "+ os.system('ls')\n",
        "+ from os import system\n",
    ]

    results = {"benign_cases": [], "malicious_cases": [], "summary": {}}

    # Test benign cases
    for case in benign_cases:
        smt = build_smt_diff(case)
        results["benign_cases"].append(
            {"diff": case.strip(), "smt": smt, "is_safe": smt == "(assert true)"}
        )

    # Test malicious cases
    for case in malicious_cases:
        smt = build_smt_diff(case)
        results["malicious_cases"].append(
            {"diff": case.strip(), "smt": smt, "is_safe": smt == "(assert true)"}
        )

    # Summary
    benign_safe = sum(1 for case in results["benign_cases"] if case["is_safe"])
    malicious_safe = sum(1 for case in results["malicious_cases"] if case["is_safe"])

    results["summary"] = {
        "benign_cases_total": len(benign_cases),
        "benign_cases_safe": benign_safe,
        "malicious_cases_total": len(malicious_cases),
        "malicious_cases_safe": malicious_safe,
        "benign_accuracy": benign_safe / len(benign_cases),
        "malicious_accuracy": (len(malicious_cases) - malicious_safe)
        / len(malicious_cases),
    }

    return results


def main():
    """Run comprehensive audit analysis."""

    print("🔍 RAFT Warning Rate Audit")
    print("=" * 50)

    # 1. Analyze warning patterns
    print("\n1. Warning Pattern Analysis")
    print("-" * 30)

    try:
        warning_analysis = analyze_warning_patterns()
        print(f"Total tests: {warning_analysis['total_tests']}")
        print(f"Warning rate: {warning_analysis['warning_rate']:.2%}")
        print(f"Benign warnings: {warning_analysis['benign_warnings']}")
        print(f"Malicious warnings: {warning_analysis['malicious_warnings']}")

        print("\nPattern distribution:")
        for pattern, count in warning_analysis["pattern_counts"].items():
            print(f"  {pattern}: {count}")

    except FileNotFoundError:
        print("❌ No fuzz report found. Run fuzz tests first.")

    # 2. Spot-check edge cases
    print("\n2. Edge Case Analysis")
    print("-" * 30)

    edge_results = spot_check_edge_cases()
    for result in edge_results:
        status = "✅" if result["correct"] else "❌"
        print(f"{status} {result['case']}")
        print(f"   Diff: {result['diff']}")
        print(f"   Expected: {'safe' if result['expected_safe'] else 'unsafe'}")
        print(f"   Actual: {'safe' if result['actual_safe'] else 'unsafe'}")
        print(f"   SMT: {result['smt_output']}")
        print()

    # 3. Validate SMT translation
    print("\n3. SMT Translation Validation")
    print("-" * 30)

    smt_validation = validate_smt_translation()
    summary = smt_validation["summary"]

    print(
        f"Benign cases: {summary['benign_cases_safe']}/{summary['benign_cases_total']} correctly identified as safe"
    )
    print(
        f"Malicious cases: {summary['malicious_cases_total'] - summary['malicious_cases_safe']}/{summary['malicious_cases_total']} correctly identified as unsafe"
    )
    print(f"Benign accuracy: {summary['benign_accuracy']:.2%}")
    print(f"Malicious accuracy: {summary['malicious_accuracy']:.2%}")

    # 4. Recommendations
    print("\n4. Recommendations")
    print("-" * 30)

    if smt_validation["summary"]["benign_accuracy"] < 1.0:
        print("⚠️  Some benign cases incorrectly flagged as unsafe")
        print("   Consider refining regex patterns to avoid false positives")

    if smt_validation["summary"]["malicious_accuracy"] < 1.0:
        print("⚠️  Some malicious cases incorrectly allowed through")
        print("   Consider adding more comprehensive pattern matching")

    if warning_analysis.get("warning_rate", 0) > 0.5:
        print("⚠️  High warning rate detected")
        print("   Consider optimizing pattern matching for better performance")

    print("\n✅ Audit complete!")


if __name__ == "__main__":
    main()

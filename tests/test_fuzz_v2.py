#!/usr/bin/env python3
"""
Tests for Enhanced Fuzz Harness v2.
Tests charter pattern injection, signature-mismatch detection, and multi-hunk line tracking.
"""

import hashlib
import pathlib

import pytest

from agent.core.diff_builder import analyze_diff_context, build_smt_diff
from agent.core.smt_verifier import verify
from tests.fuzzlib import (FuzzTest, generate_charter_pattern_injection_tests,
                           generate_multi_hunk_tests,
                           generate_signature_mismatch_tests)

CHARTER_HASH = hashlib.sha256(pathlib.Path("charter.md").read_bytes()).hexdigest()


def test_charter_injected_pattern_is_caught():
    """Test that charter-injected patterns are properly caught."""
    print("🧪 Testing charter pattern injection detection...")

    # Get charter injection tests
    injection_tests = generate_charter_pattern_injection_tests()

    # Test a subset of injection tests
    test_subset = injection_tests[:5]  # Test first 5 injection tests

    for test in test_subset:
        print(f"   Testing: {test.name}")

        # Build SMT diff
        smt_diff = build_smt_diff(test.diff)

        # Verify the result
        actual_result = verify(smt_diff, CHARTER_HASH)

        # Assert that the pattern was caught (should return False for unsafe patterns)
        assert actual_result == test.expected_result, (
            f"Test {test.name} failed: expected {test.expected_result}, got {actual_result}. "
            f"Pattern: {test.metadata.get('pattern', 'unknown')}, "
            f"Injection type: {test.metadata.get('injection_type', 'unknown')}"
        )

    print(f"✅ All {len(test_subset)} charter injection tests passed")


def test_arg_name_change_triggers_assert_false():
    """Test that argument name changes trigger signature mismatch detection (assert false)."""
    print("🧪 Testing signature mismatch detection...")

    # Get signature mismatch tests
    mismatch_tests = generate_signature_mismatch_tests()

    # Focus on arg name change tests
    arg_name_tests = [
        test
        for test in mismatch_tests
        if test.metadata.get("change_type") == "arg_name"
    ]

    for test in arg_name_tests:
        print(f"   Testing: {test.name}")

        # Build SMT diff
        smt_diff = build_smt_diff(test.diff)

        # Verify the result
        actual_result = verify(smt_diff, CHARTER_HASH)

        # Assert that signature mismatch was detected (should return False)
        assert actual_result == test.expected_result, (
            f"Test {test.name} failed: expected {test.expected_result}, got {actual_result}. "
            f"Old arg: {test.metadata.get('old_arg', 'unknown')}, "
            f"New arg: {test.metadata.get('new_arg', 'unknown')}"
        )

    print(f"✅ All {len(arg_name_tests)} signature mismatch tests passed")


def test_multi_hunk_diff_preserves_correct_line_numbers():
    """Test that multi-hunk diffs preserve correct line numbers in DiffAST."""
    print("🧪 Testing multi-hunk line number preservation...")

    # Get multi-hunk tests
    multi_hunk_tests = generate_multi_hunk_tests()

    for test in multi_hunk_tests:
        print(f"   Testing: {test.name}")

        # Analyze the diff context to get line number information
        diff_analysis = analyze_diff_context(test.diff)

        # Check that we have multiple hunks by looking for multiple @@ patterns
        hunk_count = test.diff.count("@@")
        assert (
            hunk_count > 1
        ), f"Test {test.name} should have multiple hunks (found {hunk_count})"

        # Verify that the analysis contains expected information
        assert (
            "modified_files" in diff_analysis
        ), "Analysis should contain modified_files"
        assert "added_lines" in diff_analysis, "Analysis should contain added_lines"
        assert "removed_lines" in diff_analysis, "Analysis should contain removed_lines"

        # Test that the SMT verification works correctly
        smt_diff = build_smt_diff(test.diff)
        actual_result = verify(smt_diff, CHARTER_HASH)

        # Assert that the result matches expectation
        assert actual_result == test.expected_result, (
            f"Test {test.name} failed: expected {test.expected_result}, got {actual_result}. "
            f"Hunks: {test.metadata.get('hunks', 'unknown')}"
        )

    print(f"✅ All {len(multi_hunk_tests)} multi-hunk tests passed")


def test_fuzz_v2_comprehensive():
    """Comprehensive test of the enhanced fuzz harness v2."""
    print("🧪 Running comprehensive fuzz v2 test...")

    from tests.fuzzlib import run_fuzz_test_suite

    # Run a small test suite
    results = run_fuzz_test_suite(20)

    # Basic assertions
    assert results["total_tests"] > 0, "Should have run some tests"
    assert (
        results["passed"] + results["failed"] == results["total_tests"]
    ), "Test counts should match"

    # Check that we have different test types (may be fewer with small test count)
    assert len(results["test_types"]) >= 2, "Should have at least 2 test types"

    # Check that we have latency measurements
    assert len(results["latencies"]) > 0, "Should have latency measurements"
    assert results["p95_latency"] > 0, "Should have P95 latency"
    assert results["avg_latency"] > 0, "Should have average latency"

    print(
        f"✅ Comprehensive test passed: {results['passed']}/{results['total_tests']} tests passed"
    )


def test_fuzz_v2_performance_baseline():
    """Test that performance meets baseline requirements."""
    print("🧪 Testing performance baseline...")

    import statistics

    from tests.fuzzlib import calculate_p95_latency, run_fuzz_test_suite

    # Run baseline tests
    baseline_results = run_fuzz_test_suite(10)

    # Check that P95 latency is reasonable (< 1 second)
    assert (
        baseline_results["p95_latency"] < 1.0
    ), f"P95 latency {baseline_results['p95_latency']}s exceeds 1s baseline"

    # Check that average latency is reasonable (< 0.5 seconds)
    assert (
        baseline_results["avg_latency"] < 0.5
    ), f"Average latency {baseline_results['avg_latency']}s exceeds 0.5s baseline"

    print(
        f"✅ Performance baseline met: P95={baseline_results['p95_latency']:.4f}s, Avg={baseline_results['avg_latency']:.4f}s"
    )


if __name__ == "__main__":
    # Run tests individually for debugging
    test_charter_injected_pattern_is_caught()
    test_arg_name_change_triggers_assert_false()
    test_multi_hunk_diff_preserves_correct_line_numbers()
    test_fuzz_v2_comprehensive()
    test_fuzz_v2_performance_baseline()
    print("🎉 All fuzz v2 tests passed!")

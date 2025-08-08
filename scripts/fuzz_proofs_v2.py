#!/usr/bin/env python3
"""
Enhanced Fuzz Harness v2 for RAFT.
Exercises charter pattern injection, signature-mismatch detection, 
multi-hunk line tracking, and cache fall-back paths.

Usage:
    python scripts/fuzz_proofs_v2.py [test_count] [--ci] [--verbose]
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import pathlib

from agent.core.diff_builder import build_smt_diff
from agent.core.smt_verifier import verify
from tests.fuzzlib import (
    FuzzTest,
    calculate_p95_latency,
    generate_all_fuzz_tests,
    run_fuzz_test_suite,
)

CHARTER_HASH = hashlib.sha256(pathlib.Path("charter.md").read_bytes()).hexdigest()


def run_baseline_tests() -> Dict:
    """Run baseline tests to establish performance baseline."""
    print("🔬 Running baseline tests...")

    baseline_tests = [
        FuzzTest(
            name="baseline_safe",
            diff="""
+ def safe_function():
+     return "hello"
""",
            expected_result=True,
            test_type="baseline",
        ),
        FuzzTest(
            name="baseline_unsafe",
            diff="""
+ def unsafe_function():
+     eval('rm -rf /')
""",
            expected_result=False,
            test_type="baseline",
        ),
    ]

    latencies = []
    for test in baseline_tests:
        start_time = time.time()
        smt_diff = build_smt_diff(test.diff)
        verify(smt_diff, CHARTER_HASH)
        end_time = time.time()
        latencies.append(end_time - start_time)

    baseline_p95 = calculate_p95_latency(latencies)
    baseline_avg = statistics.mean(latencies)

    return {
        "p95_latency": baseline_p95,
        "avg_latency": baseline_avg,
        "latencies": latencies,
    }


def run_enhanced_fuzz_tests(test_count: int, verbose: bool = False) -> Dict:
    """Run the enhanced fuzz test suite."""
    print(f"🚀 Running enhanced fuzz tests ({test_count} tests)...")

    # Run the comprehensive test suite
    results = run_fuzz_test_suite(test_count)

    if verbose:
        print(f"📊 Test Results:")
        print(f"   Total: {results['total_tests']}")
        print(f"   Passed: {results['passed']}")
        print(f"   Failed: {results['failed']}")
        print(f"   Success Rate: {results['passed']/results['total_tests']*100:.1f}%")
        print(f"   P95 Latency: {results['p95_latency']:.4f}s")
        print(f"   Avg Latency: {results['avg_latency']:.4f}s")

        print(f"\n📈 Test Type Breakdown:")
        for test_type, counts in results["test_types"].items():
            total = counts["passed"] + counts["failed"]
            success_rate = counts["passed"] / total * 100 if total > 0 else 0
            print(f"   {test_type}: {counts['passed']}/{total} ({success_rate:.1f}%)")

        if results["errors"]:
            print(f"\n❌ Errors:")
            for error in results["errors"][:5]:  # Show first 5 errors
                print(f"   {error['test_name']}: {error}")

    return results


def check_ci_requirements(results: Dict, baseline: Dict) -> bool:
    """Check if results meet CI requirements."""
    print("🔍 Checking CI requirements...")

    # Check for any mismatches (failures)
    if results["failed"] > 0:
        print(f"❌ CI FAILED: {results['failed']} test mismatches detected")
        return False

    # Check P95 latency (should be < 3x baseline)
    baseline_p95 = baseline["p95_latency"]
    current_p95 = results["p95_latency"]
    latency_threshold = baseline_p95 * 3

    if current_p95 > latency_threshold:
        print(
            f"❌ CI FAILED: P95 latency {current_p95:.4f}s exceeds 3x baseline {baseline_p95:.4f}s"
        )
        return False

    print(
        f"✅ CI PASSED: No mismatches, P95 latency {current_p95:.4f}s within threshold"
    )
    return True


def save_results(
    results: Dict, baseline: Dict, output_file: str = "logs/fuzz_v2_results.json"
):
    """Save test results to file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)

    full_results = {
        "timestamp": time.time(),
        "baseline": baseline,
        "results": results,
        "ci_passed": results["failed"] == 0
        and results["p95_latency"] <= baseline["p95_latency"] * 3,
    }

    with open(output_path, "w") as f:
        json.dump(full_results, f, indent=2)

    print(f"💾 Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Enhanced Fuzz Harness v2")
    parser.add_argument(
        "test_count",
        nargs="?",
        type=int,
        default=100,
        help="Number of tests to run (default: 100)",
    )
    parser.add_argument(
        "--ci", action="store_true", help="Run in CI mode with strict requirements"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--baseline-only", action="store_true", help="Only run baseline tests"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="logs/fuzz_v2_results.json",
        help="Output file for results",
    )

    args = parser.parse_args()

    print("🎯 RAFT Enhanced Fuzz Harness v2")
    print("=" * 50)

    # Run baseline tests
    baseline = run_baseline_tests()
    print(f"📊 Baseline P95: {baseline['p95_latency']:.4f}s")
    print(f"📊 Baseline Avg: {baseline['avg_latency']:.4f}s")

    if args.baseline_only:
        print("✅ Baseline tests completed")
        return 0

    # Run enhanced tests
    results = run_enhanced_fuzz_tests(args.test_count, args.verbose)

    # Save results
    save_results(results, baseline, args.output)

    # CI checks
    if args.ci:
        ci_passed = check_ci_requirements(results, baseline)
        if not ci_passed:
            print("\n❌ CI FAILED - Exiting with error code 1")
            return 1

    # Summary
    print("\n" + "=" * 50)
    print("📋 SUMMARY")
    print(f"   Tests Run: {results['total_tests']}")
    print(f"   Success Rate: {results['passed']/results['total_tests']*100:.1f}%")
    print(f"   P95 Latency: {results['p95_latency']:.4f}s")
    print(f"   Avg Latency: {results['avg_latency']:.4f}s")

    if results["failed"] == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"⚠️  {results['failed']} tests failed")
        return 0 if not args.ci else 1


if __name__ == "__main__":
    sys.exit(main())

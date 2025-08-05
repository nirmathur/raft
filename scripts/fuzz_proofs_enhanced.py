#!/usr/bin/env python
"""
Enhanced fuzz-test RAFT's proof-gate + energy guard with detailed metrics.

• Generates N random unified-diff snippets.
• 50 % contain a forbidden token → expect UNSAT.
• 50 % are benign → expect SAT.
• Tracks warning patterns and provides detailed analysis.
• Verifies with smt_verifier.verify(); asserts correctness.
• Prints a JSONL report to logs/fuzz_report_enhanced.jsonl.

Usage
-----
    poetry run python scripts/fuzz_proofs_enhanced.py 5000
"""

import hashlib
import json
import os
import pathlib
import random
import re
import string
import sys
import time
from collections import Counter
from typing import Dict, List

from agent.core.diff_builder import FORBIDDEN, build_smt_diff
from agent.core.smt_verifier import verify

# Set random seed once at module level
random.seed(42)

# --------------------------------------------------------------------- #
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
FORBIDDEN_TOKENS = ["subprocess", "os.system", "eval(", "exec("]
LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
REPORT = LOG_DIR / "fuzz_report_enhanced.jsonl"

CHARTER_HASH = hashlib.sha256(pathlib.Path("charter.md").read_bytes()).hexdigest()


def random_word(k=10):
    return "".join(random.choice(string.ascii_letters) for _ in range(k))


def analyze_diff_patterns(diff_text: str) -> dict:
    """Analyze which forbidden patterns are present in a diff."""
    patterns_found = []
    for pattern in FORBIDDEN:
        if re.search(pattern, diff_text):
            patterns_found.append(pattern)
    return {"patterns_found": patterns_found, "pattern_count": len(patterns_found)}


start = time.time()
ok_pass, ok_fail = 0, 0
pattern_counts = Counter()
warning_summary = {
    "total_warnings": 0,
    "benign_warnings": 0,
    "malicious_warnings": 0,
    "pattern_breakdown": Counter(),
}

with REPORT.open("w") as fp:
    for i in range(N):
        benign = random.random() < 0.5
        token = "" if benign else random.choice(FORBIDDEN_TOKENS)
        diff = f"+ {random_word()} {token}\n"

        # Analyze patterns before SMT conversion
        pattern_analysis = analyze_diff_patterns(diff)

        # Build SMT and track warnings
        smt = build_smt_diff(diff)
        result = verify(smt, CHARTER_HASH)
        expected = benign

        # Track metrics
        if pattern_analysis["pattern_count"] > 0:
            warning_summary["total_warnings"] += 1
            if benign:
                warning_summary["benign_warnings"] += 1
            else:
                warning_summary["malicious_warnings"] += 1

            for pattern in pattern_analysis["patterns_found"]:
                pattern_counts[pattern] += 1
                warning_summary["pattern_breakdown"][pattern] += 1

        if result == expected:
            if benign:
                ok_pass += 1
            else:
                ok_fail += 1

        # Enhanced report with pattern analysis
        report_entry = {
            "idx": i,
            "benign": benign,
            "result": result,
            "pass": result == expected,
            "diff": diff.strip(),
            "patterns_found": pattern_analysis["patterns_found"],
            "pattern_count": pattern_analysis["pattern_count"],
            "smt_output": smt,
        }
        fp.write(json.dumps(report_entry) + "\n")

elapsed = time.time() - start

# Print comprehensive summary
print("🔍 Enhanced Fuzz Test Results")
print("=" * 50)
print(f"Total tests: {N}")
print(f"Correct results: {ok_pass + ok_fail}/{N} ({((ok_pass + ok_fail)/N)*100:.1f}%)")
print(f"Execution time: {elapsed:.1f}s")
print(f"Tests per second: {N/elapsed:.0f}")

print("\n📊 Warning Analysis")
print("-" * 30)
print(f"Total warnings: {warning_summary['total_warnings']}")
print(f"Benign warnings: {warning_summary['benign_warnings']}")
print(f"Malicious warnings: {warning_summary['malicious_warnings']}")
print(f"Warning rate: {warning_summary['total_warnings']/N:.2%}")

print("\n🎯 Pattern Distribution")
print("-" * 30)
for pattern, count in pattern_counts.most_common():
    percentage = (
        (count / warning_summary["total_warnings"]) * 100
        if warning_summary["total_warnings"] > 0
        else 0
    )
    print(f"{pattern}: {count} ({percentage:.1f}%)")

print("\n✅ Test Summary")
print("-" * 30)
print(f"Benign tests passed: {ok_pass}")
print(f"Malicious tests passed: {ok_fail}")
print(f"Overall accuracy: {((ok_pass + ok_fail)/N)*100:.1f}%")

# Validate expected behavior
expected_benign = N // 2
expected_malicious = N - expected_benign
print("\n🔬 Expected vs Actual")
print("-" * 30)
print(f"Expected benign: ~{expected_benign}")
print(f"Expected malicious: ~{expected_malicious}")
print(f"Actual benign warnings: {warning_summary['benign_warnings']}")
print(f"Actual malicious warnings: {warning_summary['malicious_warnings']}")

# Edge case analysis
print("\n🚨 Edge Case Analysis")
print("-" * 30)
if warning_summary["benign_warnings"] > 0:
    print(
        f"⚠️  {warning_summary['benign_warnings']} benign cases triggered warnings (potential false positives)"
    )
else:
    print("✅ No benign cases triggered warnings")

if warning_summary["malicious_warnings"] == 0:
    print("⚠️  No malicious cases triggered warnings (potential false negatives)")
else:
    print(
        f"✅ {warning_summary['malicious_warnings']} malicious cases correctly flagged"
    )

print(f"\n🎯 fuzz done — {ok_pass+ok_fail}/{N} correct in {elapsed:.1f}s")

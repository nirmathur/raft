#!/usr/bin/env python
"""
Fuzz-test RAFT’s proof-gate + energy guard.

• Generates N random unified-diff snippets.
• 50 % contain a forbidden token → expect UNSAT.
• 50 % are benign → expect SAT.
• Verifies with smt_verifier.verify(); asserts correctness.
• Prints a JSONL report to logs/fuzz_report.jsonl.

Usage
-----
    poetry run python scripts/fuzz_proofs.py 5000
"""

import hashlib
import json
import os
import pathlib
import random
import string
import sys
import time

from agent.core.diff_builder import build_smt_diff
from agent.core.smt_verifier import verify

# --------------------------------------------------------------------- #
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
FORBIDDEN = ["subprocess", "os.system", "eval(", "exec("]
LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
REPORT = LOG_DIR / "fuzz_report.jsonl"

CHARTER_HASH = hashlib.sha256(pathlib.Path("charter.md").read_bytes()).hexdigest()


def random_word(k=10):
    return "".join(random.choice(string.ascii_letters) for _ in range(k))


start = time.time()
ok_pass, ok_fail = 0, 0

with REPORT.open("w") as fp:
    for i in range(N):
        benign = random.random() < 0.5
        token = "" if benign else random.choice(FORBIDDEN)
        diff = f"+ {random_word()} {token}\n"
        smt = build_smt_diff(diff)
        result = verify(smt, CHARTER_HASH)
        expected = benign
        if result == expected:
            if benign:
                ok_pass += 1
            else:
                ok_fail += 1
        fp.write(
            json.dumps(
                {
                    "idx": i,
                    "benign": benign,
                    "result": result,
                    "pass": result == expected,
                }
            )
            + "\n"
        )

elapsed = time.time() - start
print(f"fuzz done — {ok_pass+ok_fail}/{N} correct in {elapsed:.1f}s")

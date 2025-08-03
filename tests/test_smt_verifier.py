import hashlib

from agent.core.smt_verifier import verify

CHARTER_HASH = hashlib.sha256(b"dummy").hexdigest()

GOOD_DIFF = "(assert true)"  # trivially satisfiable
BAD_DIFF = "(assert false)"  # trivially UNSAT


def test_good_diff_passes_and_caches():
    assert verify(GOOD_DIFF, CHARTER_HASH) is True  # first run (Z3)
    assert verify(GOOD_DIFF, CHARTER_HASH) is True  # cache hit


def test_bad_diff_fails_and_caches():
    assert verify(BAD_DIFF, CHARTER_HASH) is False  # first run
    assert verify(BAD_DIFF, CHARTER_HASH) is False  # cache hit

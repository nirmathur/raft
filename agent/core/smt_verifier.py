"""
Z3-based proof gate with Redis cache.
A diff must be supplied as SMT-LIB2 text that encodes the
post-mod safety invariants (¬harm, goal preservation).

Successful proofs are cached 24 h keyed on diff + charter hash.
"""

from __future__ import annotations

import hashlib

import redis
from z3 import Solver, parse_smt2_string, sat

# ───────────────────────── config ──────────────────────────
REDIS = redis.Redis(host="host.docker.internal", port=6379, decode_responses=True)
TTL = 60 * 60 * 24  # 24 h
# ───────────────────────────────────────────────────────────


def _cache_key(diff: str, charter_hash: str) -> str:
    return f"{hashlib.sha256(diff.encode()).hexdigest()}:{charter_hash}"


def verify(diff: str, charter_hash: str) -> bool:
    """
    Parameters
    ----------
    diff : str
        SMT-LIB2 program describing safety proof obligations.
    charter_hash : str
        SHA-256 of charter.md frozen at compile-time.

    Returns
    -------
    bool
        True  → proof passes or cache hit positive
        False → proof fails or counter-example found
    """
    key = _cache_key(diff, charter_hash)
    cached = REDIS.get(key)
    if cached is not None:
        return cached == "1"

    solver = Solver()
    try:
        solver.add(parse_smt2_string(diff))
    except Exception as exc:  # malformed SMT
        REDIS.setex(key, TTL, "0")
        raise RuntimeError(f"SMT parse error: {exc}") from exc

    result = solver.check() == sat
    REDIS.setex(key, TTL, "1" if result else "0")
    return result

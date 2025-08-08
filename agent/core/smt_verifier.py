"""
Z3-based proof gate with Redis cache and counterexample extraction.
A diff must be supplied as SMT-LIB2 text that encodes the
post-mod safety invariants (¬harm, goal preservation).

Successful proofs are cached 24 h keyed on diff + charter hash.

Counterexample Format:
When a proof fails (SAT result), the system extracts variable assignments
from the Z3 model and returns them as a JSON object with the following structure:
{
    "result": false,
    "counterexample": {
        "variable_name": "value",
        "another_var": "another_value"
    },
    "model_summary": "Human-readable description of the counterexample"
}

When a proof succeeds (UNSAT result), only a boolean True is returned.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple, Union

try:  # optional dependency for CI/tests
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore
from z3 import Solver, parse_smt2_string, sat, unsat

# ───────────────────────── config / cache ──────────────────────────
# Exposed so tests can patch: agent.core.smt_verifier.REDIS
REDIS: Optional[Any] = None
TTL = 60 * 60 * 24  # 24 h
# ───────────────────────────────────────────────────────────────────


def _get_redis() -> Optional[Any]:
    """Return a cached Redis client or None if unavailable."""
    global REDIS
    if REDIS is not None:
        return REDIS
    if redis is None:
        return None
    try:
        REDIS = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"), decode_responses=True
        )
    except Exception:
        REDIS = None
    return REDIS


def _cache_key(diff: str, charter_hash: str) -> str:
    return f"{hashlib.sha256(diff.encode()).hexdigest()}:{charter_hash}"


def _extract_counterexample(solver: Solver) -> Dict[str, Any]:
    """
    Extract counterexample from Z3 model when solver result is SAT.

    Returns:
        Dict containing variable assignments and human-readable summary
    """
    model = solver.model()
    counterexample = {}

    # Extract all variable assignments from the model
    for decl in model.decls():
        var_name = decl.name()
        var_value = str(model[decl])
        counterexample[var_name] = var_value

    # Create a human-readable summary
    if counterexample:
        summary = f"Found counterexample with {len(counterexample)} variable(s): "
        summary += ", ".join([f"{k}={v}" for k, v in list(counterexample.items())[:3]])
        if len(counterexample) > 3:
            summary += f" (and {len(counterexample) - 3} more)"
    else:
        summary = "SAT result but no variable assignments found"

    return {"counterexample": counterexample, "model_summary": summary}


def verify(diff: str, charter_hash: str) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
    """
    Verify SMT-LIB2 proof obligations using Z3 solver.

    Parameters
    ----------
    diff : str
        SMT-LIB2 program describing safety proof obligations.
    charter_hash : str
        SHA-256 of charter.md frozen at compile-time.

    Returns
    -------
    Union[bool, Tuple[bool, Dict[str, Any]]]
        - True: proof passes (UNSAT - no counterexample exists)
        - (False, counterexample_dict): proof fails (SAT - counterexample found)

    The counterexample_dict contains:
        - "counterexample": Dict of variable assignments
        - "model_summary": Human-readable description
    """
    # Quick sanity: extremely malformed input (e.g., unbalanced parentheses)
    if diff.count("(") != diff.count(")"):
        raise RuntimeError("SMT parse error: unbalanced parentheses")

    key = _cache_key(diff, charter_hash)
    r = _get_redis()
    cached = r.get(key) if r is not None else None

    if cached is not None:
        if cached == "1":
            return True
        else:
            # Try to get cached counterexample
            counterexample_key = f"{key}:counterexample"
            cached_counterexample = r.get(counterexample_key) if r is not None else None
            if cached_counterexample:
                try:
                    counterexample_data = json.loads(cached_counterexample)
                    return False, counterexample_data
                except json.JSONDecodeError:
                    pass
            # Fallback if counterexample cache is corrupted
            return (
                False,
                {
                    "counterexample": {},
                    "model_summary": "Cached failure without counterexample",
                },
            )

    solver = Solver()
    try:
        solver.add(parse_smt2_string(diff))
    except Exception as exc:  # malformed SMT
        if r is not None:
            r.setex(key, TTL, "0")
        raise RuntimeError(f"SMT parse error: {exc}") from exc

    check_result = solver.check()

    if check_result == unsat:
        # Proof passes - no counterexample exists
        if r is not None:
            r.setex(key, TTL, "1")
        return True
    elif check_result == sat:
        # Proof fails - extract counterexample
        counterexample_data = _extract_counterexample(solver)

        # Cache both the failure and the counterexample
        if r is not None:
            r.setex(key, TTL, "0")
        counterexample_key = f"{key}:counterexample"
        if r is not None:
            r.setex(counterexample_key, TTL, json.dumps(counterexample_data))

        return False, counterexample_data
    else:
        # Unknown result (timeout, etc.)
        if r is not None:
            r.setex(key, TTL, "0")
        return (False, {"counterexample": {}, "model_summary": "UNKNOWN"})

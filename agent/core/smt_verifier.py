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
from typing import Dict, Any, Union, Tuple

import redis
from z3 import Solver, parse_smt2_string, sat, unsat

# ───────────────────────── config ──────────────────────────
REDIS = redis.Redis(host="localhost", port=6379, decode_responses=True)
TTL = 60 * 60 * 24  # 24 h
# ───────────────────────────────────────────────────────────


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
    
    return {
        "counterexample": counterexample,
        "model_summary": summary
    }


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
    key = _cache_key(diff, charter_hash)
    cached = REDIS.get(key)
    
    if cached is not None:
        if cached == "1":
            return True
        else:
            # Try to get cached counterexample
            counterexample_key = f"{key}:counterexample"
            cached_counterexample = REDIS.get(counterexample_key)
            if cached_counterexample:
                try:
                    counterexample_data = json.loads(cached_counterexample)
                    return False, counterexample_data
                except json.JSONDecodeError:
                    pass
            # Fallback if counterexample cache is corrupted
            return False

    solver = Solver()
    try:
        solver.add(parse_smt2_string(diff))
    except Exception as exc:  # malformed SMT
        REDIS.setex(key, TTL, "0")
        raise RuntimeError(f"SMT parse error: {exc}") from exc

    check_result = solver.check()
    
    if check_result == unsat:
        # Proof passes - no counterexample exists
        REDIS.setex(key, TTL, "1")
        return True
    elif check_result == sat:
        # Proof fails - extract counterexample
        counterexample_data = _extract_counterexample(solver)
        
        # Cache both the failure and the counterexample
        REDIS.setex(key, TTL, "0")
        counterexample_key = f"{key}:counterexample"
        REDIS.setex(counterexample_key, TTL, json.dumps(counterexample_data))
        
        return False, counterexample_data
    else:
        # Unknown result (timeout, etc.)
        REDIS.setex(key, TTL, "0")
        return False

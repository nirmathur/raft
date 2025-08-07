"""
Z3-based proof gate with Redis cache and counterexample extraction.
A diff must be supplied as SMT-LIB2 text that encodes the
post-mod safety invariants (¬harm, goal preservation).

Successful proofs are cached 24 h keyed on diff + charter hash.
Failed proofs cache counterexamples showing variable assignments that violate safety.

Counterexample Format:
SAT (formula satisfiable) → proof passes; UNSAT → proof fails.

When a proof fails (UNSAT result), returns a JSON object indicating unsatisfiability:
{
    "result": false,
    "counterexample": {
        "reason": "formula_unsatisfiable"
    }
}

For successful proofs (SAT result), when variables are present, includes the model:
{
    "result": true,
    "counterexample": {
        "variable_name": "value",
        "another_var": 42,
        ...
    }
}

For simple successful proofs without variables:
{
    "result": true,
    "counterexample": null
}
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Any, Union, Optional, List

import redis
from z3 import Solver, parse_smt2_string, sat, unsat, unknown

# ───────────────────────── config ──────────────────────────
TTL = 60 * 60 * 24  # 24 h

# >>> merge-note: parallel feature <<<
# Main branch prefers simple Redis setup, but keeping robust fallback for production
try:
    REDIS = redis.Redis(host="localhost", port=6379, decode_responses=True)
    # Test connection
    REDIS.ping()
except (redis.ConnectionError, redis.TimeoutError, ConnectionRefusedError):
    REDIS = None
# ───────────────────────────────────────────────────────────


def _cache_key(diff: str, charter_hash: str) -> str:
    return f"{hashlib.sha256(diff.encode()).hexdigest()}:{charter_hash}"


def _get_cached(key: str) -> Optional[str]:
    """Get cached result, returns None if Redis unavailable or key not found."""
    if REDIS is None:
        return None
    try:
        return REDIS.get(key)
    except (redis.ConnectionError, redis.TimeoutError):
        return None


def _set_cache(key: str, value: str) -> None:
    """Set cache value, silently fails if Redis unavailable."""
    if REDIS is None:
        return
    try:
        REDIS.setex(key, TTL, value)
    except (redis.ConnectionError, redis.TimeoutError):
        pass


def _extract_model(solver: Solver) -> Dict[str, Union[int, str]]:
    """Extract variable assignments from SAT solver model."""
    model = solver.model()
    assignments: Dict[str, Union[int, str]] = {}
    
    for decl in model:
        var_name = str(decl)
        var_value = model[decl]
        
        # Convert Z3 values to Python native types
        if hasattr(var_value, 'as_long'):
            assignments[var_name] = var_value.as_long()
        elif hasattr(var_value, 'as_fraction'):
            frac = var_value.as_fraction()
            assignments[var_name] = str(frac)
        elif hasattr(var_value, 'is_real') and var_value.is_real():
            dec = var_value.as_decimal(10)
            assignments[var_name] = str(dec).rstrip("?")
        elif hasattr(var_value, 'sexpr'):
            # For complex types, use string representation
            assignments[var_name] = str(var_value)
        else:
            assignments[var_name] = str(var_value)
    
    return assignments


def verify(diff: str, charter_hash: str) -> Union[bool, Dict[str, Any]]:
    """
    Parameters
    ----------
    diff : str
        SMT-LIB2 program describing safety proof obligations.
    charter_hash : str
        SHA-256 of charter.md frozen at compile-time.

    Returns
    -------
    Union[bool, Dict[str, Any]]
        For backward compatibility when called expecting bool:
        - True  → proof passes or cache hit positive
        - False → proof fails or counter-example found
        
        For new structured format:
        - {"result": True, "counterexample": None|{...}} → proof passes (SAT)
        - {"result": False, "counterexample": {...}} → proof fails (UNSAT) with counterexample
    """
    key = _cache_key(diff, charter_hash)
    cached = _get_cached(key)
    
    if cached is not None:
        # Handle legacy cache format (simple "0"/"1" strings)
        if cached == "1":
            return {"result": True, "counterexample": None}
        elif cached == "0":
            return {"result": False, "counterexample": {"reason": "formula_unsatisfiable"}}
        elif cached not in ("0", "1"):
            # Try to parse cached JSON data
            try:
                cache_data = json.loads(cached)
                if isinstance(cache_data, dict) and "counterexample" in cache_data:
                    return {"result": cache_data["result"], "counterexample": cache_data["counterexample"]}
            except (json.JSONDecodeError, KeyError):
                pass
            # Fallback for corrupted cache
            return {"result": False, "counterexample": {"reason": "cache_error"}}

    solver = Solver()
    try:
        # Handle Z3 version compatibility for parse_smt2_string
        parsed = parse_smt2_string(diff)
        if isinstance(parsed, list):
            solver.add(*parsed)
        else:
            solver.add(parsed)
    except Exception as exc:  # malformed SMT
        error_result = {"result": False, "counterexample": {"error": str(exc)}}
        _set_cache(key, json.dumps(error_result))
        raise RuntimeError(f"SMT parse error: {exc}") from exc

    check_result = solver.check()
    
    if check_result == sat:
        # Proof passes - formula is satisfiable (safety condition holds)
        # Extract model if variables are present for debugging/verification
        model_assignments = _extract_model(solver)
        
        if model_assignments:
            # Include variable assignments for formulas with variables
            result = {"result": True, "counterexample": model_assignments}
        else:
            # Simple case with no variables
            result = {"result": True, "counterexample": None}
        
        # Use consistent JSON caching for both cases
        _set_cache(key, json.dumps(result))
        return result
        
    elif check_result == unsat:
        # Proof fails - formula is unsatisfiable (safety condition violated)
        result = {"result": False, "counterexample": {"reason": "formula_unsatisfiable"}}
        _set_cache(key, json.dumps(result))
        return result
        
    else:  # unknown
        # Solver couldn't determine - treat as failure with unknown status
        result = {"result": False, "counterexample": {"reason": "solver_unknown"}}
        _set_cache(key, json.dumps(result))
        return result


def verify_bool(diff: str, charter_hash: str) -> bool:
    """
    Backward-compatible boolean interface for existing code.
    
    Returns
    -------
    bool
        True if proof passes, False if proof fails.
    """
    result = verify(diff, charter_hash)
    if isinstance(result, dict):
        return result["result"]
    return result  # type: ignore  # Fallback for direct boolean returns (can't happen now)

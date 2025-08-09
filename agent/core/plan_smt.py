from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

# Reuse shared Redis helper so tests' autouse fixture that patches
# agent.core.smt_verifier works for this module as well
import agent.core.smt_verifier as smt_verifier
from z3 import (
    And,
    BoolVal,
    Contains,
    IndexOf,
    IntVal,
    Length,
    Or,
    PrefixOf,
    Solver,
    StringVal,
    SubString,
    sat,
    unsat,
    Not,
)

from agent.core.plan_models import ALLOWED_RUN_TARGETS, Plan

# Module-level REDIS knob for symmetry with smt_verifier (tests may patch)
REDIS: Optional[Any] = None
TTL_SECONDS: int = 60


def _get_redis():
    # Delegate to smt_verifier so the existing autouse fixture disabling Redis applies
    return smt_verifier._get_redis()


def _stable_plan_json(plan: Plan) -> str:
    # Deterministic JSON for cache key
    data = plan.model_dump()
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _cache_key(plan_json: str) -> str:
    return f"plan-proof:{hashlib.sha256(plan_json.encode()).hexdigest()}"


def _first_violation_python(plan: Plan) -> Optional[Dict[str, Any]]:
    """Lightweight Python duplicate of checks to craft a useful counterexample."""
    for idx, step in enumerate(plan.steps):
        op = getattr(step, "op", None)
        if op == "Fetch":
            url: str = getattr(step, "url", "")
            if not (
                (url.startswith("http://") or url.startswith("https://"))
                and ("://" in url)
                and ("." in url.split("://", 1)[1] if "://" in url else False)
            ):
                return {
                    "step_idx": idx,
                    "op": op,
                    "field": "url",
                    "value": url,
                }
        elif op == "WriteFile":
            path: str = getattr(step, "path", "")
            norm = path.replace("\\", "/")
            is_relative = not norm.startswith("/") and (":/" not in norm)
            no_dotdot = ".." not in norm
            starts_artifacts = norm.startswith("artifacts/")
            if not (is_relative and no_dotdot and starts_artifacts):
                return {
                    "step_idx": idx,
                    "op": op,
                    "field": "path",
                    "value": path,
                }
        elif op == "Run":
            target: str = getattr(step, "target", "")
            if target not in ALLOWED_RUN_TARGETS:
                return {
                    "step_idx": idx,
                    "op": op,
                    "field": "target",
                    "value": target,
                }
        else:
            # Unknown op treated as violation
            return {"step_idx": idx, "op": op, "field": "op", "value": op}
    return None


def verify_plan(plan: Plan) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Prove plan safety by contradiction using Z3.

    Returns (True, None) when UNSAT (no violation exists). Otherwise
    (False, counterexample_dict).
    """
    plan_json = _stable_plan_json(plan)
    key = _cache_key(plan_json)

    # Cache lookup (best-effort)
    r = _get_redis()
    cached = None
    if r is not None:
        try:
            cached = r.get(key)
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8", "ignore")
        except Exception:
            cached = None

    if cached is not None:
        if cached == "1":
            return True, None
        elif cached == "0":
            ckey = f"{key}:counterexample"
            try:
                blob = r.get(ckey) if r is not None else None
                if isinstance(blob, bytes):
                    blob = blob.decode("utf-8", "ignore")
                if blob:
                    return False, json.loads(blob)
            except Exception:
                pass
            return False, None

    solver = Solver()
    solver.set(timeout=1500)

    violations = []

    for step in plan.steps:
        op = StringVal(getattr(step, "op", ""))

        # Fetch(url)
        url = StringVal(getattr(step, "url", ""))
        scheme_ok = Or(PrefixOf(StringVal("http://"), url), PrefixOf(StringVal("https://"), url))
        idx = IndexOf(url, StringVal("://"), IntVal(0))
        host_part = SubString(url, idx + IntVal(3), Length(url) - (idx + IntVal(3)))
        has_host_dot = And(idx >= IntVal(0), Contains(host_part, StringVal(".")))
        fetch_valid = And(scheme_ok, has_host_dot)
        fetch_violation = And(op == StringVal("Fetch"), Not(fetch_valid))

        # WriteFile(path) — keep checks on raw string without Replace
        path = StringVal(getattr(step, "path", ""))
        starts_artifacts = Or(
            PrefixOf(StringVal("artifacts/"), path),
            PrefixOf(StringVal("artifacts\\"), path),
        )
        is_relative = And(
            Not(PrefixOf(StringVal("/"), path)),
            Not(Contains(path, StringVal(":/"))),
            Not(Contains(path, StringVal(":\\"))),
        )
        no_dotdot = And(
            Not(Contains(path, StringVal(".."))),
            Not(Contains(path, StringVal("..\\"))),
        )
        wf_valid = And(is_relative, no_dotdot, starts_artifacts)
        wf_violation = And(op == StringVal("WriteFile"), Not(wf_valid))

        # Run(target)
        target = StringVal(getattr(step, "target", ""))
        allowed_list = list(sorted(ALLOWED_RUN_TARGETS))
        if allowed_list:
            allowed_any = Or(*[target == StringVal(t) for t in allowed_list])
        else:
            allowed_any = BoolVal(False)
        run_valid = allowed_any
        run_violation = And(op == StringVal("Run"), Not(run_valid))

        # Disjunction of this step's violations
        step_violation = Or(fetch_violation, wf_violation, run_violation)
        violations.append(step_violation)

    # Assert that SOME violation exists (contradiction proof)
    solver.add(Or(*violations) if violations else BoolVal(False))

    res = solver.check()

    if res == unsat:
        # Safe plan
        if r is not None:
            try:
                r.setex(key, TTL_SECONDS, "1")
            except Exception:
                pass
        return True, None

    # SAT or UNKNOWN → extract a simple, helpful counterexample
    counterexample = _first_violation_python(plan)

    if r is not None:
        try:
            r.setex(key, TTL_SECONDS, "0")
            if counterexample is not None:
                r.setex(f"{key}:counterexample", TTL_SECONDS, json.dumps(counterexample))
        except Exception:
            pass

    return False, counterexample
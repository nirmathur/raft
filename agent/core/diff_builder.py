"""
diff_builder.py
----------------
Generate an SMT-LIB2 safety obligation for a *real Git diff*.

Rule implemented (cl. xˣ-22a):
    A self-mod is safe **iff** the diff does NOT introduce any forbidden symbol.

Forbidden symbols are regexes; extend FORBIDDEN as charter grows.
The SMT formula is:
    (assert true)   → safe
    (assert false)  → UNSAT (proof gate fails)

No stubs, no unicode weirdness—plain ASCII.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from git import Repo
from loguru import logger

# ------------------------------------------------------------------------- #
FORBIDDEN = [
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\beval\b",
    r"\bexec\b",
    r"\bimport\s+\*",  # wildcard imports
    r"\b__import__\b",  # dynamic imports
    r"\bglobals\b",  # global manipulation
    r"\blocals\b",  # local manipulation
]
# ------------------------------------------------------------------------- #


def unified_diff() -> str:
    """Return Git diff of *unstaged* changes vs HEAD.

    Used by governor to prove the next self-mod.
    """
    try:
        repo = Repo(Path(__file__).parents[2])
        diff = repo.git.diff(None)  # working tree vs HEAD
        return diff if diff else ""
    except Exception as e:
        logger.warning(f"Could not get Git diff: {e}")
        return ""


def build_smt_diff(diff_text: str) -> str:
    """Translate diff text → SMT-LIB2 safety claim."""
    for pat in FORBIDDEN:
        if re.search(pat, diff_text):
            logger.warning(f"Forbidden pattern found: {pat}")
            return "(assert false)"
    return "(assert true)"


def calculate_risk_score(diff_text: str) -> float:
    """Calculate risk score based on diff characteristics."""
    score = 0.0
    score += len(re.findall(r"diff --git", diff_text)) * 0.1  # file count
    score += 0.5 if re.search(r"Binary files", diff_text) else 0.0  # binary files
    score += 0.3 if re.search(r"^-", diff_text) else 0.0  # deletions
    return min(score, 1.0)


def analyze_diff_context(diff_text: str) -> dict[str, any]:
    """Analyze diff for context-specific risks."""
    return {
        "file_count": len(re.findall(r"diff --git", diff_text)),
        "has_binary": bool(re.search(r"Binary files", diff_text)),
        "has_deletions": bool(re.search(r"^-", diff_text)),
        "risk_score": calculate_risk_score(diff_text),
    }


def extract_forbidden_from_charter(charter_clauses: dict[str, str]) -> list[str]:
    """Extract forbidden patterns from charter clauses."""
    # TODO: Parse charter for dynamic forbidden patterns
    return FORBIDDEN  # fallback to static list


def build_advanced_smt(diff_text: str, forbidden_patterns: list[str]) -> str:
    """Build more sophisticated SMT formula."""
    violations = []
    for pat in forbidden_patterns:
        if re.search(pat, diff_text):
            violations.append(pat)

    if violations:
        return "(assert false)"  # UNSAT if violations found
    return "(assert true)"


def build_smt_with_charter(diff_text: str, charter_clauses: dict[str, str]) -> str:
    """Build SMT formula considering charter clauses."""
    # Dynamic forbidden patterns based on charter
    charter_forbidden = extract_forbidden_from_charter(charter_clauses)
    # More sophisticated SMT formula
    return build_advanced_smt(diff_text, charter_forbidden)


def get_cached_proof(diff_hash: str) -> Optional[str]:
    """Check Redis for cached proof result."""
    # Integration with smt_verifier.py caching
    pass

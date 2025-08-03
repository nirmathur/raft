from __future__ import annotations

"""RAFT Governor — Beta

Responsibility:
    • One complete cognitive/control cycle.
    • Enforces all *runtime* charter checks that are programmatically testable
      inside a single iteration (spectral radius, proof‑gate, operator kill‑signal
      etc.).  Multi‑cycle drift sensors live elsewhere.

Road‑map status:
    Alpha ✔  spectral guard + event log
    Beta  ➜  integrate real Z3 verifier + Redis proof‑cache

Public API:
    run_one_cycle() → bool   # True if cycle completed and state committed
"""

import hashlib
from pathlib import Path

import numpy as np
from loguru import logger

from agent.core.charter import load_clauses
from agent.core.event_log import record
from agent.core.smt_verifier import verify  # real Z3 wrapper (Beta)
# ────────────────── internal imports (raft core) ─────────────────────────
from agent.core.spectral import spectral_radius

# ────────────────── charter & constants ─────────────────────────────────

CLAUSES = load_clauses()
CHARTER_PATH = Path(__file__).parents[2] / "charter.md"
CHARTER_HASH = hashlib.sha256(CHARTER_PATH.read_bytes()).hexdigest()

# Hard limit from clause xˣ‑17
MAX_SPECTRAL_RADIUS: float = 0.9

# Redis proof‑cache TTL is set inside smt_verifier (24 h)

# ────────────────── helpers (to be replaced in Pilot) ───────────────────


def _fake_jacobian() -> np.ndarray:  # placeholder while no model params
    """Return a deterministic 2×2 matrix so tests stay reproducible."""
    return np.array([[0.4, 0.2], [0.1, 0.3]])


def _build_smt_diff() -> str:
    """Return SMT‑LIB2 representation of the *proposed* self‑mod diff.

    In Alpha this was a stub; for Beta we still fake it but keep the API so
    later stages can replace with a real diff‑to‑SMT transformer.
    """
    return "(assert true)"  # always provable → passes verifier


# ────────────────── public entry‑point ───────────────────────────────────


def run_one_cycle() -> bool:
    """Execute exactly one governor cycle.

    Order of checks:
        1. Proof‑gate — verify proposed self‑mod via Z3 + proof‑cache.
        2. Spectral‑radius guard — ensure Jacobian contraction.
        3. Commit state + log event.

    Returns
    -------
    bool
        True  if cycle completes and state is (conceptually) committed
        False if any guard aborts (rollback implied).
    """

    # 1 ─── Z3 proof gate
    diff = _build_smt_diff()
    if not verify(diff, CHARTER_HASH):
        logger.error("Z3 gate rejected self‑mod — charter clause xˣ‑22a")
        record(
            "proof‑fail",
            {"diff": diff, "charter_hash": CHARTER_HASH[:8]},
        )
        return False

    # 2 ─── Spectral‑radius guard (xˣ‑17)
    J = _fake_jacobian()
    rho = spectral_radius(J)
    if rho >= MAX_SPECTRAL_RADIUS:
        logger.error(
            "Spectral radius %.3f ≥ limit %.2f — rollback", rho, MAX_SPECTRAL_RADIUS
        )
        record("spectral‑breach", {"rho": rho})
        return False

    # 3 ─── Commit + log success
    record(
        "cycle‑complete",
        {"rho": rho, "charter": CHARTER_HASH[:8]},
    )
    logger.info("cycle‑complete (ρ=%.3f)", rho)
    return True


if __name__ == "__main__":  # convenience CLI
    completed = run_one_cycle()
    exit(0 if completed else 1)

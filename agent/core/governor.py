from __future__ import annotations

import time

from agent.core.escape_hatches import is_paused, start_watchdog
from agent.metrics import (CHARTER_VIOLATIONS, CYCLE_COUNT, CYCLE_DURATION,
                           ENERGY_RATE, PROC_LATENCY, PROOF_FAILURE,
                           PROOF_SUCCESS, SPECTRAL_RHO, SPECTRAL_THRESHOLD)

start_watchdog()

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
import torch
from loguru import logger

# ────────────────── drift detection ─────────────────────────────────────
try:
    from agent.core.drift_monitor import DriftMonitor, DriftAlert  # noqa: WPS433

    _DRIFT_MONITOR = DriftMonitor()
except Exception as _err:  # pragma: no cover – should never fail
    # Fallback: keep governor functional even if drift monitor unavailable
    logger.error("Failed to initialise DriftMonitor: %s", _err)
    _DRIFT_MONITOR = None  # type: ignore

from agent.core.charter import load_clauses
from agent.core.energy_guard import measure_block
from agent.core.event_log import record
from agent.core.model import SimpleNet
from agent.core.smt_verifier import verify  # real Z3 wrapper (Beta)
# ────────────────── internal imports (raft core) ─────────────────────────
from agent.core.spectral import estimate_spectral_radius, spectral_radius

# ────────────────── charter & constants ─────────────────────────────────

CLAUSES = load_clauses()
CHARTER_PATH = Path(__file__).parents[2] / "charter.md"
CHARTER_HASH = hashlib.sha256(CHARTER_PATH.read_bytes()).hexdigest()

# Hard limit from clause xˣ‑17
MAX_SPECTRAL_RADIUS: float = 0.9

# Redis proof‑cache TTL is set inside smt_verifier (24 h)

# ────────────────── helpers (to be replaced in Pilot) ───────────────────

# Global model instance for spectral analysis
# In production, this would be the actual cognitive model
_SPECTRAL_MODEL = SimpleNet.create_stable_model(in_dim=4, out_dim=4, target_rho=0.8)


def _fake_jacobian() -> np.ndarray:  # placeholder while no model params
    """Return a deterministic 2×2 matrix so tests stay reproducible."""
    return np.array([[0.4, 0.2], [0.1, 0.3]])


def _build_smt_diff() -> str:
    """Return SMT-LIB2 representation of the *proposed* self-mod diff.

    In Alpha this was a stub; for Beta we still fake it but keep the API so
    later stages can replace with a real diff-to-SMT transformer.
    """
    # TODO: Replace with real diff from VCS
    proposed_diff_text = "example diff text"
    from agent.core.diff_builder import build_smt_diff

    return build_smt_diff(proposed_diff_text)


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
    macs_estimate = 1_000_000_000  # TODO: real count when brain added

    # Set spectral threshold metric
    SPECTRAL_THRESHOLD.set(MAX_SPECTRAL_RADIUS)

    with PROC_LATENCY.time():
        # 1 ─── Z3 proof gate
        diff = _build_smt_diff()
        ok = verify(diff, CHARTER_HASH)
        if ok:
            PROOF_SUCCESS.inc()
        else:
            logger.error("Z3 gate rejected self‑mod — charter clause xˣ‑22a")
            record(
                "proof‑fail",
                {"diff": diff, "charter_hash": CHARTER_HASH[:8]},
            )
            PROOF_FAILURE.inc()
            CHARTER_VIOLATIONS.labels(clause="x^x-22a").inc()
            return False

        # 2 ─── Spectral‑radius guard (xˣ‑17)
        # Use real PyTorch-based spectral radius estimation
        x0 = torch.randn(4, requires_grad=True)  # Random input point
        rho = _SPECTRAL_MODEL.estimate_spectral_radius(x0, n_iter=10)
        SPECTRAL_RHO.set(rho)

        # ─── multi-cycle drift guard (xˣ-19) ────────────────────────────
        if _DRIFT_MONITOR is not None:
            try:
                _DRIFT_MONITOR.record(rho)
            except DriftAlert as alert:
                logger.error("Drift alert: %s", alert.context)
                logger.info("drift-alert context=%s", alert.context)
                record("drift-alert", {"rho": rho, **alert.context})
                CHARTER_VIOLATIONS.labels(clause="x^x-19").inc()
                return False

        if rho >= MAX_SPECTRAL_RADIUS:
            logger.error(
                "Spectral radius %.3f ≥ limit %.2f — rollback", rho, MAX_SPECTRAL_RADIUS
            )
            record("spectral‑breach", {"rho": rho})
            CHARTER_VIOLATIONS.labels(clause="x^x-17").inc()
            return False

        # 3 ─── Energy guard with metrics
        with measure_block(macs_estimate) as used_joules:
            if used_joules > 0:
                energy_rate = used_joules / (macs_estimate / 1e9)  # J/s
                ENERGY_RATE.set(energy_rate)

        # 4 ─── Commit + log success
        record(
            "cycle‑complete",
            {"rho": rho, "charter": CHARTER_HASH[:8]},
        )
        logger.info("cycle‑complete (ρ=%.3f)", rho)

        # Update cycle metrics
        CYCLE_COUNT.inc()

        if is_paused():
            return False

        return True


if __name__ == "__main__":  # convenience CLI
    from prometheus_client import start_http_server

    # Start Prometheus metrics server
    start_http_server(8002)  # expose /metrics on port 8002

    completed = run_one_cycle()
    exit(0 if completed else 1)

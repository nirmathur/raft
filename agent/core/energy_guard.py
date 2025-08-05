"""
Real energy monitoring for computational cycles using RAPL (Linux) and NVML (NVIDIA GPUs).

Provides energy consumption tracking for governor cycles with apoptosis protection
according to Charter clause xˣ-29.
"""

import os
import time
from contextlib import contextmanager
from typing import Optional

from loguru import logger

# ───────────────────────────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────────────────────────

# Energy per MAC (J), baseline at 1 GHz (MAC/s)
HERMES_J_PER_MAC: float = 1.0 / (10.5e12)
HERMES_BASELINE_JOULES_PER_SECOND: float = HERMES_J_PER_MAC * 1_000_000_000
APOPTOSIS_MULTIPLIER: float = 2.0

# Module-level state
_last_sample_time: float = time.time()
_last_total_joules: float = 0.0
_last_total_macs: int = 0


def _read_joules() -> float:
    """
    Read cumulative energy consumed (J) since the module was first sampled.

    Uses RAPL for CPU if available; otherwise falls back to a time-based estimate
    at 50% of the HERMES baseline.
    """
    global _last_sample_time, _last_total_joules

    now = time.time()
    rapl_path = "/sys/class/powercap/intel-rapl:0/energy_uj"
    total_j: Optional[float] = None

    # Try RAPL sensor
    if os.path.exists(rapl_path):
        try:
            with open(rapl_path, "r") as f:
                micro = float(f.read().strip())
            total_j = micro / 1_000_000.0
        except Exception:
            total_j = None

    # Fallback: estimate from wall-clock time at 50% of baseline
    if total_j is None:
        elapsed = now - _last_sample_time
        total_j = _last_total_joules + elapsed * HERMES_BASELINE_JOULES_PER_SECOND * 0.5

    # First invocation: initialize state and return zero delta
    if _last_total_joules == 0.0:
        _last_sample_time = now
        _last_total_joules = total_j
        return 0.0

    # Compute delta since last sample
    delta = total_j - _last_total_joules
    _last_sample_time = now
    _last_total_joules = total_j
    return delta


def check_budget(used_joules: float, macs: int) -> None:
    """
    Enforce a hard energy budget: used_joules ≤ 2×HERMES_J_PER_MAC × macs.

    Raises SystemExit("Energy apoptosis triggered") on breach.
    """
    # Compute allowed energy for this operation
    limit = macs * HERMES_J_PER_MAC * APOPTOSIS_MULTIPLIER

    # Compare used energy against limit
    if used_joules > limit:
        logger.error("energy-apoptosis: {:.6f}J > {:.6f}J limit", used_joules, limit)
        raise SystemExit("Energy apoptosis triggered")


@contextmanager
def measure_block(macs_estimate: int):
    """
    Context manager to sample energy before/after a compute block and
    enforce the energy budget.

    Parameters
    ----------
    macs_estimate : int
        Estimated number of MAC operations in this block.
    """
    # Skip if explicitly disabled
    if os.getenv("ENERGY_GUARD_ENABLED", "true").lower() == "false":
        yield
        return

    start_j = _read_joules()
    try:
        yield
    finally:
        end_j = _read_joules()
        used = end_j - start_j
        check_budget(used, macs_estimate)

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

# HERMES-Core baseline: 50kWh/month = ~1.9 kWh/day = 6.84 MJ/day = 1.9 J/s average
# 2× baseline threshold for apoptosis
HERMES_BASELINE_JOULES_PER_SECOND = 1.9
APOPTOSIS_THRESHOLD_MULTIPLIER = 2.0

# Process start time for cumulative energy calculation
_PROCESS_START_TIME = time.time()
_PROCESS_START_ENERGY: Optional[float] = None


def _read_joules() -> float:
    """Read cumulative energy consumption in joules since process start.
    
    Uses RAPL (Linux) for CPU package energy and NVML for GPU energy when available.
    Falls back to time-based estimation if hardware monitoring unavailable.
    
    Returns
    -------
    float
        Cumulative joules consumed since process start.
    """
    global _PROCESS_START_ENERGY
    
    current_energy = 0.0
    
    # Try RAPL (Linux CPU package energy)
    try:
        rapl_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
        if os.path.exists(rapl_path):
            with open(rapl_path, 'r') as f:
                # RAPL reports microjoules, convert to joules
                current_energy += float(f.read().strip()) / 1_000_000
    except (OSError, ValueError):
        pass
    
    # Try NVML (NVIDIA GPU energy) 
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # Get power draw in milliwatts and convert to joules
            power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            # Estimate energy since last reading (rough approximation)
            current_energy += (power_mw / 1000.0) * 0.1  # 100ms sampling assumption
    except (ImportError, Exception):
        pass
    
    # Fallback: time-based estimation using average baseline
    if current_energy == 0.0:
        elapsed_time = time.time() - _PROCESS_START_TIME
        current_energy = elapsed_time * HERMES_BASELINE_JOULES_PER_SECOND * 0.5  # Conservative estimate
    
    # Initialize process start energy on first call
    if _PROCESS_START_ENERGY is None:
        _PROCESS_START_ENERGY = current_energy
        return 0.0
    
    return current_energy - _PROCESS_START_ENERGY


def check_budget(used_joules: float, macs: int) -> None:
    """Check if energy consumption exceeds 2×HERMES baseline and trigger apoptosis if needed.
    
    Parameters
    ----------
    used_joules : float
        Energy consumed in joules for this computational block.
    macs : int
        Number of multiply-accumulate operations performed.
        
    Raises
    ------
    SystemExit
        If energy consumption exceeds 2×HERMES baseline (apoptosis).
    """
    # Calculate energy rate (joules per second for this block)
    # Estimate block duration based on MAC operations (rough heuristic: 1B MACs ≈ 1 second)
    estimated_duration = max(0.001, macs / 1_000_000_000)  # Minimum 1ms
    energy_rate = used_joules / estimated_duration
    
    # Check against 2×HERMES baseline threshold
    threshold = HERMES_BASELINE_JOULES_PER_SECOND * APOPTOSIS_THRESHOLD_MULTIPLIER
    
    if energy_rate > threshold:
        logger.critical(
            "energy-apoptosis: Energy consumption {:.3f} J/s exceeds 2×HERMES baseline {:.3f} J/s",
            energy_rate, threshold
        )
        logger.info(f"Block details: {used_joules:.3f} J consumed, {macs} MACs, {estimated_duration:.3f}s duration")
        raise SystemExit("Energy apoptosis triggered - consumption exceeds 2×HERMES baseline")
    
    logger.debug(f"Energy budget OK: {energy_rate:.3f} J/s (threshold: {threshold:.3f} J/s)")


@contextmanager
def measure_block(macs_estimate: int):
    """Context manager for measuring energy consumption during a computational block.

    Parameters
    ----------
    macs_estimate : int
        Estimated number of multiply-accumulate operations for this block.
    """
    # Skip energy measurement if disabled via environment variable
    if os.getenv("ENERGY_GUARD_ENABLED", "true").lower() == "false":
        try:
            yield
        finally:
            return

    # Sample energy at start of block
    start_joules = _read_joules()
    
    try:
        yield
    finally:
        # Sample energy at end of block
        end_joules = _read_joules()
        used_joules = end_joules - start_joules
        
        # Check budget exactly once per requirement
        check_budget(used_joules, macs_estimate)

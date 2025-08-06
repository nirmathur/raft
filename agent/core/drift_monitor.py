# agent/core/drift_monitor.py
"""Drift Monitor — Multi-cycle spectral radius drift detection

Responsibility:
    • Maintains a sliding window of spectral radii across cycles
    • Detects drift patterns via rolling statistics (mean, max)
    • Raises DriftAlert when thresholds are exceeded

Charter compliance:
    • xˣ-19: Multi-cycle drift detection
    • xˣ-24: Variance monitoring
    • xˣ-25: Automated rollback triggers
"""

import os
from collections import deque
from typing import Deque

from loguru import logger


class DriftAlert(Exception):
    """Raised when spectral radius drift exceeds configured thresholds."""
    
    def __init__(self, message: str, mean_drift: float, max_drift: float):
        super().__init__(message)
        self.mean_drift = mean_drift
        self.max_drift = max_drift


class DriftMonitor:
    """Monitor spectral radius drift over multiple cycles.
    
    Maintains a sliding window of the last N spectral radii and calculates
    rolling statistics to detect concerning drift patterns.
    """
    
    def __init__(
        self,
        window_size: int = None,
        mean_threshold: float = 0.05,
        max_threshold: float = 0.1
    ):
        """Initialize drift monitor.
        
        Parameters
        ----------
        window_size : int, optional
            Size of sliding window. Defaults to DRIFT_WINDOW env var or 10.
        mean_threshold : float
            Maximum allowed rolling mean drift (default: 0.05)
        max_threshold : float  
            Maximum allowed max drift in window (default: 0.1)
        """
        if window_size is None:
            window_size = int(os.getenv("DRIFT_WINDOW", "10"))
            
        self.window_size = window_size
        self.mean_threshold = mean_threshold
        self.max_threshold = max_threshold
        
        # Sliding window of spectral radii
        self.radii: Deque[float] = deque(maxlen=window_size)
        
        logger.info(
            f"DriftMonitor initialized: window={window_size}, "
            f"mean_thresh={mean_threshold}, max_thresh={max_threshold}"
        )
    
    def record(self, rho: float) -> None:
        """Record a new spectral radius and check for drift.
        
        Parameters
        ----------
        rho : float
            Current spectral radius
            
        Raises
        ------
        DriftAlert
            If drift thresholds are exceeded
        """
        self.radii.append(rho)
        
        # Only check drift if we have enough samples
        if len(self.radii) < 2:
            return
            
        # Calculate drift metrics
        mean_drift = self._calculate_mean_drift()
        max_drift = self._calculate_max_drift()
        
        logger.debug(
            f"Drift check: rho={rho:.3f}, mean_drift={mean_drift:.4f}, "
            f"max_drift={max_drift:.4f}"
        )
        
        # Check thresholds
        if mean_drift > self.mean_threshold:
            raise DriftAlert(
                f"Mean drift {mean_drift:.4f} exceeds threshold {self.mean_threshold}",
                mean_drift,
                max_drift
            )
            
        if max_drift > self.max_threshold:
            raise DriftAlert(
                f"Max drift {max_drift:.4f} exceeds threshold {self.max_threshold}",
                mean_drift,
                max_drift
            )
    
    def _calculate_mean_drift(self) -> float:
        """Calculate rolling mean of absolute differences."""
        if len(self.radii) < 2:
            return 0.0
            
        diffs = []
        for i in range(1, len(self.radii)):
            diffs.append(abs(self.radii[i] - self.radii[i-1]))
            
        return sum(diffs) / len(diffs)
    
    def _calculate_max_drift(self) -> float:
        """Calculate maximum drift in current window."""
        if len(self.radii) < 2:
            return 0.0
            
        return max(self.radii) - min(self.radii)
    
    def reset(self) -> None:
        """Clear the sliding window."""
        self.radii.clear()
        logger.info("DriftMonitor window reset")
    
    @property
    def current_window(self) -> list[float]:
        """Return current sliding window contents."""
        return list(self.radii)
"""Drift Monitor — detects spectral radius drift over multiple governor cycles.

This module provides a `DriftMonitor` class that tracks a sliding window of the
most recent spectral-radius (ρ) measurements and raises a `DriftAlert` when the
system exhibits suspicious drift patterns, as mandated by charter clauses
xˣ-19, xˣ-24 and xˣ-25.

Detection Logic
---------------
Two complementary criteria are evaluated after each new ρ value is recorded:

1. Rolling *mean* drift
   Average absolute change between consecutive ρ values over the window.
2. Rolling *max* drift
   Largest absolute change between any two consecutive ρ values in the window.

If either metric exceeds its respective threshold an alert is raised.

Configuration
-------------
• `DRIFT_WINDOW` – number of recent ρ values to keep (default: 10)
• `mean_threshold` – alert threshold for rolling mean drift (default: 0.05)
• `max_threshold` – alert threshold for max drift (default: 0.10)

Changing any of the above may require charter approval in production.
"""
from __future__ import annotations

import os
from collections import deque
from statistics import mean
from typing import Deque, List

from loguru import logger

from agent.metrics import DRIFT_MEAN, DRIFT_MAX

__all__ = ["DriftAlert", "DriftMonitor"]


class DriftAlert(RuntimeError):
    """Raised when spectral-radius drift exceeds allowed thresholds."""

    def __init__(self, context: dict[str, float | List[float]]):
        super().__init__("Spectral radius drift detected")
        self.context: dict[str, float | List[float]] = context

    def __str__(self) -> str:  # pragma: no cover – delegated to logger mostly
        return f"DriftAlert(context={self.context})"


class DriftMonitor:
    """Monitors spectral-radius drift over multiple governor cycles.

    Parameters
    ----------
    window_size : int | None, optional
        Number of recent ρ values to retain.  If *None* (default) the value is
        read from the `DRIFT_WINDOW` environment variable and falls back to 10.
    mean_threshold : float, optional
        Rolling-mean drift alert threshold.  Defaults to 0.05.
    max_threshold : float, optional
        Rolling-max drift alert threshold.  Defaults to 0.10.
    """

    def __init__(
        self,
        window_size: int | None = None,
        *,
        mean_threshold: float | None = None,
        max_threshold: float | None = None,
    ) -> None:
        if window_size is None:
            window_size = int(os.getenv("DRIFT_WINDOW", "10"))
        if window_size < 2:
            raise ValueError("window_size must be at least 2 to compute drift")

        # Apply env-level overrides for thresholds
        if mean_threshold is None:
            mean_threshold = float(os.getenv("DRIFT_MEAN_THRESHOLD", "0.05"))
        if max_threshold is None:
            max_threshold = float(os.getenv("DRIFT_MAX_THRESHOLD", "0.10"))

        self.window_size: int = window_size
        self.mean_threshold: float = mean_threshold
        self.max_threshold: float = max_threshold
        self._values: Deque[float] = deque(maxlen=window_size)

        logger.debug(
            "DriftMonitor initialised (window=%d, mean_thr=%.3f, max_thr=%.3f)",
            self.window_size,
            self.mean_threshold,
            self.max_threshold,
        )

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def reset(self) -> None:
        """Clear the internal sliding window."""
        self._values.clear()
        logger.debug("DriftMonitor has been reset")

    @property
    def current_window(self) -> List[float]:
        """Return a *copy* of the current sliding-window values."""
        return list(self._values)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def record(self, rho: float | int) -> None:
        """Record a new spectral-radius measurement.

        Raises
        ------
        DriftAlert
            If drift exceeds either the mean or max thresholds.
        """
        try:
            rho_f = float(rho)
        except (TypeError, ValueError) as e:  # pragma: no cover – developer bug
            raise TypeError("rho must be a real number") from e

        self._values.append(rho_f)
        # Need at least two values to compute drift
        if len(self._values) < 2:
            return

        # Compute absolute differences between consecutive measurements
        diffs = [abs(self._values[i] - self._values[i - 1]) for i in range(1, len(self._values))]
        mean_drift = mean(diffs)
        max_drift = max(diffs)

        # Update Prometheus gauges
        DRIFT_MEAN.set(mean_drift)
        DRIFT_MAX.set(max_drift)

        logger.debug(
            "DriftMonitor.update ρ=%.6f mean_drift=%.6f max_drift=%.6f window=%s",
            rho_f,
            mean_drift,
            max_drift,
            list(self._values),
        )

        if mean_drift > self.mean_threshold or max_drift > self.max_threshold:
            context = {
                "mean_drift": mean_drift,
                "max_drift": max_drift,
                "window": list(self._values),
            }
            # Emit a local warning; canonical event emission happens in governor.
            logger.warning("DriftMonitor alert: %s", context)
            raise DriftAlert(context)
# agent/core/spectral.py
import numpy as np


def spectral_radius(matrix: np.ndarray) -> float:
    """Return the spectral radius (max |eigenvalue|)."""
    eigs = np.linalg.eigvals(matrix)
    return float(max(abs(eigs)))

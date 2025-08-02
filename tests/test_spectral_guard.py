import numpy as np

from agent.core.spectral import spectral_radius


def test_radius_ok():
    m = np.eye(3) * 0.5
    assert spectral_radius(m) == 0.5


def test_radius_breach():
    m = np.eye(2) * 1.1
    assert spectral_radius(m) == 1.1

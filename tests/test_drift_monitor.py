import pytest

from agent.core.drift_monitor import DriftAlert, DriftMonitor


@pytest.mark.parametrize("values", [[0.5] * 20, [0.1] * 10])
def test_constant_radii_no_alert(values):
    """DriftMonitor should *not* raise when ρ stays constant."""
    dm = DriftMonitor(window_size=10)
    for v in values:
        dm.record(v)  # should not raise


def test_trending_upward_alert():
    """Monotonic increase that exceeds thresholds triggers alert."""
    dm = DriftMonitor(window_size=5)
    with pytest.raises(DriftAlert):
        for rho in [0.10, 0.15, 0.22, 0.35, 0.47]:
            dm.record(rho)


def test_env_var_configuration(monkeypatch):
    """DRIFT_WINDOW env var should override default window size."""
    monkeypatch.setenv("DRIFT_WINDOW", "3")
    dm = DriftMonitor(window_size=None)  # rely on env var
    assert dm.window_size == 3


def test_sliding_window_behavior():
    """Ensure old values are discarded when window is full."""
    dm = DriftMonitor(window_size=3)
    dm.record(0.1)
    dm.record(0.2)
    dm.record(0.3)
    assert dm.current_window == [0.1, 0.2, 0.3]
    dm.record(0.4)  # this should evict the oldest
    assert dm.current_window == [0.2, 0.3, 0.4]


@pytest.mark.parametrize(
    "sequence",
    [
        [0.5, 0.5, 0.9],  # sudden spike
        [0.5, 0.7, 0.5, 0.8],  # oscillation with big jumps
    ],
)
def test_spikes_and_oscillations(sequence):
    dm = DriftMonitor(window_size=10)
    with pytest.raises(DriftAlert):
        for rho in sequence:
            dm.record(rho)
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


# mean drift breach without max breach
def test_mean_only_breach():
    """Mean drift above threshold triggers alert even if max drift below."""
    dm = DriftMonitor(window_size=4, mean_threshold=0.025, max_threshold=0.2)
    sequence = [0.00, 0.03, 0.06, 0.09]  # diffs 0.03 each, mean 0.03 > 0.025 but max 0.03 < 0.2
    with pytest.raises(DriftAlert) as exc:
        for rho in sequence:
            dm.record(rho)
    ctx = exc.value.context
    assert ctx["mean_drift"] > dm.mean_threshold
    assert ctx["max_drift"] < dm.max_threshold


# equality threshold should not raise
@pytest.mark.parametrize("delta", [0.05, 0.10])
def test_equal_threshold_no_alert(delta):
    dm = DriftMonitor(window_size=2)
    dm.record(0.00)
    dm.record(delta)  # diff equals threshold; should not raise


# verify context structure
def test_context_structure():
    dm = DriftMonitor(window_size=3)
    with pytest.raises(DriftAlert) as exc:
        dm.record(0.0)
        dm.record(0.2)
        dm.record(0.4)
    ctx = exc.value.context
    assert set(ctx.keys()) == {"mean_drift", "max_drift", "window"}
    assert len(ctx["window"]) <= dm.window_size


def test_env_threshold_overrides(monkeypatch):
    """Environment variables should override threshold defaults."""
    monkeypatch.setenv("DRIFT_MEAN_THRESHOLD", "0.01")
    monkeypatch.setenv("DRIFT_MAX_THRESHOLD", "0.02")
    from importlib import reload
    import agent.core.drift_monitor as dm_mod

    reload(dm_mod)  # Apply env vars
    DM = dm_mod.DriftMonitor
    DA = dm_mod.DriftAlert

    dm_inst = DM(window_size=3)
    # Sequence that triggers both thresholds (diff 0.015, 0.03):
    with pytest.raises(DA):
        dm_inst.record(0.0)
        dm_inst.record(0.02)  # diff 0.02 > mean 0.01 & max 0.02 == threshold
        dm_inst.record(0.05)  # diff 0.03 > max threshold
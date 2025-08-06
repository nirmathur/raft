import pytest
import torch
import torch.nn as nn

from agent.core.governor import MAX_SPECTRAL_RADIUS, run_one_cycle
from agent.core.model import SimpleNet


def test_radius_ok():
    """Test that stable spectral radius allows cycle completion."""
    # Use the stable model (should pass)
    result = run_one_cycle()
    assert result is True


def test_radius_breach():
    """Test that unstable spectral radius triggers rollback."""

    # Test with a simple linear function that has known high spectral radius
    def unstable_function(x):
        # Simple linear transformation with large coefficients
        return 2.0 * x  # This will have spectral radius = 2.0

    from agent.core.spectral import estimate_spectral_radius

    # Verify the function is actually unstable
    x0 = torch.randn(4, requires_grad=True)
    rho = estimate_spectral_radius(unstable_function, x0, n_iter=10)
    assert rho > MAX_SPECTRAL_RADIUS, f"Function should be unstable, got rho={rho}"

    # Test that governor detects instability by temporarily replacing the model
    from agent.core.governor import _SPECTRAL_MODEL

    original_model = _SPECTRAL_MODEL

    try:
        # Create a model that wraps our unstable function
        class UnstableModel(torch.nn.Module):
            def forward(self, x):
                return unstable_function(x)

            def estimate_spectral_radius(
                self, x, n_iter=10, tolerance=1e-6, batch_mode=False
            ):
                return estimate_spectral_radius(
                    unstable_function, x, n_iter, tolerance, batch_mode
                )

        unstable_model = UnstableModel()

        # Temporarily replace with unstable model
        import agent.core.governor

        agent.core.governor._SPECTRAL_MODEL = unstable_model

        # Governor should detect instability and return False
        result = run_one_cycle()
        assert result is False, "Governor should detect unstable spectral radius"

    finally:
        # Restore original model
        agent.core.governor._SPECTRAL_MODEL = original_model


def test_unstable_model_breach():
    """Test that unstable model with large weights triggers rollback."""
    # identity activation keeps gradients non-zero; large weights ⇒ ρ≫1
    model = SimpleNet(in_dim=4, out_dim=4, hidden_dim=64, activation="identity")
    for m in model.modules():
        if isinstance(m, nn.Linear):
            m.weight.data.fill_(2.0)
    x0 = torch.ones(4, requires_grad=True)

    # Verify it's actually unstable
    rho = model.estimate_spectral_radius(x0, n_iter=10)
    assert rho > MAX_SPECTRAL_RADIUS, f"Model should be unstable, got rho={rho}"

    # Test that governor detects instability
    from agent.core.governor import _SPECTRAL_MODEL

    original_model = _SPECTRAL_MODEL

    try:
        # Temporarily replace with unstable model
        import agent.core.governor

        agent.core.governor._SPECTRAL_MODEL = model

        # Governor should detect instability and return False
        result = run_one_cycle()
        assert result is False, "Governor should detect unstable spectral radius"

    finally:
        # Restore original model
        agent.core.governor._SPECTRAL_MODEL = original_model


def test_guard_sets_prometheus_metric():
    """Governor should set spectral_rho ≥ threshold on breach."""
    from prometheus_client import REGISTRY

    from agent.core import governor

    # monkey-patch an obviously unstable model
    unstable = SimpleNet(in_dim=4, out_dim=4, hidden_dim=16, activation="identity")
    for m in unstable.modules():
        if isinstance(m, nn.Linear):
            m.weight.data.fill_(3.0)
    governor._SPECTRAL_MODEL = unstable  # noqa: SLF001  (test-only)

    assert governor.run_one_cycle() is False
    metric_val = REGISTRY.get_sample_value("raft_spectral_radius")
    assert metric_val >= governor.MAX_SPECTRAL_RADIUS

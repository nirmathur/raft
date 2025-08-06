import torch

from agent.core.governor import run_one_cycle


def test_governor_cycle():
    # Set fixed seed for deterministic spectral radius calculation
    torch.manual_seed(42)
    assert run_one_cycle() is True

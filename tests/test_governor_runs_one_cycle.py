from agent.core.governor import run_one_cycle


def test_governor_cycle():
    assert run_one_cycle() is True

from agent.core.escape_hatches import is_paused, request_pause


def test_pause_functionality():
    """Test pause request and check functionality."""
    request_pause(True)
    assert is_paused() is True
    request_pause(False)

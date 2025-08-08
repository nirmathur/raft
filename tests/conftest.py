from unittest.mock import Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

TOKEN = "test-token"
HEADERS = {"authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _setup_test_environment():
    """Setup test environment with mocks and cleanup.

    Ensures all tests run with:
    - Mocked Redis to avoid external dependencies
    - System unpaused after test completion
    - Default configuration restored after each test
    - Clean global state between tests
    """
    # Disable Redis everywhere during tests
    with (
        patch("agent.core.smt_verifier.REDIS", new=None, create=True),
        patch("agent.core.smt_verifier._get_redis", return_value=None, create=True),
    ):
        yield

        # Cleanup after test
        try:
            # Reset pause state directly via escape hatches module
            from agent.core.config_store import update_config
            from agent.core.escape_hatches import request_pause

            # Reset pause state
            request_pause(False)

            # Reset configuration to defaults (using internal API to avoid HTTP calls)
            update_config({"rho_max": 0.9, "energy_multiplier": 2.0})

            # Reset drift monitor state to avoid cross-test contamination
            from agent.core.governor import _DRIFT_MONITOR

            if _DRIFT_MONITOR is not None:
                _DRIFT_MONITOR.reset()

        except Exception:
            # If reset fails, don't break other tests
            pass

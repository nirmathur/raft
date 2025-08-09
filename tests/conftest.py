import socket
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

TOKEN = "test-token"
HEADERS = {"authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _setup_test_environment(monkeypatch):
    """Setup test environment with mocks and cleanup.

    Ensures all tests run with:
    - Mocked Redis to avoid external dependencies
    - System unpaused after test completion
    - Default configuration restored after each test
    - Clean global state between tests
    """

    # Disable Redis everywhere during tests
    class _FakeRedis:
        def __init__(self):
            self._store = {}

        def get(self, key):
            return self._store.get(key)

        def set(self, key, value):
            self._store[key] = value
            return True

        def setex(self, key, _ttl, value):
            self._store[key] = value
            return True

    _fake_redis = _FakeRedis()

    # If redis library is present, stub its client factory to our in-memory fake
    try:  # pragma: no cover - depends on test environment
        import redis as _redis_mod  # type: ignore

        monkeypatch.setattr(
            _redis_mod.Redis,
            "from_url",
            lambda *args, **kwargs: _fake_redis,
            raising=True,
        )
    except Exception:
        pass

    with (
        patch("agent.core.smt_verifier.REDIS", new=_fake_redis, create=True),
        patch(
            "agent.core.smt_verifier._get_redis", return_value=_fake_redis, create=True
        ),
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


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """Block outbound network access for all tests unless marked with @pytest.mark.network.

    Allows in-process clients (e.g., httpx with ASGITransport) while preventing real sockets.
    """
    if request.node.get_closest_marker("network"):
        return

    def deny(*_args, **_kwargs):  # pragma: no cover - defensive
        raise RuntimeError(
            "Network access is disabled during tests. Use -k network to enable."
        )

    # Block high-level socket helpers
    monkeypatch.setattr(socket, "create_connection", deny, raising=True)

    # Block low-level connect on socket objects
    try:
        monkeypatch.setattr(socket.socket, "connect", deny, raising=True)
    except Exception:
        # Some platforms may not allow attribute patching; best-effort
        pass

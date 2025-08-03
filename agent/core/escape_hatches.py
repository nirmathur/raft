"""
Escape hatches for operator control.

Provides pause/resume functionality and watchdog monitoring.
"""

import threading
import time
from typing import Optional

# Global state
_pause_requested = False
_kill_requested = False
_watchdog_thread: Optional[threading.Thread] = None
_watchdog_running = False


def request_pause(pause: bool) -> None:
    """Request pause or resume of governor cycles."""
    global _pause_requested
    _pause_requested = pause


def request_kill() -> None:
    """Request immediate termination."""
    global _kill_requested
    _kill_requested = True


def is_paused() -> bool:
    """Check if governor should pause."""
    return _pause_requested


def load_state() -> None:
    """Load state from persistent storage (placeholder)."""
    # TODO: Implement persistent state loading
    pass


def start_watchdog() -> None:
    """Start watchdog thread for monitoring."""
    global _watchdog_thread, _watchdog_running

    if _watchdog_thread is None or not _watchdog_thread.is_alive():
        _watchdog_running = True
        _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
        _watchdog_thread.start()


def _watchdog_loop() -> None:
    """Watchdog monitoring loop."""
    global _watchdog_running, _kill_requested

    while _watchdog_running:
        if _kill_requested:
            # TODO: Implement graceful shutdown
            import os

            os._exit(1)
        time.sleep(1.0)

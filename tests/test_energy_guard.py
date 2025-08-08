"""
Unit tests for energy_guard module.

Tests real energy sampling implementation and apoptosis behavior
according to Charter clause xˣ-29.
"""

import os
import time
from unittest.mock import patch

import pytest

import agent.core.energy_guard as eg
from agent.core.energy_guard import (
    HERMES_J_PER_MAC,
    _read_joules,
    check_budget,
    measure_block,
)

# Compute the same baseline the module uses at 1 GHz
BASELINE = HERMES_J_PER_MAC * 1_000_000_000


@pytest.fixture(autouse=True)
def reset_state():
    # Reset internal counters before each test
    eg._last_sample_time = 0.0
    eg._last_total_joules = 0.0
    eg._last_total_macs = 0
    yield


class TestReadJoules:
    def test_read_joules_rapl_available(self):
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = "5000000"
            # First call initializes → 0.0
            assert _read_joules() == 0.0
            # Second call returns ≥ 0.0
            energy = _read_joules()
            assert energy >= 0.0

    def test_read_joules_fallback(self):
        with (
            patch("os.path.exists", return_value=False),
            patch("agent.core.energy_guard._last_sample_time", 1000.0),
            patch("agent.core.energy_guard._last_total_joules", 0.0),
            patch("time.time", side_effect=[1000.0, 1001.0]),
        ):
            # Init
            assert _read_joules() == 0.0
            # 1 sec elapsed → energy ≈ 1×BASELINE×0.5
            energy2 = _read_joules()
            expected = 1.0 * BASELINE * 0.5
            assert (
                abs(energy2 - expected) < 1e-4
            )  # Relaxed tolerance for floating point precision


class TestCheckBudget:
    def test_budget_under_threshold(self):
        # used_joules well under 2×HERMES_J_PER_MAC over 1B MACs
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        check_budget(used_joules=limit * 0.5, macs=1_000_000_000)

    def test_budget_at_threshold(self):
        # exactly at 2×HERMES_J_PER_MAC limit
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        check_budget(used_joules=limit, macs=1_000_000_000)

    def test_budget_over_threshold_triggers_apoptosis(self):
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        with pytest.raises(SystemExit, match="Energy apoptosis triggered"):
            check_budget(used_joules=limit * 1.5, macs=1_000_000_000)

    def test_budget_short_duration_high_energy(self):
        # High energy per MAC should trigger apoptosis
        limit = 10_000_000 * HERMES_J_PER_MAC * 2.0
        with pytest.raises(SystemExit):
            check_budget(used_joules=limit * 2.0, macs=10_000_000)

    def test_budget_minimum_duration_protection(self):
        # Tiny MAC count → no crash, low energy
        limit = 1 * HERMES_J_PER_MAC * 2.0
        check_budget(used_joules=limit * 0.5, macs=1)


class TestMeasureBlock:
    @patch("agent.core.energy_guard._read_joules")
    def test_normal_operation(self, mock_read):
        # Use realistic energy values
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        mock_read.side_effect = [0.0, limit * 0.5]  # Under threshold
        with measure_block(macs_estimate=1_000_000_000):
            pass
        assert mock_read.call_count == 2

    @patch("agent.core.energy_guard._read_joules")
    def test_high_energy_triggers_apoptosis(self, mock_read):
        # Use energy that exceeds threshold
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        mock_read.side_effect = [0.0, limit * 3.0]  # Over threshold
        with pytest.raises(SystemExit):
            with measure_block(macs_estimate=1_000_000_000):
                pass

    @patch("agent.core.energy_guard._read_joules")
    def test_disabled_via_env(self, mock_read):
        with patch.dict(os.environ, {"ENERGY_GUARD_ENABLED": "false"}):
            with measure_block(macs_estimate=1):
                pass
        mock_read.assert_not_called()

    @patch("agent.core.energy_guard._read_joules")
    def test_exception_during_work(self, mock_read):
        # Use realistic energy values
        limit = 1_000_000_000 * HERMES_J_PER_MAC * 2.0
        mock_read.side_effect = [0.0, limit * 0.5]  # Under threshold
        with pytest.raises(ValueError):
            with measure_block(macs_estimate=1_000_000_000):
                raise ValueError("test exception")
        assert mock_read.call_count == 2

    @patch("agent.core.energy_guard._read_joules")
    def test_low_macs_high_energy(self, mock_read):
        # Use energy that exceeds threshold for low MAC count
        limit = 10_000_000 * HERMES_J_PER_MAC * 2.0
        mock_read.side_effect = [0.0, limit * 3.0]  # Over threshold
        with pytest.raises(SystemExit):
            with measure_block(macs_estimate=10_000_000):
                pass

"""
Unit tests for energy_guard module.

Tests real energy sampling implementation and apoptosis behavior
according to Charter clause xˣ-29.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from agent.core.energy_guard import measure_block, check_budget, _read_joules, HERMES_BASELINE_JOULES_PER_SECOND


class TestReadJoules:
    """Test _read_joules() function."""
    
    def test_read_joules_rapl_available(self):
        """Test RAPL energy reading when available."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', create=True) as mock_open:
            # Mock RAPL file returning 5000000 microjoules (5 joules)
            mock_open.return_value.__enter__.return_value.read.return_value = "5000000"
            
            # First call initializes, second call returns difference
            _read_joules()  # Initialize
            energy = _read_joules()
            assert energy >= 0.0
    
    def test_read_joules_fallback(self):
        """Test fallback time-based estimation when hardware monitoring unavailable."""
        with patch('os.path.exists', return_value=False), \
             patch('agent.core.energy_guard._PROCESS_START_TIME', 1000.0), \
             patch('agent.core.energy_guard._PROCESS_START_ENERGY', None), \
             patch('time.time', side_effect=[1000.0, 1001.0]):  # 1 second elapsed
            
            # First call should initialize and return 0
            energy1 = _read_joules()
            assert energy1 == 0.0
            
            # Second call should return the estimated energy
            energy2 = _read_joules()
            expected = 1.0 * HERMES_BASELINE_JOULES_PER_SECOND * 0.5  # 0.95 J
            assert abs(energy2 - expected) < 0.1


class TestCheckBudget:
    """Test check_budget() function."""
    
    def test_budget_under_threshold(self):
        """Test that normal energy consumption passes budget check."""
        # Low energy consumption: 0.5 J over 1B MACs (0.5 J/s, under 3.8 J/s threshold)
        used_joules = 0.5
        macs = 1_000_000_000
        
        # Should not raise SystemExit
        check_budget(used_joules, macs)
    
    def test_budget_at_threshold(self):
        """Test energy consumption exactly at 2×HERMES threshold."""
        # Energy rate exactly at threshold: 3.8 J/s
        threshold = HERMES_BASELINE_JOULES_PER_SECOND * 2.0
        used_joules = threshold * 1.0  # 1 second duration
        macs = 1_000_000_000  # 1B MACs ≈ 1 second
        
        # Should not raise SystemExit (exactly at threshold, not over)
        check_budget(used_joules, macs)
    
    def test_budget_over_threshold_triggers_apoptosis(self):
        """Test that energy consumption over 2×HERMES baseline triggers apoptosis."""
        # High energy consumption: 10 J over 1B MACs (10 J/s, over 3.8 J/s threshold)
        used_joules = 10.0
        macs = 1_000_000_000
        
        # Should raise SystemExit with apoptosis message
        with pytest.raises(SystemExit, match="Energy apoptosis triggered"):
            check_budget(used_joules, macs)
    
    def test_budget_short_duration_high_energy(self):
        """Test high energy consumption over very short duration triggers apoptosis."""
        # Very high energy over short time: 5 J over 10M MACs (50 J/s, well over threshold)
        used_joules = 5.0
        macs = 10_000_000  # 0.01 second duration
        
        with pytest.raises(SystemExit, match="Energy apoptosis triggered"):
            check_budget(used_joules, macs)
    
    def test_budget_minimum_duration_protection(self):
        """Test that minimum duration prevents division by zero."""
        # Very small MAC count should use minimum duration
        used_joules = 0.001
        macs = 1  # Tiny MAC count
        
        # Should not crash and should pass (low energy)
        check_budget(used_joules, macs)


class TestMeasureBlock:
    """Test measure_block() context manager."""
    
    @patch('agent.core.energy_guard._read_joules')
    def test_measure_block_normal_operation(self, mock_read_joules):
        """Test measure_block with normal energy consumption."""
        # Mock energy readings: start=0, end=1 (1 joule consumed)
        mock_read_joules.side_effect = [0.0, 1.0]
        
        # Should complete normally without raising SystemExit
        with measure_block(macs_estimate=1_000_000_000):
            pass  # Simulate computational work
        
        # Verify _read_joules was called twice (start and end)
        assert mock_read_joules.call_count == 2
    
    @patch('agent.core.energy_guard._read_joules')
    def test_measure_block_high_energy_triggers_apoptosis(self, mock_read_joules):
        """Test measure_block with high energy consumption triggers apoptosis."""
        # Mock energy readings: start=0, end=20 (20 joules consumed over 1B MACs = 20 J/s)
        mock_read_joules.side_effect = [0.0, 20.0]
        
        # Should raise SystemExit due to energy apoptosis
        with pytest.raises(SystemExit, match="Energy apoptosis triggered"):
            with measure_block(macs_estimate=1_000_000_000):
                pass  # Simulate high-energy computational work
    
    @patch('agent.core.energy_guard._read_joules')
    def test_measure_block_disabled_via_env(self, mock_read_joules):
        """Test that energy measurement is skipped when disabled via environment."""
        with patch.dict(os.environ, {'ENERGY_GUARD_ENABLED': 'false'}):
            with measure_block(macs_estimate=1_000_000_000):
                pass
        
        # _read_joules should not be called when disabled
        mock_read_joules.assert_not_called()
    
    @patch('agent.core.energy_guard._read_joules')
    def test_measure_block_exception_during_work(self, mock_read_joules):
        """Test that energy measurement still occurs when exception raised during work."""
        mock_read_joules.side_effect = [0.0, 1.0]  # Normal energy consumption
        
        # Exception during work should not prevent energy measurement
        with pytest.raises(ValueError, match="test exception"):
            with measure_block(macs_estimate=1_000_000_000):
                raise ValueError("test exception")
        
        # Energy should still be measured despite exception
        assert mock_read_joules.call_count == 2
    
    @patch('agent.core.energy_guard._read_joules')
    def test_measure_block_low_macs_high_energy_triggers_apoptosis(self, mock_read_joules):
        """Test that high energy with low MAC count (high energy rate) triggers apoptosis."""
        # High energy with low MAC count: 5 J over 1M MACs = 5000 J/s (way over threshold)
        mock_read_joules.side_effect = [0.0, 5.0]
        
        with pytest.raises(SystemExit, match="Energy apoptosis triggered"):
            with measure_block(macs_estimate=1_000_000):  # Low MAC count
                pass
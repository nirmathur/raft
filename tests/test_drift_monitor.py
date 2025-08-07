# tests/test_drift_monitor.py
"""Tests for drift monitor functionality."""

import os
import pytest
from unittest.mock import patch

from agent.core.drift_monitor import DriftAlert, DriftMonitor


class TestDriftMonitor:
    """Test cases for DriftMonitor class."""
    
    def test_initialization_defaults(self):
        """Test DriftMonitor initialization with default values."""
        monitor = DriftMonitor()
        assert monitor.window_size == 10  # default value
        assert monitor.mean_threshold == 0.05
        assert monitor.max_threshold == 0.1
        assert len(monitor.radii) == 0
    
    def test_initialization_custom_values(self):
        """Test DriftMonitor initialization with custom values."""
        monitor = DriftMonitor(
            window_size=5, 
            mean_threshold=0.02, 
            max_threshold=0.08
        )
        assert monitor.window_size == 5
        assert monitor.mean_threshold == 0.02
        assert monitor.max_threshold == 0.08
    
    def test_initialization_from_env_var(self):
        """Test DriftMonitor reads window size from DRIFT_WINDOW env var."""
        with patch.dict(os.environ, {"DRIFT_WINDOW": "15"}):
            monitor = DriftMonitor()
            assert monitor.window_size == 15
    
    def test_no_alert_on_constant_radii(self):
        """Test that constant spectral radii do not trigger alerts."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.05, max_threshold=0.1)
        
        # Record constant values
        for _ in range(10):
            monitor.record(0.5)  # No exception should be raised
        
        assert len(monitor.current_window) == 5  # Should be limited by window size
        assert all(r == 0.5 for r in monitor.current_window)
    
    def test_no_alert_on_small_variations(self):
        """Test that small variations don't trigger alerts."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.05, max_threshold=0.1)
        
        # Record values with small variations
        values = [0.5, 0.51, 0.49, 0.52, 0.48]
        for val in values:
            monitor.record(val)  # No exception should be raised
        
        assert len(monitor.current_window) == 5
    
    def test_alert_when_radii_trending_upward_mean(self):
        """Test that upward trending radii trigger mean drift alert."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.05, max_threshold=0.2)
        
        # Start with first value (no check)
        monitor.record(0.1)
        
        # Add trending upward values that will exceed mean threshold
        with pytest.raises(DriftAlert) as exc_info:
            monitor.record(0.2)  # diff = 0.1
            monitor.record(0.3)  # diff = 0.1 
            monitor.record(0.4)  # diff = 0.1, mean = 0.1 > 0.05
        
        assert "Mean drift" in str(exc_info.value)
        assert exc_info.value.mean_drift > 0.05
    
    def test_alert_when_radii_trending_upward_max(self):
        """Test that large max drift triggers alert."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.5, max_threshold=0.1)
        
        # Record values with large range
        values = [0.1, 0.25]  # max_drift = 0.15 > 0.1
        monitor.record(values[0])
        
        with pytest.raises(DriftAlert) as exc_info:
            monitor.record(values[1])
        
        assert "Max drift" in str(exc_info.value)
        assert exc_info.value.max_drift > 0.1
    
    def test_no_drift_check_with_single_value(self):
        """Test that no drift check occurs with only one value."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.01, max_threshold=0.01)
        
        # Should not raise even with very low thresholds
        monitor.record(0.5)
        
        assert len(monitor.current_window) == 1
    
    def test_sliding_window_behavior(self):
        """Test that sliding window properly maintains size limit."""
        monitor = DriftMonitor(window_size=3, mean_threshold=0.5, max_threshold=0.5)
        
        # Add more values than window size
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        for val in values:
            monitor.record(val)
        
        # Should only keep last 3 values
        assert len(monitor.current_window) == 3
        assert monitor.current_window == [0.3, 0.4, 0.5]
    
    def test_reset_functionality(self):
        """Test that reset clears the sliding window."""
        monitor = DriftMonitor(window_size=5)
        
        # Add some values
        for val in [0.1, 0.2, 0.3]:
            monitor.record(val)
        
        assert len(monitor.current_window) == 3
        
        # Reset and verify
        monitor.reset()
        assert len(monitor.current_window) == 0
        assert len(monitor.radii) == 0
    
    def test_mean_drift_calculation(self):
        """Test mean drift calculation accuracy."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.5, max_threshold=0.5)
        
        # Add specific values to test calculation
        values = [0.1, 0.3, 0.2, 0.4]  # diffs: [0.2, 0.1, 0.2], mean = 0.167
        for val in values:
            monitor.record(val)
        
        expected_mean = (0.2 + 0.1 + 0.2) / 3  # 0.167
        actual_mean = monitor._calculate_mean_drift()
        assert abs(actual_mean - expected_mean) < 0.001
    
    def test_max_drift_calculation(self):
        """Test max drift calculation accuracy."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.5, max_threshold=0.5)
        
        # Add specific values
        values = [0.1, 0.5, 0.2, 0.4]  # min=0.1, max=0.5, diff=0.4
        for val in values:
            monitor.record(val)
        
        expected_max = 0.5 - 0.1  # 0.4
        actual_max = monitor._calculate_max_drift()
        assert abs(actual_max - expected_max) < 0.001
    
    def test_drift_alert_attributes(self):
        """Test that DriftAlert carries correct drift metrics."""
        monitor = DriftMonitor(window_size=3, mean_threshold=0.05, max_threshold=0.1)
        
        monitor.record(0.1)
        
        with pytest.raises(DriftAlert) as exc_info:
            monitor.record(0.3)  # Large jump
        
        alert = exc_info.value
        assert hasattr(alert, 'mean_drift')
        assert hasattr(alert, 'max_drift')
        assert alert.mean_drift > 0
        assert alert.max_drift > 0
    
    def test_current_window_property(self):
        """Test that current_window property returns correct values."""
        monitor = DriftMonitor(window_size=3)
        
        values = [0.1, 0.2, 0.3]
        for val in values:
            monitor.record(val)
        
        window = monitor.current_window
        assert isinstance(window, list)
        assert window == values
        
        # Verify it's a copy (not the actual deque)
        window.append(0.4)
        assert len(monitor.current_window) == 3  # Original unchanged


class TestDriftAlert:
    """Test cases for DriftAlert exception."""
    
    def test_drift_alert_creation(self):
        """Test DriftAlert exception creation and attributes."""
        message = "Test drift alert"
        mean_drift = 0.075
        max_drift = 0.125
        
        alert = DriftAlert(message, mean_drift, max_drift)
        
        assert str(alert) == message
        assert alert.mean_drift == mean_drift
        assert alert.max_drift == max_drift
    
    def test_drift_alert_inheritance(self):
        """Test that DriftAlert is properly an Exception."""
        alert = DriftAlert("test", 0.1, 0.2)
        assert isinstance(alert, Exception)


class TestIntegrationScenarios:
    """Integration test scenarios for realistic drift detection."""
    
    def test_gradual_upward_drift(self):
        """Test detection of gradual upward drift over time."""
        monitor = DriftMonitor(window_size=10, mean_threshold=0.03, max_threshold=0.15)
        
        # Gradual increase that should eventually trigger mean threshold
        base = 0.5
        increment = 0.04
        
        monitor.record(base)  # Start
        
        # Gradually increase
        for i in range(1, 5):
            monitor.record(base + i * increment)
        
        # Should trigger mean drift alert
        with pytest.raises(DriftAlert) as exc_info:
            monitor.record(base + 5 * increment)
        
        assert "Mean drift" in str(exc_info.value)
    
    def test_sudden_spike_detection(self):
        """Test detection of sudden spikes in spectral radius."""
        monitor = DriftMonitor(window_size=5, mean_threshold=0.1, max_threshold=0.08)
        
        # Stable values
        for _ in range(3):
            monitor.record(0.4)
        
        # Sudden spike should trigger max drift
        with pytest.raises(DriftAlert) as exc_info:
            monitor.record(0.5)  # max_drift = 0.1 > 0.08
        
        assert "Max drift" in str(exc_info.value)
    
    def test_oscillating_values_no_alert(self):
        """Test that oscillating values within limits don't trigger alerts."""
        monitor = DriftMonitor(window_size=6, mean_threshold=0.05, max_threshold=0.15)
        
        # Oscillating pattern
        values = [0.4, 0.45, 0.4, 0.45, 0.4, 0.45]
        for val in values:
            monitor.record(val)  # Should not raise
        
        assert len(monitor.current_window) == 6
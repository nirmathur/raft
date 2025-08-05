"""
Tests for Prometheus metrics integration.
"""

from unittest.mock import patch

import pytest

from agent.metrics import (CHARTER_VIOLATIONS, CYCLE_COUNT, ENERGY_RATE,
                           PROC_LATENCY, PROOF_FAILURE, PROOF_SUCCESS,
                           SPECTRAL_RHO, SPECTRAL_THRESHOLD)


class TestMetrics:
    """Test Prometheus metrics functionality."""

    def test_metrics_initialization(self):
        """Test that metrics are properly initialized."""
        # Check that metrics exist and have correct types
        assert PROC_LATENCY._name == "raft_cycle_seconds"
        assert PROOF_SUCCESS._name == "raft_proof_pass"
        assert PROOF_FAILURE._name == "raft_proof_fail"
        assert ENERGY_RATE._name == "raft_energy_rate_j_s"
        assert SPECTRAL_RHO._name == "raft_spectral_radius"
        assert SPECTRAL_THRESHOLD._name == "raft_spectral_threshold"
        assert CYCLE_COUNT._name == "raft_cycles"

    def test_metrics_increment(self):
        """Test that metrics can be incremented."""
        initial_value = PROOF_SUCCESS._value.get()
        PROOF_SUCCESS.inc()
        assert PROOF_SUCCESS._value.get() == initial_value + 1

    def test_metrics_set(self):
        """Test that gauge metrics can be set."""
        test_value = 0.85
        SPECTRAL_RHO.set(test_value)
        assert SPECTRAL_RHO._value.get() == test_value

    def test_charter_violations_labels(self):
        """Test that charter violations can be tracked with labels."""
        initial_value = CHARTER_VIOLATIONS.labels(clause="test-clause")._value.get()
        CHARTER_VIOLATIONS.labels(clause="test-clause").inc()
        assert (
            CHARTER_VIOLATIONS.labels(clause="test-clause")._value.get()
            == initial_value + 1
        )

    def test_histogram_observation(self):
        """Test that histogram metrics can observe values."""
        test_duration = 1.5
        initial_count = len(PROC_LATENCY._buckets)
        PROC_LATENCY.observe(test_duration)
        # Just verify it doesn't raise an exception
        assert PROC_LATENCY._buckets is not None

    def test_metrics_integration_with_governor(self):
        """Test that metrics work with governor cycle."""
        from agent.core.governor import run_one_cycle

        # Reset metrics for clean test
        CYCLE_COUNT._value.set(0)
        PROOF_SUCCESS._value.set(0)
        PROOF_FAILURE._value.set(0)

        # Run a cycle and check metrics are updated
        initial_cycles = CYCLE_COUNT._value.get()
        run_one_cycle()

        # Should have incremented cycle count
        assert CYCLE_COUNT._value.get() > initial_cycles

        # Should have either success or failure increment
        total_proofs = PROOF_SUCCESS._value.get() + PROOF_FAILURE._value.get()
        assert total_proofs > 0

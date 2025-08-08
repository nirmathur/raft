"""
Tests for the performance/accuracy comparison harness.

Tests both baseline and raft modes with mocked dependencies to ensure
fast, independent test execution.
"""

import csv
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from scripts.compare_baseline import (baseline_computation, raft_computation,
                                      run_comparison, write_csv)


class TestBaselineComputation:
    """Test baseline computation mode."""

    def test_baseline_computation_deterministic(self):
        """Test that baseline computation is deterministic with fixed seed."""
        # Test with same seed
        success1, rho1, energy1 = baseline_computation(42)
        success2, rho2, energy2 = baseline_computation(42)

        assert success1 == success2
        assert rho1 == rho2
        assert energy1 == energy2

        # Test with different seeds
        success3, rho3, energy3 = baseline_computation(43)
        assert success1 == success3  # Success should always be True
        assert rho1 == rho3  # Both should be None
        assert energy1 == energy3  # Both should be None

    def test_baseline_computation_returns_expected_values(self):
        """Test that baseline computation returns expected values."""
        success, rho, energy = baseline_computation(42)

        assert success is True
        assert rho is None
        assert energy is None


class TestRaftComputation:
    """Test RAFT computation mode with mocked dependencies."""

    def test_raft_computation_success_with_metrics(self):
        """Test RAFT computation when governor succeeds and metrics are available."""
        # Mock the governor and metrics modules
        with patch("agent.core.governor.run_one_cycle") as mock_run_cycle, patch(
            "agent.metrics.SPECTRAL_RHO"
        ) as mock_rho, patch("agent.metrics.ENERGY_RATE") as mock_energy:
            # Mock the governor to return True
            mock_run_cycle.return_value = True

            # Mock metrics to return values
            mock_rho._value.get.return_value = 0.75
            mock_energy._value.get.return_value = 1.5

            success, rho, energy = raft_computation(42)

            assert success is True
            assert rho == 0.75
            assert energy == 1.5
            mock_run_cycle.assert_called_once()

    def test_raft_computation_failure_with_metrics(self):
        """Test RAFT computation when governor fails but metrics are available."""
        # Mock the governor and metrics modules
        with patch("agent.core.governor.run_one_cycle") as mock_run_cycle, patch(
            "agent.metrics.SPECTRAL_RHO"
        ) as mock_rho, patch("agent.metrics.ENERGY_RATE") as mock_energy:
            # Mock the governor to return False
            mock_run_cycle.return_value = False

            # Mock metrics to return values
            mock_rho._value.get.return_value = 0.95
            mock_energy._value.get.return_value = 2.1

            success, rho, energy = raft_computation(42)

            assert success is False
            assert rho == 0.95
            assert energy == 2.1
            mock_run_cycle.assert_called_once()

    def test_raft_computation_metrics_unavailable(self):
        """Test RAFT computation when metrics are not available."""
        # Mock the governor and metrics modules
        with patch("agent.core.governor.run_one_cycle") as mock_run_cycle, patch(
            "agent.metrics.SPECTRAL_RHO"
        ) as mock_rho, patch("agent.metrics.ENERGY_RATE") as mock_energy:
            # Mock the governor to return True
            mock_run_cycle.return_value = True

            # Mock metrics to raise exceptions (simulating unavailable metrics)
            mock_rho._value.get.side_effect = AttributeError("No attribute")
            mock_energy._value.get.side_effect = ValueError("Invalid value")

            success, rho, energy = raft_computation(42)

            assert success is True
            assert rho is None
            assert energy is None
            mock_run_cycle.assert_called_once()


class TestCSVWriting:
    """Test CSV writing functionality."""

    def test_write_csv_creates_file_with_correct_header(self, tmp_path):
        """Test that CSV writing creates file with correct header."""
        output_path = tmp_path / "test_output.csv"
        data = [
            {
                "run": 1,
                "mode": "baseline",
                "timestamp": "2024-01-01T12:00:00",
                "success": True,
                "latency": 0.1,
                "rho": "",
                "energy": "",
            }
        ]

        write_csv(output_path, data)

        assert output_path.exists()

        # Check header
        with open(output_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            expected_header = [
                "run",
                "mode",
                "timestamp",
                "success",
                "latency",
                "rho",
                "energy",
            ]
            assert header == expected_header

    def test_write_csv_writes_data_correctly(self, tmp_path):
        """Test that CSV writing writes data correctly."""
        output_path = tmp_path / "test_output.csv"
        data = [
            {
                "run": 1,
                "mode": "baseline",
                "timestamp": "2024-01-01T12:00:00",
                "success": True,
                "latency": 0.1,
                "rho": "",
                "energy": "",
            },
            {
                "run": 2,
                "mode": "raft",
                "timestamp": "2024-01-01T12:01:00",
                "success": False,
                "latency": 0.5,
                "rho": 0.8,
                "energy": 1.2,
            },
        ]

        write_csv(output_path, data)

        # Check data
        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 2

            # Check first row
            assert rows[0]["run"] == "1"
            assert rows[0]["mode"] == "baseline"
            assert rows[0]["success"] == "True"
            assert rows[0]["latency"] == "0.1"
            assert rows[0]["rho"] == ""
            assert rows[0]["energy"] == ""

            # Check second row
            assert rows[1]["run"] == "2"
            assert rows[1]["mode"] == "raft"
            assert rows[1]["success"] == "False"
            assert rows[1]["latency"] == "0.5"
            assert rows[1]["rho"] == "0.8"
            assert rows[1]["energy"] == "1.2"


class TestRunComparison:
    """Test the main comparison runner."""

    @patch("scripts.compare_baseline.baseline_computation")
    def test_run_comparison_baseline_mode(self, mock_baseline, tmp_path):
        """Test running comparison in baseline mode."""
        output_path = tmp_path / "output_baseline.csv"
        collected_data = []

        # Mock baseline computation to return deterministic results
        mock_baseline.return_value = (True, None, None)

        run_comparison(
            mode="baseline",
            runs=3,
            output_path=output_path,
            seed=42,
            collected_data=collected_data,
        )

        # Check that baseline_computation was called 3 times
        assert mock_baseline.call_count == 3

        # Check that data was collected
        assert len(collected_data) == 3

        # Check CSV file was created with correct number of lines
        assert output_path.exists()
        with open(output_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 4  # Header + 3 data rows

        # Check that each row has correct mode and run numbers
        for i, row in enumerate(collected_data):
            assert row["mode"] == "baseline"
            assert row["run"] == i + 1
            assert row["success"] is True
            assert row["rho"] == ""
            assert row["energy"] == ""

    @patch("scripts.compare_baseline.raft_computation")
    def test_run_comparison_raft_mode(self, mock_raft, tmp_path):
        """Test running comparison in raft mode."""
        output_path = tmp_path / "output_raft.csv"
        collected_data = []

        # Mock raft computation to return [True, False, True] for 3 runs
        mock_raft.side_effect = [
            (True, 0.7, 1.0),
            (False, 0.9, 1.5),
            (True, 0.6, 0.8),
        ]

        run_comparison(
            mode="raft",
            runs=3,
            output_path=output_path,
            seed=42,
            collected_data=collected_data,
        )

        # Check that raft_computation was called 3 times
        assert mock_raft.call_count == 3

        # Check that data was collected
        assert len(collected_data) == 3

        # Check CSV file was created with correct number of lines
        assert output_path.exists()
        with open(output_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 4  # Header + 3 data rows

        # Check that each row has correct mode, run numbers, and success sequence
        expected_success = [True, False, True]
        expected_rho = [0.7, 0.9, 0.6]
        expected_energy = [1.0, 1.5, 0.8]

        for i, row in enumerate(collected_data):
            assert row["mode"] == "raft"
            assert row["run"] == i + 1
            assert row["success"] == expected_success[i]
            assert row["rho"] == expected_rho[i]  # Should be float, not string
            assert row["energy"] == expected_energy[i]  # Should be float, not string

    def test_run_comparison_invalid_mode(self, tmp_path):
        """Test that invalid mode raises ValueError."""
        output_path = tmp_path / "output_invalid.csv"
        collected_data = []

        with pytest.raises(ValueError, match="Unknown mode: invalid"):
            run_comparison(
                mode="invalid",
                runs=3,
                output_path=output_path,
                seed=42,
                collected_data=collected_data,
            )


class TestIntegration:
    """Integration tests that verify the complete workflow."""

    @patch("scripts.compare_baseline.baseline_computation")
    def test_baseline_integration(self, mock_baseline, tmp_path):
        """Integration test for baseline mode."""
        output_path = tmp_path / "integration_baseline.csv"
        collected_data = []

        # Mock baseline computation
        mock_baseline.return_value = (True, None, None)

        run_comparison(
            mode="baseline",
            runs=3,
            output_path=output_path,
            seed=42,
            collected_data=collected_data,
        )

        # Verify file exists and has correct structure
        assert output_path.exists()

        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 3

            for i, row in enumerate(rows):
                assert row["run"] == str(i + 1)
                assert row["mode"] == "baseline"
                assert row["success"] == "True"
                assert row["rho"] == ""
                assert row["energy"] == ""
                # Check that latency is a valid float
                assert float(row["latency"]) >= 0
                # Check that timestamp is valid ISO format
                assert "T" in row["timestamp"]

    @patch("scripts.compare_baseline.raft_computation")
    def test_raft_integration(self, mock_raft, tmp_path):
        """Integration test for raft mode."""
        output_path = tmp_path / "integration_raft.csv"
        collected_data = []

        # Mock raft computation with varying results
        mock_raft.side_effect = [
            (True, 0.7, 1.0),
            (False, 0.9, 1.5),
            (True, 0.6, 0.8),
        ]

        run_comparison(
            mode="raft",
            runs=3,
            output_path=output_path,
            seed=42,
            collected_data=collected_data,
        )

        # Verify file exists and has correct structure
        assert output_path.exists()

        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 3

            expected_success = ["True", "False", "True"]
            expected_rho = ["0.7", "0.9", "0.6"]
            expected_energy = ["1.0", "1.5", "0.8"]

            for i, row in enumerate(rows):
                assert row["run"] == str(i + 1)
                assert row["mode"] == "raft"
                assert row["success"] == expected_success[i]
                assert row["rho"] == expected_rho[i]
                assert row["energy"] == expected_energy[i]
                # Check that latency is a valid float
                assert float(row["latency"]) >= 0
                # Check that timestamp is valid ISO format
                assert "T" in row["timestamp"]

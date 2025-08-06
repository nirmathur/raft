"""
Tests for the performance comparison harness.

Tests both baseline and raft modes with mocked dependencies to ensure
reliable and fast test execution.
"""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import numpy as np

from scripts.compare_baseline import (
    baseline_cycle, 
    raft_cycle, 
    run_comparison,
    main
)


class TestBaselineCycle:
    """Test the baseline no-op cycle implementation."""
    
    def test_baseline_returns_expected_structure(self):
        """Test that baseline_cycle returns the correct metrics structure."""
        result = baseline_cycle()
        
        # Check all required keys are present
        expected_keys = {'success', 'latency', 'rho', 'energy'}
        assert set(result.keys()) == expected_keys
        
        # Check data types
        assert isinstance(result['success'], bool)
        assert isinstance(result['latency'], float)
        assert isinstance(result['rho'], float)
        assert isinstance(result['energy'], float)
    
    def test_baseline_success_always_true(self):
        """Test that baseline mode always succeeds."""
        for _ in range(5):  # Run multiple times to ensure consistency
            result = baseline_cycle()
            assert result['success'] is True
    
    def test_baseline_metrics_in_expected_ranges(self):
        """Test that baseline metrics fall within expected ranges."""
        result = baseline_cycle()
        
        # Latency should be small (1-5ms + noise)
        assert 0.0 < result['latency'] < 0.01  # Should be under 10ms
        
        # Spectral radius should be safe (0.1 to 0.8)
        assert 0.1 <= result['rho'] <= 0.8
        
        # Energy should be minimal (1-5 microjoules)
        assert 1e-6 <= result['energy'] <= 5e-6
    
    @patch('time.sleep')
    @patch('random.uniform')
    @patch('random.gauss')
    def test_baseline_deterministic_with_mocks(self, mock_gauss, mock_uniform, mock_sleep):
        """Test baseline with mocked random functions for deterministic results."""
        mock_uniform.side_effect = [0.003, 0.5, 3e-6]  # Processing time, rho, energy
        mock_gauss.return_value = 0.001  # Noise
        
        result = baseline_cycle()
        
        assert result['success'] is True
        assert mock_sleep.called
        assert result['rho'] == 0.5
        assert result['energy'] == 3e-6


class TestRaftCycle:
    """Test the RAFT cycle implementation with mocked dependencies."""
    
    @patch('scripts.compare_baseline.run_one_cycle')
    @patch('scripts.compare_baseline.spectral_radius')
    @patch('agent.core.governor._fake_jacobian')
    @patch('random.uniform')
    def test_raft_cycle_success(self, mock_uniform, mock_jacobian, mock_spectral, mock_run_cycle):
        """Test successful RAFT cycle execution."""
        # Setup mocks
        mock_run_cycle.return_value = True
        mock_jacobian.return_value = np.array([[0.4, 0.2], [0.1, 0.3]])
        mock_spectral.return_value = 0.5
        mock_uniform.return_value = 1.0  # Energy variance multiplier
        
        result = raft_cycle()
        
        # Verify structure and success
        assert result['success'] is True
        assert isinstance(result['latency'], float)
        assert result['rho'] == 0.5
        assert result['energy'] > 0
        
        # Verify mocks were called
        mock_run_cycle.assert_called_once()
        mock_spectral.assert_called_once()
    
    @patch('scripts.compare_baseline.run_one_cycle')
    @patch('scripts.compare_baseline.spectral_radius')
    @patch('agent.core.governor._fake_jacobian')
    def test_raft_cycle_failure(self, mock_jacobian, mock_spectral, mock_run_cycle):
        """Test RAFT cycle failure handling."""
        # Setup mocks for failure case
        mock_run_cycle.return_value = False
        mock_jacobian.return_value = np.array([[0.4, 0.2], [0.1, 0.3]])
        mock_spectral.return_value = 0.95  # Above threshold
        
        result = raft_cycle()
        
        assert result['success'] is False
        assert result['rho'] == 0.95
        assert isinstance(result['latency'], float)
    
    @patch('scripts.compare_baseline.run_one_cycle')
    def test_raft_cycle_exception_handling(self, mock_run_cycle):
        """Test that exceptions in RAFT cycle are handled gracefully."""
        # Setup mock to raise exception
        mock_run_cycle.side_effect = Exception("Test exception")
        
        result = raft_cycle()
        
        assert result['success'] is False
        assert np.isnan(result['rho'])
        assert result['energy'] == 0.0
        assert isinstance(result['latency'], float)


class TestRunComparison:
    """Test the main comparison runner function."""
    
    @patch('scripts.compare_baseline.baseline_cycle')
    def test_baseline_mode_execution(self, mock_baseline_cycle):
        """Test that baseline mode executes the correct number of runs."""
        # Setup mock to return predictable data
        mock_baseline_cycle.return_value = {
            'success': True,
            'latency': 0.002,
            'rho': 0.4,
            'energy': 2e-6
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory for test
            original_cwd = Path.cwd()
            tmpdir_path = Path(tmpdir)
            
            try:
                import os
                os.chdir(tmpdir)
                
                run_comparison('baseline', 3)
                
                # Check that CSV file was created
                output_file = tmpdir_path / 'output_baseline.csv'
                assert output_file.exists()
                
                # Check CSV contents
                with open(output_file, 'r') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                assert len(rows) == 3  # Should have 3 runs
                assert mock_baseline_cycle.call_count == 3
                
                # Check CSV structure
                expected_columns = {'run', 'mode', 'timestamp', 'success', 'latency', 'rho', 'energy'}
                assert set(rows[0].keys()) == expected_columns
                
                # Check data consistency
                for i, row in enumerate(rows):
                    assert row['run'] == str(i + 1)
                    assert row['mode'] == 'baseline'
                    assert row['success'] == 'True'
                    
            finally:
                os.chdir(original_cwd)
    
    @patch('scripts.compare_baseline.raft_cycle')
    def test_raft_mode_execution(self, mock_raft_cycle):
        """Test that raft mode executes the correct number of runs."""
        # Setup mock to return predictable data
        mock_raft_cycle.return_value = {
            'success': True,
            'latency': 0.05,
            'rho': 0.6,
            'energy': 1e-4
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            tmpdir_path = Path(tmpdir)
            
            try:
                import os
                os.chdir(tmpdir)
                
                run_comparison('raft', 3)
                
                # Check that CSV file was created
                output_file = tmpdir_path / 'output_raft.csv'
                assert output_file.exists()
                
                # Check CSV contents
                with open(output_file, 'r') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                assert len(rows) == 3  # Should have 3 runs
                assert mock_raft_cycle.call_count == 3
                
                # Check that mode is correctly recorded
                for row in rows:
                    assert row['mode'] == 'raft'
                    
            finally:
                os.chdir(original_cwd)
    
    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            with tempfile.TemporaryDirectory() as tmpdir:
                import os
                original_cwd = Path.cwd()
                try:
                    os.chdir(tmpdir)
                    run_comparison('invalid_mode', 1)
                finally:
                    os.chdir(original_cwd)


class TestMainFunction:
    """Test the main CLI entry point."""
    
    @patch('scripts.compare_baseline.run_comparison')
    @patch('sys.argv', ['compare_baseline.py', '--runs', '5', '--mode', 'baseline'])
    def test_main_baseline_mode(self, mock_run_comparison):
        """Test main function with baseline mode arguments."""
        main()
        mock_run_comparison.assert_called_once_with('baseline', 5)
    
    @patch('scripts.compare_baseline.run_comparison')
    @patch('sys.argv', ['compare_baseline.py', '--runs', '10', '--mode', 'raft'])
    def test_main_raft_mode(self, mock_run_comparison):
        """Test main function with raft mode arguments."""
        main()
        mock_run_comparison.assert_called_once_with('raft', 10)
    
    @patch('sys.argv', ['compare_baseline.py', '--runs', '-1', '--mode', 'baseline'])
    def test_main_invalid_runs(self):
        """Test main function with invalid number of runs."""
        with pytest.raises(SystemExit):  # argparse calls sys.exit on error
            main()
    
    @patch('sys.argv', ['compare_baseline.py', '--runs', '5', '--mode', 'invalid'])
    def test_main_invalid_mode(self):
        """Test main function with invalid mode."""
        with pytest.raises(SystemExit):  # argparse calls sys.exit on error
            main()
    
    @patch('scripts.compare_baseline.run_comparison')
    @patch('sys.argv', ['compare_baseline.py', '--runs', '3', '--mode', 'baseline'])
    def test_main_keyboard_interrupt(self, mock_run_comparison):
        """Test main function handles KeyboardInterrupt gracefully."""
        mock_run_comparison.side_effect = KeyboardInterrupt()
        
        # Should not raise exception, should handle gracefully
        main()
        mock_run_comparison.assert_called_once()


class TestIntegration:
    """Integration tests for the full comparison workflow."""
    
    @patch('scripts.compare_baseline.run_one_cycle')
    @patch('scripts.compare_baseline.spectral_radius')
    @patch('agent.core.governor._fake_jacobian')
    def test_full_workflow_both_modes(self, mock_jacobian, mock_spectral, mock_run_cycle):
        """Test complete workflow for both modes with N=3 runs each."""
        # Setup RAFT mocks
        mock_run_cycle.return_value = True
        mock_jacobian.return_value = np.array([[0.4, 0.2], [0.1, 0.3]])
        mock_spectral.return_value = 0.5
        
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            tmpdir_path = Path(tmpdir)
            
            try:
                import os
                os.chdir(tmpdir)
                
                # Run baseline comparison
                run_comparison('baseline', 3)
                baseline_file = tmpdir_path / 'output_baseline.csv'
                assert baseline_file.exists()
                
                # Run raft comparison  
                run_comparison('raft', 3)
                raft_file = tmpdir_path / 'output_raft.csv'
                assert raft_file.exists()
                
                # Verify both files have correct structure and data
                for filename, expected_mode in [(baseline_file, 'baseline'), (raft_file, 'raft')]:
                    with open(filename, 'r') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                    
                    assert len(rows) == 3
                    for row in rows:
                        assert row['mode'] == expected_mode
                        assert 'timestamp' in row
                        assert row['success'] in ['True', 'False']
                        
                        # Verify numeric fields can be parsed
                        float(row['latency'])
                        float(row['rho'])
                        float(row['energy'])
                        
            finally:
                os.chdir(original_cwd)
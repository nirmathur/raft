"""Tests for the RAFT CLI module.

Tests all CLI commands using click.testing.CliRunner:
- raft run
- raft one-cycle  
- raft version
"""

import json
import time
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from agent.cli import main, get_version


class TestCLIVersion:
    """Test version command and version retrieval."""
    
    def test_version_command(self):
        """Test that version command outputs version string."""
        runner = CliRunner()
        result = runner.invoke(main, ['version'])
        
        assert result.exit_code == 0
        assert "RAFT version" in result.output
        assert "0.1.0" in result.output or "unknown" in result.output
    
    def test_get_version_function(self):
        """Test get_version function directly."""
        version = get_version()
        assert isinstance(version, str)
        # Should be either actual version or "unknown" if file not found
        assert version == "0.1.0" or version == "unknown"


class TestCLIOneCycle:
    """Test one-cycle command."""
    
    @patch('agent.cli.run_one_cycle')
    def test_one_cycle_success(self, mock_run_one_cycle):
        """Test one-cycle command with successful cycle."""
        # Setup mock
        mock_run_one_cycle.return_value = True
        
        # Mock the Prometheus gauge values
        with patch('agent.cli.SPECTRAL_RHO._value._value', 0.5), \
             patch('agent.cli.ENERGY_RATE._value._value', 1.23e6):
            
            runner = CliRunner()
            result = runner.invoke(main, ['one-cycle'])
            
            assert result.exit_code == 0
            
            # Parse JSON output
            output_data = json.loads(result.output)
            assert output_data["status"] == "success"
            assert isinstance(output_data["rho"], float)
            assert isinstance(output_data["energy"], float)
    
    @patch('agent.cli.run_one_cycle')
    def test_one_cycle_failure(self, mock_run_one_cycle):
        """Test one-cycle command with failed cycle."""
        # Setup mock
        mock_run_one_cycle.return_value = False
        
        # Mock the Prometheus gauge values
        with patch('agent.cli.SPECTRAL_RHO._value._value', 0.95), \
             patch('agent.cli.ENERGY_RATE._value._value', 0.0):
            
            runner = CliRunner()
            result = runner.invoke(main, ['one-cycle'])
            
            assert result.exit_code == 1  # Should exit with error code
            
            # Parse JSON output
            output_data = json.loads(result.output)
            assert output_data["status"] == "failure"
            assert isinstance(output_data["rho"], float)
            assert isinstance(output_data["energy"], float)
    
    @patch('agent.cli.run_one_cycle')
    def test_one_cycle_json_format(self, mock_run_one_cycle):
        """Test that one-cycle outputs valid JSON with required fields."""
        mock_run_one_cycle.return_value = True
        
        # Mock gauge values to ensure they're accessible
        with patch('agent.cli.SPECTRAL_RHO._value._value', 0.75), \
             patch('agent.cli.ENERGY_RATE._value._value', 9.87e5):
            
            runner = CliRunner()
            result = runner.invoke(main, ['one-cycle'])
            
            # Should be valid JSON
            output_data = json.loads(result.output)
            
            # Check required fields
            assert "status" in output_data
            assert "rho" in output_data  
            assert "energy" in output_data
            
            # Check types
            assert output_data["status"] in ["success", "failure"]
            assert isinstance(output_data["rho"], (int, float))
            assert isinstance(output_data["energy"], (int, float))


class TestCLIRun:
    """Test run command."""
    
    @patch('agent.cli.start_http_server')
    @patch('agent.cli.run_one_cycle')
    @patch('agent.cli.is_paused')
    @patch('agent.cli.time.sleep')
    def test_run_command_basic(self, mock_sleep, mock_is_paused, mock_run_one_cycle, mock_start_server):
        """Test run command starts metrics server and runs cycles."""
        # Setup mocks
        mock_run_one_cycle.return_value = True
        mock_is_paused.side_effect = [False, False, True]  # Run 2 cycles then stop
        
        runner = CliRunner()
        result = runner.invoke(main, ['run', '--cycle-interval', '0.1'])
        
        assert result.exit_code == 0
        
        # Verify metrics server started
        mock_start_server.assert_called_once_with(8002)  # default port
        
        # Verify cycles were run
        assert mock_run_one_cycle.call_count >= 2
        
        # Verify sleep was called between cycles
        mock_sleep.assert_called_with(0.1)
    
    @patch('agent.cli.start_http_server')
    @patch('agent.cli.run_one_cycle')
    @patch('agent.cli.is_paused')
    @patch('agent.cli.time.sleep')
    def test_run_command_custom_port(self, mock_sleep, mock_is_paused, mock_run_one_cycle, mock_start_server):
        """Test run command with custom metrics port."""
        mock_run_one_cycle.return_value = True
        mock_is_paused.return_value = True  # Stop immediately
        
        runner = CliRunner()
        result = runner.invoke(main, ['run', '--metrics-port', '9090'])
        
        assert result.exit_code == 0
        mock_start_server.assert_called_once_with(9090)
    
    @patch('agent.cli.start_http_server')
    @patch('agent.cli.run_one_cycle')
    @patch('agent.cli.is_paused')
    def test_run_command_cycle_failure(self, mock_is_paused, mock_run_one_cycle, mock_start_server):
        """Test run command handles cycle failures gracefully."""
        # Mix of successful and failed cycles
        mock_run_one_cycle.side_effect = [True, False, True, False]
        mock_is_paused.side_effect = [False, False, False, False, True]
        
        runner = CliRunner()
        result = runner.invoke(main, ['run', '--cycle-interval', '0.01'])
        
        assert result.exit_code == 0  # Should not exit on cycle failures
        assert mock_run_one_cycle.call_count >= 4


class TestCLIMain:
    """Test main CLI group and options."""
    
    def test_main_help(self):
        """Test main command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert "RAFT - Recursive Agent for Formal Trust" in result.output
        assert "run" in result.output
        assert "one-cycle" in result.output
        assert "version" in result.output
    
    def test_verbose_option(self):
        """Test verbose option is accepted."""
        runner = CliRunner()
        result = runner.invoke(main, ['--verbose', 'version'])
        
        assert result.exit_code == 0
        assert "RAFT version" in result.output
    
    def test_subcommand_help(self):
        """Test subcommands have help text."""
        runner = CliRunner()
        
        # Test run command help
        result = runner.invoke(main, ['run', '--help'])
        assert result.exit_code == 0
        assert "continuous governor loop" in result.output
        
        # Test one-cycle command help
        result = runner.invoke(main, ['one-cycle', '--help'])
        assert result.exit_code == 0
        assert "single governor cycle" in result.output
        
        # Test version command help
        result = runner.invoke(main, ['version', '--help'])
        assert result.exit_code == 0
        assert "version information" in result.output


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    @patch('agent.cli.start_http_server')
    @patch('agent.cli.is_paused')
    def test_run_integration_with_real_cycle(self, mock_is_paused, mock_start_server):
        """Test run command with actual run_one_cycle (no mocking)."""
        # Only run one cycle to avoid long test times
        mock_is_paused.side_effect = [False, True]
        
        runner = CliRunner()
        result = runner.invoke(main, ['run', '--cycle-interval', '0.01'])
        
        # Should complete without errors (even if cycle fails due to test environment)
        assert result.exit_code == 0
        mock_start_server.assert_called_once()
    
    def test_one_cycle_integration(self):
        """Test one-cycle command with actual run_one_cycle (no mocking)."""
        runner = CliRunner()
        result = runner.invoke(main, ['one-cycle'])
        
        # Should produce valid JSON regardless of cycle success/failure
        try:
            output_data = json.loads(result.output)
            assert "status" in output_data
            assert "rho" in output_data
            assert "energy" in output_data
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
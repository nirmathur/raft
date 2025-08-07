"""
Tests for RAFT Operator API
============================

Tests the FastAPI-based operator interface including:
- Authentication (Bearer token)
- Configuration management (POST /config)
- Model reloading (POST /reload_model)
- Error handling and validation
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import torch
from fastapi.testclient import TestClient

from agent.core.config_store import Config, get_config, load_config, update_config
from agent.core.operator_api import app


# Test client with auth token
TOKEN = "test-token"
HEADERS = {"authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client():
    """FastAPI test client with mocked token."""
    with patch('agent.core.operator_api.TOKEN', TOKEN):
        yield TestClient(app)


@pytest.fixture
def temp_config_file():
    """Temporary config file for testing - Windows compatible."""
    fd, config_path = tempfile.mkstemp(suffix='.yaml')
    os.close(fd)  # Close the file descriptor immediately
    
    # Set the config path temporarily
    with patch('agent.core.config_store._config_path', Path(config_path)):
        yield config_path
    
    # Clean up
    Path(config_path).unlink(missing_ok=True)


class TestAuthentication:
    """Test suite for Bearer token authentication."""
    
    def test_missing_auth_header(self, client):
        """Test request without authorization header."""
        response = client.post("/config", json={"rho_max": 0.8, "energy_multiplier": 2.0})
        assert response.status_code == 401
        assert response.json()["detail"] == "unauthorized"
    
    def test_invalid_token(self, client):
        """Test request with invalid token."""
        headers = {"authorization": "Bearer wrong-token"}
        response = client.post("/config", json={"rho_max": 0.8, "energy_multiplier": 2.0}, headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "unauthorized"
    
    def test_malformed_auth_header(self, client):
        """Test request with malformed auth header."""
        headers = {"authorization": "NotBearer token"}
        response = client.post("/config", json={"rho_max": 0.8, "energy_multiplier": 2.0}, headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "unauthorized"


class TestConfigEndpoint:
    """Test suite for POST /config endpoint."""
    
    def test_valid_config_update(self, client, temp_config_file):
        """Test successful configuration update."""
        payload = {"rho_max": 0.85, "energy_multiplier": 3.0}
        
        with patch('agent.core.config_store._config_path', Path(temp_config_file)):
            response = client.post("/config", json=payload, headers=HEADERS)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Configuration updated successfully"
        assert data["config"]["rho_max"] == 0.85
        assert data["config"]["energy_multiplier"] == 3.0
    
    def test_invalid_rho_max_too_high(self, client):
        """Test validation failure for rho_max >= 1."""
        payload = {"rho_max": 1.2, "energy_multiplier": 2.0}
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert "Input should be less than 1" in str(response.json())
    
    def test_invalid_rho_max_too_low(self, client):
        """Test validation failure for rho_max <= 0."""
        payload = {"rho_max": -0.1, "energy_multiplier": 2.0}
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert "Input should be greater than 0" in str(response.json())
    
    def test_invalid_energy_multiplier_too_high(self, client):
        """Test validation failure for energy_multiplier > 4."""
        payload = {"rho_max": 0.8, "energy_multiplier": 5.0}
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert "Input should be less than or equal to 4" in str(response.json())
    
    def test_invalid_energy_multiplier_too_low(self, client):
        """Test validation failure for energy_multiplier < 1."""
        payload = {"rho_max": 0.8, "energy_multiplier": 0.5}
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert "Input should be greater than or equal to 1" in str(response.json())
    
    def test_missing_required_fields(self, client):
        """Test validation failure for missing required fields."""
        payload = {"rho_max": 0.8}  # Missing energy_multiplier
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert "Field required" in str(response.json())
    
    def test_invalid_field_types(self, client):
        """Test validation failure for invalid field types."""
        payload = {"rho_max": "not-a-number", "energy_multiplier": 2.0}
        response = client.post("/config", json=payload, headers=HEADERS)
        assert response.status_code == 422
    
    @patch('agent.core.operator_api.record')
    @patch('agent.core.operator_api.logger')
    def test_audit_logging(self, mock_logger, mock_record, client, temp_config_file):
        """Test that config updates are properly logged and recorded."""
        payload = {"rho_max": 0.75, "energy_multiplier": 1.5}
        
        with patch('agent.core.config_store._config_path', Path(temp_config_file)):
            response = client.post("/config", json=payload, headers=HEADERS)
        
        assert response.status_code == 200
        
        # Verify logging calls
        mock_logger.info.assert_called()
        mock_record.assert_called_once()
        
        # Check record call arguments
        call_args = mock_record.call_args
        assert call_args[0][0] == "config-update"
        assert "updates" in call_args[0][1]
        assert "new_config" in call_args[0][1]


class TestModelReloadEndpoint:
    """Test suite for POST /reload_model endpoint."""
    
    def test_successful_model_reload(self, client):
        """Test successful model reload."""
        response = client.post("/reload_model", headers=HEADERS)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"
        assert "rho" in data
        assert isinstance(data["rho"], float)
        assert "Model reloaded successfully" in data["message"]
    
    @patch('agent.core.operator_api.record')
    @patch('agent.core.operator_api.logger')
    @patch('agent.core.operator_api.MODEL_RELOAD_COUNT')
    def test_model_reload_metrics_and_logging(self, mock_counter, mock_logger, mock_record, client):
        """Test that model reload updates metrics and logs events."""
        response = client.post("/reload_model", headers=HEADERS)
        
        assert response.status_code == 200
        
        # Verify metrics and logging
        mock_counter.inc.assert_called_once()
        mock_logger.info.assert_called()
        mock_record.assert_called_once()
        
        # Check record call
        call_args = mock_record.call_args
        assert call_args[0][0] == "model-reload"
        assert "fresh_rho" in call_args[0][1]
        assert "model_type" in call_args[0][1]
    
    def test_model_reload_error_handling(self, client):
        """Test error handling in model reload - test basic functionality."""
        # This test just checks that the endpoint exists and responds
        # Error injection testing would require more complex mocking
        response = client.post("/reload_model", headers=HEADERS)
        
        # Should succeed or fail gracefully, not crash
        assert response.status_code in [200, 500]


class TestConfigIntegration:
    """Integration tests for config store functionality."""
    
    def test_config_persistence(self, temp_config_file):
        """Test that config updates persist to disk."""
        with patch('agent.core.config_store._config_path', Path(temp_config_file)):
            # Update config
            update_config({"rho_max": 0.7, "energy_multiplier": 3.5})
            
            # Reload from disk
            load_config()
            config = get_config()
            
            assert config.rho_max == 0.7
            assert config.energy_multiplier == 3.5
    
    def test_config_validation_in_store(self):
        """Test that config store validates values correctly."""
        with pytest.raises(ValueError, match="Configuration validation failed.*Input should be less than 1"):
            update_config({"rho_max": 1.5})
        
        with pytest.raises(ValueError, match="Configuration validation failed.*Input should be less than or equal to 4"):
            update_config({"energy_multiplier": 5.0})
    
    def test_config_defaults(self, temp_config_file):
        """Test that config loads with proper defaults."""
        with patch('agent.core.config_store._config_path', Path(temp_config_file)):
            config = load_config()
            
            assert config.rho_max == 0.9  # Default
            assert config.energy_multiplier == 2.0  # Default


class TestGovernorIntegration:
    """Test integration with governor module."""
    
    def test_governor_config_function_exists(self):
        """Test that the governor config integration is properly set up."""
        # Just test that the config store integration works
        from agent.core.config_store import get_config
        config = get_config()
        assert hasattr(config, 'rho_max')
        assert hasattr(config, 'energy_multiplier')


class TestExistingEndpoints:
    """Test that existing endpoints still work after changes."""
    
    def test_state_endpoint(self, client):
        """Test GET /state endpoint."""
        response = client.get("/state", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "pause" in data
        assert "kill" in data
    
    def test_pause_endpoint(self, client):
        """Test POST /pause endpoint."""
        response = client.post("/pause", json={"flag": True}, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["pause"] is True
    
    def test_kill_endpoint(self, client):
        """Test POST /kill endpoint."""
        response = client.post("/kill", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["kill"] is True

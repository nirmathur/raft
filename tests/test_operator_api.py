import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import requests
import yaml

TOKEN = os.getenv(
    "OPERATOR_TOKEN", "devtoken"
)  # matches the default in operator_api.py
HEAD = {"authorization": f"Bearer {TOKEN}"}
INVALID_HEAD = {"authorization": "Bearer invalid_token"}


def _start_server():
    proc = subprocess.Popen(
        ["uvicorn", "agent.core.operator_api:app", "--port", "8100"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return proc


def test_pause_endpoint():
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        r = requests.post(url + "/pause", json={"flag": True}, headers=HEAD, timeout=2)
        assert r.json()["pause"] is True
        r = requests.get(url + "/state", headers=HEAD, timeout=2)
        assert r.json()["pause"] is True
    finally:
        proc.send_signal(signal.SIGINT)


def test_config_endpoint_success():
    """Test successful configuration updates."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Test updating both parameters
        config_data = {"rho_max": 0.8, "energy_multiplier": 3.0}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 200
        response = r.json()
        assert response["ok"] is True
        assert response["config"]["rho_max"] == 0.8
        assert response["config"]["energy_multiplier"] == 3.0
        
        # Test updating only rho_max
        config_data = {"rho_max": 0.7}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 200
        response = r.json()
        assert response["config"]["rho_max"] == 0.7
        assert response["config"]["energy_multiplier"] == 3.0  # unchanged
        
        # Test updating only energy_multiplier
        config_data = {"energy_multiplier": 2.5}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 200
        response = r.json()
        assert response["config"]["rho_max"] == 0.7  # unchanged
        assert response["config"]["energy_multiplier"] == 2.5
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_config_endpoint_validation_errors():
    """Test configuration validation errors."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Test invalid rho_max (too high)
        config_data = {"rho_max": 1.5}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 400
        assert "rho_max must be in (0, 1]" in r.json()["detail"]
        
        # Test invalid rho_max (zero)
        config_data = {"rho_max": 0.0}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 400
        
        # Test invalid energy_multiplier (negative)
        config_data = {"energy_multiplier": -1.0}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 400
        assert "energy_multiplier must be positive" in r.json()["detail"]
        
        # Test invalid energy_multiplier (zero)
        config_data = {"energy_multiplier": 0.0}
        r = requests.post(url + "/config", json=config_data, headers=HEAD, timeout=2)
        assert r.status_code == 400
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_config_endpoint_auth_failure():
    """Test configuration endpoint authentication failure."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Test with invalid token
        config_data = {"rho_max": 0.8}
        r = requests.post(url + "/config", json=config_data, headers=INVALID_HEAD, timeout=2)
        assert r.status_code == 401
        
        # Test with no authorization header
        r = requests.post(url + "/config", json=config_data, timeout=2)
        assert r.status_code == 401
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_reload_model_endpoint_success():
    """Test successful model reload."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Create temporary model file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.model', delete=False) as f:
            f.write("fake model weights data")
            model_path = f.name
        
        try:
            # Set MODEL_PATH environment variable for the test
            original_model_path = os.environ.get("MODEL_PATH")
            os.environ["MODEL_PATH"] = model_path
            
            r = requests.post(url + "/reload_model", headers=HEAD, timeout=2)
            assert r.status_code == 200
            response = r.json()
            assert response["ok"] is True
            assert response["reloaded"] is True
            
        finally:
            # Cleanup
            Path(model_path).unlink()
            if original_model_path is not None:
                os.environ["MODEL_PATH"] = original_model_path
            elif "MODEL_PATH" in os.environ:
                del os.environ["MODEL_PATH"]
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_reload_model_endpoint_failure():
    """Test model reload failure cases."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Test with no MODEL_PATH set
        original_model_path = os.environ.get("MODEL_PATH")
        if "MODEL_PATH" in os.environ:
            del os.environ["MODEL_PATH"]
        
        try:
            r = requests.post(url + "/reload_model", headers=HEAD, timeout=2)
            assert r.status_code == 500
            assert "Model reload failed" in r.json()["detail"]
        finally:
            # Restore original MODEL_PATH
            if original_model_path is not None:
                os.environ["MODEL_PATH"] = original_model_path
        
        # Test with non-existent model file
        os.environ["MODEL_PATH"] = "/nonexistent/model/path"
        try:
            r = requests.post(url + "/reload_model", headers=HEAD, timeout=2)
            assert r.status_code == 500
        finally:
            del os.environ["MODEL_PATH"]
            if original_model_path is not None:
                os.environ["MODEL_PATH"] = original_model_path
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_reload_model_endpoint_auth_failure():
    """Test model reload endpoint authentication failure."""
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        
        # Test with invalid token
        r = requests.post(url + "/reload_model", headers=INVALID_HEAD, timeout=2)
        assert r.status_code == 401
        
        # Test with no authorization header
        r = requests.post(url + "/reload_model", timeout=2)
        assert r.status_code == 401
        
    finally:
        proc.send_signal(signal.SIGINT)


def test_config_persistence():
    """Test that configuration changes are persisted to config.yaml."""
    from agent.core.config import get_config, load_config, update_config
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config_path = f.name
    
    try:
        # Test initial load (file doesn't exist yet)
        config = load_config(config_path)
        assert config.rho_max == 0.9  # default
        assert config.energy_multiplier == 2.0  # default
        
        # Update configuration
        updated_config = update_config(rho_max=0.75, energy_multiplier=2.5)
        assert updated_config.rho_max == 0.75
        assert updated_config.energy_multiplier == 2.5
        
        # Check that config was persisted
        assert Path(config_path).exists()
        with open(config_path, 'r') as f:
            persisted_data = yaml.safe_load(f)
        assert persisted_data["rho_max"] == 0.75
        assert persisted_data["energy_multiplier"] == 2.5
        
        # Load from file and verify
        reloaded_config = load_config(config_path)
        assert reloaded_config.rho_max == 0.75
        assert reloaded_config.energy_multiplier == 2.5
        
    finally:
        # Cleanup
        if Path(config_path).exists():
            Path(config_path).unlink()

"""
Dynamic Configuration Management for RAFT
==========================================

Provides runtime configuration management with persistence to config.yaml.
Supports dynamic updates to spectral radius threshold (rho_max) and energy multiplier.
"""

import os
import threading
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import BaseModel


class RaftConfig(BaseModel):
    """RAFT runtime configuration."""
    rho_max: float = 0.9  # Maximum spectral radius (from charter xˣ‑17)
    energy_multiplier: float = 2.0  # APOPTOSIS_MULTIPLIER from energy guard


# Global configuration state with thread-safe access
_config_lock = threading.RLock()
_current_config: RaftConfig = RaftConfig()


def get_config() -> RaftConfig:
    """Get current configuration (thread-safe)."""
    with _config_lock:
        return _current_config.model_copy()


def update_config(rho_max: Optional[float] = None, energy_multiplier: Optional[float] = None) -> RaftConfig:
    """
    Update configuration parameters (thread-safe).
    
    Parameters
    ----------
    rho_max : float, optional
        New maximum spectral radius threshold.
    energy_multiplier : float, optional  
        New energy multiplier for apoptosis protection.
        
    Returns
    -------
    RaftConfig
        Updated configuration.
    """
    global _current_config
    
    with _config_lock:
        # Create updated config
        updates = {}
        if rho_max is not None:
            if not (0.0 < rho_max <= 1.0):
                raise ValueError(f"rho_max must be in (0, 1], got {rho_max}")
            updates["rho_max"] = rho_max
            
        if energy_multiplier is not None:
            if energy_multiplier <= 0:
                raise ValueError(f"energy_multiplier must be positive, got {energy_multiplier}")
            updates["energy_multiplier"] = energy_multiplier
            
        if updates:
            _current_config = _current_config.model_copy(update=updates)
            _persist_config()
            logger.info("Config updated: {}", updates)
            
        return _current_config.model_copy()


def load_config(config_path: str = "config.yaml") -> RaftConfig:
    """
    Load configuration from YAML file.
    
    Parameters
    ----------
    config_path : str
        Path to configuration file.
        
    Returns
    -------
    RaftConfig
        Loaded configuration.
    """
    global _current_config
    
    config_file = Path(config_path)
    
    with _config_lock:
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                _current_config = RaftConfig(**data)
                logger.info("Config loaded from {}: {}", config_path, _current_config.model_dump())
            except Exception as e:
                logger.warning("Failed to load config from {}: {}. Using defaults.", config_path, e)
                _current_config = RaftConfig()
        else:
            logger.info("Config file {} not found. Using defaults.", config_path)
            _current_config = RaftConfig()
            
        return _current_config.model_copy()


def _persist_config(config_path: str = "config.yaml") -> None:
    """Persist current configuration to YAML file."""
    try:
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, "w") as f:
            yaml.safe_dump(_current_config.model_dump(), f, default_flow_style=False)
        logger.debug("Config persisted to {}", config_path)
    except Exception as e:
        logger.error("Failed to persist config to {}: {}", config_path, e)


def reload_model_weights(model_path: Optional[str] = None) -> bool:
    """
    Reload model weights from disk.
    
    Parameters
    ----------
    model_path : str, optional
        Path to model weights. If None, uses MODEL_PATH environment variable.
        
    Returns
    -------
    bool
        True if reload successful, False otherwise.
    """
    if model_path is None:
        model_path = os.getenv("MODEL_PATH")
        
    if not model_path:
        logger.error("No MODEL_PATH specified for model reload")
        return False
        
    model_file = Path(model_path)
    if not model_file.exists():
        logger.error("Model file not found: {}", model_path)
        return False
        
    try:
        # In a real implementation, this would reload actual model weights
        # For now, we simulate the operation
        logger.info("Reloading model weights from: {}", model_path)
        
        # Simulate model loading delay
        import time
        time.sleep(0.1)
        
        logger.info("Model weights reloaded successfully")
        return True
        
    except Exception as e:
        logger.error("Failed to reload model weights from {}: {}", model_path, e)
        return False


# Initialize configuration on module import
load_config()
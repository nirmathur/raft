"""
Configuration Store for RAFT
=============================

Provides dynamic configuration management with hot-reloading and YAML persistence.
Supports atomic writes to prevent corruption during updates.
"""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any, Dict

import yaml
from loguru import logger
from pydantic import BaseModel, Field, ValidationError


class ConfigValidator(BaseModel):
    """Pydantic model for config validation - single source of truth."""

    rho_max: Annotated[
        float, Field(gt=0, lt=1, description="Spectral radius threshold")
    ]
    energy_multiplier: Annotated[
        float, Field(ge=1, le=4, description="Energy consumption multiplier")
    ]


@dataclass
class Config:
    """RAFT Runtime Configuration.

    All fields support hot-reloading without service restart.
    Values are validated on update to ensure system stability.
    """

    rho_max: float = 0.9
    energy_multiplier: float = 2.0

    def validate(self) -> None:
        """Validate configuration values using Pydantic.

        Raises
        ------
        ValueError
            If any configuration value is invalid
        """
        try:
            ConfigValidator(
                rho_max=self.rho_max, energy_multiplier=self.energy_multiplier
            )
        except ValidationError as e:
            # Convert Pydantic validation error to simpler ValueError
            error_details = "; ".join(
                [
                    f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
                    for err in e.errors()
                ]
            )
            raise ValueError(f"Configuration validation failed: {error_details}")


# Global singleton config instance
_config = Config()
_config_path = Path(os.getenv("RAFT_CONFIG_PATH", "config.yaml"))
_config_lock = threading.Lock()


def get_config() -> Config:
    """Get the current configuration.

    Returns
    -------
    Config
        Current configuration instance
    """
    return _config


def update_config(updates: Dict[str, Any]) -> Config:
    """Update configuration with validation and persistence.

    Thread-safe: Uses a lock to prevent race conditions during concurrent updates.

    Parameters
    ----------
    updates : dict
        Configuration updates to apply

    Returns
    -------
    Config
        Updated configuration instance

    Raises
    ------
    ValueError
        If validation fails
    """
    global _config

    with _config_lock:
        # Create new config with updates
        new_values = asdict(_config)
        new_values.update(updates)
        new_config = Config(**new_values)

        # Validate before applying
        new_config.validate()

        # Apply updates atomically
        _config = new_config

        # Persist to disk
        _save_config()

        logger.info(f"Configuration updated: {updates}")
        return _config


def load_config() -> Config:
    """Load configuration from YAML file.

    If file doesn't exist, creates it with defaults.

    Returns
    -------
    Config
        Loaded configuration
    """
    global _config

    if _config_path.exists():
        try:
            with open(_config_path, "r") as f:
                data = yaml.safe_load(f) or {}
            _config = Config(**data)
            _config.validate()
            logger.info(f"Configuration loaded from {_config_path}")
        except Exception as e:
            logger.warning(
                f"Failed to load config from {_config_path}: {e}, using defaults"
            )
            _config = Config()
            _save_config()  # Save defaults
    else:
        # Create default config file
        _config = Config()
        _save_config()
        logger.info(f"Created default configuration at {_config_path}")

    return _config


def _save_config() -> None:
    """Save current configuration to YAML file atomically.

    Uses temporary file + rename for atomic writes to prevent corruption.
    """
    try:
        # Write to temporary file in same directory
        config_dir = _config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        # Use mkstemp for better Windows compatibility (closes file handle properly)
        fd, temp_path = tempfile.mkstemp(
            dir=config_dir, prefix=".config_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                yaml.safe_dump(asdict(_config), f, default_flow_style=False)

            # Atomic rename (cross-platform: handles Windows + existing target)
            os.replace(temp_path, _config_path)
        except:
            # Clean up temp file if writing failed
            try:
                os.unlink(temp_path)
            except:
                pass
            raise
        logger.debug(f"Configuration saved to {_config_path}")

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise


# Initialize config on module import
load_config()

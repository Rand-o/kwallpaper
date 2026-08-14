#!/usr/bin/env python3
"""
kWallpaper configuration management.

Paths, config load/save/validate, and directory bootstrap.

``ensure_config_dirs()`` is idempotent and cheap: it only does filesystem
work once per process (guarded by a module-level flag), so it can be called
from any startup path without paying the cost of mkdir + default-config
creation on every ``load_config()`` call.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Use Flatpak-specific directories for self-contained storage
# This ensures the app works consistently across all environments
DEFAULT_CONFIG_DIR = Path.home() / ".var" / "app" / "top.spelunk.kwallpaper" / "config" / "kwallpaper"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_CACHE_DIR = Path.home() / ".var" / "app" / "top.spelunk.kwallpaper" / "cache" / "kwallpaper"
DEFAULT_SCHEDULE_BACKUP_DIR = DEFAULT_CACHE_DIR / "schedule-backup"
DEFAULT_THEMES_DIR = DEFAULT_CONFIG_DIR / "themes"
DEFAULT_SHUFFLE_LIST_PATH = DEFAULT_CONFIG_DIR / "shuffle-list.json"


DEFAULT_CONFIG = {
    "interval": 5400,
    "retry_attempts": 3,
    "retry_delay": 5,
    "scheduling": {
        "interval": 60,
        "daily_shuffle_enabled": True,
        "auto_start_on_launch": False
    }
}


def create_default_config(config_path: str) -> Dict[str, Any]:
    """Create default configuration if it doesn't exist.

    Args:
        config_path: Path to config file

    Returns:
        Default configuration dictionary
    """
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        default_config = {
            "interval": 60,
            "retry_attempts": 3,
            "retry_delay": 2,
            "scheduling": {
                "interval": 60,
                "run_cycle": True,
                "daily_shuffle_enabled": True
            },
            "location": {
                "timezone": "America/Phoenix",
                "latitude": 33.4484,
                "longitude": -112.074
            },
            "theme": {
                "last_applied": ""
            },
            "application": {
                "theme_mode": "system"
            }
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2, sort_keys=True)

        # Create backup.json file
        create_backup_file()
        return default_config

    with open(config_path, 'r') as f:
        return json.load(f)


_dirs_ensured = False


def ensure_config_dirs(force: bool = False) -> None:
    """Create config directories and default config if they don't exist.

    Idempotent and cheap: the actual filesystem work happens at most once
    per process unless ``force=True`` is passed.
    """
    global _dirs_ensured
    if _dirs_ensured and not force:
        return
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_SCHEDULE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_THEMES_DIR.mkdir(parents=True, exist_ok=True)

    # Create default config if missing (also creates backup.json)
    create_default_config(str(DEFAULT_CONFIG_PATH))
    _dirs_ensured = True


def create_backup_file() -> None:
    """Create backup.json file if it doesn't exist."""
    backup_path = DEFAULT_SCHEDULE_BACKUP_DIR / "backup.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if not backup_path.exists():
        default_backup = {
            "last_schedule_state": {
                "last_theme_path": "",
                "last_change_date": "",
                "current_index": 0
            },
            "theme_history": []
        }
        with open(backup_path, 'w') as f:
            json.dump(default_backup, f, indent=2)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config JSON file

    Returns:
        Configuration dictionary

    Raises:
        ValueError: If config file contains invalid JSON
        FileNotFoundError: If config file does not exist
    """
    ensure_config_dirs()

    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

    # Validate config
    validate_config(config)

    return config


def save_config(config_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to JSON file.

    Args:
        config_path: Path to save config JSON file
        config: Configuration dictionary to save
    """
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, sort_keys=True)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If config is invalid
    """
    required_fields = ['interval', 'retry_attempts', 'retry_delay']

    for field in required_fields:
        if field not in config:
            raise ValueError(f"Config validation failed: Missing required field '{field}'")

    # Validate interval
    if not isinstance(config['interval'], int) or config['interval'] <= 0:
        raise ValueError("Config validation failed: 'interval' must be a positive integer")

    # Validate retry_attempts
    if not isinstance(config['retry_attempts'], int) or config['retry_attempts'] <= 0:
        raise ValueError("Config validation failed: 'retry_attempts' must be a positive integer")

    # Validate retry_delay
    if not isinstance(config['retry_delay'], int) or config['retry_delay'] <= 0:
        raise ValueError("Config validation failed: 'retry_delay' must be a positive integer")

    # Validate scheduling config if present
    if 'scheduling' in config:
        scheduling = config['scheduling']
        if not isinstance(scheduling, dict):
            raise ValueError("Config validation failed: 'scheduling' must be a dictionary")
        if 'interval' in scheduling:
            if not isinstance(scheduling['interval'], int) or scheduling['interval'] <= 0:
                raise ValueError("Config validation failed: 'scheduling.interval' must be a positive integer")
        if 'daily_change_time' in scheduling:
            if not isinstance(scheduling['daily_change_time'], str):
                raise ValueError("Config validation failed: 'scheduling.daily_change_time' must be a string")
        if 'run_cycle' in scheduling:
            if not isinstance(scheduling['run_cycle'], bool):
                raise ValueError("Config validation failed: 'scheduling.run_cycle' must be a boolean")
        if 'daily_shuffle_enabled' in scheduling:
            if not isinstance(scheduling['daily_shuffle_enabled'], bool):
                raise ValueError("Config validation failed: 'scheduling.daily_shuffle_enabled' must be a boolean")
        if 'auto_start_on_launch' in scheduling:
            if not isinstance(scheduling['auto_start_on_launch'], bool):
                raise ValueError("Config validation failed: 'scheduling.auto_start_on_launch' must be a boolean")

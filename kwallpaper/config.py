#!/usr/bin/env python3
"""
kWallpaper configuration management.

Paths, config load/save/validate, and directory bootstrap.

Config schema (v2)::

    {
      "version": 2,
      "appearance": { "theme_mode": "system" },
      "autostart": { "enabled": false, "start_scheduler_on_launch": true },
      "location": { "latitude": 33.4484, "longitude": -112.074,
                    "timezone": "America/Phoenix" },
      "scheduling": { "cycle_interval": 60, "run_cycle": true,
                      "daily_shuffle_enabled": true },
      "theme": { "last_applied": "" }
    }

Legacy v1 keys (top-level ``interval``/``retry_attempts``/``retry_delay``,
``scheduling.interval``, ``scheduling.auto_start_on_launch``,
``application.*``) are migrated in place on first load by
:meth:`normalize_config`.  ``load_config`` never mutates the file itself;
callers that save will persist the normalized form.

``ensure_config_dirs()`` is idempotent and cheap: it only does filesystem
work once per process (guarded by a module-level flag), so it can be called
from any startup path without paying the cost of mkdir + default-config
creation on every ``load_config()`` call.
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONFIG_VERSION = 2

# Use Flatpak-specific directories for self-contained storage
# This ensures the app works consistently across all environments
DEFAULT_CONFIG_DIR = Path.home() / ".var" / "app" / "top.spelunk.kwallpaper" / "config" / "kwallpaper"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_CACHE_DIR = Path.home() / ".var" / "app" / "top.spelunk.kwallpaper" / "cache" / "kwallpaper"
DEFAULT_SCHEDULE_BACKUP_DIR = DEFAULT_CACHE_DIR / "schedule-backup"
DEFAULT_THEMES_DIR = DEFAULT_CONFIG_DIR / "themes"
DEFAULT_SHUFFLE_LIST_PATH = DEFAULT_CONFIG_DIR / "shuffle-list.json"


def _default_config() -> Dict[str, Any]:
    """Return a fresh copy of the default configuration."""
    return copy.deepcopy({
        "version": CONFIG_VERSION,
        "appearance": {
            "theme_mode": "system",          # system | light | dark
        },
        "autostart": {
            "enabled": False,                # launch app at login
            "start_scheduler_on_launch": True,
        },
        "location": {
            "latitude": 33.4484,
            "longitude": -112.074,
            "timezone": "America/Phoenix",
        },
        "scheduling": {
            "cycle_interval": 60,            # seconds between cycle runs
            "run_cycle": True,
            "daily_shuffle_enabled": True,
            "safety_interval": 600,          # sun-mode safety-net tick (seconds)
            "suntime_model": "legacy",       # legacy | sun
        },
        "theme": {
            "last_applied": "",
            "last_applied_image": "",        # path of last successfully applied image
        },
    })


#: Default configuration (v2 schema).  Do not mutate; use ``_default_config()``.
DEFAULT_CONFIG = _default_config()


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a config dict to the v2 schema (in place) and return it.

    Handles:
    - legacy top-level ``interval`` / ``retry_attempts`` / ``retry_delay``
      (removed; ``scheduling.interval`` is the live cycle interval),
    - legacy ``scheduling.interval`` -> ``scheduling.cycle_interval``,
    - legacy ``scheduling.auto_start_on_launch`` ->
      ``autostart.start_scheduler_on_launch``,
    - legacy ``application.theme_mode`` / ``application.autostart`` ->
      ``appearance.theme_mode`` / ``autostart.enabled``,
    - missing sections/keys are filled in from the defaults.
    """
    defaults = _default_config()

    # ── legacy field migration ─────────────────────────────────────────
    old_scheduling = config.get("scheduling")
    if isinstance(old_scheduling, dict):
        if "cycle_interval" not in old_scheduling and "interval" in old_scheduling:
            old_scheduling["cycle_interval"] = old_scheduling.pop("interval")
        if "auto_start_on_launch" in old_scheduling:
            autostart = config.setdefault("autostart", {})
            if not isinstance(autostart, dict):
                autostart = config["autostart"] = {}
            autostart.setdefault("start_scheduler_on_launch",
                                 old_scheduling.pop("auto_start_on_launch"))

    old_application = config.get("application")
    if isinstance(old_application, dict):
        appearance = config.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = config["appearance"] = {}
        if "theme_mode" in old_application:
            appearance.setdefault("theme_mode", old_application.pop("theme_mode"))
        if "autostart" in old_application:
            autostart = config.setdefault("autostart", {})
            if not isinstance(autostart, dict):
                autostart = config["autostart"] = {}
            autostart.setdefault("enabled", old_application.pop("autostart"))

    # Drop removed legacy top-level keys (and any now-empty legacy section).
    for legacy_key in ("interval", "retry_attempts", "retry_delay"):
        config.pop(legacy_key, None)
    if isinstance(old_application, dict) and not old_application:
        config.pop("application", None)

    # ── fill in any missing sections/keys from defaults ────────────────
    for section, values in defaults.items():
        if section not in config or not isinstance(config[section], dict):
            config[section] = copy.deepcopy(values)
            continue
        for key, value in values.items():
            config[section].setdefault(key, copy.deepcopy(value))

    config["version"] = CONFIG_VERSION
    return config


def create_default_config(config_path: str) -> Dict[str, Any]:
    """Create default configuration if it doesn't exist.

    Args:
        config_path: Path to config file

    Returns:
        The configuration dictionary (existing contents if the file
        already exists, defaults otherwise).
    """
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        default_config = _default_config()
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

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

    The returned dict is normalized to the v2 schema (legacy keys
    migrated, missing keys filled in from defaults).  The file on disk
    is left untouched; save it with :func:`save_config` to persist the
    normalized form.

    Args:
        config_path: Path to config JSON file

    Returns:
        Normalized configuration dictionary

    Raises:
        ValueError: If config file contains invalid JSON or is invalid
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

    if not isinstance(config, dict):
        raise ValueError("Config validation failed: top-level value must be an object")

    # Validate, then migrate to the current schema.
    validate_config(config)
    return normalize_config(config)


def save_config(config_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to JSON file.

    The config is normalized to the v2 schema before writing, so saves
    always produce a clean, current-format file.

    Args:
        config_path: Path to save config JSON file
        config: Configuration dictionary to save
    """
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    config = normalize_config(config)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def _require_positive_int(config: Dict[str, Any], dotted: str) -> None:
    section_name, _, key = dotted.partition(".")
    section = config.get(section_name)
    if not isinstance(section, dict) or key not in section:
        return
    value = section[key]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            f"Config validation failed: '{dotted}' must be a positive integer")


def _require_bool(config: Dict[str, Any], dotted: str) -> None:
    section_name, _, key = dotted.partition(".")
    section = config.get(section_name)
    if not isinstance(section, dict) or key not in section:
        return
    if not isinstance(section[key], bool):
        raise ValueError(
            f"Config validation failed: '{dotted}' must be a boolean")


def _require_str(config: Dict[str, Any], dotted: str) -> None:
    section_name, _, key = dotted.partition(".")
    section = config.get(section_name)
    if not isinstance(section, dict) or key not in section:
        return
    if not isinstance(section[key], str):
        raise ValueError(
            f"Config validation failed: '{dotted}' must be a string")


def _require_number(config: Dict[str, Any], dotted: str) -> None:
    section_name, _, key = dotted.partition(".")
    section = config.get(section_name)
    if not isinstance(section, dict) or key not in section:
        return
    value = section[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"Config validation failed: '{dotted}' must be a number")


def _require_suntime_model(config: Dict[str, Any]) -> None:
    section = config.get("scheduling")
    if not isinstance(section, dict) or "suntime_model" not in section:
        return
    if section["suntime_model"] not in ("legacy", "sun"):
        raise ValueError(
            "Config validation failed: 'scheduling.suntime_model' must be "
            "'legacy' or 'sun'")


def validate_config(config: Dict[str, Any]) -> None:
    """Validate a configuration dictionary (v2 schema; legacy keys ok).

    All sections are optional — missing values fall back to defaults in
    :func:`normalize_config`.  Present values must have the right type.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(config, dict):
        raise ValueError("Config validation failed: config must be a dictionary")

    # appearance
    if "appearance" in config and not isinstance(config["appearance"], dict):
        raise ValueError("Config validation failed: 'appearance' must be a dictionary")
    _require_str(config, "appearance.theme_mode")

    # autostart
    if "autostart" in config and not isinstance(config["autostart"], dict):
        raise ValueError("Config validation failed: 'autostart' must be a dictionary")
    _require_bool(config, "autostart.enabled")
    _require_bool(config, "autostart.start_scheduler_on_launch")

    # location
    if "location" in config and not isinstance(config["location"], dict):
        raise ValueError("Config validation failed: 'location' must be a dictionary")
    _require_number(config, "location.latitude")
    _require_number(config, "location.longitude")
    _require_str(config, "location.timezone")

    # scheduling
    if "scheduling" in config and not isinstance(config["scheduling"], dict):
        raise ValueError("Config validation failed: 'scheduling' must be a dictionary")
    _require_positive_int(config, "scheduling.cycle_interval")
    # legacy alias, validated for backward compatibility
    _require_positive_int(config, "scheduling.interval")
    _require_positive_int(config, "scheduling.safety_interval")
    _require_bool(config, "scheduling.run_cycle")
    _require_bool(config, "scheduling.daily_shuffle_enabled")
    _require_str(config, "scheduling.daily_change_time")
    # legacy alias
    _require_bool(config, "scheduling.auto_start_on_launch")
    _require_suntime_model(config)

    # theme
    if "theme" in config and not isinstance(config["theme"], dict):
        raise ValueError("Config validation failed: 'theme' must be a dictionary")
    _require_str(config, "theme.last_applied")
    _require_str(config, "theme.last_applied_image")

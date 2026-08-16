import pytest
import tempfile
import os
import json
from pathlib import Path
from kwallpaper import wallpaper_changer
load_config = wallpaper_changer.load_config
validate_config = wallpaper_changer.validate_config
save_config = wallpaper_changer.save_config
normalize_config = wallpaper_changer.normalize_config


def test_validate_config_valid():
    config = {
        "version": 2,
        "appearance": {"theme_mode": "light"},
        "autostart": {"enabled": True, "start_scheduler_on_launch": False},
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True},
        "theme": {"last_applied": "24hr-Bristlecone"},
    }
    validate_config(config)


@pytest.mark.parametrize("dotted,value", [
    ("scheduling.cycle_interval", 0),
    ("scheduling.cycle_interval", -1),
])
def test_validate_config_invalid_positive_fields(dotted, value):
    section, key = dotted.split(".")
    config = {section: {key: value}}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


@pytest.mark.parametrize("dotted,value", [
    ("scheduling.run_cycle", "yes"),
    ("autostart.enabled", 1),
    ("appearance.theme_mode", 42),
    ("location.latitude", "north"),
])
def test_validate_config_invalid_types(dotted, value):
    section, key = dotted.split(".")
    config = {section: {key: value}}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_validate_config_empty_ok():
    # All sections are optional; missing values fall back to defaults.
    validate_config({})


def test_load_config_with_validation():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"scheduling": {"cycle_interval": 60}}, f)
        temp_path = f.name
    try:
        config = load_config(temp_path)
        assert config["scheduling"]["cycle_interval"] == 60
    finally:
        os.unlink(temp_path)


def test_save_config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    try:
        config = {"scheduling": {"cycle_interval": 120, "run_cycle": False}}
        save_config(temp_path, config)
        loaded = load_config(temp_path)
        assert loaded["scheduling"]["cycle_interval"] == 120
        assert loaded["scheduling"]["run_cycle"] is False
        assert loaded["version"] == 2
    finally:
        os.unlink(temp_path)


class TestNormalizeLegacy:
    """Legacy v1 configs must migrate to the v2 schema on load."""

    LEGACY = {
        "application": {"autostart": True, "theme_mode": "dark"},
        "interval": 60,
        "location": {"latitude": 33.4484, "longitude": -112.074,
                     "timezone": "America/Phoenix"},
        "retry_attempts": 3,
        "retry_delay": 2,
        "scheduling": {
            "auto_start_on_launch": True,
            "daily_shuffle_enabled": True,
            "interval": 60,
            "run_cycle": True,
        },
        "theme": {"last_applied": "24hr-Bristlecone"},
    }

    def test_legacy_migrates(self):
        config = normalize_config(json.loads(json.dumps(self.LEGACY)))
        assert config["version"] == 2
        # removed legacy keys
        assert "interval" not in config
        assert "retry_attempts" not in config
        assert "retry_delay" not in config
        assert "application" not in config or \
            not ("interval" in config.get("scheduling", {}))
        # scheduling.interval -> scheduling.cycle_interval
        assert config["scheduling"]["cycle_interval"] == 60
        assert "interval" not in config["scheduling"]
        # scheduling.auto_start_on_launch -> autostart.start_scheduler_on_launch
        assert "auto_start_on_launch" not in config["scheduling"]
        assert config["autostart"]["start_scheduler_on_launch"] is True
        # application.* -> appearance/autostart
        assert config["appearance"]["theme_mode"] == "dark"
        assert config["autostart"]["enabled"] is True
        # untouched values preserved
        assert config["theme"]["last_applied"] == "24hr-Bristlecone"
        assert config["location"]["timezone"] == "America/Phoenix"

    def test_legacy_loads_through_load_config(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps(self.LEGACY))
        config = load_config(str(p))
        assert config["scheduling"]["cycle_interval"] == 60
        assert config["autostart"]["start_scheduler_on_launch"] is True
        assert config["appearance"]["theme_mode"] == "dark"

    def test_legacy_save_persists_normalized(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps(self.LEGACY))
        config = load_config(str(p))
        save_config(str(p), config)
        on_disk = json.loads(p.read_text())
        assert "retry_attempts" not in on_disk
        assert on_disk["scheduling"]["cycle_interval"] == 60
        assert "interval" not in on_disk["scheduling"]
        assert on_disk["autostart"]["start_scheduler_on_launch"] is True

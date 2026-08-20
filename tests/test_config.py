import pytest
import tempfile
import json
import os
from kwallpaper import wallpaper_changer


def test_load_config_valid():
    load_config = wallpaper_changer.load_config

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "version": 2,
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": True},
        }, f)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert isinstance(config, dict)
        assert config["scheduling"]["cycle_interval"] == 60
        # normalization fills in missing sections from defaults
        assert config["location"]["timezone"]
        assert config["appearance"]["theme_mode"] == "system"
    finally:
        os.unlink(temp_path)


def test_load_config_invalid_json():
    import tempfile
    from kwallpaper import wallpaper_changer
    load_config = wallpaper_changer.load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        invalid_path = f.name

    with pytest.raises(ValueError, match="Invalid JSON in config file"):
        load_config(invalid_path)


def test_load_config_file_not_found():
    from kwallpaper import wallpaper_changer
    load_config = wallpaper_changer.load_config

    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.json")


# ── Phase 4: default suntime_model flip ─────────────────────────────────────
from kwallpaper.config import _default_config, load_config


def test_default_config_suntime_model_is_sun():
    """Phase 4: the canonical default is the sun-position model."""
    assert _default_config()["scheduling"]["suntime_model"] == "sun"


def test_load_config_absent_suntime_model_defaults_to_sun(tmp_path):
    """A config without the field (all pre-Phase-2 configs) picks up the
    new default at load time — this is the whole migration."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "location": {"timezone": "UTC", "latitude": 0.0, "longitude": 0.0},
        "scheduling": {"cycle_interval": 60},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "sun"


def test_load_config_explicit_legacy_preserved(tmp_path):
    """A user who explicitly chose the legacy model keeps it — the default
    flip must never overwrite an existing value."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "scheduling": {"suntime_model": "legacy"},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "legacy"


def test_load_config_explicit_sun_preserved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "scheduling": {"suntime_model": "sun"},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "sun"

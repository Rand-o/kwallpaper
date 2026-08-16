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

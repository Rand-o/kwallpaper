import pytest
import tempfile
import json
import os
from kwallpaper import wallpaper_changer


def test_load_config_valid():
    load_config = wallpaper_changer.load_config

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            "current_image_index": 0,
            "current_time_of_day": "day"
        }, f)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert isinstance(config, dict)
        assert "interval" in config
        assert "retry_attempts" in config
        assert "retry_delay" in config
        assert "current_image_index" in config
        assert "current_time_of_day" in config
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

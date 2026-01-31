import pytest
import tempfile
import os
import json
from pathlib import Path
from kwallpaper import wallpaper_changer
load_config = wallpaper_changer.load_config
validate_config = wallpaper_changer.validate_config
save_config = wallpaper_changer.save_config


def test_validate_config_valid():
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5, "current_image_index": 0, "current_time_of_day": "day"}
    validate_config(config)


@pytest.mark.parametrize("field,value", [("interval", 0), ("interval", -1), ("retry_attempts", 0), ("retry_delay", 0)])
def test_validate_config_invalid_positive_fields(field, value):
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5, "current_image_index": 0, "current_time_of_day": "day"}
    config[field] = value
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_validate_config_missing_field():
    config = {"interval": 100}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_validate_config_invalid_time_of_day():
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5, "current_image_index": 0, "current_time_of_day": "invalid"}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


@pytest.mark.parametrize("value", [-1, 1.5])
def test_validate_config_current_image_index_invalid(value):
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5, "current_image_index": value, "current_time_of_day": "day"}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_load_config_with_validation():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"interval": 5400, "retry_attempts": 3, "retry_delay": 5, "current_image_index": 0, "current_time_of_day": "day"}, f)
        temp_path = f.name
    try:
        assert load_config(temp_path) == {"interval": 5400, "retry_attempts": 3, "retry_delay": 5, "current_image_index": 0, "current_time_of_day": "day"}
    finally:
        os.unlink(temp_path)


def test_save_config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    try:
        config = {"interval": 100, "retry_attempts": 2, "retry_delay": 10, "current_image_index": 1, "current_time_of_day": "night"}
        save_config(temp_path, config)
        assert load_config(temp_path) == config
    finally:
        os.unlink(temp_path)

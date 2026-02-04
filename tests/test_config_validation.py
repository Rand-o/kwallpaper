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
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5}
    validate_config(config)

@pytest.mark.parametrize("field,value", [("interval", 0), ("interval", -1), ("retry_attempts", 0), ("retry_delay", 0)])
def test_validate_config_invalid_positive_fields(field, value):
    config = {"interval": 100, "retry_attempts": 3, "retry_delay": 5}
    config[field] = value
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_validate_config_missing_field():
    config = {"interval": 100}
    with pytest.raises(ValueError, match="Config validation failed"):
        validate_config(config)


def test_load_config_with_validation():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"interval": 5400, "retry_attempts": 3, "retry_delay": 5}, f)
        temp_path = f.name
    try:
        assert load_config(temp_path) == {"interval": 5400, "retry_attempts": 3, "retry_delay": 5}
    finally:
        os.unlink(temp_path)


def test_save_config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    try:
        config = {"interval": 100, "retry_attempts": 2, "retry_delay": 10}
        save_config(temp_path, config)
        assert load_config(temp_path) == config
    finally:
        os.unlink(temp_path)


def test_save_config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    try:
        config = {"interval": 100, "retry_attempts": 2, "retry_delay": 10}
        save_config(temp_path, config)
        assert load_config(temp_path) == config
    finally:
        os.unlink(temp_path)

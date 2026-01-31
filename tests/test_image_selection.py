import pytest
import tempfile
import os
import json
from pathlib import Path
from kwallpaper import wallpaper_changer
import sys
from pathlib import Path as TestPath

# Add parent directory to path for imports
sys.path.insert(0, str(TestPath(__file__).parent.parent))
select_next_image = wallpaper_changer.select_next_image
load_config = wallpaper_changer.load_config
save_config = wallpaper_changer.save_config


def test_select_next_image_cycles_through_list(tmp_path):
    """Test that selecting next image increments index and cycles."""
    # Create config file
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 0,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    # Create theme.json with 5 images
    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [1, 2, 3, 4, 5],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    # Create image files
    for i in range(1, 6):
        (tmp_path / f"test_{i}.jpg").touch()

    # Select next image (index 0 means test_1 is current, so next is test_2)
    result1 = select_next_image(str(tmp_path), str(config_path))
    assert result1 == str(tmp_path / "test_2.jpg")

    # Load config to verify index updated (now points to test_2)
    config = load_config(str(config_path))
    assert config['current_image_index'] == 1

    # Select next image (index 1 means test_2 is current, so next is test_3)
    result2 = select_next_image(str(tmp_path), str(config_path))
    assert result2 == str(tmp_path / "test_3.jpg")

    config = load_config(str(config_path))
    assert config['current_image_index'] == 2

    # Select next image (index 2 means test_3 is current, so next is test_4)
    result3 = select_next_image(str(tmp_path), str(config_path))
    assert result3 == str(tmp_path / "test_4.jpg")


def test_select_next_image_cycles_back_to_first(tmp_path):
    """Test that selecting wraps around to first image after last."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 4,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [1, 2, 3, 4, 5],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    for i in range(1, 6):
        (tmp_path / f"test_{i}.jpg").touch()

    # Start at index 4 (5th image is current)
    result = select_next_image(str(tmp_path), str(config_path))
    assert result == str(tmp_path / "test_1.jpg")  # Should wrap to first

    config = load_config(str(config_path))
    assert config['current_image_index'] == 0  # Reset to 0


def test_select_next_image_invalid_image_path(tmp_path):
    """Test that selecting invalid image path raises FileNotFoundError."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 0,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [1],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    # Create image file
    (tmp_path / "test_1.jpg").touch()

    # Select image (should work)
    result = select_next_image(str(tmp_path), str(config_path))
    assert result == str(tmp_path / "test_1.jpg")

    # Delete image to simulate missing file
    os.unlink(tmp_path / "test_1.jpg")

    # Next selection should raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="Image file not found"):
        select_next_image(str(tmp_path), str(config_path))


def test_select_next_image_switches_time_of_day(tmp_path):
    """Test that empty image list switches to next time-of-day category."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 0,
        "current_time_of_day": "sunrise"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [10, 11],
        "sunriseImageList": [],  # Empty
        "dayImageList": [1, 2],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    for i in [10, 11, 1, 2]:
        (tmp_path / f"test_{i}.jpg").touch()

    # Select with empty sunrise list - switches to next category in order: day
    # Index 0 means test_1 is current, so next is test_2
    result = select_next_image(str(tmp_path), str(config_path))
    assert result == str(tmp_path / "test_2.jpg")  # First image in day list

    config = load_config(str(config_path))
    assert config['current_image_index'] == 1  # Reset to 0 then incremented to 1
    assert config['current_time_of_day'] == 'day'


def test_select_next_image_all_empty_lists(tmp_path):
    """Test that all time-of-day lists empty raises ValueError."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 0,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    with pytest.raises(ValueError, match="No images available"):
        select_next_image(str(tmp_path), str(config_path))


def test_select_next_image_single_image(tmp_path):
    """Test that single image theme doesn't cycle (index stays 0)."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 0,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Single Image",
        "imageCredits": "Test",
        "imageFilename": "single.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [1],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    (tmp_path / "single.jpg").touch()

    # Select image multiple times
    for _ in range(5):
        result = select_next_image(str(tmp_path), str(config_path))
        assert result == str(tmp_path / "single.jpg")

    config = load_config(str(config_path))
    assert config['current_image_index'] == 0


def test_select_next_image_updates_config(tmp_path):
    """Test that select_next_image updates config file."""
    config_path = tmp_path / "config.json"
    config = {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "current_image_index": 2,
        "current_time_of_day": "day"
    }
    save_config(str(config_path), config)

    theme_json = tmp_path / "theme.json"
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [],
        "sunriseImageList": [],
        "dayImageList": [1, 2, 3, 4],
        "nightImageList": []
    }
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    for i in range(1, 5):
        (tmp_path / f"test_{i}.jpg").touch()

    # Select next image (index 2 -> test_4.jpg)
    result = select_next_image(str(tmp_path), str(config_path))
    assert result == str(tmp_path / "test_4.jpg")

    # Verify config updated
    config = load_config(str(config_path))
    assert config['current_image_index'] == 3
    assert config['current_time_of_day'] == 'day'

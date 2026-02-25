import pytest
import zipfile
import tempfile
import os
import json
from pathlib import Path
from kwallpaper import wallpaper_changer
extract_theme = wallpaper_changer.extract_theme


def test_extract_theme_valid_zip(tmp_path):
    """Test extracting theme from valid .ddw zip file."""
    # Create a temporary zip file with theme.json
    zip_path = tmp_path / "test.zip"
    theme_json = tmp_path / "theme.json"

    # Create theme.json content
    theme_data = {
        "displayName": "Test Theme",
        "imageCredits": "Test Credits",
        "imageFilename": "test_*.jpg",
        "sunsetImageList": [1, 2],
        "sunriseImageList": [3],
        "dayImageList": [4, 5],
        "nightImageList": [6]
    }

    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    # Create image files
    (tmp_path / "test_1.jpg").touch()
    (tmp_path / "test_2.jpg").touch()

    # Create zip file
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(theme_json, "theme.json")
        zf.write(tmp_path / "test_1.jpg", "test_1.jpg")
        zf.write(tmp_path / "test_2.jpg", "test_2.jpg")

    # Extract theme
    result = extract_theme(str(zip_path), cleanup=True)

    # Verify result
    assert result["displayName"] == "Test Theme"
    assert result["imageCredits"] == "Test Credits"
    assert result["imageFilename"] == "test_*.jpg"
    assert result["sunsetImageList"] == [1, 2]
    assert result["sunriseImageList"] == [3]
    assert result["dayImageList"] == [4, 5]
    assert result["nightImageList"] == [6]


def test_extract_theme_missing_theme_json(tmp_path):
    """Test that extracting .ddw without theme.json raises FileNotFoundError."""
    zip_path = tmp_path / "test.zip"

    # Create zip file without theme.json
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("test.jpg", "fake content")

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="theme.json not found"):
        extract_theme(str(zip_path))


def test_extract_theme_cleanup_removes_directory(tmp_path):
    """Test that cleanup=True removes the temp directory."""
    zip_path = tmp_path / "test.zip"
    theme_json = tmp_path / "theme.json"

    # Create theme.json
    theme_data = {"displayName": "Test", "imageCredits": "Test", "imageFilename": "test_*.jpg",
                  "sunsetImageList": [], "sunriseImageList": [], "dayImageList": [], "nightImageList": []}
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    # Create zip
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(theme_json, "theme.json")

    # Extract with cleanup
    extract_theme(str(zip_path), cleanup=True)

    # Verify temp directory removed
    extracted_dir = Path.home() / ".cache" / "wallpaper-changer" / "theme_"
    assert not extracted_dir.exists()


def test_extract_theme_cleanup_false_keeps_directory(tmp_path):
    """Test that cleanup=False keeps the temp directory."""
    zip_path = tmp_path / "test.zip"
    theme_json = tmp_path / "theme.json"

    # Create theme.json
    theme_data = {"displayName": "Test", "imageCredits": "Test", "imageFilename": "test_*.jpg",
                  "sunsetImageList": [], "sunriseImageList": [], "dayImageList": [], "nightImageList": []}
    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    # Create zip
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(theme_json, "theme.json")

    # Extract without cleanup
    extract_theme(str(zip_path), cleanup=False)

    # Verify temp directory still exists (using Path.home()/.cache/)
    # Verify temp directory still exists (using DEFAULT_CACHE_DIR)
    extracted_dir = wallpaper_changer.DEFAULT_CACHE_DIR


def test_extract_theme_includes_all_time_of_day_lists(tmp_path):
    """Test that all time-of-day image lists are returned."""
    zip_path = tmp_path / "test.zip"
    theme_json = tmp_path / "theme.json"

    theme_data = {
        "displayName": "Full Theme",
        "imageCredits": "Full Credits",
        "imageFilename": "full_*.png",
        "sunsetImageList": [10, 11],
        "sunriseImageList": [1, 2],
        "dayImageList": [5, 6, 7],
        "nightImageList": [15, 16]
    }

    with open(theme_json, 'w') as f:
        json.dump(theme_data, f)

    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(theme_json, "theme.json")

    result = extract_theme(str(zip_path), cleanup=True)

    assert set(result.keys()) == {
        "extract_dir", "displayName", "imageCredits", "imageFilename",
        "sunsetImageList", "sunriseImageList",
        "dayImageList", "nightImageList"
    }
    assert result["sunsetImageList"] == [10, 11]
    assert result["sunriseImageList"] == [1, 2]
    assert result["dayImageList"] == [5, 6, 7]
    assert result["nightImageList"] == [15, 16]

import pytest
from unittest.mock import MagicMock
from kwallpaper import wallpaper_changer
change_wallpaper = wallpaper_changer.change_wallpaper


def test_change_wallpaper_plasma_apply_fails(monkeypatch):
    """Test wallpaper change when gdbus fails (Plasma not running)."""
    mock_run = MagicMock()
    mock_run.return_value.stdout = ""
    mock_run.return_value.returncode = 1
    monkeypatch.setattr('subprocess.run', mock_run)

    result = change_wallpaper('/path/to/image.jpg')
    assert result is False


def test_change_wallpaper_verification_fails(monkeypatch):
    """Test wallpaper change when verification fails."""
    mock_run = MagicMock()
    mock_run.return_value.stdout = ""
    mock_run.return_value.returncode = 1
    monkeypatch.setattr('subprocess.run', mock_run)

    result = change_wallpaper('/path/to/image.jpg')
    assert result is False
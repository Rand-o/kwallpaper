import pytest
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError
from kwallpaper import wallpaper_changer
change_wallpaper = wallpaper_changer.change_wallpaper


def test_change_wallpaper_success(monkeypatch):
    """Test successful wallpaper change."""
    mock_run = MagicMock()
    monkeypatch.setattr('subprocess.run', mock_run)

    # Mock successful kwriteconfig5 and kreadconfig5
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='/path/to/image.jpg',
        stderr=''
    )

    result = change_wallpaper('/path/to/image.jpg')
    assert result is True
    assert mock_run.call_count == 3  # pgrep + kwriteconfig5 + kreadconfig5


def test_change_wallpaper_kwriteconfig5_fails(monkeypatch):
    """Test wallpaper change when kwriteconfig5 fails."""
    mock_run = MagicMock()
    monkeypatch.setattr('subprocess.run', mock_run)

    # Mock kwriteconfig5 failure
    mock_run.side_effect = CalledProcessError(1, 'kwriteconfig5')

    result = change_wallpaper('/path/to/image.jpg')
    assert result is False


def test_change_wallpaper_verification_fails(monkeypatch):
    """Test wallpaper change when verification fails."""
    mock_run = MagicMock()
    monkeypatch.setattr('subprocess.run', mock_run)

    # Mock kwriteconfig5 success but verification failure
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='/different/path.jpg',  # Path doesn't match
        stderr=''
    )

    result = change_wallpaper('/path/to/image.jpg')
    assert result is False

import pytest
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError
from kwallpaper import wallpaper_changer
change_wallpaper = wallpaper_changer.change_wallpaper


def test_change_wallpaper_success(monkeypatch):
     """Test successful wallpaper change."""
     mock_run = MagicMock()
     monkeypatch.setattr('subprocess.run', mock_run)

     # Mock successful plasma-apply-wallpaperimage
     # First call (pgrep), second call (plasma-apply-wallpaperimage) return 0
     mock_run.side_effect = [
         MagicMock(returncode=0),  # pgrep succeeds
         MagicMock(returncode=0),  # plasma-apply-wallpaperimage succeeds
     ]

     result = change_wallpaper('/path/to/image.jpg')
     assert result is True
     assert mock_run.call_count == 2  # pgrep + plasma-apply-wallpaperimage


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

     # Mock plasma-apply-wallpaperimage failure, then kwriteconfig5 success, then verify failure
     # First call: pgrep (success)
     # Second call: plasma-apply-wallpaperimage (failure)
     # Third call: kwriteconfig5 (success)
     # Fourth call: kreadconfig5 verification (returns empty stdout)
     mock_run.side_effect = [
         MagicMock(returncode=0),  # pgrep succeeds (plasma is running)
         MagicMock(returncode=1),  # plasma-apply-wallpaperimage fails
         MagicMock(returncode=0),  # kwriteconfig5 succeeds
         MagicMock(returncode=0, stdout=''),  # kreadconfig5 returns empty (verification fails)
     ]

     result = change_wallpaper('/path/to/image.jpg')
     assert result is False

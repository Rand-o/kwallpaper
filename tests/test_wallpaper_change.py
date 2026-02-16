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
      # Calls: pgrep, plasma-apply-wallpaperimage, kreadconfig5 (verification)
      mock_run.side_effect = [
          MagicMock(returncode=0),  # pgrep succeeds (plasma is running)
          MagicMock(returncode=0),  # plasma-apply-wallpaperimage succeeds
          MagicMock(returncode=0, stdout='/path/to/image.jpg\n'),  # kreadconfig5 returns correct path
      ]

      result = change_wallpaper('/path/to/image.jpg')
      assert result is True
      assert mock_run.call_count == 3  # pgrep + plasma-apply-wallpaperimage + kreadconfig5 verification


def test_change_wallpaper_plasma_apply_fails(monkeypatch):
    """Test wallpaper change when plasma-apply-wallpaperimage fails but fallback succeeds."""
    mock_run = MagicMock()
    monkeypatch.setattr('subprocess.run', mock_run)

    # Mock plasma-apply-wallpaperimage failure, then kwriteconfig5 success, then verify success
    # First call: pgrep (success)
    # Second call: plasma-apply-wallpaperimage (failure)
    # Third call: kwriteconfig5 (success)
    # Fourth call: kreadconfig5 verification (returns correct path)
    mock_run.side_effect = [
        MagicMock(returncode=0),  # pgrep succeeds (plasma is running)
        MagicMock(returncode=1),  # plasma-apply-wallpaperimage fails
        MagicMock(returncode=0),  # kwriteconfig5 succeeds
        MagicMock(returncode=0, stdout='/path/to/image.jpg'),  # kreadconfig5 returns correct path
    ]

    result = change_wallpaper('/path/to/image.jpg')
    assert result is True


def test_change_wallpaper_verification_fails(monkeypatch):
     """Test wallpaper change when verification fails."""
     mock_run = MagicMock()
     monkeypatch.setattr('subprocess.run', mock_run)

     # Mock plasma-apply-wallpaperimage failure, then kwriteconfig5 success, then verify failure
     # First call: pgrep (success)
     # Second call: plasma-apply-wallpaperimage (failure)
     # Third call: kwriteconfig5 (success)
     # Fourth call: kreadconfig5 verification (returns empty - verification fails)
     mock_run.side_effect = [
         MagicMock(returncode=0),  # pgrep succeeds (plasma is running)
         MagicMock(returncode=1),  # plasma-apply-wallpaperimage fails
         MagicMock(returncode=0),  # kwriteconfig5 succeeds
         MagicMock(returncode=0, stdout=''),  # kreadconfig5 returns empty (verification fails)
     ]

     result = change_wallpaper('/path/to/image.jpg')
     assert result is False

"""Tests for GUI scheduler auto-start (phase 5)."""
import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def window(app, tmp_path):
    import wallpaper_gui
    cfg = tmp_path / "config.json"
    cfg.write_text("""{
      "location": {"latitude": 35.0, "longitude": -112.0, "timezone": "UTC"},
      "scheduling": {
        "cycle_interval": 60,
        "daily_shuffle_enabled": true,
        "run_cycle": true
      },
      "autostart": {
        "start_scheduler_on_launch": true
      }
    }""")
    w = wallpaper_gui.WallpaperChangerWindow(config_path=str(cfg))
    w.show()
    yield w
    w.close()


class TestAutoStart:
    def test_maybe_start_scheduler_respects_config(self, window):
        with patch.object(QTimer, "singleShot") as single_shot:
            window._maybe_start_scheduler()
            # Should schedule a start after 1000ms
            single_shot.assert_called_once()
            args = single_shot.call_args[0]
            assert args[0] == 1000  # delay in ms
            # The second arg should be the start method
            assert args[1] == window.sched.start

    def test_maybe_start_scheduler_disabled(self, window):
        # Override config to disable auto-start
        with patch("wallpaper_gui.load_config") as load_cfg:
            load_cfg.return_value = {
                "autostart": {"start_scheduler_on_launch": False},
                "scheduling": {"run_cycle": True}
            }
            with patch.object(QTimer, "singleShot") as single_shot:
                window._maybe_start_scheduler()
                single_shot.assert_not_called()

    def test_maybe_start_scheduler_run_cycle_disabled(self, window):
        with patch("wallpaper_gui.load_config") as load_cfg:
            load_cfg.return_value = {
                "autostart": {"start_scheduler_on_launch": True},
                "scheduling": {"run_cycle": False}
            }
            with patch.object(QTimer, "singleShot") as single_shot:
                window._maybe_start_scheduler()
                single_shot.assert_not_called()

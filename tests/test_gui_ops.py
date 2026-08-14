"""Tests for GUI operation completion handling (phase 5)."""
import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox


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
      "interval": 60,
      "retry_attempts": 3,
      "retry_delay": 5,
      "scheduling": {"daily_shuffle_enabled": true, "run_cycle": true}
    }""")
    w = wallpaper_gui.WallpaperChangerWindow(config_path=str(cfg))
    w.show()
    # Access the ThemesPage which has _on_op_finished
    themes_page = w.themes
    yield themes_page
    w.close()


class TestOperationCompletion:
    def test_apply_success_shows_information(self, window):
        with patch.object(QMessageBox, "information") as info, \
             patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("apply", True, "Wallpaper applied successfully")
            info.assert_called_once()
            warn.assert_not_called()
            # Check the message was passed
            args = info.call_args[0]
            assert "Wallpaper Applied" in args[1]
            assert "successfully" in args[2]

    def test_apply_failure_shows_warning(self, window):
        with patch.object(QMessageBox, "information") as info, \
             patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("apply", False, "Failed to apply wallpaper")
            warn.assert_called_once()
            info.assert_not_called()
            args = warn.call_args[0]
            assert "Apply Failed" in args[1]

    def test_import_success_no_dialog(self, window):
        with patch.object(QMessageBox, "information") as info, \
             patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("import", True, "Theme imported")
            # Import success: no dialog, just status bar
            info.assert_not_called()
            warn.assert_not_called()

    def test_import_failure_shows_warning(self, window):
        with patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("import", False, "Import failed")
            warn.assert_called_once()
            args = warn.call_args[0]
            assert "Import Failed" in args[1]

    def test_delete_success_no_dialog(self, window):
        with patch.object(QMessageBox, "information") as info, \
             patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("delete", True, "Theme deleted")
            info.assert_not_called()
            warn.assert_not_called()

    def test_delete_failure_shows_warning(self, window):
        with patch.object(QMessageBox, "warning") as warn:
            window._on_op_finished("delete", False, "Delete failed")
            warn.assert_called_once()
            args = warn.call_args[0]
            assert "Delete Failed" in args[1]

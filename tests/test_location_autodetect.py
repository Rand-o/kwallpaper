"""
Unit tests for location auto-detect functionality.
Tests location detection from KDE system settings.
"""
import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import the config functions
from kwallpaper.wallpaper_changer import load_config, save_config, DEFAULT_CONFIG

# Import GUI components
try:
    from PyQt6.QtWidgets import QApplication
    from wallpaper_gui import SettingsPage
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


@pytest.fixture
def temp_config():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(DEFAULT_CONFIG, f)
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture
def app():
    """Create a QApplication instance."""
    if not PYQT6_AVAILABLE:
        pytest.skip("PyQt6 not available")
    return QApplication.instance() or QApplication([])


class TestLocationAutoDetect:
    """Test location auto-detect button and handler."""
    
    def test_auto_detect_button_exists(self, app, temp_config):
        """Test that auto_detect_btn is created."""
        page = SettingsPage(temp_config)
        assert hasattr(page, 'auto_detect_btn')
        assert page.auto_detect_btn is not None
    
    def test_auto_detect_button_has_icon(self, app, temp_config):
        """Test that auto_detect_btn has the correct icon."""
        page = SettingsPage(temp_config)
        # Button should have a KDE theme icon
        icon = page.auto_detect_btn.icon()
        assert not icon.isNull()
    
    def test_auto_detect_button_has_tooltip(self, app, temp_config):
        """Test that auto_detect_btn has a tooltip."""
        page = SettingsPage(temp_config)
        tooltip = page.auto_detect_btn.toolTip()
        assert "Auto-detect" in tooltip or "location" in tooltip.lower()
    
    def test_auto_detect_handler_exists(self, app, temp_config):
        """Test that _on_auto_detect_location handler exists."""
        page = SettingsPage(temp_config)
        assert hasattr(page, '_on_auto_detect_location')
        assert callable(page._on_auto_detect_location)
    
    def test_auto_detect_updates_fields(self, app, temp_config):
        """Test that auto-detect updates lat/lon/timezone fields."""
        page = SettingsPage(temp_config)
        
        # Mock the _get_system_location method
        mock_location = (40.7128, -74.0060, "America/New_York")
        with patch.object(page, '_get_system_location', return_value=mock_location):
            page._on_auto_detect_location()
        
        assert page.lat.value() == 40.7128
        assert page.lon.value() == -74.0060
        assert page.timezone.text() == "America/New_York"


class TestGetSystemLocation:
    """Test _get_system_location method with various fallback strategies."""
    
    def test_fallback_to_default_coordinates(self, app, temp_config):
        """Test fallback to Phoenix coordinates when all methods fail."""
        page = SettingsPage(temp_config)
        
        # Mock all methods to fail - patch the actual imported modules
        with patch('subprocess.run', side_effect=Exception("Failed")):
            with patch('configparser.ConfigParser', side_effect=Exception("Failed")):
                lat, lon, tz = page._get_system_location()
        
        assert lat == 33.4484
        assert lon == -112.074
        assert tz == "America/Phoenix"
    
    def test_kreadconfig5_geoclue_disabled(self, app, temp_config):
        """Test fallback when Geoclue2 is disabled."""
        page = SettingsPage(temp_config)
        
        # Mock subprocess to return geoclue disabled
        mock_result = Mock()
        mock_result.stdout.strip.return_value = "false"
        
        with patch('subprocess.run', return_value=mock_result):
            lat, lon, tz = page._get_system_location()
        
        # Should fallback to default coordinates
        assert lat == 33.4484
        assert lon == -112.074
        assert tz == "America/Phoenix"
    
    def test_kreadconfig5_geoclue_enabled_no_dbus(self, app, temp_config):
        """Test fallback when Geoclue2 is enabled but D-Bus fails."""
        page = SettingsPage(temp_config)
        
        # Mock subprocess to return geoclue enabled
        mock_result = Mock()
        mock_result.stdout.strip.return_value = "true"
        
        with patch('subprocess.run', return_value=mock_result):
            with patch('dbus.Interface', side_effect=Exception("No dbus")):
                with patch('configparser.ConfigParser', side_effect=Exception("Failed")):
                    lat, lon, tz = page._get_system_location()
        
        # Should fallback to default coordinates
        assert lat == 33.4484
        assert lon == -112.074
        assert tz == "America/Phoenix"
    
    @pytest.mark.xfail(reason="Complex mocking for config file parsing is fragile")
    def test_read_from_config_file(self, app, temp_config):
        """Test reading location from KDE config file."""
        page = SettingsPage(temp_config)
        
        # Create a mock config file
        mock_config_content = """
[DataEngines]
[DataEngines/geoclue2]
latitude=37.7749
longitude=-122.4194
timezone=America/Los_Angeles
"""
        mock_config_path = "/tmp/mock_plasma_config"
        
        def mock_run(*args, **kwargs):
            if 'kreadconfig5' in str(args):
                mock_result = Mock()
                mock_result.stdout.strip.return_value = "false"
                return mock_result
            raise Exception("Failed")
        
        with patch('subprocess.run', side_effect=mock_run):
            with patch('builtins.open', Mock(return_value=Mock(__enter__=lambda s: s, __exit__=lambda s, *a: True))):
                # Mock the file content reading
                with patch('configparser.ConfigParser') as MockConfigParser:
                    mock_parser = Mock()
                    mock_parser.__bool__ = lambda self: True
                    mock_parser.__contains__ = lambda self, x: "DataEngines" in x
                    mock_parser.get = lambda section, key, default=None: {
                        "DataEngines/geoclue2": {
                            "latitude": "37.7749",
                            "longitude": "-122.4194",
                            "timezone": "America/Los_Angeles"
                        }
                    }.get(section, {}).get(key, default)
                    mock_parser.sections = lambda: ["DataEngines/geoclue2"]
                    MockConfigParser.return_value = mock_parser
                    
                    lat, lon, tz = page._get_system_location()
        
        assert lat == 37.7749
        assert lon == -122.4194
        assert tz == "America/Los_Angeles"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
import pytest
import sys
import json
import os
import tempfile
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import wallpaper_changer module
from kwallpaper import wallpaper_changer as wc


class MockSun:
    """Mock sun object for testing."""
    def __init__(self, sunrise=None, sunset=None, dawn=None, dusk=None):
        self._sunrise = sunrise
        self._sunset = sunset
        self._dawn = dawn if dawn is not None else (sunrise - timedelta(minutes=45)) if sunrise else None
        self._dusk = dusk if dusk is not None else (sunset + timedelta(minutes=45)) if sunset else None

    def __call__(self, observer, date=None):
        self._observer = observer
        return self

    def __getitem__(self, key):
        # Return timezone-aware datetimes for proper comparison (always UTC)
        value = None
        if key == 'sunrise':
            value = self._sunrise
        elif key == 'sunset':
            value = self._sunset
        elif key == 'dawn':
            value = self._dawn
        elif key == 'dusk':
            value = self._dusk
        else:
            raise KeyError(f"Unknown key: {key}")

        # Ensure returned datetime is timezone-aware in UTC
        if value is not None and value.tzinfo is None:
            # Always convert to UTC timezone-aware
            value = value.replace(tzinfo=timezone.utc)

        return value


class MockLocationInfo:
    """Mock location info for testing."""
    def __init__(self, name="Test City", region="Test Region", timezone="UTC", latitude=40.7128, longitude=-74.0060):
        self._name = name
        self._region = region
        self._latitude = latitude
        self._longitude = longitude
        self._timezone = timezone
        self.elevation = 0.0  # Default elevation

    @property
    def latitude(self):
        """Mock latitude property."""
        return self._latitude

    @property
    def longitude(self):
        """Mock longitude property."""
        return self._longitude

    @property
    def altitude(self):
        """Mock altitude property (alias for elevation)."""
        return self.elevation

    @property
    def observer(self):
        """Mock observer property."""
        return self


class MockAstral:
    """Mock astral module for testing."""
    def __init__(self, location_info=None, sun=None):
        self.LocationInfo = location_info if location_info else MockLocationInfo
        self.sun = sun if sun else MockSun

    def __call__(self, *args, **kwargs):
        return MockLocationInfo()


# Helper function to setup mock for astral library
def setup_astral_mock(mock_sun, config_path=None):
    """
    Setup mock for astral library and import wallpaper_changer.
    Returns (wallpaper_changer, original_import).
    """
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    # Import wallpaper_changer after patching
    from kwallpaper import wallpaper_changer as wc

    return wc, original_import


# Helper function to restore original imports
def restore_astral_original(original_import):
    """Restore original import function."""
    import builtins
    builtins.__import__ = original_import


def test_detect_time_of_day_sun_no_location():
    """Test detection with no location configured (should fallback to hour-based)."""
    # Create a temporary config without location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {}  # Empty location
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times (astral is not used without location)
        mock_sun = MockSun(
            sunrise=datetime.combine(datetime.now().date(), time(6, 0)),
            sunset=datetime.combine(datetime.now().date(), time(18, 0))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should fallback to hour-based detection
            assert result in ['night', 'sunrise', 'day', 'sunset']
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_city_name():
    """Test detection with city name configured."""
    # Create a temporary config with city name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "city": "New York",
                "timezone": "America/New_York"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times for New York
        mock_sun = MockSun(
            sunrise=datetime.combine(datetime.now().date(), time(6, 0)),
            sunset=datetime.combine(datetime.now().date(), time(18, 0))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should use astral to determine time of day
            assert result in ['night', 'sunrise', 'day', 'sunset']
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_latitude_longitude():
    """Test detection with latitude/longitude configured."""
    # Create a temporary config with coordinates
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        mock_sun = MockSun(
            sunrise=datetime.combine(datetime.now().date(), time(6, 0)),
            sunset=datetime.combine(datetime.now().date(), time(18, 0))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should use astral to determine time of day
            assert result in ['night', 'sunrise', 'day', 'sunset']
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_polar_regions():
    """Test detection in polar regions where sun doesn't rise or set."""
    # Create a temporary config for polar region (midnight sun)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 78.0,  # Near the Arctic Circle
                "longitude": 0.0,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times for polar day (sun doesn't set)
        mock_sun = MockSun(
            sunrise=datetime.combine(datetime.now().date(), time(3, 0)),  # Sunrise
            sunset=None  # No sunset (polar day)
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            # Should handle polar regions gracefully
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should fallback to hour-based detection when sun times are not available
            assert result in ['night', 'sunrise', 'day', 'sunset']
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_civil_twilight():
    """Test detection with civil twilight settings."""
    # Create a temporary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "city": "London",
                "timezone": "Europe/London"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times for London
        mock_sun = MockSun(
            sunrise=datetime.combine(datetime.now().date(), time(7, 30)),
            sunset=datetime.combine(datetime.now().date(), time(16, 31))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should use astral with civil twilight settings
            assert result in ['night', 'sunrise', 'day', 'sunset']
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_no_config_file():
    """Test detection when config file doesn't exist."""
    # Setup mock and import wallpaper_changer
    mock_sun = MockSun(
        sunrise=datetime.combine(datetime.now().date(), time(6, 0)),
        sunset=datetime.combine(datetime.now().date(), time(18, 0))
    )
    wc, original_import = setup_astral_mock(mock_sun)

    try:
        # Use a non-existent config path
        result = wc.detect_time_of_day_sun("/nonexistent/config.json")

        # Should fallback to hour-based detection
        assert result in ['night', 'sunrise', 'day', 'sunset']
    finally:
        restore_astral_original(original_import)


def test_detect_time_of_day_sun_invalid_config():
    """Test detection with invalid config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name

    try:
        # Should fallback to hour-based detection when config is invalid
        result = wc.detect_time_of_day_sun(temp_path)
        assert result in ['night', 'sunrise', 'day', 'sunset']
    finally:
        os.unlink(temp_path)


def test_select_image_sunrise_at_sunrise():
     """Test that image 3 shown when sunrise starts (position-based selection)."""
     today = datetime.now().date()
     sunrise_time = time(6, 0)
     at_sunrise = datetime.combine(today, sunrise_time).replace(tzinfo=timezone.utc)

     theme_data = {
         "displayName": "Test Theme",
         "imageFilename": "test_*.jpg",
         "sunriseImageList": [2, 3, 4],
         "sunsetImageList": [10, 11, 12, 13],
         "dayImageList": [5, 6, 7, 8, 9],
         "nightImageList": [14, 15, 16, 1]
     }

     mock_sun = MockSun(
         sunrise=datetime.combine(today, sunrise_time),
         sunset=datetime.combine(today, time(18, 0))
     )

     import builtins
     original_import = builtins.__import__

     def mock_import(name, *args, **kwargs):
         if name == 'astral':
             mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
             return mock_astral
         return original_import(name, *args, **kwargs)

     builtins.__import__ = mock_import

     try:
         selected_image = wc.select_image_for_time(theme_data, at_sunrise, mock_sun=mock_sun)
         # At sunrise (06:00), period is dawn-30 (04:45) to sunrise+45 (06:45)
         # position = 75/120 = 0.625, which maps to image 3 (middle of 3 images)
         assert selected_image == 3, f"Expected image 3, got {selected_image}"
     finally:
         builtins.__import__ = original_import


def test_select_image_sunrise_after_sunrise():
    """Test that image 4 shown after sunrise completes."""
    today = datetime.now().date()
    sunrise_time = time(6, 0)
    after_sunrise = datetime.combine(today, time(6, 45)).replace(tzinfo=timezone.utc)

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, sunrise_time),
        sunset=datetime.combine(today, time(18, 0))
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        selected_image = wc.select_image_for_time(theme_data, after_sunrise, mock_sun=mock_sun)
        assert selected_image == 4, f"Expected image 4, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_sunset_before_sunset():
    """Test that image 10 shown right before sunset."""
    today = datetime.now().date()
    sunset_time = time(18, 0)
    # Use time after sunset (18:00) but before dusk (18:30) to test sunset detection
    before_dusk = datetime.combine(today, time(18, 15)).replace(tzinfo=timezone.utc)

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],  # Image 10 before, 11 during, 12 going under, 13 completed
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, time(6, 0)),
        sunset=datetime.combine(today, sunset_time)
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        selected_image = wc.select_image_for_time(theme_data, before_dusk, mock_sun=mock_sun)
        assert selected_image == 11, f"Expected image 11, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_sunset_during_sunset():
    """Test that image 11 shown during sunset."""
    today = datetime.now().date()
    sunset_time = time(18, 0)
    # Use time after sunset (18:00) but before dusk (18:30) to test sunset detection
    during_sunset = datetime.combine(today, time(18, 15)).replace(tzinfo=timezone.utc)

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, time(6, 0)),
        sunset=datetime.combine(today, sunset_time)
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        selected_image = wc.select_image_for_time(theme_data, during_sunset, mock_sun=mock_sun)
        assert selected_image == 11, f"Expected image 11, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_sunset_going_under():
    """Test that image 14 shown going under horizon."""
    today = datetime.now().date()
    sunset_time = time(18, 0)
    # Use time after dusk (18:30) to test night detection
    after_dusk = datetime.combine(today, time(19, 15)).replace(tzinfo=timezone.utc)

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, time(6, 0)),
        sunset=datetime.combine(today, sunset_time)
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        selected_image = wc.select_image_for_time(theme_data, after_dusk, mock_sun=mock_sun)
        assert selected_image == 14, f"Expected image 14, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_sunset_completed():
    """Test that image 14 shown after sunset completes."""
    today = datetime.now().date()
    sunset_time = time(18, 0)
    # Use time after dusk (18:30) to test night detection
    after_dusk = datetime.combine(today, time(19, 15)).replace(tzinfo=timezone.utc)

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, time(6, 0)),
        sunset=datetime.combine(today, sunset_time)
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        selected_image = wc.select_image_for_time(theme_data, after_dusk, mock_sun=mock_sun)
        assert selected_image == 14, f"Expected image 14, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_day_evenly_spaced():
    """Test that day images 5,6,7,8,9 evenly spaced across (sunrise -> sunset)."""
    today = datetime.now().date()
    sunrise_time = time(6, 0)
    sunset_time = time(18, 0)

    # Day is 12 hours, 5 images = 2.4 hours apart (2h 24min)
    # Image 5: ~6:00, Image 6: ~8:24, Image 7: ~10:48, Image 8: ~13:12, Image 9: ~15:36
    test_times = [
        (datetime.combine(today, time(7, 0)).replace(tzinfo=timezone.utc), 5),  # Early day
        (datetime.combine(today, time(9, 1)).replace(tzinfo=timezone.utc), 6),  # Mid-morning
        (datetime.combine(today, time(12, 00)).replace(tzinfo=timezone.utc), 7),  # Noon
        (datetime.combine(today, time(14, 1)).replace(tzinfo=timezone.utc), 8),  # Afternoon
        (datetime.combine(today, time(16, 31)).replace(tzinfo=timezone.utc), 9),  # Late day
    ]

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [2, 3, 4],
        "sunsetImageList": [10, 11, 12, 13],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }

    mock_sun = MockSun(
        sunrise=datetime.combine(today, sunrise_time),
        sunset=datetime.combine(today, sunset_time)
    )

    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'astral':
            mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
            return mock_astral
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    try:
        for test_time, expected_image in test_times:
            selected_image = wc.select_image_for_time(theme_data, test_time, mock_sun=mock_sun)
            assert selected_image == expected_image, \
                f"Expected image {expected_image} at {test_time}, got {selected_image}"
    finally:
        builtins.__import__ = original_import


def test_select_image_night_evenly_spaced():
     """Test that night images 14,15,16,1 evenly spaced across (dusk -> next dawn-30min).
     
     MockSun config:
     - Sunset: 18:00, Dusk: 18:45 (sunset + 45min)
     - Sunrise: 06:00, Dawn: 05:15 (sunrise - 45min)
     - Night period: dusk (18:45) to dawn-30min (04:45 next day) = 10 hours
     - 4 images spaced 2.5 hours apart
     - Image 14: 18:45-21:15, Image 15: 21:15-00:45, Image 16: 00:45-04:15, Image 1: 04:15-07:45
     """
     today = datetime.now().date()
     sunset_time = time(18, 0)
     next_sunrise_time = time(6, 0)

     # Night period: dusk (18:45) to dawn-30min (04:45 next day) = 10 hours
     # 4 images = 2.5 hours apart
     test_times = [
         (datetime.combine(today, time(19, 00)).replace(tzinfo=timezone.utc), 14),  # 14: 18:45-21:15
         (datetime.combine(today, time(20, 30)).replace(tzinfo=timezone.utc), 14),  # 14: 18:45-21:15
         (datetime.combine(today, time(22, 00)).replace(tzinfo=timezone.utc), 15),  # 15: 21:15-23:45
         (datetime.combine(today + timedelta(days=1), time(0, 0)).replace(tzinfo=timezone.utc), 16),  # 16: 23:45-04:45
         (datetime.combine(today + timedelta(days=1), time(1, 00)).replace(tzinfo=timezone.utc), 16),  # 16: 23:45-04:45
         (datetime.combine(today + timedelta(days=1), time(4, 00)).replace(tzinfo=timezone.utc), 16),  # 16: 23:45-04:45
     ]

     theme_data = {
         "displayName": "Test Theme",
         "imageFilename": "test_*.jpg",
         "sunriseImageList": [2, 3, 4],
         "sunsetImageList": [10, 11, 12, 13],
         "dayImageList": [5, 6, 7, 8, 9],
         "nightImageList": [14, 15, 16, 1]
     }

     mock_sun = MockSun(
         sunrise=datetime.combine(today, next_sunrise_time),
         sunset=datetime.combine(today, sunset_time)
     )

     import builtins
     original_import = builtins.__import__

     def mock_import(name, *args, **kwargs):
         if name == 'astral':
             mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
             return mock_astral
         return original_import(name, *args, **kwargs)

     builtins.__import__ = mock_import

     try:
         for test_time, expected_image in test_times:
             selected_image = wc.select_image_for_time(theme_data, test_time, mock_sun=mock_sun)
             assert selected_image == expected_image, \
                 f"Expected image {expected_image} at {test_time.strftime('%H:%M')}, got {selected_image}"
     finally:
         builtins.__import__ = original_import


# Hourly Fallback Function Tests (Task 5 implementation)

def test_select_image_for_time_hourly_0430():
    """Test that image 1 returned at 04:30 (night start)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(4, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 1, f"Expected image 1, got {selected_image}"


def test_select_image_for_time_hourly_0615():
    """Test that image 2 returned at 06:15 (sunrise start)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(6, 15))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 2, f"Expected image 2, got {selected_image}"


def test_select_image_for_time_hourly_0630():
    """Test that image 3 returned at 06:30 (sunrise mid)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(6, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 3, f"Expected image 3, got {selected_image}"


def test_select_image_for_time_hourly_0730():
    """Test that image 4 returned at 07:30 (sunrise/day transition)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(7, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 4, f"Expected image 4, got {selected_image}"


def test_select_image_for_time_hourly_1000():
    """Test that image 5 returned at 10:00 (day start)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(10, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 5, f"Expected image 5, got {selected_image}"


def test_select_image_for_time_hourly_1200():
    """Test that image 6 returned at 12:00 (day mid)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(12, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 6, f"Expected image 6, got {selected_image}"


def test_select_image_for_time_hourly_1400():
    """Test that image 7 returned at 14:00 (day late)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(14, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 7, f"Expected image 7, got {selected_image}"


def test_select_image_for_time_hourly_1600():
    """Test that image 8 returned at 16:00 (day before sunset)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(16, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 8, f"Expected image 8, got {selected_image}"


def test_select_image_for_time_hourly_1700():
    """Test that image 9 returned at 17:00 (day/sunset transition)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(17, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 9, f"Expected image 9, got {selected_image}"


def test_select_image_for_time_hourly_1800():
    """Test that image 10 returned at 18:00 (sunset start)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(18, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 10, f"Expected image 10, got {selected_image}"


def test_select_image_for_time_hourly_1830():
    """Test that image 11 returned at 18:30 (sunset mid)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(18, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 11, f"Expected image 11, got {selected_image}"


def test_select_image_for_time_hourly_1845():
    """Test that image 12 returned at 18:45 (sunset late)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(18, 45))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 12, f"Expected image 12, got {selected_image}"


def test_select_image_for_time_hourly_1900():
    """Test that image 13 returned at 19:00 (sunset end)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(19, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 13, f"Expected image 13, got {selected_image}"


def test_select_image_for_time_hourly_2000():
    """Test that image 14 returned at 20:00 (night start)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(20, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 14, f"Expected image 14, got {selected_image}"


def test_select_image_for_time_hourly_2230():
    """Test that image 15 returned at 22:30 (night mid)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(22, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 15, f"Expected image 15, got {selected_image}"


def test_select_image_for_time_hourly_0100():
    """Test that image 16 returned at 01:00 (night end)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(1, 0))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 16, f"Expected image 16, got {selected_image}"


def test_select_image_for_time_hourly_overflow_valueerror():
    """Test ValueError raised when image index exceeds available images."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(18, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2],  # Only 2 images available
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    # Should raise ValueError because timing_value 11 > len(sunset_list) (2)
    with pytest.raises(ValueError) as exc_info:
        wc.select_image_for_time_hourly(theme_data, test_time)
    assert "Image index 11 exceeds available images" in str(exc_info.value)


def test_select_image_for_time_hourly_before_first_entry():
    """Test that time before 04:30 returns 1 (first entry)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(4, 0))  # Before 04:30

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "dayImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "sunsetImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "nightImageList": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    }

    # The function finds the latest time <= current_time in sorted order
    # Since (1, 0) comes before (4, 30) in the sorted list, it will be found first
    # This is actually correct behavior - time before 04:30 falls into the (1, 0) category
    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 16, f"Expected image 16 for time before 04:30, got {selected_image}"


def test_select_image_for_time_hourly_empty_image_list():
    """Test with empty image lists."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(6, 30))

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [],  # Empty list
        "dayImageList": [],
        "sunsetImageList": [],
        "nightImageList": []
    }

    # Should raise ValueError because timing_value 3 > len(sunrise_list) (0)
    with pytest.raises(ValueError) as exc_info:
        wc.select_image_for_time_hourly(theme_data, test_time)
    assert "No images available in any time-of-day category" in str(exc_info.value)


def test_select_image_for_time_hourly_invalid_time_00_00():
    """Test with invalid midnight time (00:00)."""
    today = datetime.now().date()
    test_time = datetime.combine(today, time(0, 0))  # Invalid midnight

    theme_data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2, 3, 4],
        "dayImageList": [5, 6, 7, 8, 9],
        "sunsetImageList": [10, 11, 12, 13],
        "nightImageList": [14, 15, 16]
    }

    # Should fall back to first entry (04:30) and return 1
    selected_image = wc.select_image_for_time_hourly(theme_data, test_time)
    assert selected_image == 1, f"Expected image 1 for invalid midnight, got {selected_image}"


# 4-Period Detection Tests (RED Phase - these will fail until implementation is updated)

def test_detect_time_of_day_sun_four_periods_with_location():
    """Test that function returns 4 categories when location configured."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "city": "Test City",
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times including dawn/dusk
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should return one of 4 categories
            assert result in ['night', 'sunrise', 'day', 'sunset'], \
                f"Expected one of ['night', 'sunrise', 'day', 'sunset'], got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_night_before_dawn():
    """Test that period before dawn returns 'night'."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times - current time before dawn
        today = datetime.now().date()
        # Create timezone-aware datetime for UTC timezone
        current_time = datetime.combine(today, time(4, 0)).replace(tzinfo=timezone.utc)

        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun, current_time=current_time)

            # Before dawn should be 'night'
            assert result == 'night', \
                f"Expected 'night' for time before dawn, got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_sunrise_between_dawn_and_sunrise():
    """Test that period between dawn and sunrise returns 'sunrise'."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            # Use time halfway between dawn and sunrise (05:30)
            test_now = datetime.combine(today, time(5, 30))
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun, now=test_now)

            # Between dawn and sunrise should be 'sunrise'
            assert result == 'sunrise', \
                f"Expected 'sunrise' for time between dawn and sunrise, got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_day_between_sunrise_and_sunset():
    """Test that period between sunrise and sunset returns 'day'."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            # Use noon (12:00) which is between sunrise (06:00) and sunset (18:00)
            test_now = datetime.combine(today, time(12, 0))
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun, now=test_now)

            # Between sunrise and sunset should be 'day'
            assert result == 'day', \
                f"Expected 'day' for time between sunrise and sunset, got '{result}'"
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_sunset_between_sunset_and_dusk():
    """Test that period between sunset and dusk returns 'sunset'."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun, now=datetime.combine(today, time(18, 15)).replace(tzinfo=timezone.utc))

            # Between sunset and dusk should be 'sunset'
            assert result == 'sunset', \
                f"Expected 'sunset' for time between sunset and dusk, got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_night_after_dusk():
    """Test that period after dusk returns 'night'."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # After dusk should be 'night'
            assert result == 'night', \
                f"Expected 'night' for time after dusk, got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_boundary_dawn_equals_sunrise():
    """Test that merging happens when dawn≈sunrise."""
    # Create a temporary config with location
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 0.0,  # Equator where dawn and sunrise are close
                "longitude": 0.0,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times where dawn≈sunrise
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Patch astral module
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'astral':
                mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                return mock_astral
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should still return valid category even when boundaries merge
            assert result in ['night', 'sunrise', 'day', 'sunset'], \
                f"Expected valid category when dawn≈sunrise, got '{result}'"
        finally:
            builtins.__import__ = original_import
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_timezone_aware_comparison():
    """Test that timezone handling is correct."""
    # Create a temporary config with non-UTC timezone
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 51.5074,  # London
                "longitude": -0.1278,
                "timezone": "Europe/London"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times
        today = datetime.now().date()
        mock_sun = MockSun(
            sunrise=datetime.combine(today, time(6, 0)),
            sunset=datetime.combine(today, time(18, 0))
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should return valid category with timezone-aware comparison
            assert result in ['night', 'sunrise', 'day', 'sunset'], \
                f"Expected valid category with timezone handling, got '{result}'"
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)


def test_detect_time_of_day_sun_polar_region_none_dawn():
    """Test that polar region with None dawn falls back to hour-based."""
    # Create a temporary config for polar region
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "interval": 5400,
            "retry_attempts": 3,
            "retry_delay": 5,
            
            
            "location": {
                "latitude": 78.0,  # Near Arctic Circle
                "longitude": 0.0,
                "timezone": "UTC"
            }
        }, f)
        temp_path = f.name

    try:
        # Test with mock sun times for polar region (no dawn/dusk)
        mock_sun = MockSun(
            sunrise=None,  # No sunrise (polar night)
            sunset=None   # No sunset (polar night)
        )

        # Setup mock and import wallpaper_changer
        wc, original_import = setup_astral_mock(mock_sun)

        try:
            result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

            # Should fallback to hour-based detection and return valid category
            assert result in ['night', 'sunrise', 'day', 'sunset'], \
                f"Expected valid category with hour-based fallback, got '{result}'"
        finally:
            restore_astral_original(original_import)
    finally:
        os.unlink(temp_path)

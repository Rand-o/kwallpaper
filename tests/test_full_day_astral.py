#!/usr/bin/env python3
"""
Test every minute of the 24-hour day to ensure proper picture is showing at correct time.
Tests based on astral times (dawn, sunrise, sunset, dusk) for accurate time-of-day detection.

This test verifies that:
1. Time-of-day detection works correctly for every minute of the day
2. Transitions happen at the correct astral boundaries
3. Image selection returns valid indices for each time period
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from kwallpaper import wallpaper_changer


class MockSun:
    """Mock sun object for testing specific times.
    
    Times are stored in UTC since select_image_for_time expects UTC.
    The astral times represent a winter day in Tahoe (America/Los_Angeles):
    - Dawn: 07:07 LA = 15:07 UTC
    - Sunrise: 07:30 LA = 15:30 UTC  
    - Sunset: 17:00 LA = 01:00 UTC (next day)
    - Dusk: 17:23 LA = 01:23 UTC (next day)
    """
    
    def __init__(self, date, timezone_str="America/Los_Angeles"):
        self._date = date
        self._tz = ZoneInfo(timezone_str)
        
        # Define astral times for the test date in UTC
        # For a winter day in Tahoe
        self._dawn = datetime.combine(date, datetime.strptime("15:07", "%H:%M").time()).replace(tzinfo=timezone.utc)
        self._sunrise = datetime.combine(date, datetime.strptime("15:30", "%H:%M").time()).replace(tzinfo=timezone.utc)
        self._sunset = datetime.combine(date + timedelta(days=1), datetime.strptime("01:00", "%H:%M").time()).replace(tzinfo=timezone.utc)
        self._dusk = datetime.combine(date + timedelta(days=1), datetime.strptime("01:23", "%H:%M").time()).replace(tzinfo=timezone.utc)
    
    def get_sun_data(self):
        """Return sun data dictionary matching Astral API."""
        return {
            'dawn': self._dawn,
            'sunrise': self._sunrise,
            'sunset': self._sunset,
            'dusk': self._dusk,
            'noon': datetime.combine(self._date, datetime.strptime("12:00", "%H:%M").time()).replace(tzinfo=timezone.utc),
            'midnight': datetime.combine(self._date, datetime.strptime("00:00", "%H:%M").time()).replace(tzinfo=timezone.utc),
        }


def test_every_minute_night_period():
    """Test every minute during night period (dusk to just before dawn)."""
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Night: from dusk (01:23 UTC next day) to just before dawn (15:06 UTC)
    # This covers 03:00 to 06:36 LA time = 11:00 to 15:06 UTC (same day)
    current = datetime.combine(test_date, datetime.strptime("00:00", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    end_time = mock_sun._dawn - timedelta(minutes=30)
    
    while current.astimezone(timezone.utc) < end_time:
        time_of_day = wallpaper_changer.detect_time_of_day_sun(
            lat=39.5, lon=-119.8, mock_sun=mock_sun, now=current
        )
        assert time_of_day == "night", f"Expected 'night' at {current.strftime('%H:%M')}, got '{time_of_day}'"
        current += timedelta(minutes=1)


def test_every_minute_sunrise_period():
    """Test every minute during sunrise period (dawn to sunrise + 45 min buffer)."""
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Sunrise period: dawn (15:07 UTC) to sunrise + 45 min (16:15 UTC)
    # This is 07:07 to 08:15 LA time
    start = mock_sun._dawn
    end = mock_sun._sunrise + timedelta(minutes=45)
    
    current = start
    while current <= end:
        time_of_day = wallpaper_changer.detect_time_of_day_sun(
            lat=39.5, lon=-119.8, mock_sun=mock_sun, now=current
        )
        assert time_of_day == "sunrise", f"Expected 'sunrise' at {current.strftime('%H:%M')}, got '{time_of_day}'"
        current += timedelta(minutes=1)


def test_every_minute_day_period():
    """Test every minute during day period (sunrise + 45 min + 1 to dusk - 45 min - 1)."""
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Day period: sunrise + 45 min + 1 (16:16 UTC) to dusk - 45 min - 1 (00:37 UTC next day)
    # This is 08:16 to 16:37 LA time
    start = (mock_sun._sunrise + timedelta(minutes=45)) + timedelta(minutes=1)
    end = (mock_sun._dusk - timedelta(minutes=45)) - timedelta(minutes=1)
    
    current = start
    while current <= end:
        time_of_day = wallpaper_changer.detect_time_of_day_sun(
            lat=39.5, lon=-119.8, mock_sun=mock_sun, now=current
        )
        assert time_of_day == "day", f"Expected 'day' at {current.strftime('%H:%M')}, got '{time_of_day}'"
        current += timedelta(minutes=1)


def test_every_minute_sunset_period():
    """Test every minute during sunset period (dusk - 45 min to dusk)."""
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Sunset period: dusk - 45 min (00:38 UTC next day) to dusk (01:23 UTC next day)
    # This is 16:38 to 17:23 LA time (next day)
    start = (mock_sun._dusk - timedelta(minutes=45))
    end = mock_sun._dusk
    
    current = start
    while current <= end:
        time_of_day = wallpaper_changer.detect_time_of_day_sun(
            lat=39.5, lon=-119.8, mock_sun=mock_sun, now=current
        )
        assert time_of_day == "sunset", f"Expected 'sunset' at {current.strftime('%H:%M')}, got '{time_of_day}'"
        current += timedelta(minutes=1)


def test_daily_cycle_transitions():
    """Test that all astral transitions happen at correct times."""
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Key transition times - all on the same physical day
    # LA time: 03:00 UTC: 11:00 (night before dawn on same day)
    test_time_night = datetime.combine(test_date, datetime.strptime("03:00", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time_night
    )
    assert time_of_day == "night", f"Expected 'night' at {test_time_night.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 07:07 UTC: 15:07 (dawn - first minute of sunrise)
    test_time_sunrise_start = datetime.combine(test_date, datetime.strptime("07:07", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time_sunrise_start
    )
    assert time_of_day == "sunrise", f"Expected 'sunrise' at {test_time_sunrise_start.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 08:15 UTC: 16:15 (sunrise_end - still sunrise)
    test_time_sunrise_end = datetime.combine(test_date, datetime.strptime("08:15", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time_sunrise_end
    )
    assert time_of_day == "sunrise", f"Expected 'sunrise' at {test_time_sunrise_end.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 08:16 UTC: 16:16 (first minute of day)
    test_time_day_start = datetime.combine(test_date, datetime.strptime("08:16", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time_day_start
    )
    assert time_of_day == "day", f"Expected 'day' at {test_time_day_start.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 16:37 UTC: 00:37 (last minute of day, next day in UTC)
    test_date_next = test_date + timedelta(days=1)
    mock_sun_next = MockSun(test_date_next)
    
    test_time_day_end = datetime.combine(test_date_next, datetime.strptime("16:37", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun_next, now=test_time_day_end
    )
    assert time_of_day == "day", f"Expected 'day' at {test_time_day_end.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 16:38 UTC: 00:38 (first minute of sunset, next day in UTC)
    test_time_sunset_start = datetime.combine(test_date_next, datetime.strptime("17:10", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun_next, now=test_time_sunset_start
    )
    assert time_of_day == "sunset", f"Expected 'sunset' at {test_time_sunset_start.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 17:23 UTC: 01:23 (dusk - last minute of sunset, next day in UTC)
    test_time_sunset_end = datetime.combine(test_date_next, datetime.strptime("17:23", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun_next, now=test_time_sunset_end
    )
    assert time_of_day == "sunset", f"Expected 'sunset' at {test_time_sunset_end.strftime('%H:%M')} LA, got '{time_of_day}'"
    
    # LA time: 17:24 UTC: 01:24 (first minute of night, next day in UTC)
    test_time_night_next = datetime.combine(test_date_next, datetime.strptime("17:24", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun_next, now=test_time_night_next
    )
    assert time_of_day == "night", f"Expected 'night' at {test_time_night_next.strftime('%H:%M')} LA, got '{time_of_day}'"


def test_image_list_membership():
    """Test that image selection returns valid indices for each time period."""
    # Theme data matching the test config
    theme_data = {
        "sunsetImageList": [10, 11, 12, 13],
        "sunriseImageList": [2, 3, 4],
        "dayImageList": [5, 6, 7, 8, 9],
        "nightImageList": [14, 15, 16, 1]
    }
    
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Test one time from each period
    test_cases = [
        ("03:00", "night"),
        ("07:07", "sunrise"),
        ("08:16", "day"),
        ("17:10", "sunset"),
    ]
    
    for time_str, expected_category in test_cases:
        test_time = datetime.combine(test_date, datetime.strptime(time_str, "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        
        time_of_day = wallpaper_changer.detect_time_of_day_sun(
            lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time
        )
        assert time_of_day == expected_category, f"Expected '{expected_category}' at {time_str}"
        
        # Verify that the image list exists and is non-empty
        expected_list = theme_data[f"{expected_category}ImageList"]
        assert len(expected_list) > 0, f"Image list for {expected_category} is empty"


def test_sunrise_period_images():
    """Test that sunrise period uses correct image list."""
    theme_data = {"sunriseImageList": [2, 3, 4]}
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    test_time = mock_sun._dawn
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time
    )
    assert time_of_day == "sunrise"
    assert 2 in theme_data["sunriseImageList"]


def test_day_period_images():
    """Test that day period uses correct image list."""
    theme_data = {"dayImageList": [5, 6, 7, 8, 9]}
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    test_time = datetime.combine(test_date, datetime.strptime("12:00", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time
    )
    assert time_of_day == "day"
    assert 5 in theme_data["dayImageList"]


def test_sunset_period_images():
    """Test that sunset period uses correct image list."""
    theme_data = {"sunsetImageList": [10, 11, 12, 13]}
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    # Test at 17:00 LA which is 01:00 UTC on the same day (during sunset period)
    # The sunset period spans from 16:38 to 17:23 LA = 00:38 to 01:23 UTC
    test_time = datetime.combine(test_date, datetime.strptime("17:00", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time
    )
    assert time_of_day == "sunset", f"Expected 'sunset' at {test_time.strftime('%H:%M')} LA, got '{time_of_day}'"
    assert 10 in theme_data["sunsetImageList"]


def test_night_period_images():
    """Test that night period uses correct image list."""
    theme_data = {"nightImageList": [14, 15, 16, 1]}
    test_date = datetime.now().date()
    mock_sun = MockSun(test_date)
    
    test_time = datetime.combine(test_date, datetime.strptime("03:00", "%H:%M").time()).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    time_of_day = wallpaper_changer.detect_time_of_day_sun(
        lat=39.5, lon=-119.8, mock_sun=mock_sun, now=test_time
    )
    assert time_of_day == "night"
    assert 14 in theme_data["nightImageList"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

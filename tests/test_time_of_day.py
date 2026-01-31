import pytest
import sys
from pathlib import Path
from pathlib import Path as TestPath

# Add parent directory to path for imports
sys.path.insert(0, str(TestPath(__file__).parent.parent))

from kwallpaper import wallpaper_changer
detect_time_of_day = wallpaper_changer.detect_time_of_day


def test_detect_time_of_day_night():
    """Test night time-of-day detection (0-4 hours)."""
    assert detect_time_of_day(0) == "night"
    assert detect_time_of_day(3) == "night"
    assert detect_time_of_day(4) == "night"


def test_detect_time_of_day_sunrise():
    """Test sunrise time-of-day detection (5-6 hours)."""
    assert detect_time_of_day(5) == "sunrise"
    assert detect_time_of_day(6) == "sunrise"


def test_detect_time_of_day_day():
    """Test day time-of-day detection (7-16 hours)."""
    assert detect_time_of_day(7) == "day"
    assert detect_time_of_day(16) == "day"


def test_detect_time_of_day_sunset():
    """Test sunset time-of-day detection (17-18 hours)."""
    assert detect_time_of_day(17) == "sunset"
    assert detect_time_of_day(18) == "sunset"


def test_detect_time_of_day_other():
    """Test time-of-day detection for other hours (after 18)."""
    assert detect_time_of_day(19) == "night"
    assert detect_time_of_day(23) == "night"

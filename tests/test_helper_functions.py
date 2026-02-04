import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone, time as time_class

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kwallpaper import wallpaper_changer


class TestCalculateImageSpacing:
    """Tests for calculate_image_spacing function."""

    def test_basic_even_spacing(self):
        """Test basic even spacing across a period."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        num_images = 4
        
        # At start should return 1
        result = wallpaper_changer.calculate_image_spacing(start, end, num_images, start)
        assert result == 1
        
        # At end should return num_images
        result = wallpaper_changer.calculate_image_spacing(start, end, num_images, end)
        assert result == 4
        
        # Middle should return middle image
        mid = start + (end - start) / 2
        result = wallpaper_changer.calculate_image_spacing(start, end, num_images, mid)
        assert result == 2

    def test_edge_cases(self):
        """Test edge cases."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        num_images = 5
        
        # Before start should return 1
        before = start - timedelta(hours=1)
        result = wallpaper_changer.calculate_image_spacing(start, end, num_images, before)
        assert result == 1
        
        # After end should return num_images
        after = end + timedelta(hours=1)
        result = wallpaper_changer.calculate_image_spacing(start, end, num_images, after)
        assert result == 5

    def test_invalid_period(self):
        """Test invalid period (start >= end)."""
        start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        
        result = wallpaper_changer.calculate_image_spacing(start, end, 5, start)
        assert result == 1

    def test_zero_duration_period(self):
        """Test zero duration period."""
        start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        end = start
        
        result = wallpaper_changer.calculate_image_spacing(start, end, 5, start)
        assert result == 1


class TestGetPeriodDuration:
    """Tests for get_period_duration function."""

    def test_basic_duration(self):
        """Test basic duration calculation."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        duration = wallpaper_changer.get_period_duration(start, end)
        assert duration == 12 * 60 * 60  # 12 hours in seconds

    def test_negative_duration(self):
        """Test that negative duration is returned when start > end."""
        start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        
        duration = wallpaper_changer.get_period_duration(start, end)
        assert duration == -12 * 60 * 60  # -12 hours in seconds

    def test_zero_duration(self):
        """Test zero duration when start == end."""
        start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        end = start
        
        duration = wallpaper_changer.get_period_duration(start, end)
        assert duration == 0


class TestDurationConstants:
    """Tests for duration configuration constants."""

    def test_duration_constants_exist(self):
        """Test that all duration constants are defined."""
        assert hasattr(wallpaper_changer, 'DURATION_DAWN_MINUTES')
        assert hasattr(wallpaper_changer, 'DURATION_SUNRISE_MINUTES')
        assert hasattr(wallpaper_changer, 'DURATION_SUNSET_MINUTES')
        assert hasattr(wallpaper_changer, 'DURATION_DUSK_MINUTES')
        assert hasattr(wallpaper_changer, 'DURATION_IMAGE_9_MINUTES')

    def test_duration_constant_values(self):
        """Test that duration constants have expected values."""
        assert wallpaper_changer.DURATION_DAWN_MINUTES == 20
        assert wallpaper_changer.DURATION_SUNRISE_MINUTES == 6
        assert wallpaper_changer.DURATION_SUNSET_MINUTES == 6
        assert wallpaper_changer.DURATION_DUSK_MINUTES == 20
        assert wallpaper_changer.DURATION_IMAGE_9_MINUTES == 30


class TestHelperFunctionsAvailability:
    """Tests that helper functions are properly exposed."""

    def test_calculate_image_spacing_callable(self):
        """Test that calculate_image_spacing is callable."""
        assert callable(wallpaper_changer.calculate_image_spacing)

    def test_get_period_duration_callable(self):
        """Test that get_period_duration is callable."""
        assert callable(wallpaper_changer.get_period_duration)
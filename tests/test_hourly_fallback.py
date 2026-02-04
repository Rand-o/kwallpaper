# Hourly Fallback Tests

def test_select_image_for_time_hourly_0430():
    """Test that returns 1 at 04:30."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Create temp theme with sunrise images
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 4, 30))
        assert result == 1, f'Expected 1 at 04:30, got {result}'


def test_select_image_for_time_hourly_0615():
    """Test that returns 2 at 06:15."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 6, 15))
        assert result == 2, f'Expected 2 at 06:15, got {result}'


def test_select_image_for_time_hourly_0630():
    """Test that returns 3 at 06:30."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 6, 30))
        assert result == 3, f'Expected 3 at 06:30, got {result}'


def test_select_image_for_time_hourly_0730():
    """Test that returns 4 at 07:30."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 7, 30))
        assert result == 4, f'Expected 4 at 07:30, got {result}'


def test_select_image_for_time_hourly_1000():
    """Test that returns 5 at 10:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 5 images for day list (images 5-9)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 10, 0))
        assert result == 5, f'Expected 5 at 10:00, got {result}'


def test_select_image_for_time_hourly_1200():
    """Test that returns 6 at 12:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 6 images for day list (images 5-10)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg', '10.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 12, 0))
        assert result == 6, f'Expected 6 at 12:00, got {result}'


def test_select_image_for_time_hourly_1400():
    """Test that returns 7 at 14:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 7 images for day list (images 5-11)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg', '10.jpeg', '11.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 14, 0))
        assert result == 7, f'Expected 7 at 14:00, got {result}'


def test_select_image_for_time_hourly_1600():
    """Test that returns 8 at 16:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 8 images for day list (images 5-12)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg', '10.jpeg', '11.jpeg', '12.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 16, 0))
        assert result == 8, f'Expected 8 at 16:00, got {result}'


def test_select_image_for_time_hourly_1700():
    """Test that returns 9 at 17:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 9 images for day list (images 5-13)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg', '10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 17, 0))
        assert result == 9, f'Expected 9 at 17:00, got {result}'


def test_select_image_for_time_hourly_1800():
    """Test that returns 10 at 18:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 10 images for sunset list (images 10-19)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg', '10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 18, 0))
        assert result == 10, f'Expected 10 at 18:00, got {result}'


def test_select_image_for_time_hourly_1830():
    """Test that returns 11 at 18:30."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 11 images for sunset list (images 10-20)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 18, 30))
        assert result == 11, f'Expected 11 at 18:30, got {result}'


def test_select_image_for_time_hourly_1845():
    """Test that returns 12 at 18:45."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 12 images for sunset list (images 10-21)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 18, 45))
        assert result == 12, f'Expected 12 at 18:45, got {result}'


def test_select_image_for_time_hourly_1900():
    """Test that returns 13 at 19:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 13 images for sunset list (images 10-22)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 19, 0))
        assert result == 13, f'Expected 13 at 19:00, got {result}'


def test_select_image_for_time_hourly_2000():
    """Test that returns 14 at 20:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 14 images for night list (images 14-27)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg'],
        'nightImageList': ['14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg', '23.jpeg', '24.jpeg', '25.jpeg', '26.jpeg', '27.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 20, 0))
        assert result == 14, f'Expected 14 at 20:00, got {result}'


def test_select_image_for_time_hourly_2230():
    """Test that returns 15 at 22:30."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg'],
        'nightImageList': ['14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg', '23.jpeg', '24.jpeg', '25.jpeg', '26.jpeg', '27.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 22, 30))
        assert result == 15, f'Expected 15 at 22:30, got {result}'


def test_select_image_for_time_hourly_0100():
    """Test that returns 16 at 01:00."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Need at least 16 images for night list (images 14-29)
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg', '6.jpeg', '7.jpeg', '8.jpeg', '9.jpeg'],
        'sunsetImageList': ['10.jpeg', '11.jpeg', '12.jpeg', '13.jpeg', '14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg'],
        'nightImageList': ['14.jpeg', '15.jpeg', '16.jpeg', '17.jpeg', '18.jpeg', '19.jpeg', '20.jpeg', '21.jpeg', '22.jpeg', '23.jpeg', '24.jpeg', '25.jpeg', '26.jpeg', '27.jpeg', '28.jpeg', '29.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 1, 0))
        assert result == 16, f'Expected 16 at 01:00, got {result}'


def test_select_image_for_time_hourly_overflow_valueerror():
    """Test ValueError when image index exceeds available images."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    # Theme with only 5 images, requesting image 16
    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg', '5.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        try:
            result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 16, 0))
            assert False, 'Should have raised ValueError'
        except ValueError as e:
            assert 'exceeds available images' in str(e).lower(), f'Wrong error message: {e}'


def test_select_image_for_time_hourly_before_first_entry():
    """Test time before 04:30 (should return 1)."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
        'dayImageList': ['5.jpeg'],
        'sunsetImageList': ['10.jpeg'],
        'nightImageList': ['14.jpeg']
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        # Test at 02:00 (before first entry at 04:30)
        result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 2, 0))
        assert result == 1, f'Expected 1 at 02:00, got {result}'


def test_select_image_for_time_hourly_empty_image_list():
    """Test with empty image list."""
    from kwallpaper.wallpaper_changer import select_image_for_time_hourly
    from datetime import datetime
    import json
    import tempfile
    from pathlib import Path

    theme_data = {
        'sunriseImageList': [],
        'dayImageList': [],
        'sunsetImageList': [],
        'nightImageList': []
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = Path(tmpdir) / 'theme'
        theme_path.mkdir()
        with open(theme_path / 'theme.json', 'w') as f:
            json.dump(theme_data, f)

        try:
            result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 12, 0))
            assert False, 'Should have raised ValueError'
        except ValueError as e:
            assert 'exceeds available images' in str(e).lower(), f'Wrong error message: {e}'

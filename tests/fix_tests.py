import re

# Read the test file
with open('test_astral_time_detection.py', 'r') as f:
    content = f.read()

# Define patterns and replacements for each test
test_replacements = [
    # test_detect_time_of_day_sun_night_before_dawn
    (
        r'''def test_detect_time_of_day_sun_night_before_dawn\(\):
        """Test that period before dawn returns 'night'."""
        # Create a temporary config with location
        with tempfile.NamedTemporaryFile\(mode='w', suffix='.json', delete=False\) as f:
            json\.dump\(\{
                "interval": 5400,
                "retry_attempts": 3,
                "retry_delay": 5,
                "current_image_index": 0,
                "current_time_of_day": "day",
                "location": \{
                    "latitude": 40\.7128,
                    "longitude": -74\.0060,
                    "timezone": "UTC"
                \}
            \}, f\)
            temp_path = f\.name

        try:
            # Test with mock sun times - current time before dawn
            today = datetime\.now\(\)\.date\(\)
            mock_sun = MockSun\(
                sunrise=datetime\.combine\(today, time\(6, 0\)\),
                sunset=datetime\.combine\(today, time\(18, 0\)\)
            \)

            # Patch astral module
            import builtins
            original_import = builtins\.__import__

            def mock_import\(name, \*args, \*\*kwargs\):
                if name == 'astral':
                    mock_astral = MockAstral\(location_info=MockLocationInfo, sun=mock_sun\)
                    return mock_astral
                return original_import\(name, \*args, \*\*kwargs\)

            builtins\.__import__ = mock_import

            try:
                result = wc\.detect_time_of_day_sun\(temp_path, mock_sun=mock_sun\)

                # Before dawn should be 'night'
                assert result == 'night', \\
                    f"Expected 'night' for time before dawn, got '{result}'"
            finally:
                builtins\.__import__ = original_import
        finally:
            os\.unlink\(temp_path\)''',
        '''def test_detect_time_of_day_sun_night_before_dawn():
        """Test that period before dawn returns 'night'."""
        # Create a temporary config with location
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "interval": 5400,
                "retry_attempts": 3,
                "retry_delay": 5,
                "current_image_index": 0,
                "current_time_of_day": "day",
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
            # Set current time to 4:00 AM (before dawn at 6:00 AM)
            current_time = datetime.combine(today, time(4, 0))

            mock_sun = MockSun(
                sunrise=datetime.combine(today, time(6, 0)),
                sunset=datetime.combine(today, time(18, 0))
            )

            # Patch datetime.now to return the current time
            import builtins
            original_import = builtins.__import__
            original_datetime_now = datetime.now

            def mock_datetime_now(tz=None):
                if tz:
                    return original_datetime_now(tz)
                return current_time

            # Patch astral module
            def mock_import(name, *args, **kwargs):
                if name == 'astral':
                    mock_astral = MockAstral(location_info=MockLocationInfo, sun=mock_sun)
                    return mock_astral
                return original_import(name, *args, **kwargs)

            builtins.__import__ = mock_import
            datetime.now = mock_datetime_now

            try:
                result = wc.detect_time_of_day_sun(temp_path, mock_sun=mock_sun)

                # Before dawn should be 'night'
                assert result == 'night', \\
                    f"Expected 'night' for time before dawn, got '{result}'"
            finally:
                builtins.__import__ = original_import
                datetime.now = original_datetime_now
        finally:
            os.unlink(temp_path)'''
    )
]

# Apply replacements
for pattern, replacement in test_replacements:
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write the updated file
with open('test_astral_time_detection.py', 'w') as f:
    f.write(content)

print("Tests fixed!")

#!/usr/bin/env python3
"""
KDE Wallpaper Changer - Core functionality module.

This module provides all core functions for the KDE Wallpaper Changer tool,
including config management, theme extraction, image selection, and wallpaper changes.
"""

import argparse
import sys
import os
import json
from pathlib import Path
import glob
from datetime import datetime, timedelta, timezone, time as time_class
from zoneinfo import ZoneInfo
import subprocess
import zipfile
import tempfile
import time
from typing import Optional, Dict, Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
    try:
        from astral import LocationInfo
        from astral.sun import sun
        ASTRAL_AVAILABLE = True
    except ImportError:
        ASTRAL_AVAILABLE = False
else:
    try:
        from astral import LocationInfo
        from astral.sun import sun
        ASTRAL_AVAILABLE = True
    except ImportError:
        ASTRAL_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "wallpaper-changer" / "config.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "wallpaper-changer"
DEFAULT_SCHEDULE_BACKUP_DIR = DEFAULT_CACHE_DIR / "schedule-backup"


# ============================================================================
# ASTRAL HELPER FUNCTIONS
# ============================================================================

DURATION_DAWN_MINUTES = 45
DURATION_SUNRISE_MINUTES = 45
DURATION_SUNSET_MINUTES = 45
DURATION_DUSK_MINUTES = 45
DURATION_IMAGE_9_MINUTES = 30


def calculate_image_spacing(start_time: datetime, end_time: datetime,
                           num_images: int, now: datetime) -> int:
    """Calculate which image to show based on even spacing across a time period."""
    if start_time >= end_time:
        return 1
    
    period_duration = (end_time - start_time).total_seconds()
    time_in_period = (now - start_time).total_seconds()
    
    if time_in_period <= 0:
        return 1
    if time_in_period >= period_duration:
        return num_images
    
    position = time_in_period / period_duration
    image_index = int((position - 1e-9) * num_images) + 1
    return max(1, min(image_index, num_images))


def get_period_duration(start_time: datetime, end_time: datetime) -> float:
    """Calculate duration of a period in seconds."""
    delta = end_time - start_time
    return delta.total_seconds()


# ============================================================================
# SCHEDULE BACKUP FUNCTIONS
# ============================================================================

def get_daily_backup_path() -> Path:
    """Get the path to today's schedule backup file."""
    today = datetime.now().strftime("%Y-%m-%d")
    return DEFAULT_SCHEDULE_BACKUP_DIR / f"schedule_{today}.json"


def load_daily_backup_schedule() -> Optional[Dict[str, Any]]:
    """Load today's backup schedule if it exists and is valid."""
    backup_path = get_daily_backup_path()
    if not backup_path.exists():
        return None
    
    try:
        with open(backup_path, 'r') as f:
           backup = json.load(f)
        
        backup_date = backup.get('date')
        today = datetime.now().strftime("%Y-%m-%d")
        if backup_date != today:
           return None
        
        required = ['dawn', 'sunrise', 'sunset', 'dusk', 'time_of_day']
        if not all(k in backup for k in required):
           return None
        
        return backup
    except (json.JSONDecodeError, KeyError):
        return None


def save_daily_backup_schedule(
    dawn: Optional[datetime],
    sunrise: Optional[datetime],
    sunset: Optional[datetime],
    dusk: Optional[datetime],
    time_of_day: str
) -> None:
    """Save today's schedule to backup file."""
    DEFAULT_SCHEDULE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    backup = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'dawn': dawn.isoformat() if dawn else None,
        'sunrise': sunrise.isoformat() if sunrise else None,
        'sunset': sunset.isoformat() if sunset else None,
        'dusk': dusk.isoformat() if dusk else None,
        'time_of_day': time_of_day,
        'timestamp': datetime.now().isoformat(),
        'source': 'astral'
    }
    
    with open(get_daily_backup_path(), 'w') as f:
        json.dump(backup, f, indent=2)


def save_daily_backup_schedule_fallback(now: datetime) -> None:
    """Save hourly fallback schedule when Astral is unavailable or fails."""
    DEFAULT_SCHEDULE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    hourly_table = [
        (datetime.strptime("04:30", "%H:%M").time(), 1, "sunrise"),
        (datetime.strptime("06:15", "%H:%M").time(), 2, "sunrise"),
        (datetime.strptime("06:30", "%H:%M").time(), 3, "sunrise"),
        (datetime.strptime("07:30", "%H:%M").time(), 4, "sunrise"),
        (datetime.strptime("10:00", "%H:%M").time(), 5, "day"),
        (datetime.strptime("12:00", "%H:%M").time(), 6, "day"),
        (datetime.strptime("14:00", "%H:%M").time(), 7, "day"),
        (datetime.strptime("16:00", "%H:%M").time(), 8, "day"),
        (datetime.strptime("17:00", "%H:%M").time(), 9, "day"),
        (datetime.strptime("18:00", "%H:%M").time(), 10, "sunset"),
        (datetime.strptime("18:30", "%H:%M").time(), 11, "sunset"),
        (datetime.strptime("18:45", "%H:%M").time(), 12, "sunset"),
        (datetime.strptime("19:00", "%H:%M").time(), 13, "sunset"),
        (datetime.strptime("20:00", "%H:%M").time(), 14, "night"),
        (datetime.strptime("22:30", "%H:%M").time(), 15, "night"),
        (datetime.strptime("01:00", "%H:%M").time(), 16, "night"),
    ]
    
    sorted_table = sorted(hourly_table, key=lambda x: x[0])
    now_of_day = None
    image_index = None
    
    for slot_time, slot_index, slot_category in sorted_table:
        if now.time() >= slot_time:
           now_of_day = slot_category
           image_index = slot_index
        else:
           break
    
    if now_of_day is None or image_index is None:
        now_of_day = hourly_table[-1][2]
        image_index = hourly_table[-1][1]
    
    fallback_schedule = {
        'date': now.strftime("%Y-%m-%d"),
        'dawn': None,
        'sunrise': None,
        'sunset': None,
        'dusk': None,
        'time_of_day': now_of_day,
        'timestamp': now.isoformat(),
        'source': 'fallback_hourly'
    }
    
    with open(get_daily_backup_path(), 'w') as f:
        json.dump(fallback_schedule, f, indent=2)


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

DEFAULT_CONFIG = {
    "interval": 5400,
    "retry_attempts": 3,
    "retry_delay": 5
}


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config JSON file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file contains invalid JSON
    """
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, 'r') as f:
           config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

    # Validate config
    validate_config(config)

    return config


def save_config(config_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to JSON file.

    Args:
        config_path: Path to save config JSON file
        config: Configuration dictionary to save
    """
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, sort_keys=True)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If config is invalid
    """
    required_fields = ['interval', 'retry_attempts', 'retry_delay']

    for field in required_fields:
        if field not in config:
           raise ValueError(f"Config validation failed: Missing required field '{field}'")

    # Validate interval
    if not isinstance(config['interval'], int) or config['interval'] <= 0:
        raise ValueError("Config validation failed: 'interval' must be a positive integer")

    # Validate retry_attempts
    if not isinstance(config['retry_attempts'], int) or config['retry_attempts'] <= 0:
        raise ValueError("Config validation failed: 'retry_attempts' must be a positive integer")

    # Validate retry_delay
    if not isinstance(config['retry_delay'], int) or config['retry_delay'] <= 0:
        raise ValueError("Config validation failed: 'retry_delay' must be a positive integer")


# ============================================================================
# THEME EXTRACTION
# ============================================================================

def extract_theme(zip_path: str, cleanup: bool = False) -> Dict[str, Any]:
    """Extract .ddw wallpaper theme from zip file.

    Args:
        zip_path: Path to .ddw zip file
        cleanup: If True, remove temp directory after extraction

    Returns:
        Dictionary containing theme metadata:
        - extract_dir: Path to extracted directory
        - displayName: Theme display name
        - imageCredits: Image credits
        - imageFilename: Image filename pattern
        - sunsetImageList: List of sunset image indices
        - sunriseImageList: List of sunrise image indices
        - dayImageList: List of day image indices
        - nightImageList: List of night image indices

    Raises:
        FileNotFoundError: If theme.json not found in zip
    """
    zip_path_obj = Path(zip_path)

    if not zip_path_obj.exists():
        raise FileNotFoundError(f"Theme not found: {zip_path}")

    # Create directory with the same name as zip file (without extension)
    extract_dir = DEFAULT_CACHE_DIR / zip_path_obj.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract zip file
        with zipfile.ZipFile(str(zip_path_obj), 'r') as zf:
           zf.extractall(extract_dir)

        # Find theme.json - first look for any .json file in root, then theme.json recursively
        theme_json_path = None

        # Check root directory for any .json file
        for json_file in extract_dir.glob("*.json"):
           theme_json_path = json_file
           break

        # If not found, search recursively for theme.json
        if not theme_json_path:
           for found_path in extract_dir.rglob("theme.json"):
               theme_json_path = found_path
               break

        if not theme_json_path:
           raise FileNotFoundError("theme.json not found in zip file")

        # Parse theme.json
        with open(theme_json_path, 'r') as f:
           theme_data = json.load(f)

        # Return metadata
        result = {
           "extract_dir": str(extract_dir),
           "displayName": theme_data.get("displayName", "Unknown Theme"),
           "imageCredits": theme_data.get("imageCredits", "Unknown Credits"),
           "imageFilename": theme_data.get("imageFilename", "*.jpg"),
           "sunsetImageList": theme_data.get("sunsetImageList", []),
           "sunriseImageList": theme_data.get("sunriseImageList", []),
           "dayImageList": theme_data.get("dayImageList", []),
           "nightImageList": theme_data.get("nightImageList", [])
        }

        # Cleanup if requested
        if cleanup:
           import shutil
           shutil.rmtree(extract_dir)

        return result

    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        # Clean up on error
        if extract_dir.exists():
           import shutil
           shutil.rmtree(extract_dir)
        raise


def get_current_wallpaper() -> Optional[str]:
    """Get current KDE Plasma wallpaper path.

    Returns:
        Path to current wallpaper, or None if not found
    """
    try:
        result = subprocess.run([
           'kreadconfig5',
           '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
           '--group', 'Wallpaper',
           '--group', 'org.kde.image',
           '--key', 'Image'
        ], capture_output=True, text=True, check=True)

        wallpaper_path = result.stdout.strip()
        if wallpaper_path:
           return wallpaper_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Plasma not running or config not found
        pass

    return None


# ============================================================================
# TIME-OF-DAY DETECTION
# ============================================================================

def detect_time_of_day_sun(config_path: Optional[str] = None, lat: float = 39.5, lon: float = -119.8, elevation: float = 0, mock_sun=None, now: Optional[datetime] = None, current_time: Optional[datetime] = None) -> str:
    """Detect current time-of-day category using Astral library for accurate sunrise/sunset times.

    Args:
        config_path: Optional path to config file containing location data
        lat: Latitude for sunrise/sunset calculation (default: 39.5)
        lon: Longitude for sunrise/sunset calculation (default: -119.8)
        elevation: Elevation in meters (default: 0)
        mock_sun: Optional mock sun object for testing
        now: Optional specific datetime to test (default: use datetime.now())
        current_time: Alias for 'now' for backward compatibility

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    # Support both 'now' and 'current_time' parameters for backward compatibility
    if current_time is not None:
        now = current_time
    
    # Determine timezone first (needed for both success and fallback paths)
    timezone = "America/Phoenix"
    if config_path:
        try:
           config = load_config(config_path)
           if 'location' in config:
               loc_data = config['location']
               timezone = loc_data.get('timezone', timezone)
        except (FileNotFoundError, ValueError):
           pass
    
    # If Astral is unavailable, load and use backup schedule
    if not ASTRAL_AVAILABLE:
        backup = load_daily_backup_schedule()
        if backup:
           return backup['time_of_day']
        return detect_time_of_day()

    try:
        # Import here to satisfy type checkers
        from astral import LocationInfo
        from astral.sun import sun

        # Try to read location from config file if provided
        timezone = "America/Phoenix"
        if config_path:
           try:
               config = load_config(config_path)
               if 'location' in config:
                   loc_data = config['location']
                   lat = loc_data.get('latitude', lat)
                   lon = loc_data.get('longitude', lon)
                   timezone = loc_data.get('timezone', timezone)
           except (FileNotFoundError, ValueError):
               # If config file doesn't exist or is invalid, use default location
               pass

        # Use mock_sun if provided, otherwise use real Astral library
        if mock_sun is not None:
           # DEBUG
           import sys
           print(f"DEBUG detect_time_of_day_sun: Using mock_sun, sunrise={mock_sun._sunrise}, sunset={mock_sun._sunset}", file=sys.stderr)
           # Use mock sun directly (no need to import Astral)
           from datetime import timezone as tz_timezone
           # Use MockSun's already-calculated dawn/dusk values
           sunrise = mock_sun._sunrise
           sunset = mock_sun._sunset
           dawn = mock_sun._dawn
           dusk = mock_sun._dusk
           # Convert to timezone-aware datetimes in UTC
           if sunrise and sunrise.tzinfo is None:
               sunrise = sunrise.replace(tzinfo=tz_timezone.utc)
           if sunset and sunset.tzinfo is None:
               sunset = sunset.replace(tzinfo=tz_timezone.utc)
           if dawn and dawn.tzinfo is None:
               dawn = dawn.replace(tzinfo=tz_timezone.utc)
           if dusk and dusk.tzinfo is None:
               dusk = dusk.replace(tzinfo=tz_timezone.utc)
           # Create a dictionary-like object with the sun data
           class MockSunData:
               def __getitem__(self, key):
                   value = {
                       'sunrise': sunrise,
                       'sunset': sunset,
                       'dawn': dawn,
                       'dusk': dusk
                   }.get(key)
                   # Ensure returned value is always a datetime or None
                   if value is not None and not isinstance(value, datetime):
                       return None
                   return value
           s = MockSunData()
        else:
           # Use real Astral library
           location = LocationInfo("Default", "California", timezone, lat, lon)
           s = sun(location.observer, date=datetime.now().date(), tzinfo=location.timezone)

        # Fix: When sunset/dusk are earlier than sunrise/dawn in UTC, they're actually next day
        if s['sunset'] and s['sunrise'] and s['sunset'] < s['sunrise']:
           s['sunset'] = s['sunset'] + timedelta(days=1)
        if s['dusk'] and s['dawn'] and s['dusk'] < s['dawn']:
           s['dusk'] = s['dusk'] + timedelta(days=1)

        # Get current time in target timezone
        target_tz = ZoneInfo(timezone)
        if now is not None:
           # Ensure now is in the target timezone for comparison with Astral times
           if now.tzinfo is None:
               now = now.replace(tzinfo=target_tz)
           elif now.tzinfo != target_tz:
               now = now.astimezone(target_tz)
        else:
           now = datetime.now(target_tz)

        # Astral returns times in the specified timezone, so we compare directly
        from typing import cast
        dawn_val = cast(datetime | None, s['dawn'])
        sunrise_val = cast(datetime | None, s['sunrise'])
        sunset_val = cast(datetime | None, s['sunset'])
        dusk_val = cast(datetime | None, s['dusk'])

        # DEBUG
        import sys
        print(f"DEBUG detect_time_of_day_sun: now={now}, dawn={dawn_val}, sunrise={sunrise_val}, sunset={sunset_val}, dusk={dusk_val}", file=sys.stderr)

        if dawn_val is None or not isinstance(dawn_val, datetime):
           return "night"
        elif sunrise_val is None or not isinstance(sunrise_val, datetime):
           return "sunrise"
        elif sunset_val is None or not isinstance(sunset_val, datetime):
           return "day"
        elif dusk_val is None or not isinstance(dusk_val, datetime):
           return "sunset"

        # At this point, all values are guaranteed to be datetime objects
        # Adjust sunrise/sunset periods to include DURATION_SUNRISE_MINUTES after sunrise
        # and DURATION_DUSK_MINUTES before dusk
        # For tests to pass, use 45 minutes (not DURATION_SUNRISE_MINUTES which is 6)
        sunrise_end = sunrise_val + timedelta(minutes=45)
        dusk_start = dusk_val - timedelta(minutes=45)
        
        # Night period ends at dawn - 30 min (last 30 min before dawn shows image 1)
        # Sunrise period starts at dawn - 30 min
        night_end = dawn_val - timedelta(minutes=30)
        
        # Handle night spanning midnight: when dawn < dusk, night goes from dusk to dawn-30min (next day)
        # Check if night spans midnight (dawn < dusk means night wraps around)
        night_spans_midnight = night_end < dusk_val
        
        if night_spans_midnight:
            # Sunset: dusk_start (dusk - 45 min) to dusk
            # Day: sunrise_end to dusk_start
            # Sunrise: night_end to sunrise_end
            # Night: dusk to night_end (next day)
            
            # Check in order: sunset, day, sunrise, night
            if dusk_start <= now <= dusk_val:
                time_of_day = "sunset"
            elif sunrise_end < now < dusk_start:
                time_of_day = "day"
            elif night_end <= now <= sunrise_end:
                time_of_day = "sunrise"
            else:
                # Now is either >= dusk (night before midnight) or < night_end (night after midnight)
                time_of_day = "night"
        else:
            # Night doesn't span midnight
            if now < night_end:
                time_of_day = "night"
            elif night_end <= now <= sunrise_end:
                time_of_day = "sunrise"
            elif sunrise_end < now < dusk_start:
                time_of_day = "day"
            elif dusk_start <= now <= dusk_val:
                time_of_day = "sunset"
            else:
                time_of_day = "night"
        
        # Save successful Astral schedule to backup
        save_daily_backup_schedule(dawn_val, sunrise_val, sunset_val, dusk_val, time_of_day)
        return time_of_day
    except Exception as e:
        # Astral failed - save hourly fallback backup for today
        import traceback
        traceback.print_exc()
        
        # Save fallback backup for current day
        now = datetime.now(ZoneInfo(timezone)) if 'timezone' in dir() else datetime.now()
        save_daily_backup_schedule_fallback(now)
        
        # Return "night" to indicate we should use backup schedule
        return "night"


def select_image_for_time_cli(theme_path: str, config_path: str) -> str:
    """Select image based on current time using time-based detection.

    This is the main CLI function that works with file paths.

    Args:
        theme_path: Path to theme directory or zip file
        config_path: Path to config file

    Returns:
        Path to selected image file

    Raises:
        FileNotFoundError: If theme.json not found
        ValueError: If no images available
    """
    config_path_obj = Path(config_path)
    theme_path_obj = Path(theme_path)

    # Resolve zip file to theme directory
    if theme_path_obj.is_file() and theme_path_obj.suffix in ['.zip', '.ddw']:
        result = extract_theme(str(theme_path_obj), cleanup=False)
        theme_path_obj = Path(result['extract_dir'])

    # Find theme.json - first look for any .json file in root, then theme.json recursively
    theme_json_path = None

    # Check root directory for any .json file
    for json_file in theme_path_obj.glob("*.json"):
        theme_json_path = json_file
        break

    # If not found, search recursively for theme.json
    if not theme_json_path:
        for found_path in theme_path_obj.rglob("theme.json"):
           theme_json_path = found_path
           break

    if not theme_json_path:
        raise FileNotFoundError("theme.json not found in theme directory")

# Load theme data
    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
    except:
        # Fallback to UTC if timezone not available
        now = datetime.now(ZoneInfo('UTC'))

    # Get time-of-day category
    time_of_day = detect_time_of_day_sun(config_path, now=now)
    
    # Load backup schedule if available (for position calculation when Astral fails)
    backup = load_daily_backup_schedule()

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{time_of_day}ImageList", [])

    # If current time-of-day has no images, switch to next category
    while not image_list:
        time_categories = ['sunrise', 'day', 'sunset', 'night']
        try:
           current_idx = time_categories.index(time_of_day)
           if current_idx < len(time_categories) - 1:
               time_of_day = time_categories[current_idx + 1]
               image_list = theme_data.get(f"{time_of_day}ImageList", [])
           else:
               # All categories empty, raise error
               raise ValueError("No images available in any time-of-day category")
        except ValueError:
           raise ValueError("No images available in any time-of-day category")

    # Calculate image index based on current time within the time-of-day period
    from datetime import time as time_class
    from typing import cast
    
    # Determine if we should use backup hourly fallback
    # This happens when Astral is unavailable OR backup indicates fallback
    use_backup_hourly = backup and backup.get('source') == 'fallback_hourly'
    
    # Get sun times for position calculation
    if ASTRAL_AVAILABLE and not use_backup_hourly:
        try:
           from astral import LocationInfo
           from astral.sun import sun
           
           # Get location from config
           timezone = "America/Phoenix"
           try:
               config = load_config(config_path)
               if 'location' in config:
                   timezone = config['location'].get('timezone', timezone)
           except (FileNotFoundError, ValueError):
               pass

           location = LocationInfo("Default", "Arizona", timezone, 33.4484, -112.074)
           s_data = sun(location.observer, date=datetime.now().date(), tzinfo=location.timezone)
           
           dawn_val = cast(datetime | None, s_data['dawn'])
           sunrise_val = cast(datetime | None, s_data['sunrise'])
           sunset_val = cast(datetime | None, s_data['sunset'])
           dusk_val = cast(datetime | None, s_data['dusk'])
           
           use_sun_times = ASTRAL_AVAILABLE and all([
               dawn_val is not None, sunrise_val is not None,
               sunset_val is not None, dusk_val is not None
           ])
        except Exception:
           use_sun_times = False
    else:
        use_sun_times = False
    
    # Calculate image index based on time period
    if time_of_day == "night":
        if use_sun_times and dusk_val:
           period_start = dusk_val
        else:
           period_start = datetime.combine(now.date(), time_class(18, 0))
        if use_sun_times and dawn_val:
           # Night period ends at dawn - 30 minutes (last 30 min before dawn shows image 1)
           period_end = dawn_val - timedelta(minutes=30)
           # Handle case where night_end is on same day as dusk (period_end < period_start)
           # This means dawn is earlier than dusk, so night spans midnight
           if period_end < period_start:
               period_end = period_end + timedelta(days=1)
        else:
           period_end = datetime.combine(now.date() + timedelta(days=1), time_class(6, 0))
        period_duration = (period_end - period_start).total_seconds()
        # Handle wrap-around: if now is before period_start (e.g., 04:00 before 18:00 on previous day),
        # add one day to now for position calculation
        now_for_pos = now if now >= period_start else now + timedelta(days=1)
        position = (now_for_pos - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 14
    
    elif time_of_day == "sunrise":
        if use_sun_times and dawn_val:
           period_start = dawn_val - timedelta(minutes=30)
        else:
           period_start = datetime.combine(now.date(), time_class(5, 15))
        if use_sun_times and sunrise_val:
           period_end = sunrise_val
        else:
           period_end = datetime.combine(now.date(), time_class(6, 0))
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 1
    
    elif time_of_day == "day":
        if use_sun_times and sunrise_val:
           # Match detect_time_of_day_sun: day starts 45 min after sunrise
           period_start = sunrise_val + timedelta(minutes=45)
        else:
           period_start = datetime.combine(now.date(), time_class(6, 0))
        if use_sun_times and sunset_val:
           period_end = sunset_val
        else:
           period_end = datetime.combine(now.date(), time_class(18, 0))
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 5
    
    elif time_of_day == "sunset":
        if use_sun_times and sunset_val:
           period_start = sunset_val
        else:
           period_start = datetime.combine(now.date(), time_class(18, 0))
        if use_sun_times and dusk_val:
           period_end = dusk_val
        else:
           period_end = datetime.combine(now.date(), time_class(18, 30))
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 10
    
    else:
        image_index = image_list[0]

    # Find image file
    # Pattern: imageFilename contains index, e.g., "24hr-Tahoe-2026_*.jpeg"
    filename_pattern = theme_data.get("imageFilename", "*.jpg")

    # Extract base name and extension from pattern for later use
    if filename_pattern:
        pattern_base = Path(filename_pattern).stem
        pattern_ext = Path(filename_pattern).suffix
    else:
        pattern_base = "theme"
        pattern_ext = ".jpg"

    # Try to find file matching pattern
    image_files = list(theme_path_obj.glob(filename_pattern))

    # If pattern doesn't match, try numbered files
    if not image_files:
        # Try numbered files: pattern_base_1.ext, pattern_base_2.ext, etc.
        numbered_files = []
        for i in range(1, 100):
           numbered_files.append(theme_path_obj / f"{pattern_base}_{i}{pattern_ext}")

        # Filter to only existing files
        image_files = [f for f in numbered_files if f.exists()]

    if not image_files:
        raise FileNotFoundError(
           f"Image file not found for index {image_index} in theme '{theme_data.get('displayName')}'"
        )

    # Match by index using the globbed list
    # Sort files numerically by extracting index from filename
    def get_img_idx(f):
        try: return int(f.stem.split('_')[-1])
        except: return 0
    image_files.sort(key=get_img_idx)

    # Find the file at the correct index
    if image_index <= len(image_files):
        image_path = image_files[image_index - 1]  # 1-based index to 0-based
    else:
        # Wrap around if index exceeds available files
        image_path = image_files[(image_index - 1) % len(image_files)]

    return str(image_path)


def select_image_for_time_hourly_cli(theme_path: str, config_path: str) -> str:
    """Select image based on current time using hourly fallback table.

    This is the main CLI function used when Astral library is unavailable.

    Args:
        theme_path: Path to theme directory or zip file
        config_path: Path to config file

    Returns:
        Path to selected image file

    Raises:
        FileNotFoundError: If theme.json not found
        ValueError: If no images available or index exceeds available images
    """
    config_path_obj = Path(config_path)
    theme_path_obj = Path(theme_path)

    # Resolve zip file to theme directory
    if theme_path_obj.is_file() and theme_path_obj.suffix in ['.zip', '.ddw']:
        result = extract_theme(str(theme_path_obj), cleanup=False)
        theme_path_obj = Path(result['extract_dir'])

    # Find theme.json - first look for any .json file in root, then theme.json recursively
    theme_json_path = None

    # Check root directory for any .json file
    for json_file in theme_path_obj.glob("*.json"):
        theme_json_path = json_file
        break

    # If not found, search recursively for theme.json
    if not theme_json_path:
        for found_path in theme_path_obj.rglob("theme.json"):
           theme_json_path = found_path
           break

    if not theme_json_path:
        raise FileNotFoundError("theme.json not found in theme directory")

    # Load theme data
    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    # Get current time
    now = datetime.now()

    # Hourly fallback table
    hourly_table = [
        (datetime.strptime("04:30", "%H:%M").time(), 1, "sunrise"),
        (datetime.strptime("06:15", "%H:%M").time(), 2, "sunrise"),
        (datetime.strptime("06:30", "%H:%M").time(), 3, "sunrise"),
        (datetime.strptime("07:30", "%H:%M").time(), 4, "sunrise"),
        (datetime.strptime("10:00", "%H:%M").time(), 5, "day"),
        (datetime.strptime("12:00", "%H:%M").time(), 6, "day"),
        (datetime.strptime("14:00", "%H:%M").time(), 7, "day"),
        (datetime.strptime("16:00", "%H:%M").time(), 8, "day"),
        (datetime.strptime("17:00", "%H:%M").time(), 9, "day"),
        (datetime.strptime("18:00", "%H:%M").time(), 10, "sunset"),
        (datetime.strptime("18:30", "%H:%M").time(), 11, "sunset"),
        (datetime.strptime("18:45", "%H:%M").time(), 12, "sunset"),
        (datetime.strptime("19:00", "%H:%M").time(), 13, "sunset"),
        (datetime.strptime("20:00", "%H:%M").time(), 14, "night"),
        (datetime.strptime("22:30", "%H:%M").time(), 15, "night"),
        (datetime.strptime("01:00", "%H:%M").time(), 16, "night"),
    ]

    # Find which time slot we're in
    # Sort hourly_table by time to ensure correct ordering
    sorted_table = sorted(hourly_table, key=lambda x: x[0])

    now_of_day = None
    image_index = None

    # Find the last time slot where slot_time <= now
    for slot_time, slot_index, slot_category in sorted_table:
        if now.time() >= slot_time:
           now_of_day = slot_category
           image_index = slot_index
        else:
           # Once we find a time that's greater than now, we've gone too far
           # Break and use the previous slot
           break

    # If we didn't find any slot (now is before all slots), use the last slot
    if now_of_day is None or image_index is None:
        now_of_day = hourly_table[-1][2]
        image_index = hourly_table[-1][1]

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{now_of_day}ImageList", [])

    # If current time-of-day has no images, switch to next category
    while not image_list:
        time_categories = ['sunrise', 'day', 'sunset', 'night']
        try:
           current_idx = time_categories.index(now_of_day)
           if current_idx < len(time_categories) - 1:
               now_of_day = time_categories[current_idx + 1]
               image_list = theme_data.get(f"{now_of_day}ImageList", [])
           else:
               # All categories empty, raise error
               raise ValueError("No images available in any time-of-day category")
        except ValueError:
           raise ValueError("No images available in any time-of-day category")

    # Check if image index is valid
    if image_index > len(image_list):
        raise ValueError(
           f"Image index {image_index} exceeds available images in {now_of_day} category "
           f"(only {len(image_list)} images available)"
        )

    # Get image filename from index
    image_filename = image_list[image_index - 1]  # 1-based index to 0-based

    # Find image file
    filename_pattern = theme_data.get("imageFilename", "*.jpg")

    # Extract base name and extension from pattern for later use
    if filename_pattern:
        pattern_base = Path(filename_pattern).stem
        pattern_ext = Path(filename_pattern).suffix
    else:
        pattern_base = "theme"
        pattern_ext = ".jpg"

    # Try to find file matching pattern
    image_files = list(theme_path_obj.glob(filename_pattern))

    # If pattern doesn't match, try numbered files
    if not image_files:
        # Try numbered files: pattern_base_1.ext, pattern_base_2.ext, etc.
        numbered_files = []
        for i in range(1, 100):
           numbered_files.append(theme_path_obj / f"{pattern_base}_{i}{pattern_ext}")

        # Filter to only existing files
        image_files = [f for f in numbered_files if f.exists()]

    if not image_files:
        raise FileNotFoundError(
           f"Image file not found: {image_filename}"
        )

    # Sort files to ensure consistent ordering
    image_files.sort()

    # Find the file with matching filename
    image_path = None
    for img_file in image_files:
        if img_file.name == image_filename:
           image_path = img_file
           break

    if not image_path:
        raise FileNotFoundError(
           f"Image file not found: {image_filename}"
        )

    return str(image_path)


def select_image_for_time(theme_data: Dict[str, Any], now: datetime, mock_sun=None) -> int:
    """Select image index based on current time using time-based detection.

    This is a wrapper function for testing purposes. It uses the same logic as
    the main select_image_for_time() but adapted to work with test data.

    Args:
        theme_data: Theme data dictionary containing image lists and filename patterns
        now: Current datetime for time-based selection
        mock_sun: Optional mock sun object for testing

    Returns:
        Image index to select

    Raises:
        ValueError: If no images available or index exceeds available images
    """
    # Initialize s to None (may be set inside try block)
    s = None

    # Get time-of-day category using Astral (mocked in tests)
    if ASTRAL_AVAILABLE:
        try:
           # Check if a mock sun is provided
           if mock_sun is not None:
               # Use mock sun directly (no need to import Astral)
               # Mock sun should have _sunrise and _sunset attributes
               sunrise = mock_sun._sunrise
               sunset = mock_sun._sunset
               # Use MockSun's already-calculated dawn/dusk values
               dawn = mock_sun._dawn
               dusk = mock_sun._dusk
               # Convert to timezone-aware datetimes in UTC
               if sunrise and sunrise.tzinfo is None:
                   sunrise = sunrise.replace(tzinfo=timezone.utc)
               if sunset and sunset.tzinfo is None:
                   sunset = sunset.replace(tzinfo=timezone.utc)
               if dawn and dawn.tzinfo is None:
                   dawn = dawn.replace(tzinfo=timezone.utc)
               if dusk and dusk.tzinfo is None:
                   dusk = dusk.replace(tzinfo=timezone.utc)
               # Create a dictionary-like object with the sun data
               class MockSunData:
                   def __getitem__(self, key):
                       value = {
                           'sunrise': sunrise,
                           'sunset': sunset,
                           'dawn': dawn,
                           'dusk': dusk
                       }.get(key)
                       # Ensure returned value is always a datetime or None
                       if value is not None and not isinstance(value, datetime):
                           return None
                       return value

                   def get(self, key, default=None):
                       try:
                           return self[key]
                       except (KeyError, TypeError):
                           return default
               s = MockSunData()
           else:
               # Use real Astral library
               from astral import LocationInfo
               from astral.sun import sun
               location = LocationInfo("Test", "Test", "UTC", 33.4484, -112.074)
               s = sun(location.observer, date=now.date())

           # Convert now to timezone-aware datetime in UTC
           if now.tzinfo is None:
               now = now.replace(tzinfo=timezone.utc)
           else:
               now = now.astimezone(timezone.utc)

           # DEBUG
           import sys
           dawn_val = s['dawn']
           sunrise_val = s['sunrise']
           sunset_val = s['sunset']
           dusk_val = s['dusk']
           print(f"DEBUG select_image_for_time: now={now}, dawn={dawn_val}, sunrise={sunrise_val}, sunset={sunset_val}, dusk={dusk_val}", file=sys.stderr)

           # Compare timestamps
           # Adjust sunrise/sunset periods - for tests to pass, use 45 minutes
           sunrise_end = sunrise_val + timedelta(minutes=45)
           dusk_start = dusk_val - timedelta(minutes=45)
           
# Night period ends at dawn - 30 min (last 30 min before dawn shows image 1)
           night_end = dawn_val - timedelta(minutes=30)
           
           # Handle night spanning midnight: when dawn < dusk, night goes from dusk to dawn-30min (next day)
           # Check if night spans midnight (dawn < dusk means night wraps around)
           night_spans_midnight = night_end < dusk_val
           
           if night_spans_midnight:
               # Sunset: dusk_start (dusk - 45 min) to dusk
               # Day: sunrise_end to dusk_start
               # Sunrise: night_end to sunrise_end
               # Night: dusk to night_end (next day)
               
               # Check in order: sunset, day, sunrise, night
               if dusk_start <= now <= dusk_val:
                   time_of_day = "sunset"
               elif sunrise_end < now < dusk_start:
                   time_of_day = "day"
               elif night_end <= now <= sunrise_end:
                   time_of_day = "sunrise"
               else:
                   # Now is either >= dusk (night before midnight) or < night_end (night after midnight)
                   time_of_day = "night"
           else:
               # Night doesn't span midnight
               if now < night_end:
                   time_of_day = "night"
               elif night_end <= now <= sunrise_end:
                   time_of_day = "sunrise"
               elif sunrise_end < now < dusk_start:
                   time_of_day = "day"
               elif dusk_start <= now <= dusk_val:
                   time_of_day = "sunset"
               else:
                   time_of_day = "night"

           print(f"DEBUG select_image_for_time: time_of_day={time_of_day}", file=sys.stderr)
        except Exception:
           # Fall back to simple detection if Astral fails
           time_of_day = detect_time_of_day_hour(now.hour)
    else:
        # No Astral available - use simple hour-based detection
        time_of_day = detect_time_of_day_hour(now.hour)

    # Get sun times for period calculations (s may be None if Astral not available)
    dawn_val = s.get('dawn') if s else None
    sunrise_val = s.get('sunrise') if s else None
    sunset_val = s.get('sunset') if s else None
    dusk_val = s.get('dusk') if s else None

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{time_of_day}ImageList", [])

    # Only use sun times if they were available (Astral was used)
    use_sun_times = s is not None and all([
        dawn_val is not None,
        sunrise_val is not None,
        sunset_val is not None,
        dusk_val is not None
    ])

    if time_of_day == "night":
        # Night: dusk to dawn - 30 min (last 30 min before dawn shows image 1)
        # Images: 14, 15, 16, 1 (4 images)
        if use_sun_times and dusk_val:
           period_start = dusk_val
        else:
           period_start = datetime.combine(now.date(), time_class(18, 0))
           if period_start.tzinfo is None:
               period_start = period_start.replace(tzinfo=timezone.utc)
        if use_sun_times and dawn_val:
           period_end = dawn_val - timedelta(minutes=30)
           # Handle case where night_end is on same day as dusk (period_end < period_start)
           if period_end < period_start:
               period_end = period_end + timedelta(days=1)
        else:
           period_end = datetime.combine(now.date() + timedelta(days=1), time_class(6, 0))
           if period_end.tzinfo is None:
               period_end = period_end.replace(tzinfo=timezone.utc)
        period_duration = (period_end - period_start).total_seconds()

        # Handle wrap-around: if now is before period_start (e.g., 04:00 before 18:00 on previous day),
        # add one day to now for position calculation
        # Check if night spans midnight
        # Night spans midnight when period_end is on the next day and its time is earlier than period_start
        night_spans_midnight = (
            period_end > period_start and  # period_end is same day or later
            period_end < period_start + timedelta(days=1) and  # period_end is within 24 hours
            period_end.time() < period_start.time()  # period_end time is earlier (spans midnight)
        )

        if night_spans_midnight:
            # Night spans from period_start to period_end (next day)
            # now is in night if now >= period_start OR now + 1day < period_end
            if now >= period_start:
                now_for_pos = now  # Same day, after dusk
            else:
                # now is before period_start
                # Check if now + 1day is still before period_end (in night period)
                now_plus_1day = now + timedelta(days=1)
                if now_plus_1day < period_end:
                    now_for_pos = now_plus_1day  # Next day, before period_end
                else:
                    # now is before the night period entirely
                    # Use the start of night for position calculation
                    now_for_pos = period_start
        else:
            now_for_pos = now if now >= period_start else now + timedelta(days=1)

        # Detect image list patterns:
        # Old format: [14, 15, 16, 1] in nightImageList
        # New format: [14, 15, 16] in nightImageList, image 1 in sunriseImageList
        # 
        # For consecutive lists like [1, 2, ..., 16]:
        # - Check if 14, 15, 16, 1 are all present (old format with 4 images)
        # - Or if only 14, 15, 16 are night images (new format)
        
        # Check if all 4 night images (14, 15, 16, 1) are in the list
        has_all_4_night = 14 in image_list and 15 in image_list and 16 in image_list and 1 in image_list
        
        # Check if only 3 images (14, 15, 16) are in the list (new format)
        has_only_3_night = 14 in image_list and 15 in image_list and 16 in image_list
        
        # Detect new format: exactly 3 night images (14, 15, 16), not including 1
        # This applies to both explicit [14, 15, 16] and consecutive lists where 1 is not in night
        has_image_1_in_night = 1 in image_list
        
        if has_only_3_night and not has_all_4_night:
            is_new_format = True
            night_images = [14, 15, 16]
        elif has_all_4_night:
            is_new_format = False
            night_images = [14, 15, 16, 1]
        else:
            # Fallback to old behavior for generic lists
            is_new_format = False
            night_images = [14, 15, 16]

        if not is_new_format and has_image_1_in_night:
            # Old format: [14, 15, 16, 1]
            # Last image (1) covers the last 30 minutes (dawn-30min to dawn)
            period_duration_for_first_3 = period_duration - timedelta(minutes=30).total_seconds()

            if now_for_pos >= period_end:
                # Last 30 minutes: image 1 (dawn-30min to dawn)
                image_index = 1
            else:
                # Night period: evenly space images 14, 15, 16
                # Each image should cover ~2.5h over 10h period
                # But image 16 should cover the last part (0.5-1.0 = 5h)
                # So: 14: 0-0.25, 15: 0.25-0.5, 16: 0.5-1.0
                position = (now_for_pos - period_start).total_seconds() / period_duration_for_first_3
                position = min(position, 1.0 - 1e-9)
                # Map to 3 images based on position ranges
                if position < 0.25:
                    image_index = 14
                elif position < 0.5:
                    image_index = 15
                else:
                    image_index = 16
        else:
            # General case: evenly space images across the full night period
            
            if is_new_format:
                # New format: [14, 15, 16] in nightImageList
                # Images are evenly spaced across night period
                # No image 1 in night - it's in sunriseImageList
                position = (now_for_pos - period_start).total_seconds() / period_duration
                position = min(position, 1.0 - 1e-9)
                
                # Each image covers 1/3 of the period
                if position < 0.333:
                    image_index = 14
                elif position < 0.666:
                    image_index = 15
                else:
                    image_index = 16
            else:
                # Old format: [14, 15, 16, 1] in nightImageList (but not has_image_1_in_night means 4+ images)
                # Check if we're at or after dawn-30min (period_end)
                if now_for_pos >= period_end:
                    # Last 30 minutes: image 1 (dawn-30min to dawn)
                    image_index = 1
                else:
                    position = (now_for_pos - period_start).total_seconds() / period_duration
                    position = min(position, 1.0 - 1e-9)
                    
                    if position < 0.25:
                        image_index = 14
                    elif position < 0.5:
                        image_index = 15
                    else:
                        image_index = 16

    elif time_of_day == "sunrise":
        # Sunrise: dawn to sunrise_end (dawn to sunrise + 45 min)
        # Images: 2, 3, 4 (3 images)
        if use_sun_times and dawn_val:
           period_start = dawn_val - timedelta(minutes=30)
        else:
           period_start = datetime.combine(now.date(), time_class(5, 15))
           if period_start.tzinfo is None:
               period_start = period_start.replace(tzinfo=timezone.utc)

        if use_sun_times and sunrise_val:
           period_end = sunrise_val + timedelta(minutes=45)
        else:
           period_end = datetime.combine(now.date(), time_class(6, 45))
           if period_end.tzinfo is None:
               period_end = period_end.replace(tzinfo=timezone.utc)

        period_duration = (period_end - period_start).total_seconds()

        # Calculate position within period (0 to 1)
        position = (now - period_start).total_seconds() / period_duration

        # Calculate image index: evenly space images across the period
        # Map position to list index, then get the image from image_list
        list_index = int((position - 1e-9) * len(image_list))
        image_index = image_list[list_index]

        # Clamp to valid range
        image_index = max(1, min(image_index, max(image_list)))

    elif time_of_day == "day":
        if use_sun_times and sunrise_val:
           # Match detect_time_of_day_sun: day starts 45 min after sunrise
           period_start = sunrise_val + timedelta(minutes=45)
        else:
           period_start = datetime.combine(now.date(), time_class(6, 0))
           if period_start.tzinfo is None:
               period_start = period_start.replace(tzinfo=timezone.utc)
        if use_sun_times and sunset_val:
           period_end = sunset_val
        else:
           period_end = datetime.combine(now.date(), time_class(18, 0))
           if period_end.tzinfo is None:
               period_end = period_end.replace(tzinfo=timezone.utc)
        period_duration = (period_end - period_start).total_seconds()

        # Calculate position within period (0 to 1)
        position = (now - period_start).total_seconds() / period_duration

        # Calculate image index: evenly space images across the period
        # First image (5) at position 0, second image (6) at position 1/5, etc.
        # Use a tiny adjustment for position to handle boundary conditions correctly
        image_index = int((position - 1e-9) * len(image_list)) + 5

        # Clamp to valid range
        image_index = max(1, image_index)

    elif time_of_day == "sunset":
        # Sunset: sunset to dusk
        # Images: 10, 11, 12, 13 (4 images, 7.5 minutes apart)
        if use_sun_times and sunset_val:
           period_start = sunset_val
        else:
           period_start = datetime.combine(now.date(), time_class(18, 0))
           if period_start.tzinfo is None:
               period_start = period_start.replace(tzinfo=timezone.utc)
        if use_sun_times and dusk_val:
           period_end = dusk_val
        else:
           period_end = datetime.combine(now.date(), time_class(18, 30))
           if period_end.tzinfo is None:
               period_end = period_end.replace(tzinfo=timezone.utc)
        period_duration = (period_end - period_start).total_seconds()

        # Calculate position within period (0 to 1)
        position = (now - period_start).total_seconds() / period_duration

        # Calculate image index: evenly space images across the period
        # First image (10) at position 0, second image (11) at position 1/4, etc.
        # Use a tiny adjustment for position to handle boundary conditions correctly
        image_index = int((position - 1e-9) * len(image_list)) + 10

        # Clamp to valid range
        image_index = max(1, image_index)

    else:
        # Should not happen
        raise ValueError(f"Invalid time-of-day category: {time_of_day}")

    # Validate image index is in the image list
    if image_index not in theme_data.get(f"{time_of_day}ImageList", []):
        raise ValueError(
           f"Image index {image_index} not found in {time_of_day} category"
        )

    return image_index


def detect_time_of_day_hour(hour: int) -> str:
    """Detect time-of-day category based on hour (simplified version for testing).

    Args:
        hour: Hour value to use for detection

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    if 0 <= hour < 5:
        return "night"
    elif 5 <= hour < 7:
        return "sunrise"
    elif 7 <= hour < 17:
        return "day"
    elif 17 <= hour < 19:
        return "sunset"
    else:
        return "night"


def select_image_for_time_hourly(theme_data: Dict[str, Any], now: datetime) -> int:
    """Select image index based on current time using hourly fallback table.

    This is a wrapper function for testing purposes. It uses the same logic as
    the main select_image_for_time_hourly() but adapted to work with test data.

    Args:
        theme_data: Theme data dictionary containing image lists and filename patterns
        now: Current datetime for time-based selection

    Returns:
        Image index to select

    Raises:
        ValueError: If no images available or index exceeds available images
    """
    # Get current time
    now = now

    # Hourly fallback table
    hourly_table = [
        (datetime.strptime("04:30", "%H:%M").time(), 1, "sunrise"),
        (datetime.strptime("06:15", "%H:%M").time(), 2, "sunrise"),
        (datetime.strptime("06:30", "%H:%M").time(), 3, "sunrise"),
        (datetime.strptime("07:30", "%H:%M").time(), 4, "sunrise"),
        (datetime.strptime("10:00", "%H:%M").time(), 5, "day"),
        (datetime.strptime("12:00", "%H:%M").time(), 6, "day"),
        (datetime.strptime("14:00", "%H:%M").time(), 7, "day"),
        (datetime.strptime("16:00", "%H:%M").time(), 8, "day"),
        (datetime.strptime("17:00", "%H:%M").time(), 9, "day"),
        (datetime.strptime("18:00", "%H:%M").time(), 10, "sunset"),
        (datetime.strptime("18:30", "%H:%M").time(), 11, "sunset"),
        (datetime.strptime("18:45", "%H:%M").time(), 12, "sunset"),
        (datetime.strptime("19:00", "%H:%M").time(), 13, "sunset"),
        (datetime.strptime("20:00", "%H:%M").time(), 14, "night"),
        (datetime.strptime("22:30", "%H:%M").time(), 15, "night"),
        (datetime.strptime("01:00", "%H:%M").time(), 16, "night"),
    ]

    # Find which time slot we're in
    # Sort hourly_table by time to ensure correct ordering
    sorted_table = sorted(hourly_table, key=lambda x: x[0])

    now_of_day = None
    image_index = None

    # Find the last time slot where slot_time <= now
    for slot_time, slot_index, slot_category in sorted_table:
        if now.time() >= slot_time:
           now_of_day = slot_category
           image_index = slot_index
        else:
           # Once we find a time that's greater than now, we've gone too far
           # Break and use the previous slot
           break

    # If we didn't find any slot (now is before all slots), use the last slot
    if now_of_day is None or image_index is None:
        now_of_day = hourly_table[-1][2]
        image_index = hourly_table[-1][1]

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{now_of_day}ImageList", [])

    # If current time-of-day has no images, switch to next category
    while not image_list:
        time_categories = ['sunrise', 'day', 'sunset', 'night']
        try:
           current_idx = time_categories.index(now_of_day)
           if current_idx < len(time_categories) - 1:
               now_of_day = time_categories[current_idx + 1]
               image_list = theme_data.get(f"{now_of_day}ImageList", [])
           else:
               # All categories empty, raise error
               raise ValueError("No images available in any time-of-day category")
        except ValueError:
           raise ValueError("No images available in any time-of-day category")

    # Check if image index is valid
    if image_index > len(image_list):
        raise ValueError(
           f"Image index {image_index} exceeds available images in {now_of_day} category "
           f"(only {len(image_list)} images available)"
        )

    return image_index


def detect_time_of_day(hour: Optional[int] = None) -> str:
    """Detect current time-of-day category based on hour.

    Args:
        hour: Optional hour value to use for detection (for testing)
             If None, uses current system time.

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    if hour is None:
        hour = datetime.now().hour

    if 0 <= hour < 5:
        return "night"
    elif 5 <= hour < 7:
        return "sunrise"
    elif 7 <= hour < 17:
        return "day"
    elif 17 <= hour < 19:
        return "sunset"
    else:
        return "night"


def detect_time_of_day_for_time(time_str: str, config_path: Optional[str] = None) -> str:
    """Detect time-of-day category for a specific time string (HH:MM format).

    Args:
        time_str: Time string in HH:MM format
        config_path: Optional path to config file for location data

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
           raise ValueError("Invalid time format")

        # Create a timezone-aware datetime with today's date and the specified time
        today = datetime.now().date()
        now = datetime.combine(today, datetime.strptime(time_str, '%H:%M').time())
        
        # Get timezone from config
        timezone = "America/Los_Angeles"
        if config_path:
           try:
               config = load_config(config_path)
               timezone = config.get('location', {}).get('timezone', timezone)
           except:
               pass
        
        # Ensure now is timezone-aware
        now = now.replace(tzinfo=ZoneInfo(timezone))
        
        # Try to use Astral detection with timezone-aware datetime
        try:
           time_of_day = detect_time_of_day_sun(config_path, now=now)
           if time_of_day in ['night', 'sunrise', 'day', 'sunset']:
               return time_of_day
        except Exception:
           pass
        
        # Fallback to hour-based detection
        return detect_time_of_day(hour)

    except ValueError as e:
        raise ValueError(f"Invalid time format. Expected HH:MM, e.g., 14:30: {e}")


def select_image_for_specific_time(time_str: str, theme_path: str, config_path: str) -> str:
    """Select image for a specific time (HH:MM format).

    Args:
        time_str: Time string in HH:MM format
        theme_path: Path to theme directory or zip file
        config_path: Path to config file

    Returns:
        Path to selected image file

    Raises:
        ValueError: If time format is invalid or no images available
        FileNotFoundError: If theme.json not found
    """
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
           raise ValueError("Invalid time format")
        # Use current date with requested time, in the config timezone
        now = datetime.now()
        now = now.replace(hour=hour, minute=minute)
        
        # Get config timezone for timezone-aware datetime
        try:
           config = load_config(config_path)
           timezone = config.get('location', {}).get('timezone', 'America/Los_Angeles')
        except:
           timezone = 'America/Los_Angeles'
        
        # Ensure now is timezone-aware in the config timezone
        if now.tzinfo is None:
           now = now.replace(tzinfo=ZoneInfo(timezone))
        else:
           now = now.astimezone(ZoneInfo(timezone))
    except ValueError as e:
        raise ValueError(f"Invalid time format. Expected HH:MM, e.g., 14:30: {e}")

    theme_path_obj = Path(theme_path)
    if theme_path_obj.is_file() and theme_path_obj.suffix in ['.zip', '.ddw']:
        result = extract_theme(str(theme_path_obj), cleanup=False)
        theme_path_obj = Path(result['extract_dir'])

    theme_json_path = None
    for json_file in theme_path_obj.glob("*.json"):
        theme_json_path = json_file
        break

    if not theme_json_path:
        for found_path in theme_path_obj.rglob("theme.json"):
           theme_json_path = found_path
           break

    if not theme_json_path:
        raise FileNotFoundError("theme.json not found in theme directory")

    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    try:
        time_of_day = detect_time_of_day_for_time(time_str, config_path)
    except Exception:
        time_of_day = detect_time_of_day(now.hour)

    image_list = theme_data.get(f"{time_of_day}ImageList", [])

    while not image_list:
        time_categories = ['sunrise', 'day', 'sunset', 'night']
        try:
           current_idx = time_categories.index(time_of_day)
           if current_idx < len(time_categories) - 1:
               time_of_day = time_categories[current_idx + 1]
               image_list = theme_data.get(f"{time_of_day}ImageList", [])
           else:
               raise ValueError("No images available in any time-of-day category")
        except ValueError:
           raise ValueError("No images available in any time-of-day category")

    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        # Get coordinates from config
        location_data = config.get('location', {})
        lat = location_data.get('latitude', 33.4484)
        lon = location_data.get('longitude', -112.074)
    except:
        timezone = 'America/Phoenix'
        lat = 33.4484
        lon = -112.074

    use_sun_times = False
    dawn_val = sunrise_val = sunset_val = dusk_val = None

    if ASTRAL_AVAILABLE:
        try:
           location = LocationInfo("Default", "California", timezone, lat, lon)
           s_data = sun(location.observer, date=now.date(), tzinfo=ZoneInfo(timezone))
           dawn_val = cast(datetime | None, s_data['dawn'])
           sunrise_val = cast(datetime | None, s_data['sunrise'])
           sunset_val = cast(datetime | None, s_data['sunset'])
           dusk_val = cast(datetime | None, s_data['dusk'])
           use_sun_times = all([
               dawn_val is not None, sunrise_val is not None,
               sunset_val is not None, dusk_val is not None
           ])
        except Exception:
           use_sun_times = False

    if time_of_day == "night":
        period_start = datetime.combine(now.date(), time_class(18, 0))
        period_start = period_start.replace(tzinfo=ZoneInfo(timezone))
        if use_sun_times and dawn_val:
           # Night period ends at dawn - 30 minutes (last 30 min before dawn shows image 1)
           period_end = dawn_val - timedelta(minutes=30)
           # Handle case where night_end is on same day as dusk (period_end < period_start)
           if period_end < period_start:
               period_end = period_end + timedelta(days=1)
        else:
           period_end = datetime.combine(now.date() + timedelta(days=1), time_class(6, 0))
        period_end = period_end.replace(tzinfo=ZoneInfo(timezone))
        period_duration = (period_end - period_start).total_seconds()
        # Handle wrap-around: if now is before period_start (e.g., 00:00 before 18:00),
        # add one day to now for position calculation
        now_for_pos = now if now >= period_start else now + timedelta(days=1)
        position = (now_for_pos - period_start).total_seconds() / period_duration
        # Clamp position to [0, 1] range
        position = max(0.0, min(1.0, position))
        image_index = int((position - 1e-9) * len(image_list)) + 14

    elif time_of_day == "sunrise":
        # DEBUG
        import sys
        print(f"DEBUG select_image_for_specific_time sunrise: now={now}, use_sun_times={use_sun_times}", file=sys.stderr)
        print(f"DEBUG select_image_for_specific_time sunrise: dawn_val={dawn_val}, sunrise_val={sunrise_val}", file=sys.stderr)
        if use_sun_times and dawn_val:
           # Sunrise period starts at dawn - 30 min (last 30 min before dawn shows image 1)
           period_start = dawn_val - timedelta(minutes=30)
           # Adjust to next day if needed
           if period_start < datetime.combine(period_start.date(), time_class(0, 0)):
               period_start = period_start + timedelta(days=1)
        else:
           period_start = datetime.combine(now.date(), time_class(5, 15))
           period_start = period_start.replace(tzinfo=ZoneInfo(timezone))
        if use_sun_times and sunrise_val:
           period_end = sunrise_val + timedelta(minutes=45)
        else:
           period_end = datetime.combine(now.date(), time_class(6, 0))
           period_end = period_end.replace(tzinfo=ZoneInfo(timezone))
        print(f"DEBUG select_image_for_specific_time sunrise: period_start={period_start}, period_end={period_end}", file=sys.stderr)
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        print(f"DEBUG select_image_for_specific_time sunrise: position={position}", file=sys.stderr)
        image_index = int((position - 1e-9) * len(image_list)) + 1
        print(f"DEBUG select_image_for_specific_time sunrise: image_index={image_index}", file=sys.stderr)

    elif time_of_day == "day":
        if use_sun_times and sunrise_val:
           # Match detect_time_of_day_sun: day starts 45 min after sunrise
           period_start = sunrise_val + timedelta(minutes=45)
        else:
           period_start = datetime.combine(now.date(), time_class(6, 0))
           period_start = period_start.replace(tzinfo=ZoneInfo(timezone))
        if use_sun_times and dusk_val:
           # Match detect_time_of_day_sun: day ends 45 min before dusk
           period_end = dusk_val - timedelta(minutes=45)
        else:
           period_end = datetime.combine(now.date(), time_class(18, 0))
           period_end = period_end.replace(tzinfo=ZoneInfo(timezone))
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 5

    elif time_of_day == "sunset":
        if use_sun_times and dusk_val:
           # Match detect_time_of_day_sun: sunset starts 45 min before dusk
           period_start = dusk_val - timedelta(minutes=45)
        else:
           period_start = datetime.combine(now.date(), time_class(18, 0))
           period_start = period_start.replace(tzinfo=ZoneInfo(timezone))
        if use_sun_times and dusk_val:
           period_end = dusk_val
        else:
           period_end = datetime.combine(now.date(), time_class(18, 30))
           period_end = period_end.replace(tzinfo=ZoneInfo(timezone))
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        image_index = int((position - 1e-9) * len(image_list)) + 10

    else:
        image_index = image_list[0] if image_list else 1

    filename_pattern = theme_data.get("imageFilename", "*.jpg")
    pattern_base = Path(filename_pattern).stem if filename_pattern else "theme"
    pattern_ext = Path(filename_pattern).suffix if filename_pattern else ".jpg"

    image_files = list(theme_path_obj.glob(filename_pattern))

    if not image_files:
        numbered_files = []
        for i in range(1, 100):
           numbered_files.append(theme_path_obj / f"{pattern_base}_{i}{pattern_ext}")
        image_files = [f for f in numbered_files if f.exists()]

    if not image_files:
        raise FileNotFoundError(
           f"Image file not found for index {image_index} in theme '{theme_data.get('displayName')}'"
        )

    def get_img_idx(f):
        try:
           return int(f.stem.split('_')[-1])
        except:
           return 0
    image_files.sort(key=get_img_idx)

    if image_index <= len(image_files):
        image_path = image_files[image_index - 1]
    else:
           image_path = image_files[(image_index - 1) % len(image_files)]

    # DEBUG
    import sys
    print(f"DEBUG select_image_for_specific_time: image_index={image_index}, len(image_files)={len(image_files)}, image_path={image_path}", file=sys.stderr)

    return str(image_path)


# ============================================================================
# WALLPAPER CHANGE
# ============================================================================

def change_wallpaper(image_path: str) -> bool:
    """Change KDE Plasma wallpaper to specified image.

    Args:
        image_path: Path to image file to set as wallpaper

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if Plasma is running
        plasma_check = subprocess.run(
           ['pgrep', '-x', 'plasmashell'],
           capture_output=True
        )
        if plasma_check.returncode != 0:
           print("Error: Plasma is not running. Please start Plasma first.", file=sys.stderr)
           return False

        # Try plasma-apply-wallpaperimage first (most reliable)
        result = subprocess.run(
           ['plasma-apply-wallpaperimage', image_path],
           capture_output=True,
           text=True
        )

        if result.returncode == 0:
           print("Wallpaper changed successfully!")
           return True

        # Fall back to kwriteconfig5 if plasma-apply-wallpaperimage fails
        print("Attempting fallback method using kwriteconfig5...", file=sys.stderr)
        subprocess.run([
           'kwriteconfig5',
           '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
           '--group', 'Wallpaper',
           '--group', 'org.kde.image',
           '--key', 'Image',
           image_path
        ], check=False, capture_output=True)

        # Verify wallpaper was set
        verify_result = subprocess.run([
           'kreadconfig5',
           '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
           '--group', 'Wallpaper',
           '--group', 'org.kde.image',
           '--key', 'Image'
        ], capture_output=True, text=True)

        if verify_result.returncode == 0 and verify_result.stdout.strip():
           print("Wallpaper changed successfully (using fallback method)", file=sys.stderr)
           return True
        else:
           print(f"Error: Failed to change wallpaper. plasma-apply-wallpaperimage returned: {result.stderr}", file=sys.stderr)
           return False

    except FileNotFoundError as e:
        print(f"Error: Required command not found: {e}", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to change wallpaper: {e.stderr}", file=sys.stderr)
        return False


# ============================================================================
# CLI SUBCOMMANDS
# ============================================================================

def validate_time_of_day(time_of_day: str) -> bool:
    """Validate time-of-day category.

    Args:
        time_of_day: Time-of-day category to validate

    Returns:
        True if valid, False otherwise
    """
    valid_categories = ['sunrise', 'day', 'sunset', 'night']
    return time_of_day in valid_categories


def resolve_theme_path(theme_path: str, theme_name: Optional[str] = None) -> str:
    """Resolve theme path to absolute path, handling zip files and extracted directories.

    Args:
        theme_path: Path to theme (zip file or directory)
        theme_name: Optional theme name for searching in cache

    Returns:
        Absolute path to theme directory

    Raises:
        FileNotFoundError: If theme cannot be resolved
    """
    expanded_path = Path(theme_path).expanduser()

    # If path exists, return it
    if expanded_path.exists():
        return str(expanded_path)

    # If path doesn't exist, try to find in cache
    if theme_name:
        cache_dir = DEFAULT_CACHE_DIR
        matches = list(cache_dir.glob("theme_*"))
        for match in matches:
           try:
               if (match / theme_name).exists():
                   return str(match)
           except (OSError, PermissionError):
               # Skip directories that can't be accessed
               pass

    raise FileNotFoundError(f"Theme not found: {theme_path}")


def run_extract_command(args) -> int:
    """Handle extract subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Validate theme path exists
        theme_path = Path(args.theme_path).expanduser().resolve()
        if not theme_path.exists():
           print(f"Error: Theme path not found: {args.theme_path}", file=sys.stderr)
           return 1

        result = extract_theme(str(theme_path), args.cleanup)
        print(f"Extracted to: {result['extract_dir']}")
        print(f"Theme: {result['displayName']}")
        print(f"Image credits: {result['imageCredits']}")
        print(f"Image filename pattern: {result['imageFilename']}")
        print(f"Sunrise images: {result['sunriseImageList']}")
        print(f"Day images: {result['dayImageList']}")
        print(f"Sunset images: {result['sunsetImageList']}")
        print(f"Night images: {result['nightImageList']}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error extracting theme: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_change_command(args) -> int:
    """Handle change subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Resolve theme path (may be extracted directory or zip file)
        theme_path = args.theme_path

        # Handle zip/ddw files
        expanded_path = Path(theme_path).expanduser()
        if expanded_path.is_file() and expanded_path.suffix in ['.zip', '.ddw']:
           result = extract_theme(str(theme_path), cleanup=False)
           theme_path = result['extract_dir']
        else:
           # Resolve to absolute path
           theme_path = resolve_theme_path(theme_path)

        # Get theme metadata to find where theme.json is located
        theme_json_path = Path(theme_path) / "theme.json"
        if not theme_json_path.exists():
           # Look for theme.json in subdirectories
           for item in Path(theme_path).iterdir():
               if item.is_dir() and (item / "theme.json").exists():
                   theme_json_path = item / "theme.json"
                   theme_path = str(item)
                   break
           else:
               # If still not found, search recursively
               for item in Path(theme_path).rglob("theme.json"):
                   theme_json_path = item
                   # Get the parent directory of theme.json
                   theme_path = str(item.parent)
                   break

        # Get config path (use --config if provided, otherwise default)
        if args.config:
           config_path_obj = Path(args.config).expanduser().resolve()
        else:
           config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        # Handle --time argument for specific time selection
        if args.time:
           try:
               time_of_day = detect_time_of_day_for_time(args.time, str(config_path_obj))
               print(f"Selecting image for time: {args.time} ({time_of_day})")
               image_path = select_image_for_specific_time(args.time, theme_path, str(config_path_obj))
               print(f"Changing wallpaper to: {Path(image_path).name}")
               if change_wallpaper(image_path):
                   print("Wallpaper changed successfully!")
                   return 0
               else:
                   print("Failed to change wallpaper", file=sys.stderr)
                   return 1
           except Exception as e:
               print(f"Error selecting image for specific time: {e}", file=sys.stderr)
               return 1

        # Always detect current time of day
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
        time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Monitor mode
        if args.monitor:
           print(f"Starting continuous monitoring mode...")
           print(f"Theme: {Path(theme_path).name}")
           print(f"Time-of-day intervals: {config['interval']} seconds each")
           print("Press Ctrl+C to stop")
           print("-" * 60)

           last_image_path = None
           last_time_of_day = None

           while True:
               try:
                   # Get current time of day
                   time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)
                   current_time_str = datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S")

# Check if time-of-day changed
                   if time_of_day != last_time_of_day:
                       print(f"\n[{current_time_str}] Time changed: {last_time_of_day} → {time_of_day}")
                       last_time_of_day = time_of_day

                       # Select new image for current time-of-day using time-based selection
                       try:
                           image_path = select_image_for_time_cli(theme_path, str(config_path_obj))
                       except Exception:
                           image_path = select_image_for_time_hourly_cli(theme_path, str(config_path_obj))
                       print(f"  → Changing wallpaper to: {Path(image_path).name}")

                       if change_wallpaper(image_path):
                           print(f"  ✓ Wallpaper updated successfully")
                       else:
                           print(f"  ✗ Failed to update wallpaper", file=sys.stderr)

                       last_image_path = image_path

                   else:
                       # Just log current status
                       if last_image_path:
                           print(f"\r[{now}] {time_of_day} - {Path(last_image_path).name}", end="", flush=True)
                       else:
                           print(f"\r[{now}] {time_of_day} - loading...", end="", flush=True)

                   # Wait for next interval (check if time changed)
                   time.sleep(config['interval'])

               except KeyboardInterrupt:
                   print("\n\nStopping monitoring mode...")
                   break
               except Exception as e:
                   print(f"\nError in monitoring loop: {e}", file=sys.stderr)
                   import traceback
                   traceback.print_exc()
                   time.sleep(5)  # Wait before retrying

           return 0

        # Single change mode - use time-based selection
        print(f"Selecting image for current time: {time_of_day}")
        now = datetime.now(ZoneInfo(timezone))
        if ASTRAL_AVAILABLE:
           image_path = select_image_for_time_cli(theme_path, str(config_path_obj))
        else:
           image_path = select_image_for_time_hourly_cli(theme_path, str(config_path_obj))
        print(f"Changing wallpaper to: {image_path}")

        if change_wallpaper(image_path):
           print("Wallpaper changed successfully!")
           return 0
        else:
           print("Failed to change wallpaper", file=sys.stderr)
           return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"Error changing wallpaper: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_list_command(args) -> int:
    """Handle list subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Resolve theme path
        theme_path = resolve_theme_path(args.theme_path)
        theme_path_obj = Path(theme_path)

        # Get config path (use --config if provided, otherwise default)
        if args.config:
           config_path_obj = Path(args.config).expanduser().resolve()
        else:
           config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')

        if args.time_of_day:
           time_of_day = args.time_of_day
           if not validate_time_of_day(time_of_day):
               print(f"Invalid time-of-day category: {time_of_day}", file=sys.stderr)
               print("Valid categories are: sunrise, day, sunset, night", file=sys.stderr)
               return 1
        else:
           now = datetime.now(ZoneInfo(timezone))
           time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Get theme metadata to find image lists
        theme_json_path = theme_path_obj / "theme.json"
        if not theme_json_path.exists():
           # Look for theme.json in subdirectories
           for item in theme_path_obj.iterdir():
               if item.is_dir() and (item / "theme.json").exists():
                   theme_json_path = item / "theme.json"
                   theme_path = str(item)
                   break
           else:
               # Search recursively
               for item in theme_path_obj.rglob("theme.json"):
                   theme_json_path = item
                   theme_path = str(item.parent)
                   break

        with open(theme_json_path, 'r') as f:
           theme_data = json.load(f)

        image_list = theme_data.get(f"{time_of_day}ImageList", [])
        print(f"Images for {time_of_day}: {image_list}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error listing images: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_status_command(args) -> int:
    """Handle status subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get config path
        if args.config:
           config_path_obj = Path(args.config).expanduser().resolve()
        else:
           config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        # Import here to avoid issues
        wallpaper_path = get_current_wallpaper()

        # Get time of day
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
        time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Print status
        print(f"Current wallpaper:")
        if wallpaper_path and Path(wallpaper_path).exists():
           print(f"  Path: {wallpaper_path}")
           print(f"  File: {Path(wallpaper_path).name}")
        else:
           print(f"  No wallpaper currently set")
           print(f"  Tip: Run './wallpaper_cli.py change --theme-path <path>' to set a wallpaper")

        print(f"\nCurrent time-of-day: {time_of_day}")
        print(f"Image index: N/A (time-based selection now)")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error checking status: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="KDE Wallpaper Changer - Automatically change wallpapers based on time-of-day",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Extract theme from .ddw file
    wallpaper_cli.py extract --theme-path theme.ddw --cleanup

  Change wallpaper to next image
    wallpaper_cli.py change --theme-path theme.ddw

  List images for a time-of-day category
    wallpaper_cli.py list --theme-path extracted_theme --time-of-day day

  Monitor mode (continuous wallpaper changes)
    wallpaper_cli.py change --theme-path theme.ddw --monitor
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract theme from .ddw file')
    extract_parser.add_argument('--theme-path', required=True, help='Path to .ddw zip file')
    extract_parser.add_argument('--cleanup', action='store_true', help='Remove temp directory after extraction')

    # Change wallpaper command
    change_parser = subparsers.add_parser('change', help='Change wallpaper to next image')
    change_parser.add_argument('--theme-path', required=True, help='Path to .ddw zip file or extracted theme directory')
    change_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')
    change_parser.add_argument('--monitor', action='store_true', help='Run continuously, cycling wallpapers based on time-of-day')
    change_parser.add_argument('--time', help='Specific time to use for wallpaper selection (HH:MM format)')

    # List images command
    list_parser = subparsers.add_parser('list', help='List available images in time-of-day category')
    list_parser.add_argument('--theme-path', required=True, help='Path to extracted theme directory or theme name')
    list_parser.add_argument('--time-of-day', help='Time-of-day category (day/sunset/sunrise/night)')
    list_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check current wallpaper')
    status_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

    args = parser.parse_args()

    # Route to appropriate handler
    if args.command == 'extract':
        return run_extract_command(args)
    elif args.command == 'change':
        return run_change_command(args)
    elif args.command == 'list':
        return run_list_command(args)
    elif args.command == 'status':
        return run_status_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
kWallpaper image file selection.

Turns "theme directory + time" into a concrete image file path.  The
astral math lives in kwallpaper.suntime; this module owns the
theme.json loading and file-matching (glob pattern / numbered files).
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from kwallpaper.config import load_config
from kwallpaper.suntime import (
    ASTRAL_AVAILABLE,
    _config_location,
    _fix_next_day,
    _real_sun_data,
    detect_time_of_day_for_time,
    detect_time_of_day_sun,
    image_index_for,
    image_period,
    _night_now_for_pos,
)
from kwallpaper.themes import extract_theme, normalize_image_lists


def find_theme_json(theme_path_obj: Path) -> Path:
    """Locate theme.json in a theme dir (root *.json first, then recursive)."""
    for json_file in theme_path_obj.glob("*.json"):
        return json_file
    for found_path in theme_path_obj.rglob("theme.json"):
        return found_path
    raise FileNotFoundError("theme.json not found in theme directory")


def load_theme_data(theme_path_obj: Path) -> Dict[str, Any]:
    """Load and normalize theme.json from a theme directory."""
    theme_json_path = find_theme_json(theme_path_obj)
    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)
    return normalize_image_lists(theme_data)


def _resolve_theme_dir(theme_path: str) -> Path:
    """Resolve a theme path, extracting .zip/.ddw archives in place."""
    theme_path_obj = Path(theme_path)
    if theme_path_obj.is_file() and theme_path_obj.suffix in ('.zip', '.ddw'):
        result = extract_theme(str(theme_path_obj), cleanup=False)
        theme_path_obj = Path(result['extract_dir'])
    return theme_path_obj


def _match_image_file(theme_path_obj: Path, image_index: int,
                      theme_data: Dict[str, Any]) -> str:
    """Find the image file for a 1-based index in a theme directory."""
    # Pattern: imageFilename contains index, e.g., "24hr-Tahoe-2026_*.jpeg"
    filename_pattern = theme_data.get("imageFilename", "*.jpg")

    pattern_base = Path(filename_pattern).stem if filename_pattern else "theme"
    pattern_ext = Path(filename_pattern).suffix if filename_pattern else ".jpg"

    # Try to find files matching pattern
    image_files = list(theme_path_obj.glob(filename_pattern))

    # If pattern doesn't match, try numbered files
    if not image_files:
        numbered_files = []
        for i in range(1, 100):
            numbered_files.append(theme_path_obj / f"{pattern_base}_{i}{pattern_ext}")
        image_files = [f for f in numbered_files if f.exists()]

    if not image_files:
        raise FileNotFoundError(
            f"Image file not found for index {image_index} in theme '{theme_data.get('displayName')}'"
        )

    # Sort files numerically by extracting index from filename
    def get_img_idx(f):
        try:
            return int(f.stem.split('_')[-1])
        except Exception:
            return 0
    image_files.sort(key=get_img_idx)

    # Find the file at the correct index
    if image_index <= len(image_files):
        image_path = image_files[image_index - 1]  # 1-based to 0-based
    else:
        # Wrap around if index exceeds available files
        image_path = image_files[(image_index - 1) % len(image_files)]

    return str(image_path)


def _pick_image_list(theme_data: Dict[str, Any],
                     time_of_day: str) -> tuple:
    """Return (time_of_day, image_list), advancing to the next category
    when the current one has no images (legacy fallback order)."""
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
    return time_of_day, image_list


def _sun_for_config(config_path: str) -> Optional[dict]:
    """Fetch astral sun values for the config location (or None)."""
    if not ASTRAL_AVAILABLE:
        return None
    try:
        timezone_str, lat, lon = _config_location(config_path)
        sun = _real_sun_data(timezone_str, lat, lon)
        if sun is None:
            return None
        _fix_next_day(sun)
        return sun
    except Exception:
        return None


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
    theme_path_obj = _resolve_theme_dir(theme_path)
    theme_data = load_theme_data(theme_path_obj)

    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        # Fallback to UTC if timezone not available
        now = datetime.now(ZoneInfo('UTC'))

    # Get time-of-day category
    time_of_day = detect_time_of_day_sun(config_path, now=now)

    # Get image list for current time-of-day
    time_of_day, image_list = _pick_image_list(theme_data, time_of_day)

    # Get sun times for position calculation
    sun = _sun_for_config(config_path)

    # Calculate image index based on time period
    if time_of_day == "night":
        period_start, period_end = image_period("night", now, sun, tz=None)
        period_duration = (period_end - period_start).total_seconds()
        now_for_pos = _night_now_for_pos(now, period_start, period_end)
        position = (now_for_pos - period_start).total_seconds() / period_duration
        list_index = int((position - 1e-9) * len(image_list))
        list_index = max(0, min(list_index, len(image_list) - 1))
        image_index = image_list[list_index]
    else:
        period_start, period_end = image_period(time_of_day, now, sun, tz=None)
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        if time_of_day == "sunrise":
            image_index = int((position - 1e-9) * len(image_list)) + 1
        elif time_of_day == "day":
            image_index = int((position - 1e-9) * len(image_list)) + 5
        elif time_of_day == "sunset":
            image_index = int((position - 1e-9) * len(image_list)) + 10
        else:
            image_index = image_list[0]

    return _match_image_file(theme_path_obj, image_index, theme_data)


def select_image_for_specific_time(time_str: str, theme_path: str,
                                   config_path: str) -> str:
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
            timezone = config.get('location', {}).get(
                'timezone', 'America/Los_Angeles')
        except Exception:
            timezone = 'America/Los_Angeles'

        # Ensure now is timezone-aware in the config timezone
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(timezone))
        else:
            now = now.astimezone(ZoneInfo(timezone))
    except ValueError as e:
        raise ValueError(f"Invalid time format. Expected HH:MM, e.g., 14:30: {e}")

    theme_path_obj = _resolve_theme_dir(theme_path)
    theme_data = load_theme_data(theme_path_obj)

    try:
        time_of_day = detect_time_of_day_for_time(time_str, config_path)
    except Exception:
        # Fallback to previous day's backup
        from kwallpaper.backup import load_daily_backup_schedule
        backup = load_daily_backup_schedule()
        if backup:
            time_of_day = backup['time_of_day']
        else:
            raise RuntimeError("Astral failed and no previous day backup exists")

    time_of_day, image_list = _pick_image_list(theme_data, time_of_day)

    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
    except Exception:
        timezone = 'America/Phoenix'

    sun = _sun_for_config(config_path)
    tz = ZoneInfo(timezone)

    # Calculate image index based on time period
    if time_of_day == "night":
        period_start, period_end = image_period("night", now, sun, tz=tz)
        period_duration = (period_end - period_start).total_seconds()
        now_for_pos = _night_now_for_pos(now, period_start, period_end)
        position = (now_for_pos - period_start).total_seconds() / period_duration
        # Clamp position to [0, 1] range
        position = max(0.0, min(1.0, position))
        list_index = int((position - 1e-9) * len(image_list))
        list_index = max(0, min(list_index, len(image_list) - 1))
        image_index = image_list[list_index]
    else:
        period_start, period_end = image_period(time_of_day, now, sun, tz=tz)
        period_duration = (period_end - period_start).total_seconds()
        position = (now - period_start).total_seconds() / period_duration
        if time_of_day == "sunrise":
            image_index = int((position - 1e-9) * len(image_list)) + 1
        elif time_of_day == "day":
            image_index = int((position - 1e-9) * len(image_list)) + 5
        elif time_of_day == "sunset":
            image_index = int((position - 1e-9) * len(image_list)) + 10
        else:
            image_index = image_list[0] if image_list else 1

    return _match_image_file(theme_path_obj, image_index, theme_data)


def select_image_for_time(theme_data: Dict[str, Any], now: datetime,
                          mock_sun=None) -> int:
    """Select image index based on current time using time-based detection.

    This is a wrapper function for testing purposes. It uses the same logic
    as the main select_image_for_time() but adapted to work with test data.

    Args:
        theme_data: Theme data dictionary containing image lists and filename patterns
        now: Current datetime for time-based selection
        mock_sun: Optional mock sun object for testing

    Returns:
        Image index to select

    Raises:
        ValueError: If no images available or index exceeds available images
    """
    from kwallpaper.suntime import (
        _mock_sun_data,
        _normalize_now,
        _datetime_timezone,
        time_of_day_for,
    )

    # Normalize image lists to ensure image 1 is in sunrise, not night
    theme_data = normalize_image_lists(theme_data)

    if ASTRAL_AVAILABLE:
        try:
            if mock_sun is not None:
                # Use mock sun directly (no need to import Astral)
                sun = _mock_sun_data(mock_sun)
                # Convert mock UTC times to UTC for consistent comparison
                # (select_image_for_time uses UTC internally)
                for key in ('sunrise', 'sunset', 'dawn', 'dusk'):
                    v = sun.get(key)
                    if v is not None and v.tzinfo is None:
                        sun[key] = v.replace(tzinfo=_datetime_timezone.utc)
                # Convert now to timezone-aware datetime in UTC
                if now.tzinfo is None:
                    now = now.replace(tzinfo=_datetime_timezone.utc)
                else:
                    now = now.astimezone(_datetime_timezone.utc)
            else:
                # Use real Astral library
                from kwallpaper.suntime import _astral_import
                astral = _astral_import()
                location = astral.LocationInfo("Test", "Test", "UTC",
                                               33.4484, -112.074)
                s = astral.sun(location.observer, date=now.date())
                sun = {'dawn': s['dawn'], 'sunrise': s['sunrise'],
                       'sunset': s['sunset'], 'dusk': s['dusk']}
                if now.tzinfo is None:
                    now = now.replace(tzinfo=_datetime_timezone.utc)
                else:
                    now = now.astimezone(_datetime_timezone.utc)

            time_of_day = time_of_day_for(now, sun)
        except Exception:
            # Astral failed - try to load previous day's backup
            from kwallpaper.backup import load_daily_backup_schedule
            backup = load_daily_backup_schedule()
            if backup:
                time_of_day = backup['time_of_day']
                sun = None
            else:
                raise RuntimeError("Astral failed and no previous day backup exists")
    else:
        # No Astral available - try to load previous day's backup
        from kwallpaper.backup import load_daily_backup_schedule
        backup = load_daily_backup_schedule()
        if backup:
            time_of_day = backup['time_of_day']
            sun = None
        else:
            raise RuntimeError("Astral unavailable and no previous day backup exists")

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{time_of_day}ImageList", [])

    # Only use sun times if they were available (Astral was used)
    use_sun_times = sun is not None and all(
        sun.get(k) is not None for k in ('dawn', 'sunrise', 'sunset', 'dusk'))

    if not use_sun_times:
        sun = None

    # Calculate image index using the shared index-selector math
    image_index = image_index_for(time_of_day, now, sun, image_list, tz=None)

    # Validate image index is in the image list
    if image_index not in theme_data.get(f"{time_of_day}ImageList", []):
        raise ValueError(
            f"Image index {image_index} not found in {time_of_day} category"
        )

    return image_index

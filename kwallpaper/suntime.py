#!/usr/bin/env python3
"""
kWallpaper astral time-of-day math.

ONE implementation of the dawn/sunrise/sunset/dusk period model shared by:

- ``detect_time_of_day_sun``   (time-of-day category detection)
- ``select_image_for_time``    (image index selection, test wrapper)
- ``select_image_for_time_cli``(image file selection, CLI)
- ``select_image_for_specific_time`` (image file selection for HH:MM)

The period model (all boundaries derived from four astral values):

    night_end   = dawn  - 30 min   (dawn lead-in; last 30 min before dawn)
    sunrise_end = sunrise + 45 min (transition offset)
    dusk_start  = dusk  - 45 min   (transition offset)

    night   : [dusk, next dawn - 30 min]   (spans midnight)
    sunrise : [night_end, sunrise_end]
    day     : (sunrise_end, dusk_start)
    sunset  : [dusk_start, dusk]

Behaviour-preservation notes (differences between the four legacy copies,
now pinned by tests/test_suntime.py):

- Category detection (detect_time_of_day_sun) uses the model above.
- Image *file* selection for "day" (select_image_for_time_cli /
  select_image_for_specific_time) also uses dusk-45min as the period end,
  matching detection.
- Image *index* selection for "day" (select_image_for_time) uses the raw
  **sunset** value as the period end (legacy quirk, preserved).
- Image *file* selection for "sunrise" (CLI copies) ends the period at
  06:00 local in the no-sun-times fallback, while the index selector uses
  06:45; the CLI copies start the fallback at 05:15, the index selector at
  05:15 as well.
- The "day" image index in the index selector is offset by +5 and "sunset"
  by +10 (legacy numbering); the CLI file selectors use plain list-index
  math.  All of this is preserved verbatim.
"""

import logging
from datetime import datetime, timedelta, timezone, time as time_class
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Save reference to datetime.timezone before local variable shadows it
_datetime_timezone = timezone

# Astral availability (checked once; tests may patch ``_astral_import``)
try:
    import astral as _astral_module
    ASTRAL_AVAILABLE = True
except ImportError:
    _astral_module = None
    ASTRAL_AVAILABLE = False


# ============================================================================
# Constants (public API — tests import these from wallpaper_changer)
# ============================================================================

DURATION_DAWN_MINUTES = 30
DURATION_SUNRISE_MINUTES = 6
DURATION_SUNSET_MINUTES = 6
DURATION_DUSK_MINUTES = 30
DURATION_IMAGE_9_MINUTES = 30

# Transition offsets used in time-of-day boundary calculations
TRANSITION_OFFSET_MINUTES = 45

# Night lead-in: the last 30 minutes before dawn belong to the sunrise
# period (they show the first sunrise image).
NIGHT_LEAD_IN_MINUTES = 30

TIME_CATEGORIES = ["sunrise", "day", "sunset", "night"]


# ============================================================================
# Low-level helpers
# ============================================================================

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


def _astral_import():
    """Import astral (indirection point for tests that patch __import__)."""
    import astral
    return astral


def _mock_sun_data(mock_sun):
    """Build a dict-like accessor over a mock sun object.

    Two mock conventions are supported (both used by the test-suite):

    - ``mock_sun._from_setup_astral`` is True: the mock was installed via a
      patched ``__import__``; the real (mocked) astral.sun() is called and
      its raw attributes are read (avoids the __getitem__ naive->UTC
      conversion bug in the test double).
    - plain mock: raw ``_dawn/_sunrise/_sunset/_dusk`` attributes are used
      directly (naive datetimes, compared as-is).

    Returns a dict with keys dawn/sunrise/sunset/dusk (values may be None).
    """
    if getattr(mock_sun, '_from_setup_astral', False):
        astral = _astral_import()
        location = astral.LocationInfo("Default", "California", "UTC", 0.0, 0.0)
        s_unwrapped = astral.sun(location.observer,
                                 date=datetime.now().date(), tzinfo="UTC")
        return {
            'dawn': s_unwrapped._dawn,
            'sunrise': s_unwrapped._sunrise,
            'sunset': s_unwrapped._sunset,
            'dusk': s_unwrapped._dusk,
        }
    return {
        'dawn': mock_sun._dawn,
        'sunrise': mock_sun._sunrise,
        'sunset': mock_sun._sunset,
        'dusk': mock_sun._dusk,
    }


def _real_sun_data(timezone_str: str, lat: float, lon: float,
                   date=None) -> Optional[Dict[str, Optional[datetime]]]:
    """Fetch dawn/sunrise/sunset/dusk from the real astral library.

    Returns a dict (values may be None) or None on any failure.
    """
    if not ASTRAL_AVAILABLE:
        return None
    try:
        astral = _astral_import()
        location = astral.LocationInfo("Default", "California", timezone_str,
                                       lat, lon)
        s = astral.sun(location.observer,
                       date=date or datetime.now().date(),
                       tzinfo=location.timezone)
        return {
            'dawn': s['dawn'],
            'sunrise': s['sunrise'],
            'sunset': s['sunset'],
            'dusk': s['dusk'],
        }
    except Exception:
        return None


def _fix_next_day(sun: Dict[str, Optional[datetime]]) -> None:
    """When sunset/dusk are earlier than sunrise/dawn in UTC, they belong to
    the next day.  Adjust in place (legacy behaviour)."""
    if sun['sunset'] and sun['sunrise'] and sun['sunset'] < sun['sunrise']:
        sun['sunset'] = sun['sunset'] + timedelta(days=1)
    if sun['dusk'] and sun['dawn'] and sun['dusk'] < sun['dawn']:
        sun['dusk'] = sun['dusk'] + timedelta(days=1)


def _config_location(config_path: Optional[str]):
    """Read (timezone, lat, lon) from config, with legacy defaults."""
    timezone_str = "America/Phoenix"
    lat, lon = 33.4484, -112.074
    if config_path:
        try:
            from kwallpaper.config import load_config
            config = load_config(config_path)
            loc = config.get('location', {})
            timezone_str = loc.get('timezone', timezone_str)
            lat = loc.get('latitude', lat)
            lon = loc.get('longitude', lon)
        except (FileNotFoundError, ValueError):
            pass
    return timezone_str, lat, lon


def _normalize_now(now: Optional[datetime], target_tz,
                   mock_sun=None) -> datetime:
    """Bring ``now`` into the same clock as the sun values.

    - mock suns use naive local datetimes -> strip tzinfo from now.
    - real astral values are in target_tz -> convert now to target_tz.
    """
    if mock_sun is not None:
        if now is not None and now.tzinfo is not None:
            return now.replace(tzinfo=None)
        return now if now is not None else datetime.now()
    if now is None:
        return datetime.now(target_tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=target_tz)
    if now.tzinfo != target_tz:
        return now.astimezone(target_tz)
    return now


# ============================================================================
# Period model
# ============================================================================

def period_boundaries(sun: Dict[str, Optional[datetime]]) -> Dict[str, Optional[datetime]]:
    """Compute the four period boundaries from astral values.

    Args:
        sun: dict with dawn/sunrise/sunset/dusk (timezone-aware datetimes,
            already next-day-adjusted; values may be None).

    Returns:
        dict with keys: night_end, sunrise_end, dusk_start, night_spans_midnight
        (any boundary is None if the underlying astral value is missing).
    """
    dawn_val = sun.get('dawn')
    sunrise_val = sun.get('sunrise')
    dusk_val = sun.get('dusk')

    night_end = dawn_val - timedelta(minutes=NIGHT_LEAD_IN_MINUTES) \
        if dawn_val is not None else None
    sunrise_end = sunrise_val + timedelta(minutes=TRANSITION_OFFSET_MINUTES) \
        if sunrise_val is not None else None
    dusk_start = dusk_val - timedelta(minutes=TRANSITION_OFFSET_MINUTES) \
        if dusk_val is not None else None
    night_spans_midnight = (
        night_end is not None and dusk_val is not None
        and night_end < dusk_val
    )
    return {
        'night_end': night_end,
        'sunrise_end': sunrise_end,
        'dusk_start': dusk_start,
        'night_spans_midnight': night_spans_midnight,
    }


def time_of_day_for(now: datetime, sun: Dict[str, Optional[datetime]]) -> str:
    """Classify ``now`` into night/sunrise/day/sunset.

    Mirrors the legacy ``detect_time_of_day_sun`` decision tree exactly,
    including the None-value fallbacks (dawn missing -> night, sunrise
    missing -> sunrise, sunset missing -> day, dusk missing -> sunset).
    """
    dawn_val = sun.get('dawn')
    sunrise_val = sun.get('sunrise')
    sunset_val = sun.get('sunset')
    dusk_val = sun.get('dusk')

    if dawn_val is None or not isinstance(dawn_val, datetime):
        return "night"
    elif sunrise_val is None or not isinstance(sunrise_val, datetime):
        return "sunrise"
    elif sunset_val is None or not isinstance(sunset_val, datetime):
        return "day"
    elif dusk_val is None or not isinstance(dusk_val, datetime):
        return "sunset"

    b = period_boundaries(sun)
    night_end = b['night_end']
    sunrise_end = b['sunrise_end']
    dusk_start = b['dusk_start']

    if b['night_spans_midnight']:
        # Sunset: dusk_start (dusk - 45 min) to dusk
        # Day: sunrise_end to dusk_start
        # Sunrise: night_end to sunrise_end
        # Night: dusk to night_end (next day)
        if dusk_start <= now <= dusk_val:
            return "sunset"
        elif sunrise_end < now < dusk_start:
            return "day"
        elif night_end <= now <= sunrise_end:
            return "sunrise"
        else:
            # Now is either >= dusk (night before midnight) or
            # < night_end (night after midnight)
            return "night"
    else:
        # Night doesn't span midnight
        if now < night_end:
            return "night"
        elif night_end <= now <= sunrise_end:
            return "sunrise"
        elif sunrise_end < now < dusk_start:
            return "day"
        elif dusk_start <= now <= dusk_val:
            return "sunset"
        else:
            return "night"


def image_period(time_of_day: str, now: datetime,
                 sun: Optional[Dict[str, Optional[datetime]]],
                 tz=None) -> tuple:
    """Compute (period_start, period_end) for image position math.

    This is the *file-selector* variant (select_image_for_time_cli /
    select_image_for_specific_time): the "day" period ends at dusk-45min.

    Args:
        time_of_day: category.
        now: current time (aware in the location timezone, or naive).
        sun: astral values or None (fallback to fixed local times).
        tz: ZoneInfo for the fallback branch (default UTC).
    """
    if tz is None:
        tz = ZoneInfo('UTC')
    use_sun = sun is not None

    def _aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt

    if time_of_day == "night":
        if use_sun and sun.get('dusk'):
            period_start = sun['dusk']
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(18, 0)))
        if use_sun and sun.get('dawn'):
            period_end = sun['dawn'] - timedelta(minutes=NIGHT_LEAD_IN_MINUTES)
            if period_end < period_start:
                period_end = period_end + timedelta(days=1)
        else:
            period_end = _aware(
                datetime.combine(now.date() + timedelta(days=1), time_class(6, 0)))
    elif time_of_day == "sunrise":
        if use_sun and sun.get('dawn'):
            period_start = sun['dawn'] - timedelta(minutes=NIGHT_LEAD_IN_MINUTES)
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(5, 15)))
        if use_sun and sun.get('sunrise'):
            period_end = sun['sunrise'] + timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(6, 0)))
    elif time_of_day == "day":
        if use_sun and sun.get('sunrise'):
            period_start = sun['sunrise'] + timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(6, 0)))
        if use_sun and sun.get('dusk'):
            period_end = sun['dusk'] - timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(18, 0)))
    elif time_of_day == "sunset":
        if use_sun and sun.get('dusk'):
            period_start = sun['dusk'] - timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(18, 0)))
        if use_sun and sun.get('dusk'):
            period_end = sun['dusk']
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(18, 30)))
    else:
        raise ValueError(f"Invalid time-of-day category: {time_of_day}")
    return period_start, period_end


def index_period(time_of_day: str, now: datetime,
                 sun: Optional[Dict[str, Optional[datetime]]],
                 tz=None) -> tuple:
    """Compute (period_start, period_end) for the *index-selector* variant
    (select_image_for_time).

    Deliberate differences from image_period() (legacy quirks, pinned by
    tests):
    - "day" ends at raw **sunset** (not dusk - 45 min).
    - "sunrise" fallback end is 06:45 (not 06:00).
    - "night" fallback uses UTC when tz is None (legacy behaviour).
    """
    if tz is None:
        tz = _datetime_timezone.utc

    def _aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt

    use_sun = sun is not None

    if time_of_day == "night":
        if use_sun and sun.get('dusk'):
            period_start = sun['dusk']
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(18, 0)))
        if use_sun and sun.get('dawn'):
            period_end = sun['dawn'] - timedelta(minutes=NIGHT_LEAD_IN_MINUTES)
            if period_end < period_start:
                period_end = period_end + timedelta(days=1)
        else:
            period_end = _aware(
                datetime.combine(now.date() + timedelta(days=1), time_class(6, 0)))
    elif time_of_day == "sunrise":
        if use_sun and sun.get('dawn'):
            period_start = sun['dawn'] - timedelta(minutes=NIGHT_LEAD_IN_MINUTES)
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(5, 15)))
        if use_sun and sun.get('sunrise'):
            period_end = sun['sunrise'] + timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(6, 45)))
    elif time_of_day == "day":
        if use_sun and sun.get('sunrise'):
            period_start = sun['sunrise'] + timedelta(minutes=TRANSITION_OFFSET_MINUTES)
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(6, 0)))
        # Legacy quirk: index selector uses raw sunset, not dusk-45min
        if use_sun and sun.get('sunset'):
            period_end = sun['sunset']
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(18, 0)))
    elif time_of_day == "sunset":
        if use_sun and sun.get('sunset'):
            period_start = sun['sunset']
        else:
            period_start = _aware(datetime.combine(now.date(), time_class(18, 0)))
        if use_sun and sun.get('dusk'):
            period_end = sun['dusk']
        else:
            period_end = _aware(datetime.combine(now.date(), time_class(18, 30)))
    else:
        raise ValueError(f"Invalid time-of-day category: {time_of_day}")
    return period_start, period_end


def _night_now_for_pos(now: datetime, period_start: datetime,
                       period_end: datetime) -> datetime:
    """Pick the ``now`` used for night position math (wrap-around handling).

    select_image_for_time_cli / select_image_for_specific_time use the simple
    rule: now < period_start -> now + 1 day.
    """
    return now if now >= period_start else now + timedelta(days=1)


def _index_night_now_for_pos(now: datetime, period_start: datetime,
                             period_end: datetime) -> datetime:
    """select_image_for_time's more elaborate night wrap-around rule."""
    night_spans_midnight = (
        period_end > period_start
        and period_end < period_start + timedelta(days=1)
        and period_end.time() < period_start.time()
    )
    if night_spans_midnight:
        if now >= period_start:
            return now
        now_plus_1day = now + timedelta(days=1)
        if now_plus_1day < period_end:
            return now_plus_1day
        return period_start
    return now if now >= period_start else now + timedelta(days=1)


# ============================================================================
# Image index selection (select_image_for_time logic, shared)
# ============================================================================

def _night_image_index(now_for_pos: datetime, period_start: datetime,
                       period_end: datetime, image_list: List[int]) -> int:
    """Night image index with the legacy Tahoe-format special cases."""
    period_duration = (period_end - period_start).total_seconds()

    # Detect image list patterns:
    # Old format: [14, 15, 16, 1] in nightImageList
    # New format: [14, 15, 16] in nightImageList, image 1 in sunriseImageList
    has_all_4_night = all(x in image_list for x in (14, 15, 16, 1))
    has_only_3_night = all(x in image_list for x in (14, 15, 16))
    has_image_1_in_night = 1 in image_list

    if has_only_3_night and not has_all_4_night:
        is_new_format = True
    elif has_all_4_night:
        is_new_format = False
    else:
        is_new_format = False

    if not is_new_format and has_image_1_in_night:
        # Old format: [14, 15, 16, 1]
        # Last image (1) covers the last 30 minutes (dawn-30min to dawn)
        period_duration_for_first_3 = period_duration - timedelta(minutes=30).total_seconds()

        if now_for_pos >= period_end:
            image_index = 1
        else:
            position = (now_for_pos - period_start).total_seconds() / period_duration_for_first_3
            position = min(position, 1.0 - 1e-9)
            if position < 0.25:
                image_index = 14
            elif position < 0.5:
                image_index = 15
            else:
                image_index = 16
    else:
        if is_new_format:
            # New format: [14, 15, 16] in nightImageList, image 1 in sunriseImageList
            if now_for_pos >= period_end:
                image_index = 1
            else:
                position = (now_for_pos - period_start).total_seconds() / period_duration
                position = min(position, 1.0 - 1e-9)
                if position < 0.333:
                    image_index = 14
                elif position < 0.666:
                    image_index = 15
                else:
                    image_index = 16
        else:
            # Old format fallback
            if now_for_pos >= period_end:
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
    return image_index


def image_index_for(time_of_day: str, now: datetime,
                    sun: Optional[Dict[str, Optional[datetime]]],
                    image_list: List[int], tz=None) -> int:
    """Select the image index for a category (select_image_for_time logic).

    Preserves the legacy index-selector quirks:
    - night: Tahoe-format special cases + elaborate wrap-around
    - sunrise: list-index math, clamped to [1, max(image_list)]
    - day: int((pos - 1e-9) * len) + 5
    - sunset: int((pos - 1e-9) * len) + 10
    """
    if not image_list:
        raise ValueError("No images available in image list")

    period_start, period_end = index_period(time_of_day, now, sun, tz=tz)
    period_duration = (period_end - period_start).total_seconds()

    if time_of_day == "night":
        now_for_pos = _index_night_now_for_pos(now, period_start, period_end)
        return _night_image_index(now_for_pos, period_start, period_end, image_list)

    position = (now - period_start).total_seconds() / period_duration

    if time_of_day == "sunrise":
        list_index = int((position - 1e-9) * len(image_list))
        image_index = image_list[list_index]
        image_index = max(1, min(image_index, max(image_list)))
    elif time_of_day == "day":
        image_index = int((position - 1e-9) * len(image_list)) + 5
        image_index = max(1, image_index)
    elif time_of_day == "sunset":
        image_index = int((position - 1e-9) * len(image_list)) + 10
        image_index = max(1, image_index)
    else:
        raise ValueError(f"Invalid time-of-day category: {time_of_day}")
    return image_index


# ============================================================================
# High-level detection / selection
# ============================================================================

def _get_sun(config_path: Optional[str], lat: float, lon: float,
             mock_sun=None, now: Optional[datetime] = None):
    """Fetch sun values (mock or real) and normalize ``now``.

    Returns (sun_dict, now, timezone_str, target_tz, used_mock).
    """
    timezone_str, cfg_lat, cfg_lon = _config_location(config_path)
    lat = lat if mock_sun is not None else cfg_lat
    lon = lon if mock_sun is not None else cfg_lon
    target_tz = ZoneInfo(timezone_str)

    if mock_sun is not None:
        sun = _mock_sun_data(mock_sun)
        now = _normalize_now(now, target_tz, mock_sun=mock_sun)
        return sun, now, timezone_str, target_tz, True

    sun = _real_sun_data(timezone_str, cfg_lat, cfg_lon)
    if sun is None:
        raise RuntimeError("Astral failed")
    _fix_next_day(sun)
    now = _normalize_now(now, target_tz, mock_sun=None)
    return sun, now, timezone_str, target_tz, False


def detect_time_of_day_sun(config_path: Optional[str] = None,
                           lat: float = 39.5, lon: float = -119.8,
                           elevation: float = 0, mock_sun=None,
                           now: Optional[datetime] = None,
                           current_time: Optional[datetime] = None) -> str:
    """Detect current time-of-day category using Astral sunrise/sunset times.

    Args:
        config_path: Optional path to config file containing location data
        lat: Latitude for sunrise/sunset calculation (default: 39.5)
        lon: Longitude for sunrise/sunset calculation (default: -119.8)
        elevation: Elevation in meters (default: 0, unused)
        mock_sun: Optional mock sun object for testing
        now: Optional specific datetime to test (default: datetime.now())
        current_time: Alias for 'now' for backward compatibility

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    if current_time is not None:
        now = current_time

    # If Astral is unavailable, load and use previous day's backup schedule
    if not ASTRAL_AVAILABLE and mock_sun is None:
        from kwallpaper.backup import load_daily_backup_schedule
        backup = load_daily_backup_schedule()
        if backup:
            return backup['time_of_day']
        raise RuntimeError("Astral unavailable and no previous day backup exists")

    try:
        sun, now, _, _, _ = _get_sun(config_path, lat, lon,
                                     mock_sun=mock_sun, now=now)
        result = time_of_day_for(now, sun)
        # Save successful Astral schedule to backup (real sun only)
        if mock_sun is None:
            from kwallpaper.backup import save_daily_backup_schedule
            save_daily_backup_schedule(sun.get('dawn'), sun.get('sunrise'),
                                       sun.get('sunset'), sun.get('dusk'),
                                       result)
        return result
    except Exception as e:
        # Astral failed - try to load previous day's backup
        logger.debug(f"detect_time_of_day_sun failed: {e}")
        from kwallpaper.backup import load_daily_backup_schedule
        backup = load_daily_backup_schedule()
        if backup:
            return backup['time_of_day']
        raise RuntimeError(f"Astral failed and no previous day backup exists: {e}")


def detect_time_of_day_for_time(time_str: str,
                                config_path: Optional[str] = None) -> str:
    """Detect time-of-day category for a specific time string (HH:MM format)."""
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("Invalid time format")

        today = datetime.now().date()
        now = datetime.combine(today, datetime.strptime(time_str, '%H:%M').time())

        timezone_str = "America/Los_Angeles"
        if config_path:
            try:
                from kwallpaper.config import load_config
                config = load_config(config_path)
                timezone_str = config.get('location', {}).get(
                    'timezone', timezone_str)
            except Exception:
                pass

        now = now.replace(tzinfo=ZoneInfo(timezone_str))

        try:
            time_of_day = detect_time_of_day_sun(config_path, now=now)
            if time_of_day in TIME_CATEGORIES:
                return time_of_day
        except Exception:
            pass

        from kwallpaper.backup import load_daily_backup_schedule
        backup = load_daily_backup_schedule()
        if backup:
            return backup['time_of_day']
        raise RuntimeError("Astral failed and no previous day backup exists")

    except ValueError as e:
        raise ValueError(f"Invalid time format. Expected HH:MM, e.g., 14:30: {e}")

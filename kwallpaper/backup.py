#!/usr/bin/env python3
"""
kWallpaper daily schedule backup.

Persists the previous day's astral schedule so the app can still classify
time-of-day when Astral is unavailable or fails at runtime.

Exactly one backup file is kept at a time: ``schedule_backup.json``.  It
always contains the most recent successful schedule (tagged with the date
it was computed for) and is overwritten on every save.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from kwallpaper.config import DEFAULT_SCHEDULE_BACKUP_DIR

#: Single rolling backup file (overwritten on every save).
BACKUP_FILE_NAME = "schedule_backup.json"


def get_daily_backup_path() -> Path:
    """Get the path to the (single, rolling) schedule backup file."""
    return DEFAULT_SCHEDULE_BACKUP_DIR / BACKUP_FILE_NAME


def load_daily_backup_schedule() -> Optional[Dict[str, Any]]:
    """Load the most recent backup schedule if it exists and is valid.

    The backup is only useful for the *previous* day's sun times, so a
    backup whose date is older than yesterday is ignored (treated as
    missing).
    """
    backup_path = get_daily_backup_path()
    if not backup_path.exists():
        return None

    try:
        with open(backup_path, 'r') as f:
            backup = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Validate JSON structure
    if not isinstance(backup, dict):
        return None

    # Validate required fields
    required = ['dawn', 'sunrise', 'sunset', 'dusk', 'time_of_day', 'previous_date']
    if not all(k in backup for k in required):
        return None

    # Only the previous day's schedule is usable as a fallback.
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if backup.get('previous_date') != yesterday:
        return None

    return backup


def save_daily_backup_schedule(
    dawn: Optional[datetime],
    sunrise: Optional[datetime],
    sunset: Optional[datetime],
    dusk: Optional[datetime],
    time_of_day: str
) -> None:
    """Save the current schedule to the single rolling backup file.

    Overwrites any previous backup; the file is tagged with yesterday's
    date (the schedule it stands in for when Astral is unavailable).
    """
    DEFAULT_SCHEDULE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    backup = {
        'date': yesterday,
        'dawn': dawn.isoformat() if dawn else None,
        'sunrise': sunrise.isoformat() if sunrise else None,
        'sunset': sunset.isoformat() if sunset else None,
        'dusk': dusk.isoformat() if dusk else None,
        'time_of_day': time_of_day,
        'timestamp': datetime.now().isoformat(),
        'source': 'astral',
        'previous_date': yesterday
    }

    with open(get_daily_backup_path(), 'w') as f:
        json.dump(backup, f, indent=2)

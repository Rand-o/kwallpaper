#!/usr/bin/env python3
"""
kWallpaper daily schedule backup.

Persists the previous day's astral schedule so the app can still classify
time-of-day when Astral is unavailable or fails at runtime.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from kwallpaper.config import DEFAULT_SCHEDULE_BACKUP_DIR


def get_daily_backup_path() -> Path:
    """Get the path to previous day's schedule backup file."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return DEFAULT_SCHEDULE_BACKUP_DIR / f"schedule_{yesterday}.json"


def load_daily_backup_schedule() -> Optional[Dict[str, Any]]:
    """Load previous day's backup schedule if it exists and is valid."""
    backup_path = get_daily_backup_path()
    if not backup_path.exists():
        return None

    try:
        with open(backup_path, 'r') as f:
            backup = json.load(f)

        # Validate required fields
        required = ['dawn', 'sunrise', 'sunset', 'dusk', 'time_of_day', 'previous_date']
        if not all(k in backup for k in required):
            return None

        # Validate JSON structure
        if not isinstance(backup, dict):
            return None

        return backup
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_daily_backup_schedule(
    dawn: Optional[datetime],
    sunrise: Optional[datetime],
    sunset: Optional[datetime],
    dusk: Optional[datetime],
    time_of_day: str
) -> None:
    """Save previous day's schedule to backup file with 'previous_date' field."""
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

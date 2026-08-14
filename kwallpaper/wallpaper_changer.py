#!/usr/bin/env python3
"""
kWallpaper - Core functionality module (compatibility facade).

This module used to be a ~2,700-line god module.  Phase 3 split it into:

- kwallpaper.config     paths, load/save/validate, dir bootstrap
- kwallpaper.backup     daily astral schedule backup
- kwallpaper.suntime    ONE implementation of dawn/sunrise/sunset/dusk math
- kwallpaper.selection  image file/index selection (theme.json + glob)
- kwallpaper.themes     discovery, extraction, import/delete, thumbnails
- kwallpaper.wallpaper  Plasma D-Bus wallpaper application
- kwallpaper.cli        argparse dispatch (run_*_command, main)
- kwallpaper.core       high-level apply/import/delete API

Everything below is re-exported so existing imports
(``from kwallpaper.wallpaper_changer import X``) keep working.
"""

import logging

from kwallpaper.config import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    DEFAULT_CACHE_DIR,
    DEFAULT_SCHEDULE_BACKUP_DIR,
    DEFAULT_THEMES_DIR,
    DEFAULT_SHUFFLE_LIST_PATH,
    create_default_config,
    ensure_config_dirs,
    create_backup_file,
    load_config,
    save_config,
    validate_config,
)

from kwallpaper.backup import (
    get_daily_backup_path,
    load_daily_backup_schedule,
    save_daily_backup_schedule,
)

from kwallpaper.suntime import (
    ASTRAL_AVAILABLE,
    DURATION_DAWN_MINUTES,
    DURATION_SUNRISE_MINUTES,
    DURATION_SUNSET_MINUTES,
    DURATION_DUSK_MINUTES,
    DURATION_IMAGE_9_MINUTES,
    TRANSITION_OFFSET_MINUTES,
    TIME_CATEGORIES,
    calculate_image_spacing,
    get_period_duration,
    period_boundaries,
    time_of_day_for,
    image_period,
    index_period,
    image_index_for,
    detect_time_of_day_sun,
    detect_time_of_day_for_time,
)

from kwallpaper.selection import (
    select_image_for_time_cli,
    select_image_for_specific_time,
    select_image_for_time,
)

from kwallpaper.themes import (
    discover_themes,
    resolve_theme_path,
    normalize_image_lists,
    extract_theme,
    import_theme,
    delete_theme,
    ensure_thumbnail,
)

from kwallpaper.wallpaper import (
    change_wallpaper,
    get_current_wallpaper,
)

from kwallpaper.cli import (
    validate_time_of_day,
    run_extract_command,
    run_change_command,
    run_cycle_command,
    run_shuffle_list_command,
    run_list_command,
    run_status_command,
    run_themes_command,
    run_themes_list,
    run_themes_add,
    run_themes_remove,
    run_themes_reshuffle,
    main,
)

# Legacy alias used by the monitor loop
_datetime_timezone = None

logger = logging.getLogger(__name__)

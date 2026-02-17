# KDE Wallpaper Changer - Codebase Summary

## Overview

A beautiful, native KDE Plasma 6 application for automatically changing wallpapers based on time-of-day categories using `.ddw` (KDE wallpaper theme) zip files. Features a modern GUI with cross-fade image previews, scheduler controls, and system tray integration.

**Project URL:** https://github.com/Rand-o/kwallpaper

## Architecture

### Directory Structure

```
kwallpaper/
├── wallpaper_gui.py              # Main GUI application (1069 lines)
├── wallpaper_cli.py              # CLI wrapper (29 lines)
├── kwallpaper/
│   ├── __init__.py               # Package initialization
│   ├── wallpaper_changer.py      # Core module (848 lines)
│   ├── scheduler.py              # Background scheduler (243 lines)
│   └── shuffle_list_manager.py   # Theme shuffling (186 lines)
├── tests/                        # Test suite
│   ├── test_config.py
│   ├── test_config_validation.py
│   ├── test_zip_extraction.py
│   ├── test_helper_functions.py
│   ├── test_wallpaper_change.py
│   ├── test_full_day_astral.py
│   └── test_astral_time_detection.py
├── requirements.txt              # Python dependencies
└── README.md                     # User documentation
```

### Code Organization

**Three main entry points:**

1. **`wallpaper_gui.py`** - Main GUI application with PyQt6, providing:
   - Native KDE Plasma 6 integration
   - Cross-fade image preview widget
   - System tray with scheduler controls
   - Multiple tab interface (Themes, Settings, Scheduler)
   - Single-instance enforcement via socket

2. **`wallpaper_cli.py`** - Simple CLI wrapper that imports and runs the main function from `kwallpaper/wallpaper_changer.py`

3. **`kwallpaper/wallpaper_changer.py`** - Core module containing all background functionality:
   - Configuration management
   - Theme extraction
   - Time-of-day detection using Astral
   - Image selection algorithms
   - Wallpaper change commands

## Core Functionality

### 1. Configuration Management

**Default config location:** `~/.var/app/org.kde.kwallpaper/config/wallpaper-changer/config.json`

```json
{
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "scheduling": {
    "interval": 60,
    "run_cycle": true,
    "daily_shuffle_enabled": true
  },
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix"
  },
  "application": {
    "theme_mode": "system"
  },
  "theme": {
    "last_applied": "theme-name"
  }
}
```

**Key functions:**
- `load_config()` - Loads and validates config from JSON
- `save_config()` - Saves configuration changes
- `validate_config()` - Ensures required fields and valid types

### 2. Theme Extraction

**Source:** `.ddw` zip files containing:
- Image files (JPEG)
- Theme metadata JSON (e.g., `24hr-Tahoe-2026.json`)

**Extraction process:**
1. Creates cache directory: `~/.var/app/org.kde.kwallpaper/cache/wallpaper-changer/{theme-name}/`
2. Extracts zip contents to cache directory
3. Finds and parses theme metadata JSON
4. Normalizes image lists (ensures image 1 in sunrise)
5. Returns extracted directory path and metadata

**Key functions:**
- `extract_theme()` - Extracts theme from zip, creates/reuses cache directory
- `normalize_image_lists()` - Ensures image 1 is in sunrise, not night
- `discover_themes()` - Lists all extracted themes

### 3. Time-of-Day Detection

**Categories and time ranges:**
- `night`: 00:00 - 04:59
- `sunrise`: 05:00 - 06:59
- `day`: 07:00 - 16:59
- `sunset`: 17:00 - 18:59

**Key functions:**
- `detect_time_of_day(hour)` - Returns category based on hour (uses current time if not provided)

### 3. Time-of-Day Detection

**Categories and time ranges (calculated by Astral):**
- `night`: From dusk until dawn-30min (last 30 min shows image 1)
- `sunrise`: From dawn-30min until sunrise+45min
- `day`: From sunrise+45min until sunset-45min
- `sunset`: From sunset-45min until dusk

**Key functions:**
- `detect_time_of_day_sun()` - Returns category using Astral calculations
- `select_image_for_time()` - Selects image based on position in time period

### 4. Image Selection

**Selection algorithm:**
1. Loads config (theme and position data)
2. Gets time-of-day category using Astral
3. Gets image list for current category from theme metadata
4. Calculates position within time period
5. Selects image index based on position
6. Finds image file matching pattern
7. Returns full path to selected image

**Key functions:**
- `select_image_for_time()` - Selects image based on time position
- `select_image_for_time_cli()` - CLI wrapper with file path handling

### 5. Wallpaper Change

**Method:** Uses `plasma-apply-wallpaperimage` command (most reliable)

**Fallback:** If plasma-apply-wallpaperimage fails, uses `kwriteconfig5` with verification

**Process:**
1. Checks if Plasma is running (`pgrep -x plasmashell`)
2. Runs `plasma-apply-wallpaperimage <image-path>`
3. Verifies wallpaper was set using `kreadconfig5`
4. Returns success/failure status

**Key functions:**
- `change_wallpaper()` - Changes KDE Plasma wallpaper
- `get_current_wallpaper()` - Retrieves current wallpaper path

### 6. Background Scheduler

**Based on:** APScheduler library for robust background task management

**Tasks:**
- Cycle task - Runs at configurable interval
- Change task - Enables theme shuffling

**Key functions:**
- `SchedulerManager` - Manages scheduler lifecycle
- `create_scheduler()` - Factory function for scheduler creation

### 7. Theme Shuffling

**Purpose:** Rotate between multiple themes automatically

**Features:**
- Random shuffle list creation
- Daily state persistence
- Automatic reshuffle when list exhausted

**Key functions:**
- `create_initial_shuffle()` - Creates shuffled theme list
- `save_shuffle_list()` - Persists shuffle state
- `load_shuffle_list()` - Loads shuffle state
- `get_next_theme()` - Gets next theme in rotation

## Key Design Decisions

### 1. Cache Directory Naming
**Decision:** Use theme name instead of timestamp

**Reasoning:**
- Avoids creating 20+ directories for same theme
- Makes cache organized and easy to navigate
- `mkdir(..., exist_ok=True)` handles existing directories
- Original .ddw file preserved for regeneration

### 2. Wallpaper Setting Method
**Decision:** Use `plasma-apply-wallpaperimage` instead of `kwriteconfig5` alone

**Reasoning:**
- `kwriteconfig5` alone doesn't apply wallpaper in KDE Plasma
- `plasma-apply-wallpaperimage` is the proper Plasma API
- Falls back to `kwriteconfig5` if plasma-apply fails
- More reliable and follows KDE best practices

### 3. JSON File Detection
**Decision:** Search for any `.json` file in root first, then recursive `theme.json`

**Reasoning:**
- Some .ddw files use custom names (24hr-Tahoe-2026.json)
- Some may have nested structure requiring recursive search
- Handles both cases without breaking existing functionality

### 4. Two-File Structure
**Decision:** Separate `wallpaper_cli.py` from `kwallpaper/wallpaper_changer.py`

**Reasoning:**
- `wallpaper_cli.py` - 29 lines, simple entry point
- `kwallpaper/wallpaper_changer.py` - 848 lines, self-contained module
- Follows Python package conventions
- Makes module importable for testing and reuse

## Troubleshooting

**Common issues:**

1. **Wallpaper not changing:**
   - Check Plasma is running: `pgrep -x plasmashell`
   - Verify image path exists
   - Check permissions on image file

2. **Theme.json not found:**
   - Verify .ddw file contains JSON file
   - Check file isn't corrupted

3. **Plasma not responding:**
   - Restart Plasma: `plasmashell --replace`

## Future Enhancements

**Potential improvements:**
- Support for PNG and other image formats
- Animated wallpaper support
- Multiple monitor support
- Custom time range configuration
- Wallpaper fade-in transitions
- Theme repository integration

## Technical Details

**Image matching:**
1. Uses `Path.glob()` with pattern from metadata
2. Falls back to numbered files if pattern doesn't match
3. Sorts files for consistent ordering
4. Maps 1-based index to 0-based list access

**Error handling:**
- Comprehensive try-catch blocks
- Specific error messages for common issues
- Graceful fallbacks (e.g., plasma-apply → kwriteconfig5)
- Config validation before use

**Performance:**
- One-time extraction from zip
- Config persistence avoids re-extraction
- Image files cached in memory while running
- No unnecessary file operations

## Author

Created for use with KDE Plasma on Fedora 43.

## License

This project is provided as-is for personal use.

# KDE Wallpaper Changer - Codebase Summary

## Overview

A Python CLI tool for KDE Plasma that automatically changes wallpapers based on time-of-day categories using `.ddw` (KDE wallpaper theme) zip files.

**Project URL:** https://github.com/Rand-o/kwallpaper

## Architecture

### Directory Structure

```
kwallpaper/
├── __init__.py                  # Package initialization
├── wallpaper_changer.py         # Core module (848 lines)
├── requirements.txt             # Python dependencies
├── setup.py                     # Installation configuration
├── README.md                    # User documentation
└── tests/                       # Test suite
    ├── test_config.py
    ├── test_config_validation.py
    ├── test_zip_extraction.py
    ├── test_image_selection.py
    ├── test_time_of_day.py
    ├── test_wallpaper_change.py
    └── test_cli.py

wallpaper_cli.py                 # CLI entry point (29 lines)
```

### Code Organization

**Two main entry points:**

1. **`wallpaper_cli.py`** - Simple CLI wrapper that imports and runs the main function from `kwallpaper/wallpaper_changer.py`

2. **`kwallpaper/wallpaper_changer.py`** - Core module containing all functionality:
   - Configuration management
   - Theme extraction
   - Image selection
   - Wallpaper changes
   - CLI argument parsing

## Core Functionality

### 1. Configuration Management

**Default config location:** `~/.config/wallpaper-changer/config.json`

```json
{
  "interval": 5400,           // Seconds between changes (1.5 hours)
  "retry_attempts": 3,        // Retry attempts on failure
  "retry_delay": 5,           // Delay between retries (seconds)
  "current_image_index": 0,   // Current image in cycling sequence
  "current_time_of_day": "day" // Current time category
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
1. Creates cache directory: `~/.cache/wallpaper-changer/{theme-name}/`
2. Extracts zip contents to cache directory
3. Finds and parses theme metadata JSON
4. Returns extracted directory path and metadata

**Theme metadata structure:**
```json
{
  "displayName": "Tahoe 2026",
  "imageCredits": "24 Hour Wallpaper",
  "imageFilename": "24hr-Tahoe-2026_*.jpeg",
  "sunsetImageList": [10, 11, 12, 13],
  "sunriseImageList": [2, 3, 4],
  "dayImageList": [5, 6, 7, 8, 9],
  "nightImageList": [14, 15, 16, 1]
}
```

**Key functions:**
- `extract_theme()` - Extracts theme from zip, creates/reuses cache directory
- Supports both `.zip` and `.ddw` file extensions
- Searches for JSON files in root or recursively

### 3. Time-of-Day Detection

**Categories and time ranges:**
- `night`: 00:00 - 04:59
- `sunrise`: 05:00 - 06:59
- `day`: 07:00 - 16:59
- `sunset`: 17:00 - 18:59

**Key functions:**
- `detect_time_of_day(hour)` - Returns category based on hour (uses current time if not provided)

### 4. Image Selection

**Selection algorithm:**
1. Loads current config (image index + time category)
2. Gets image list for current time-of-day from theme metadata
3. If category has no images, switches to next category (sunrise → day → sunset → night)
4. Validates image index (wraps around if exceeds available images)
5. Finds image file matching pattern:
   - First tries pattern from `imageFilename` metadata (e.g., `24hr-Tahoe-2026_*.jpeg`)
   - Falls back to numbered files: `name_1.jpeg`, `name_2.jpeg`, etc.
6. Updates config with new index and category
7. Returns full path to selected image

**Key functions:**
- `select_next_image(theme_path, config_path)` - Selects and returns image path

### 5. Wallpaper Change

**Method:** Uses `plasma-apply-wallpaperimage` command (most reliable)

**Fallback:** If plasma-apply-wallpaperimage fails, uses `kwriteconfig5` with verification

**Process:**
1. Checks if Plasma is running (`pgrep -x plasmashell`)
2. Runs `plasma-apply-wallpaperimage <image-path>`
3. Verifies wallpaper was set using `kreadconfig5`
4. Returns success/failure status

**Key functions:**
- `change_wallpaper(image_path)` - Changes KDE Plasma wallpaper
- `get_current_wallpaper()` - Retrieves current wallpaper path

## CLI Commands

### extract
Extract theme from `.ddw` zip file to cache directory.

```bash
./wallpaper_cli.py extract --theme-path theme.ddw --cleanup
```

**Options:**
- `--theme-path`: Path to zip file
- `--cleanup`: Remove temp directory after extraction

### change
Change wallpaper to next image in current time category.

```bash
./wallpaper_cli.py change --theme-path theme.ddw
```

**Options:**
- `--theme-path`: Path to zip file or extracted directory
- `--config`: Custom config file path
- `--monitor`: Continuous mode (cycles wallpapers based on time)

### list
List images for a specific time-of-day category.

```bash
./wallpaper_cli.py list --theme-path theme --time-of-day day
```

**Options:**
- `--theme-path`: Path to theme directory
- `--time-of-day`: Category (sunrise/day/sunset/night)
- `--config`: Custom config file path

### status
Check current wallpaper and configuration.

```bash
./wallpaper_cli.py status
```

## Workflow Examples

### Single Wallpaper Change
```
1. User runs: ./wallpaper_cli.py change --theme-path theme.ddw
2. Script extracts theme to ~/.cache/wallpaper-changer/theme-name/
3. Loads config (current_image_index=0, current_time_of_day="day")
4. Gets dayImageList = [5, 6, 7, 8, 9]
5. Selects image at index 0: 24hr-Tahoe-2026_5.jpeg
6. Changes wallpaper using plasma-apply-wallpaperimage
7. Updates config: current_image_index=1
8. Saves config
```

### Monitor Mode (Continuous)
```
1. User runs: ./wallpaper_cli.py change --theme-path theme.ddw --monitor
2. Loop starts:
   a. Checks current time
   b. If time category changed → select new image
   c. Change wallpaper
   d. Wait for interval (default 5400 seconds)
   e. Repeat
3. User presses Ctrl+C to stop
```

## Theme Detection Logic

**When changing wallpaper:**
1. Extracts theme if zip file provided
2. Searches for JSON metadata file (root or recursive)
3. Parses theme metadata
4. Checks config for `current_time_of_day`
5. Gets image list for that category
6. If empty, cycles through categories until finding images
7. Selects image at `current_image_index`
8. Updates config

**JSON file detection:**
- First checks root directory for any `.json` file
- Falls back to recursive search for `theme.json`
- Supports files like `24hr-Tahoe-2026.json`

## Configuration Persistence

**What persists across reboots:**
- `current_image_index` - Which image to show next
- `current_time_of_day` - Current time category

**What doesn't persist:**
- Extracted theme files (regenerated from .ddw zip)

**Why this design:**
- Config is small (2 integers) - easy to restore
- Themes are large (100MB+) - extracted on demand
- Original .ddw zip file always available for regeneration

## Dependencies

**System requirements:**
- KDE Plasma 5.x
- `kwriteconfig5` - KDE config tool
- `kreadconfig5` - KDE config read tool
- `plasma-apply-wallpaperimage` - Plasma wallpaper setter

**Python requirements:**
- Python 3.8+
- No external Python packages required

## Testing

**Test coverage:** 34/35 tests passing

**Test files:**
- `test_config.py` - Configuration loading and validation
- `test_config_validation.py` - Config schema validation
- `test_zip_extraction.py` - Theme extraction from zip
- `test_image_selection.py` - Image selection logic
- `test_time_of_day.py` - Time-of-day detection
- `test_wallpaper_change.py` - Wallpaper change functionality
- `test_cli.py` - CLI argument parsing

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

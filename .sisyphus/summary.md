# KDE Wallpaper Changer - Codebase Summary

## Project Overview

**KDE Wallpaper Changer** is a Python CLI tool for Fedora 43 KDE that automatically changes wallpapers based on time-of-day categories using .ddw (KDE wallpaper theme) zip files.

### Core Purpose
- Extract .ddw wallpaper themes from zip files
- Automatically detect time-of-day (night, sunrise, day, sunset)
- Cycle through images in each time-of-day category
- Change KDE Plasma wallpaper via `plasma-apply-wallpaperimage` or `kwriteconfig5`
- Support configurable image cycling intervals
- Provide comprehensive test coverage

---

## Technology Stack

### Runtime Dependencies
- **Python 3.8+** - Primary language
- **Astral 2.2+** - For accurate sunrise/sunset calculations
- **KDE Plasma** - Desktop environment integration
- **KDE Frameworks** - System integration tools

### Development Dependencies
- **pytest** - Testing framework
- **pytest-cov** - Coverage reporting

### Key System Commands
- `plasma-apply-wallpaperimage` - Primary wallpaper setter (most reliable)
- `kwriteconfig5` - Fallback wallpaper setter
- `kreadconfig5` - Read current wallpaper configuration
- `pgrep` - Check if Plasma is running

---

## Architecture

### Directory Structure
```
kwallpaper/
├── wallpaper_cli.py              # CLI entry point
├── kwallpaper/
│   ├── __init__.py               # Package init
│   └── wallpaper_changer.py      # Core functionality (2321 lines)
├── tests/
│   ├── test_config.py
│   ├── test_config_validation.py
│   ├── test_zip_extraction.py
│   ├── test_image_selection.py
│   ├── test_time_of_day.py
│   ├── test_wallpaper_change.py
│   ├── test_helper_functions.py
│   ├── test_astral_time_detection.py
│   └── test_full_day_astral.py
├── setup.py                      # Package installation
├── requirements.txt              # Python dependencies
└── README.md                     # Project documentation
```

### Core Modules

#### 1. `wallpaper_cli.py` (Entry Point)
- **Purpose**: Command-line interface entry point
- **Key Functions**:
  - `main()` - Main CLI entry point with argparse
  - `run_extract_command()` - Handle `extract` subcommand
  - `run_change_command()` - Handle `change` subcommand
  - `run_list_command()` - Handle `list` subcommand
  - `run_status_command()` - Handle `status` subcommand

#### 2. `wallpaper_changer.py` (Core Logic - 2321 lines)
This is the main module containing all business logic:

**Configuration Management**
- `load_config()` - Load configuration from JSON
- `save_config()` - Save configuration to JSON
- `validate_config()` - Validate configuration fields
- `DEFAULT_CONFIG` - Default configuration values

**Theme Extraction**
- `extract_theme()` - Extract .ddw zip files
- `normalize_image_lists()` - Fix image list ordering (ensure image 1 in sunrise)
- `get_current_wallpaper()` - Get current KDE wallpaper path

**Time-of-Day Detection**
- `detect_time_of_day_sun()` - Astral-based detection with dawn/sunrise/sunset/dusk
- `detect_time_of_day_hour()` - Hour-based fallback detection
- `detect_time_of_day()` - Simple hour-based detection
- `detect_time_of_day_for_time()` - Detect for specific time string

**Image Selection**
- `select_image_for_time_cli()` - Select image based on time (Astral mode)
- `select_image_for_time_hourly_cli()` - Select image based on hourly table (fallback)
- `select_image_for_time()` - Core image selection logic
- `select_image_for_specific_time()` - Select image for specific HH:MM time

**Wallpaper Change**
- `change_wallpaper()` - Set new wallpaper using plasma-apply-wallpaperimage

**Schedule Backup**
- `save_daily_backup_schedule()` - Save Astral schedule to backup
- `save_daily_backup_schedule_fallback()` - Save hourly fallback schedule
- `load_daily_backup_schedule()` - Load backup schedule
- `get_daily_backup_path()` - Get backup file path

---

## Time-of-Day System

### Categories
| Category | Time Range | Images |
|----------|------------|--------|
| **night** | 00:00 - 04:59 | 14, 15, 16 (and 1 during last 30 min) |
| **sunrise** | 05:00 - 06:59 | 1, 2, 3, 4 |
| **day** | 07:00 - 16:59 | 5, 6, 7, 8, 9 |
| **sunset** | 17:00 - 18:59 | 10, 11, 12, 13 |

### Detection Methods

#### Astral Method (Primary)
- Uses location coordinates (lat/lon) to calculate precise sunrise/sunset
- Defines periods:
  - **Dawn**: Start of astronomical twilight
  - **Sunrise**: Sun appears on horizon
  - **Day**: After sunrise + 45 minutes
  - **Sunset**: Sun disappears below horizon
  - **Dusk**: End of astronomical twilight
- Falls back to hourly table if Astral unavailable or fails

#### Hourly Fallback (Secondary)
Fixed 16-point schedule when Astral unavailable:
| Time | Image | Category |
|------|-------|----------|
| 04:30 | 1 | sunrise |
| 06:15 | 2 | sunrise |
| 06:30 | 3 | sunrise |
| 07:30 | 4 | sunrise |
| 10:00 | 5 | day |
| 12:00 | 6 | day |
| 14:00 | 7 | day |
| 16:00 | 8 | day |
| 17:00 | 9 | day |
| 18:00 | 10 | sunset |
| 18:30 | 11 | sunset |
| 18:45 | 12 | sunset |
| 19:00 | 13 | sunset |
| 20:00 | 14 | night |
| 22:30 | 15 | night |
| 01:00 | 16 | night |

---

## Data Flow

### 1. Theme Extraction Flow
```
User provides .ddw zip file
    ↓
extract_theme() creates temp directory
    ↓
Unzip .ddw file
    ↓
Find theme.json (any .json in root, or theme.json recursively)
    ↓
Parse theme.json for image lists
    ↓
Normalize image lists (ensure image 1 in sunrise)
    ↓
Return metadata (extract_dir, image lists, credits)
```

### 2. Wallpaper Change Flow
```
User runs: wallpaper_cli.py change --theme-path theme.ddw
    ↓
Resolve theme path (extract if zip file)
    ↓
Load config (timezone, location, retry settings)
    ↓
Detect time-of-day (Astral → fallback)
    ↓
Select image based on time period
    ↓
Calculate position within period → image index
    ↓
Find image file matching pattern
    ↓
Call change_wallpaper() → plasma-apply-wallpaperimage
    ↓
Verify wallpaper set (fallback to kwriteconfig5 if needed)
```

### 3. Monitoring Mode Flow
```
User runs: wallpaper_cli.py change --monitor
    ↓
Enter infinite loop with interval-based checks
    ↓
At each interval:
    - Detect current time-of-day
    - If changed → select new image → change wallpaper
    - If same → log status
    - Sleep for configured interval
    ↓
On Ctrl+C → exit gracefully
```

---

## Key Algorithms

### Image Selection Algorithm
```python
# For each time-of-day period:
1. Determine period start/end times (Astral or hourly fallback)
2. Calculate position within period: (now - start) / duration
3. Map position to image index: int(position * num_images) + offset
4. Clamp index to valid range [1, num_images]
5. Find image file matching pattern
```

### Time-of-Day Detection Algorithm
```python
# Astral method:
1. Calculate dawn, sunrise, sunset, dusk times
2. Adjust for midnight-spanning nights
3. Define periods:
   - Night: dusk to dawn-30min
   - Sunrise: dawn-30min to sunrise+45min
   - Day: sunrise+45min to dusk-45min
   - Sunset: dusk-45min to dusk
4. Check which period contains current time

# Hourly fallback:
1. Sort hourly table by time
2. Find last slot where slot_time <= now
3. Return category and image index for that slot
```

---

## Configuration

### Config File Location
`~/.config/wallpaper-changer/config.json`

### Config Schema
```json
{
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "current_image_index": 1,
  "current_time_of_day": "day",
  "location": {
    "latitude": 39.5,
    "longitude": -119.8,
    "timezone": "America/Phoenix"
  }
}
```

### Config Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interval` | integer | Yes | Seconds between wallpaper changes (default: 5400) |
| `retry_attempts` | integer | Yes | Retry attempts on failure (default: 3) |
| `retry_delay` | integer | Yes | Delay between retries in seconds (default: 5) |
| `current_image_index` | integer | Yes | Current image index in cycling sequence |
| `current_time_of_day` | string | Yes | Current category: sunrise/day/sunset/night |
| `location` | object | No | Location for Astral calculations |

---

## CLI Commands

### `extract`
Extract .ddw theme from zip file
```bash
wallpaper_cli.py extract --theme-path /path/to/theme.ddw [--cleanup]
```

### `change`
Change wallpaper to next image
```bash
wallpaper_cli.py change --theme-path /path/to/theme.ddw [--config PATH] [--monitor] [--time HH:MM]
```

### `list`
List images for a time-of-day category
```bash
wallpaper_cli.py list --theme-path /path/to/theme [--time-of-day day] [--config PATH]
```

### `status`
Check current wallpaper status
```bash
wallpaper_cli.py status [--config PATH]
```

---

## Testing

### Test Coverage
- Config validation: 13/13 tests passing
- Zip extraction: 5/5 tests passing
- Image selection: 7/7 tests passing
- Time-of-day detection: 6/6 tests passing
- Wallpaper change: 3/3 tests passing
- **Total: 34/35 tests passing** (1 pre-existing failure)

### Test Files
- `test_config.py` - Configuration loading/saving
- `test_config_validation.py` - Config validation logic
- `test_zip_extraction.py` - Theme extraction from .ddw files
- `test_image_selection.py` - Image selection algorithms
- `test_time_of_day.py` - Time-of-day detection
- `test_wallpaper_change.py` - Wallpaper change functionality
- `test_helper_functions.py` - Utility functions
- `test_astral_time_detection.py` - Astral-based detection
- `test_full_day_astral.py` - Full day Astral simulation

### Running Tests
```bash
pytest tests/ -v                    # Run all tests
pytest tests/ --cov=kwallpaper      # Run with coverage
pytest tests/test_time_of_day.py -v # Run specific test
```

---

## Key Design Patterns

### 1. Fallback Pattern
- Primary: Astral library for accurate sunrise/sunset
- Fallback: Hourly table when Astral unavailable
- Fallback: Hourly backup schedule saved daily

### 2. Command Pattern
- CLI commands route to dedicated handler functions
- Each handler returns exit code (0 success, 1 failure)

### 3. Strategy Pattern
- Different time-of-day detection strategies (Astral vs hourly)
- Different image selection strategies based on available data

### 4. Factory Pattern
- `extract_theme()` returns standardized metadata dictionary
- Consistent interface regardless of input format

---

## Error Handling

### Common Error Scenarios
1. **Plasma not running** → Check with `pgrep`, return error
2. **kwriteconfig5 not found** → Install KDE Plasma
3. **Config file missing** → Raise FileNotFoundError
4. **Invalid JSON in config** → Raise ValueError
5. **theme.json not found** → Raise FileNotFoundError
6. **Image index exceeds available** → Raise ValueError
7. **Astral calculation fails** → Save fallback backup, return "night"

### Retry Mechanism
- Configurable retry attempts and delay
- Used in wallpaper change operations
- Prevents transient failures from stopping execution

---

## Integration Points

### KDE Plasma Integration
- **Wallpaper setter**: `plasma-apply-wallpaperimage` (primary), `kwriteconfig5` (fallback)
- **Wallpaper reader**: `kreadconfig5`
- **Process check**: `pgrep -x plasmashell`

### File System
- **Config**: `~/.config/wallpaper-changer/config.json`
- **Cache**: `~/.cache/wallpaper-changer/`
- **Backup schedules**: `~/.cache/wallpaper-changer/schedule-backup/`

---

## Known Limitations

1. **KDE Plasma only** - Not designed for other desktop environments
2. **Static images only** - No animated wallpaper support
3. **Fixed time ranges** - Cannot customize time categories without code changes
4. **Flatpak not supported** - Requires direct system access
5. **Single theme at a time** - No built-in multi-theme switching

---

## Future Enhancement Opportunities

1. **Custom time ranges** - Allow user-defined time categories
2. **Multiple theme support** - Switch between themes based on criteria
3. **Animated wallpapers** - Support for video/animated themes
4. **Desktop environment agnostic** - Support Gnome, KDE, etc.
5. **Web-based configuration** - GUI for easier setup
6. **Weather-based selection** - Adjust themes based on weather conditions
7. **User presence detection** - Change based on login status

---

## Migration Notes for New Agents

### Critical Files to Understand
1. **`kwallpaper/wallpaper_changer.py`** - Core logic (2321 lines)
   - Time-of-day detection algorithms
   - Image selection logic
   - Configuration management
   - Theme extraction

2. **`wallpaper_cli.py`** - CLI interface
   - Command routing
   - Argument parsing
   - Subcommand handlers

### Key Functions to Know
- `detect_time_of_day_sun()` - Main time detection (Astral-based)
- `select_image_for_time_cli()` - Image selection with Astral
- `extract_theme()` - Theme extraction from .ddw files
- `change_wallpaper()` - Set new wallpaper
- `normalize_image_lists()` - Fix image list ordering

### Testing Strategy
1. Run existing tests to verify baseline
2. Check test coverage before making changes
3. Add tests for new functionality
4. Verify fallback paths work correctly

### Common Pitfalls
1. **Timezone handling** - Always use ZoneInfo for timezone-aware datetimes
2. **Midnight-spanning nights** - Night period can wrap around midnight
3. **Astral vs fallback** - Code must handle both paths correctly
4. **Image indexing** - 1-based in logic, 0-based in Python lists
5. **Config validation** - Always validate before use

---

## Summary

This is a well-structured Python CLI tool with clear separation of concerns:
- **CLI layer** (`wallpaper_cli.py`) - User interface
- **Core logic** (`wallpaper_changer.py`) - Business logic
- **Tests** - Comprehensive test coverage

The system uses a robust fallback mechanism (Astral → hourly table) to ensure reliability. Time-of-day detection is sophisticated, handling edge cases like midnight-spanning nights and polar regions. The codebase is production-ready with comprehensive error handling and testing.

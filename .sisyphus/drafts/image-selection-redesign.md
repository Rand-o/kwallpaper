# Draft: kwallpaper Image Selection Redesign

## Requirements (confirmed)
- Redesign image selection to anchor images to astronomical events (dawn, sunrise, sunset, dusk)
- Use astral library for seasonal accuracy instead of fixed time buffers
- Map all 16 images to specific events or time periods
- Use ONLY 4 astral times as anchors (dawn, sunrise, sunset, dusk) - simplify approach
- Maintain existing hourly fallback when astral unavailable
- Use simple time-based scheduling instead of elevation-based complexity
- Add average durations for dawn/sunrise/sunset/dusk images (6 min for sunrise/sunset, 20 min for dawn/dusk)
- Add evenly spaced day and night images between anchor times
- Use TDD approach with pytest
- Graceful fallback to old hourly fallback when astral unavailable


## Image Assignment Plan (Simplified Approach)
### Astral Times as Anchors (Phoenix, AZ - Feb 3, 2026)
- Dawn: 06:56
- Sunrise: 07:22
- Sunset: 18:01
- Dusk: 18:28

### Image Durations
- Image 2 (Dawn): 20 minutes (starts at dawn)
- Image 3 (Sunrise): 6 minutes (starts at sunrise)
- Image 11 (Sunset): 6 minutes (starts at sunset)
- Image 13 (Dusk): 20 minutes (starts at dusk)

### Period 1: Dawn/Sunrise (Event-anchored)
- Image 2: Dawn (06:56 - 07:16) - 20 min
- Image 3: Sunrise (07:22 - 07:28) - 6 min
- Image 4: Post-sunrise (07:22 - 10:02) - Uses time_at_elevation(+4°)

### Period 2: Day (Evenly Spaced)
- Images 5-9 evenly spaced between Image 4 end (10:02) and Image 10 start (15:22)
- Interval: ~1 hour 19 minutes between images
- Image 5: 10:02 - 11:22
- Image 6: 11:22 - 12:42
- Image 7: 12:42 - 14:02
- Image 8: 14:02 - 15:22
- Image 9: 15:22 - 15:22 (NEEDS FIX - currently 0 duration)

### Period 3: Sunset/Dusk (Event-anchored)
- Image 10: Pre-sunset (15:22 - 17:22) - Uses time_at_elevation(+4°)
- Image 11: Sunset (18:01 - 18:07) - 6 min
- Image 12: Post-sunset (18:01 - 18:28) - Uses time_at_elevation(-2°)
- Image 13: Dusk (18:28 - 18:48) - 20 min

### Period 4: Night (Evenly Spaced)
- Images 14-16, 1 evenly spaced between dusk (18:28) and dawn (06:56 next day)
- Interval: ~4 hours 9 minutes between images
- Image 14: 18:28 - 22:37
- Image 15: 22:37 - 02:47
- Image 16: 02:47 - 06:56
- Image 1: 06:56 - 06:56 (NEEDS FIX - currently 24:00 duration, should be before dawn)

### Updated Schedule After User Decisions
- **Image 1**: Before dawn (last night image, ends at 06:56)
- **Image 2**: Dawn (06:56 - 07:16, 20 min)
- **Image 3**: Sunrise (07:22 - 07:28, 6 min)
- **Image 4**: Post-sunrise (07:22 - 10:02) - Uses time_at_elevation(+4°)
- **Image 5-8**: Evenly spaced between Image 4 end (10:02) and Image 9 start
- **Image 9**: 30 minutes duration (late day before pre-sunset)
- **Image 10**: Pre-sunset (Image 9 end - 15:22) - Uses time_at_elevation(+4°)
- **Image 11**: Sunset (18:01 - 18:07, 6 min)
- **Image 12**: Post-sunset (18:01 - 18:28) - Uses time_at_elevation(-2°)
- **Image 13**: Dusk (18:28 - 18:48, 20 min)

### Issues to Resolve
1. **Image 1 duration**: Currently shows 24:00 (overnight), should show last night image ending at dawn (06:56) with proper duration
2. **Image 9 duration**: Currently shows 0:00, should be 30 minutes
3. **Image 10 timing**: Should start after Image 9 ends (not fixed at 15:22)
4. **Calculate proper intervals**: Need to recalculate evenly spaced intervals for all images
## Configuration Constants
**Location**: `~/.config/wallpaper-changer/config.json` → location section

**New Fields to Add**:
```json
{
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix",
    "elevation_angle_post_sunrise": 4,
    "elevation_angle_pre_sunset": 4,
    "elevation_angle_post_sunset": -2
  }
}
```

**Field Descriptions**:
- `elevation_angle_post_sunrise`: Solar elevation (degrees) when image 4 should display (+4°)
- `elevation_angle_pre_sunset`: Solar elevation (degrees) when image 10 should display (+4°)
- `elevation_angle_post_sunset`: Solar elevation (degrees) when image 12 should display (-2°)

**Why Config-Based**: User can tune these values without code changes based on visual testing.

**Default Values**: +4° for image 4 (post-sunrise), +4° for image 10 (pre-sunset), -2° for image 12 (post-sunset)

### User Decisions (Confirmed)
 1. **Approach**: Use ONLY 4 astral times (dawn, sunrise, sunset, dusk) as anchors - simplify approach
 2. **Day Images**: Evenly spaced between Image 4 end and Image 10 start
 3. **Night Images**: Evenly spaced between dusk and dawn
 4. **Image 1**: Early morning sunlight (dawn period)
 5. **Image 9**: Late day before pre-sunset
 6. **Average Durations**: 6 min for sunrise/sunset, 20 min for dawn/dusk
 7. **Test Strategy**: YES (TDD with pytest)

### Implementation Approach
- Use ONLY 4 astral times (dawn, sunrise, sunset, dusk) as anchors
- Use simple time-based scheduling instead of elevation-based complexity
- Calculate average durations for dawn/sunrise/sunset/dusk (6 min for sunrise/sunset, 20 min for dawn/dusk)
- Evenly space day images between dawn and dusk (Image 4 end to Image 10 start)
- Evenly space night images between dusk and dawn
- Keep existing hourly fallback when astral unavailable
- All tests will be written first (RED), then implementation (GREEN), then refactoring (REFACTOR)

## Image Assignment Plan
### Period 1: Night (Evenly distributed)
- Images 14, 15, 16, 1 distributed from dusk to dawn

### Period 2: Dawn/Sunrise (Event-anchored)
- Image 2: Dawn (civil twilight starts, -6° elevation)
- Image 3: Sunrise (sun at 0°)
- Image 4: Post-sunrise (sun at +4° elevation) - **Elevation-based, configurable**

### Period 3: Day (Evenly distributed)
- Images 5, 6, 7, 8, 9 distributed from post-sunrise to pre-sunset

### Period 4: Sunset/Dusk (Event-anchored)
- Image 10: Pre-sunset (sun at +4° elevation) - **Elevation-based, configurable**
- Image 11: Sunset (sun at 0°)
- Image 12: Post-sunset (sun at -2° elevation) - **Elevation-based, configurable**
- Image 13: Dusk (civil twilight ends, -6° elevation)

## Configuration Constants
**Location**: `~/.config/wallpaper-changer/config.json` → location section

**New Fields to Add**:
```json
{
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix",
    "elevation_angle_post_sunrise": 4,
    "elevation_angle_pre_sunset": 4,
    "elevation_angle_post_sunset": -2
  }
}
```

**Field Descriptions**:
- `elevation_angle_post_sunrise`: Solar elevation (degrees) when image 4 should display (+4°)
- `elevation_angle_pre_sunset`: Solar elevation (degrees) when image 10 should display (+4°)
- `elevation_angle_post_sunset`: Solar elevation (degrees) when image 12 should display (-2°)

**Why Config-Based**: User can tune these values without code changes based on visual testing.

### User Decisions (Confirmed)
1. **Constants Location**: Config file (add elevation_angle_* fields to location section)
2. **Inverse Lookup Algorithm**: Binary search between sunrise/sunset
3. **Image 4/12 Transitions**: Elevation-based transitions (configurable via config file)
4. **Test Strategy**: YES (TDD with pytest)

### Implementation Approach
- Use astral.sun.elevation() for solar elevation calculations
- Implement binary search between sunrise and noon to find time for target elevation
- Add elevation_angle_* fields to config.json location section
- Store current time boundaries for 16 image transition times
- Keep existing hourly fallback when astral unavailable
- All tests will be written first (RED), then implementation (GREEN), then refactoring (REFACTOR)

## Open Questions
- Current configuration pattern in codebase (where to add constants?) → **ANSWERED: Add to location section in config.json**
- Current image file location and naming convention → Not changing
- How to handle timezone/observer location configuration → Already in config.json location section
- Existing test infrastructure status → Tests exist in tests/ directory

## Scope Boundaries
- INCLUDE: Complete rewrite of image selection logic
  - Replace `select_image_for_time()` with elevation-based approach
  - Add `find_time_for_elevation()` function using binary search
  - Add `calculate_daily_boundaries()` function
- INCLUDE: Elevation-based transition calculation for images 4 and 12
- INCLUDE: Configuration constants for elevation angles (in config.json)
- INCLUDE: Daily boundary calculation function
- EXCLUDE: Changes to image file collection/management
- EXCLUDE: Changes to wallpaper display/refresh logic
- EXCLUDE: Changes to hourly fallback mechanism structure
- EXCLUDE: Changes to detect_time_of_day_sun() function (keep as-is)
- EXCLUDE: Changes to detect_time_of_day_sun() function (keep as-is)

## Research Findings

### Current Implementation Structure

**Main Module**: `kwallpaper/wallpaper-changer.py`

**Key Functions**:
- `select_image_for_time()` - Main image selection using astral library
- `select_image_for_time_hourly()` - Fallback using hourly table
- `detect_time_of_day_sun()` - Time detection using astral
- `detect_time_of_day_hour()` - Time detection using hour ranges
- `load_config()` / `save_config()` - Configuration management
- `validate_config()` - Config validation

**Current Image Assignment**:
- **Night**: Images 14, 15, 16, 1 (4 images)
  - Period: dusk to dawn (45 min before/after sunrise/sunset)
  - Distribution: Evenly spaced within period
- **Sunrise**: Images 2, 3, 4 (3 images)
  - Period: dawn to sunrise (45 min before sunrise)
  - Distribution: Evenly spaced within period
- **Day**: Images 5, 6, 7, 8, 9 (5 images)
  - Period: sunrise to sunset
  - Distribution: Evenly spaced within period
- **Sunset**: Images 10, 11, 12, 13 (4 images)
  - Period: sunset to dusk (45 min after sunset)
  - Distribution: Evenly spaced within period

**Current Issues**:
- Uses fixed 45-minute buffers for dawn/dusk (not astronomically accurate)
- No elevation-based transitions
- Fixed time ranges don't account for seasonal variation
- Dawn/dusk defined as ±45 minutes from sunrise/sunset

### Astral Library API

**Currently Used**:
- `LocationInfo()` - Observer location (lat, lon, elevation, timezone)
- `sun()` - Returns dict with 'dawn', 'sunrise', 'sunset', 'dusk' (datetime objects)

**New Functionality Needed**:
- `sun.elevation()` - Returns solar elevation at a specific time
- Inverse lookup needed: Find time when elevation reaches target angle

### Package Structure

```
kwallpaper/
├── kwallpaper/
│   └── wallpaper-changer.py  # Main implementation
├── tests/                     # Test files
│   ├── test_astral_time_detection.py
│   ├── test_hourly_fallback.py
│   ├── test_image_selection.py
│   └── ...
├── .config/wallpaper-changer/
│   └── tests/                # Alternative test location
├── requirements.txt          # astral>=2.2, pytest
└── README.md                  # Documentation
```

**Config File**: `~/.config/wallpaper-changer/config.json`
```json
{
  "current_image_index": 1,
  "current_time_of_day": "day",
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix"
  }
}
```

**Location**: The config already has latitude, longitude, timezone - perfect for astral calculations!

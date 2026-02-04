# Draft: Time-Based Wallpaper Enhancement

## Requirements (User's stated goal)
- Create functionality that the time in the picture will change based on the time of day at the user's location
- Need options for the best, most reliable, and simple way to implement this

## Current Implementation Analysis

### How detect_time_of_day() works (lines 43-65 of wallpaper_changer.py)
```python
def detect_time_of_day(hour: Optional[int] = None) -> str:
    """Detect current time-of-day category based on hour.

    Args:
        hour: Optional hour value to use for detection (for testing)
              If None, uses current system time.

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    if hour is None:
        hour = datetime.now().hour  # Uses naive datetime (no timezone)

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
```

### Current Limitations
1. **No timezone awareness**: Uses `datetime.now().hour` which assumes system local time but doesn't account for timezone offsets
2. **Fixed time ranges**: Hardcoded ranges don't adapt to location (e.g., 5 AM in Alaska vs. 5 AM in Florida)
3. **No sunrise/sunset accuracy**: Doesn't calculate actual sun position, just uses fixed hour ranges

### Monitor Mode Usage (lines 609-624)
```python
while True:
    try:
        # Get current time of day
        time_of_day = detect_time_of_day()
        current_time = datetime.now().strftime("%H:%M:%S")

        # Check if time-of-day changed
        if time_of_day != last_time_of_day:
            print(f"\n[{current_time}] Time changed: {last_time_of_day} → {time_of_day}")
            last_time_of_day = time_of_day

            # Select new image for current time-of-day
            image_path = select_next_image(theme_path, str(config_path_obj))
```

### Existing Tests
Located in `test_time_of_day.py` - tests the hour-based detection logic

## Research Findings So Far

### Timezone Detection Libraries

**Option 1: tzlocal (Recommended for simplicity)**
- **Pros**: Auto-detects system timezone, requires no manual configuration
- **Cons**: Only detects timezone, doesn't calculate sunrise/sunset
- **Install**: `pip install tzlocal`
- **Usage**:
```python
from tzlocal import get_localzone
from datetime import datetime

local_tz = get_localzone()
now = datetime.now(local_tz)  # Timezone-aware datetime
hour = now.hour
```

**Option 2: pytz (More control)**
- **Pros**: Comprehensive timezone database, can convert between timezones
- **Cons**: Requires selecting specific timezone, more complex
- **Install**: `pip install pytz`
- **Usage**:
```python
from pytz import timezone
from datetime import datetime

tz = timezone('America/New_York')
now = datetime.now(tz)
hour = now.hour
```

### Sunrise/Sunset Calculation Libraries

**Option 3: Astral (Recommended for accuracy)**
- **Pros**:
  - Calculates actual sunrise/sunset for specific locations
  - Handles timezone automatically
  - Simple API
  - Includes city database for common locations
- **Cons**: Additional dependency (~200KB)
- **Install**: `pip install astral`
- **Usage**:
```python
from astral import LocationInfo
from astral.sun import sun

city = LocationInfo("San Francisco", "California", "America/Los_Angeles", 37.7749, -122.4194)
s = sun(city.observer, date=datetime.now())

print(f"Sunrise: {s['sunrise']}")
print(f"Sunset: {s['sunset']}")
```

**Option 4: Skyfield (Most accurate but complex)**
- **Pros**: Highly accurate astronomical calculations
- **Cons**: Large dependency (~10MB), complex API
- **Install**: `pip install skyfield`
- **Usage**: More complex setup with ephemeris files

## User Decisions (Confirmed)

### Decision 1: Accuracy Level
- **Selected**: Accurate (Sunrise/Sunset)
- **Rationale**: Calculate actual sunrise/sunset times for the user's location
- **Implementation**: Use `astral` library (Option 3 from research)

### Decision 2: Location Configuration
- **Selected**: Manually configured
- **Rationale**: User will provide latitude/longitude or select a city
- **Implementation**: Add location fields to config file (lat, lon, city_name, timezone)

### Decision 3: Time Categories
- **Selected**: 4 categories (Current)
- **Rationale**: Matches existing implementation, no need for additional granularity
- **Categories**: night, sunrise, day, sunset

### Chosen Implementation Approach
- **Approach B: Sunrise/Sunset Calculation** (from draft)
- **Dependencies**: tzlocal + astral
- **Changes**:
  - Add location configuration (lat/lon or city name)
  - Calculate actual sunrise/sunset times
  - Define categories based on sun position
  - Modify detect_time_of_day() to use astral calculations

## Potential Implementation Approaches

### Approach A: Simple Timezone Detection
- **Complexity**: Low
- **Dependencies**: tzlocal only
- **Change**: Modify `detect_time_of_day()` to use `datetime.now(get_localzone()).hour`
- **Pros**: Simple, no location configuration
- **Cons**: Still uses fixed hour ranges, doesn't account for seasonal variations

### Approach B: Sunrise/Sunset Calculation
- **Complexity**: Medium
- **Dependencies**: tzlocal + astral
- **Change**:
  - Add location configuration (lat/lon or city name)
  - Calculate actual sunrise/sunset times
  - Define categories based on sun position (e.g., before sunrise, after sunset, etc.)
- **Pros**: Accurate, follows natural day/night cycle
- **Cons**: Requires location configuration, more complex

### Approach C: Hybrid (Recommended)
- **Complexity**: Medium
- **Dependencies**: tzlocal + astral
- **Change**:
  - Auto-detect system timezone (tzlocal)
  - Calculate sunrise/sunset for current location (astral)
  - Use calculated times to determine categories
  - Allow manual override if needed
- **Pros**: Best of both worlds - automatic + accurate
- **Cons**: Requires location configuration, but can auto-detect

## Project Context (from README)

### Current Implementation
- Python CLI tool for KDE Plasma
- Uses `kwriteconfig5` to change wallpapers
- Configuration: `~/.config/wallpaper-changer/config.json`
- Test infrastructure: pytest + pytest-cov (34/35 tests passing)
- Current time categories: night, sunrise, day, sunset (hardcoded hours)

### Existing Test Coverage
- Config validation: 13/13 tests passing
- Zip extraction: 5/5 tests passing
- Image selection: 7/7 tests passing
- Time-of-day detection: 6/6 tests passing
- Wallpaper change: 3/3 tests passing

## Next Steps
- Present findings to user
- Get user preference on approach
- Create work plan for implementation

# Draft: Astral-Based Sunrise/Sunset System

## Requirements (confirmed)
- Replace simple fixed time range detection with astronomical sunrise/sunset calculations
- Use `astral` library to get varying sunrise/sunset times throughout the year
- During sunrise period, show different images based on exact time:
  - Image 2: sun just under horizon
  - Image 3: sun just above horizon
  - Image 4: sunrise just completed, day almost started

## Current Implementation
**File**: `kwallpaper/wallpaper_changer.py` (lines 243-265)

**Current `detect_time_of_day()` function:**
```python
def detect_time_of_day(hour: Optional[int] = None) -> str:
    if hour is None:
        hour = datetime.now().hour

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

**Current approach:**
- Fixed time ranges based on hour of day
- Simple categorical detection
- No astronomical calculations

## Research Findings (pending)
- Astral library installation and API usage
- Sunrise/sunset calculation patterns
- KDE theme metadata structure
- Best practices for location/timezone handling

## Open Questions

### Location Configuration
**Question 1**: How should users configure their location for sunrise/sunset calculations?

Options:
- A) Ask user for latitude/longitude during first run
- B) Ask user for city name (astral supports city lookups)
- C) Read from config file (`location: {lat: 39.5, lon: -98.35}`)
- D) Auto-detect from system settings
- E) Use hardcoded default (e.g., user's timezone center)

**Recommendation**: Option C (config file) - most flexible, allows users to update location without reinstalling

### Time Zone Handling
**Question 2**: How to handle time zones and daylight saving time?

**Concerns**:
- Sunrise/sunset times vary by timezone
- Daylight saving time shifts affect calculations
- System time vs local time for display

**Options**:
- A) Use system timezone (what user's system is set to)
- B) Use config file timezone (user-specified)
- C) Always use UTC (simplest, but not user-friendly)
- D) Detect from geolocation

**Recommendation**: Option A (system timezone) - most intuitive for users

### Sunrise/Sunset Period Duration
**Question 3**: How long should the "sunrise" period last?

Current fixed range: 05:00 - 06:59 (2 hours)

**Options**:
- A) Keep 2-hour window (backward compatible)
- B) Use actual sunrise + 30 minutes before
- C) Use actual sunrise + 1 hour before
- D) Use only exact sunrise time (no transition period)
- E) Dynamic: duration varies by season (shorter in summer, longer in winter)

**Recommendation**: Option A (keep 2-hour window) - simplest for users, backward compatible

### Image Selection Logic
**Question 4**: How to map exact time to specific images during sunrise?

User specified:
- Image 2: sun just under horizon
- Image 3: sun just above horizon
- Image 4: sunrise just completed, day almost started

**Current metadata**: `sunriseImageList: [2, 3, 4]`

**Options**:
- A) Fixed mapping based on time ranges (e.g., 05:00-05:30 → image 2, 05:30-06:00 → image 3, 06:00-06:30 → image 4)
- B) Proportional mapping (first third of period = image 2, middle third = image 3, last third = image 4)
- C) Based on actual sunrise time (e.g., 30 min before sunrise = image 2, at sunrise = image 3, 30 min after = image 4)
- D) Cycling through images based on time elapsed since sunrise

**Recommendation**: Option C (based on actual sunrise time) - most accurate representation of astronomical events

### Night/Sunset Transition
**Question 5**: How to handle transitions between categories?

**Options**:
- A) Detect based on current time vs calculated sunrise/sunset (dynamic)
- B) Keep using current time-based detection as fallback
- C) Always use astronomical calculation
- D) Hybrid: astronomical for sunrise/sunset, time-based for night/day

**Recommendation**: Option A (detect based on current time vs calculated sunrise/sunset) - most accurate

### Backward Compatibility
**Question 6**: Should the change be backward compatible with existing themes?

**Concerns**:
- Existing themes have fixed time ranges
- New themes would have astronomical times
- Config files need migration

**Options**:
- A) Full backward compatibility - check if theme has astronomical config, otherwise use old method
- B) Breaking change - all themes must be updated to use astronomical times
- C) Auto-detect - if sunriseImageList has astronomical metadata, use it; otherwise use old method

**Recommendation**: Option C (auto-detect) - best user experience

## Technical Decisions (to be made)
- [ ] Location configuration method
- [ ] Timezone handling approach
- [ ] Sunrise period duration
- [ ] Image selection logic
- [ ] Transition detection method
- [ ] Backward compatibility strategy

## Scope Boundaries
- INCLUDE: Astral library integration, sunrise/sunset calculations, enhanced image selection
- EXCLUDE: Changes to CLI interface (except for location config), changes to wallpaper change mechanism, changes to theme extraction

## Dependencies
- Add `astral` package to requirements.txt
- Verify timezone handling (Python's `zoneinfo` for Python 3.9+)

## Fallback Timings (Hour-Based Detection)
When Astral library is NOT used (no location configured), the fallback image selection uses these fixed times:

| Image | Time | Category |
|-------|------|----------|
| 1.jpeg | 04:30 | night |
| 2.jpeg | 06:15 | sunrise |
| 3.jpeg | 06:30 | sunrise |
| 4.jpeg | 07:30 | sunrise/day transition |
| 5.jpeg | 10:00 | day |
| 6.jpeg | 12:00 | day |
| 7.jpeg | 14:00 | day |
| 8.jpeg | 16:00 | day |
| 9.jpeg | 17:00 | day/sunset transition |
| 10.jpeg | 18:00 | sunset |
| 11.jpeg | 18:30 | sunset |
| 12.jpeg | 18:45 | sunset |
| 13.jpeg | 19:00 | sunset |
| 14.jpeg | 20:00 | night |
| 15.jpeg | 22:30 | night |
| 16.jpeg | 01:00 | night |

**Key Points**:
- Night images: 1, 14, 15, 16 (covering 04:30-02:00)
- Sunrise period: 2, 3, 4 (06:15-07:30)
- Day images: 5, 6, 7, 8, 9 (10:00-17:00)
- Sunset period: 10, 11, 12, 13 (18:00-19:00)
- No Astral calculation needed for fallback - simple time comparison
- Fallback triggers when: location not configured in config.json

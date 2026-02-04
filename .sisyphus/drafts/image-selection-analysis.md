# Image Selection Logic Analysis

## Investigation Summary

After analyzing the codebase, I've identified **4 potential timing issues** that could cause images to display at the wrong times:

---

## Issue 1: Monitoring Loop Polling Interval (CRITICAL)

**Location**: `wallpaper_changer.py` lines 1404, 1413

**Problem**:
```python
# Wait for next interval (check if time changed)
time.sleep(config['interval'])  # Default: 5400 seconds (1.5 hours)
```

The monitoring loop only checks for time-of-day changes every 1.5 hours. If a time transition occurs between checks, the wrong image will be displayed until the next check.

**Impact**:
- **High**: Images may display incorrectly for up to 1.5 hours after a time transition
- Examples:
  - Sunset at 17:59 → Changes at 18:00
  - If check happens at 17:30, wrong image shown until 19:00
  - Night at 20:00 → Changes at 20:00
  - If check happens at 18:30, wrong image shown until 20:00

**Expected Behavior**:
Should check for time changes frequently (e.g., every minute) rather than waiting 1.5 hours.

---

## Issue 2: Hourly Fallback Table Gaps

**Location**: `wallpaper_changer.py` lines 539-556

**Problem**:
The hourly fallback table has gaps between time points:

| Time | Image Index | Category |
|------|-------------|----------|
| 02:00 | **?** | night |
| 04:30 | 1 | sunrise |
| 06:15 | 2 | sunrise |
| ... | ... | ... |
| 18:30 | 11 | sunset |
| **18:31-19:00** | **?** | sunset |
| 19:00 | 13 | sunset |
| **19:01-20:00** | **?** | night |
| 20:00 | 14 | night |
| **20:01-22:30** | **?** | night |
| 22:30 | 15 | night |
| **22:31-01:00** | **?** | night |
| 01:00 | 16 | night |

**Impact**:
- Times between table entries use the LAST entry's image index
- Examples:
  - 02:00 uses image 16 (night)
  - 18:31-19:00 uses image 11 (sunset)
  - 19:01-20:00 uses image 13 (sunset)
  - 20:01-22:30 uses image 15 (night)
  - 22:31-01:00 uses image 16 (night)

**Expected Behavior**:
Should interpolate or use explicit entries for all times between table points.

---

## Issue 3: Sunset Period Image Cycling Speed (MEDIUM)

**Location**: `wallpaper_changer.py` lines 857-871

**Problem**:
- Sunset period is only 30 minutes (18:00-18:30)
- 4 images are distributed across this period
- Each image displays for only 7.5 minutes

**Impact**:
- Very rapid transitions between 4 sunset images
- Potential flickering or visual discomfort
- May not align with actual sunset duration (which can vary from 20-40 minutes)

**Expected Behavior**:
Should use actual sunset duration from Astral library, not a fixed 30 minutes.

---

## Issue 4: Boundary Condition Adjustment (LOW)

**Location**: `wallpaper_changer.py` lines 796, 880

**Problem**:
```python
image_index = int((position - 1e-9) * len(image_list)) + base_index
```

The `-1e-9` adjustment is meant to prevent index out-of-bounds at boundaries, but may cause off-by-one errors at exact boundaries.

**Impact**:
- Minor: May cause wrong image at exact boundary moments
- Example: At position = 0.999999999, the adjustment could cause index to be 2 instead of 3

**Expected Behavior**:
Should use proper boundary handling without epsilon tricks.

---

## Root Cause Analysis

The **primary issue** is **Issue 1 (Monitoring Loop Polling Interval)** because:

1. It affects the main monitoring mode which is the primary usage
2. The 1.5-hour interval is too long for accurate time-based image changes
3. Time transitions happen frequently (every 20-40 minutes for sunset/sunrise)
4. The 7.5-minute image cycling in sunset period means transitions happen every 7.5 minutes

**Secondary issue** is **Issue 3 (Sunset Period Speed)** because:
- Very rapid transitions may cause visual problems
- Not aligned with actual astronomical events

**Tertiary issue** is **Issue 4 (Boundary Condition Adjustment)** because:
- Epsilon adjustment may cause off-by-one errors at exact boundaries

---

## Recommended Fixes

### Fix 1: Reduce Monitoring Interval (CRITICAL)

Change from checking every 1.5 hours to checking every minute:

```python
# Current (line 1404):
time.sleep(config['interval'])

# Proposed:
time.sleep(60)  # Check every minute
```

Or add continuous time checking:
```python
# Check time every second, but only change wallpaper every interval
last_wallpaper_change = None
while True:
    time_of_day = detect_time_of_day()
    current_time = datetime.now()

    if time_of_day != last_time_of_day:
        # Change wallpaper immediately
        image_path = select_next_image(theme_path, str(config_path_obj))
        change_wallpaper(image_path)
        last_time_of_day = time_of_day
        last_wallpaper_change = current_time

    # Check time every second (not every interval)
    time.sleep(1)
```

### Fix 2: Use Actual Sunset Duration

Replace fixed 30-minute period with actual duration from Astral:

```python
elif time_of_day == "sunset":
    # Sunset: sunset to dusk (using actual Astral duration)
    if use_sun_times and sunset_val:
        period_start = sunset_val
    else:
        period_start = datetime.combine(current_time.date(), time_class(18, 0))
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)

    # Use actual Astral dusk time instead of fixed 18:30
    if use_sun_times and dusk_val:
        period_end = dusk_val  # Actual astronomical dusk
    else:
        period_end = datetime.combine(current_time.date(), time_class(18, 30))
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
    # ... rest of logic unchanged
```

### Fix 3: Remove Epsilon Adjustment

Replace `int()` with proper boundary handling:

```python
# Current:
image_index = int((position - 1e-9) * len(image_list)) + base_index

# Proposed:
image_index = int(position * len(image_list)) + base_index
# Clamp to valid range (already done)
image_index = max(1, min(image_index, len(image_list)))
```

---

## Testing Strategy

After fixes, verify:

1. **Monitoring mode**:
   - Change wallpaper immediately when time transitions
   - Test at sunset time (17:59 → 18:00 transition)
   - Test at sunrise time (05:59 → 06:00 transition)

2. **Sunset period**:
   - Verify 4 images spread across ACTUAL sunset duration
   - Check transitions at astronomical sunset/sunrise times

3. **Boundary conditions**:
   - Verify correct image at exact period boundaries
   - Test at position = 0, position = 1, position = 0.999999999

---

## Next Steps

1. **Priority 1**: Fix Issue 1 (reduce monitoring interval)
2. **Priority 2**: Fix Issue 3 (use actual sunset duration)
3. **Priority 3**: Fix Issue 4 (remove epsilon adjustment)
4. **Testing**: Run all tests and add regression tests for new behavior

---

## Files to Modify

- `kwallpaper/wallpaper_changer.py` (main implementation)
- `tests/test_image_selection.py` (add boundary condition tests)

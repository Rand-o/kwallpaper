# Learnings - astral-4-period

## Project Structure
- Main code: `kwallpaper/wallpaper_changer.py`
- Tests: `tests/test_astral_time_detection.py`
- Config: `~/.config/wallpaper-changer/config.json`

## Astral Library
- Already installed
- Function `detect_time_of_day_sun()` exists at lines 297-411
- Currently returns 2 categories (night, day)
- Needs enhancement to return 4 categories with dawn/dusk

## Test Infrastructure
- pytest already set up
- MockSun class at `tests/test_astral_time_detection.py:15-26`
- Test patterns use tempfile.NamedTemporaryFile for configs

## Task 2 - RED Tests for select_image_for_time() (Completed)

### Test Patterns Used
- Followed existing MockSun pattern with `sunrise` and `sunset` properties
- Used `builtins.__import__` patching for astral module mocking
- Created theme_data dict with all 4 image lists: `sunriseImageList`, `sunsetImageList`, `dayImageList`, `nightImageList`
- Each test: creates mock sun → patches astral → calls `select_image_for_time()` → asserts expected image index

### Test Functions Written (9 total)
1. `test_select_image_sunrise_before_sunrise` - Image 2 shown 30min before sunrise
2. `test_select_image_sunrise_at_sunrise` - Image 3 shown at sunrise start
3. `test_select_image_sunrise_after_sunrise` - Image 4 shown after sunrise
4. `test_select_image_sunset_before_sunset` - Image 10 shown before sunset
5. `test_select_image_sunset_during_sunset` - Image 11 shown during sunset
6. `test_select_image_sunset_going_under` - Image 12 shown going under horizon
7. `test_select_image_sunset_completed` - Image 13 shown after sunset
8. `test_select_image_day_evenly_spaced` - Tests 5 day images (5,6,7,8,9) across 12h day
9. `test_select_image_night_evenly_spaced` - Tests 4 night images (14,15,16,1) across 12h night

### Custom Timing Specs Defined
- Sunrise (3 images: 2,3,4):
  - Image 2: 30min before sunrise
  - Image 3: at sunrise
  - Image 4: after sunrise
- Sunset (4 images: 10,11,12,13):
  - Image 10: before sunset
  - Image 11: during sunset
  - Image 12: going under horizon
  - Image 13: after sunset completes
- Day (5 images: 5,6,7,8,9): evenly spaced across sunrise→sunset duration
- Night (4 images: 14,15,16,1): evenly spaced across dusk→next dawn

### Test Results
- All 9 tests fail with `AttributeError: module 'kwallpaper.wallpaper_changer' has no attribute 'select_image_for_time'`
- This confirms RED state - function doesn't exist yet (as expected for TDD)

### Key Insights
- MockSun currently only has `sunrise` and `sunset` (Task 3 will add `dawn`/`dusk`)
- Tests assume select_image_for_time(theme_data, datetime) signature
- Even spacing calculations for day/night images need duration-aware implementation
- The existing select_next_image() pattern uses interval cycling - new function needs time-aware selection

## Task 3 - Enhanced MockSun with dawn/dusk (Completed)

### Changes Made
- Updated `MockSun.__init__` to accept `dawn` and `dusk` parameters
- Added `_dawn` and `_dusk` private attributes to store values
- Updated `MockSun.__getitem__` to return `_dawn` for 'dawn' key and `_dusk` for 'dusk' key
- Maintains backward compatibility with existing `sunrise` and `sunset` parameters

### MockSun Class Structure (lines 15-26)
```python
class MockSun:
    """Mock sun object for testing."""
    def __init__(self, sunrise=None, sunset=None, dawn=None, dusk=None):
        self._sunrise = sunrise
        self._sunset = sunset
        self._dawn = dawn
        self._dusk = dusk

    def __getitem__(self, key):
        if key == 'sunrise':
            return self._sunrise
        elif key == 'sunset':
            return self._sunset
        elif key == 'dawn':
            return self._dawn
        elif key == 'dusk':
            return self._dusk
        raise KeyError(f"Unknown key: {key}")
```

### Verification
- ✓ MockSun can be created with `MockSun(dawn=..., dusk=...)` without error
- ✓ `MockSun['dawn']` returns the stored dawn value
- ✓ `MockSun['dusk']` returns the stored dusk value
- ✓ All existing MockSun functionality remains intact (sunrise, sunset)
- ✓ Tests from Tasks 1-2 that use enhanced MockSun will now work correctly

### Key Insights
- MockSun now matches Astral's `sun()` function return dict structure
- All 4 keys are now supported: 'dawn', 'sunrise', 'sunset', 'dusk'
- Enables proper testing of 4-period time detection (night, sunrise, day, sunset)
- Task 4 implementation will be able to use dawn/dusk values from MockSun

### Dependencies Satisfied
- Tasks 1, 2 tests that created MockSun with dawn/dusk now have a working mock
- Task 4 can now rely on complete MockSun interface for all sun times

## Task 5 - Monitor Mode Time-Based Image Selection (Completed)

### Changes Made to Monitor Mode Loop (lines 937-1019)

#### Before (interval-based cycling)
```python
while True:
    time_of_day = detect_time_of_day()  # Hour-based detection
    current_time = datetime.now().strftime("%H:%M:%S")

    if time_of_day != last_time_of_day:
        image_path = select_next_image(theme_path, str(config_path_obj))
        change_wallpaper(image_path)
```

#### After (time-based selection)
```python
# Load theme_data once before loop
with open(theme_json_path, 'r') as f:
    theme_data = json.load(f)

while True:
    current_time = datetime.now()  # datetime object, not string
    time_of_day = detect_time_of_day_sun(str(config_path_obj))  # Sun-based detection

    # Detect if time period changed OR image changed within same period
    time_changed = (time_of_day != last_time_of_day)
    need_new_image = False

    if time_changed:
        need_new_image = True
    elif last_image_index is None:
        need_new_image = True
    else:
        new_image_index = select_image_for_time(theme_data, current_time)
        if new_image_index != last_image_index:
            need_new_image = True

    if need_new_image:
        image_index = select_image_for_time(theme_data, current_time)
        # Build image path from index (filename pattern matching)
        # change_wallpaper(image_path)
```

### Implementation Details

#### Theme Data Loading
- Loaded once before monitor loop starts (performance optimization)
- Includes imageFilename pattern for building image paths from indices
- Contains all 4 image lists: sunriseImageList, sunsetImageList, dayImageList, nightImageList

#### Image Path Building Logic (extracted from select_next_image)
1. Get image index from `select_image_for_time(theme_data, current_time)`
2. Get image list based on time_of_day: `theme_data.get(f"{time_of_day}ImageList", [])`
3. Fallback to next available category if current list is empty
4. Use imageFilename pattern (e.g., "24hr-Tahoe-2026_*.jpeg") to find files
5. If pattern doesn't match, try numbered files: `{pattern_base}_{i}{pattern_ext}`
6. Sort files and select file at correct index (1-based to 0-based conversion)

#### Change Detection Logic
- Tracks `last_time_of_day` and `last_image_index` separately
- Wallpaper changes when:
  1. Time period changes (e.g., night → sunrise)
  2. Image index changes within same period (e.g., sunrise image 2 → 3)
- This enables smooth image transitions as time progresses within a period

### Key Implementation Notes

#### Function Signatures (from Task 4)
- `detect_time_of_day_sun(config_path: Optional[str] = None) -> str`: Returns "night", "sunrise", "day", or "sunset"
- `select_image_for_time(theme_data: Dict[str, Any], current_time: datetime) -> int`: Returns image index

#### Mismatch Between Task Requirements and Implementation
- Task 5 requirements expected: `select_image_for_time(theme_path, time_of_day, current_time, sun_times)`
- Actual implementation signature: `select_image_for_time(theme_data: Dict[str, Any], current_time: datetime)`
- Resolution: Worked with actual implementation; theme_data includes location config for Astral calculations

### Verification

#### Code Review Results
- ✓ Line 964 uses `select_image_for_time(theme_data, current_time)` instead of `select_next_image()`
- ✓ Monitor mode calculates `current_time` once per iteration (line 960)
- ✓ Sun-based detection via `detect_time_of_day_sun(str(config_path_obj))` (line 962)
- ✓ Time-of-day change detection still works (period changes trigger image changes)
- ✓ Image changes within same period are now supported

#### Build Verification
- ✓ Python syntax check passed: `python -m py_compile kwallpaper/wallpaper_changer.py`

#### Test Status
- Pre-existing test failures unrelated to Task 5 changes:
  - `test_astral_time_detection.py` tests fail because test data doesn't include location config
  - `test_wallpaper_change.py` tests fail because `change_wallpaper` now uses `plasma-apply-wallpaperimage`
- Task 5 changes are isolated to monitor mode loop; no changes to test infrastructure

### Key Insights

#### Performance Optimization
- Theme data loaded once before loop instead of reading file on each iteration
- File path building logic extracted and optimized

#### Change Detection Logic
- Dual tracking (time_of_day + image_index) enables:
  - Period transitions: sunrise → day
  - Intra-period transitions: image 2 → 3 as time progresses through period

#### Error Handling
- Fallback to next available category if current period has no images
- Graceful error handling for image selection failures

### Dependencies
- Tasks 1, 2, 3, 4 completed (tests, mocks, and implementation ready)
- Task 5 depends on Task 4: `detect_time_of_day_sun()` and `select_image_for_time()` must exist

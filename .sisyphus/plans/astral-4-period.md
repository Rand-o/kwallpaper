# Astral 4-Period Time-Based Detection - Hourly Fallback

## TL;DR

> **Quick Summary**: Add hourly fallback image selection with specific 16-timing table (04:30→1, 06:15→2, ..., 01:00→16) when Astral is unavailable or fails. Implement robust error handling with ValueError on image index overflow.
>
> **Deliverables**:
> - New `select_image_for_time_hourly(theme_data, current_time)` function with 16-timing table
> - Monitor mode integration to use hourly fallback when Astral ImportError + ValueError
> - 16 test functions for hourly fallback timing table
> - Edge case tests for overflow/invalid inputs
> - README.md documentation of hourly fallback
>
> **Estimated Effort**: Medium (3-4 hours)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 (function implementation) → Task 2 (monitor mode integration) → Task 3 (tests) → Task 4 (documentation)

---

## Context

### Original Request
Add a new feature to automatically show wallpapers based on time periods (sunrise, day, sunset, night) using Astral library to calculate sunrise/sunset times based on user's location and current date.

### Oracle & Metis Review Findings
**Critical Discovery**: Previous plan was based on outdated analysis. Most "new" features already exist:
- ✅ `detect_time_of_day_sun()` already returns 4 categories with dawn/dusk
- ✅ `select_image_for_time()` already exists with custom timing logic
- ✅ Monitor mode already uses `select_image_for_time()`
- ✅ MockSun already supports dawn/dusk
- ✅ Most tests already exist (27 test functions in test_astral_time_detection.py)

**ACTUAL GAPS**:
1. Missing `select_image_for_time_hourly()` function with fixed 16-timing table
2. Monitor mode needs to call hourly fallback when Astral ImportError + ValueError
3. Need 16 test functions for the hourly fallback function
4. README needs to document hourly fallback

### Decisions Made
- **Timing table**: Fixed 16 entries (04:30→1, 06:15→2, 06:30→3, 07:30→4, 10:00→5, 12:00→6, 14:00→7, 16:00→8, 17:00→9, 18:00→10, 18:30→11, 18:45→12, 19:00→13, 20:00→14, 22:30→15, 01:00→16)
- **Fallback trigger**: When Astral ImportError (not installed) OR ValueError (any Astral failure)
- **Overflow handling**: Return ValueError when image index (1-16) exceeds available images
- **Return value**: Function returns the timing table value (1-16), monitor mode looks up in appropriate image list
- **Scope**: Only add hourly fallback, do NOT modify existing functions

---

## Work Objectives

### Core Objective
Add hourly fallback image selection with specific 16-timing table. When Astral library fails (ImportError or ValueError), use hourly fallback instead. Implement robust error handling with ValueError on image index overflow (when requested image number 1-16 doesn't exist in theme).

### Concrete Deliverables
- New `select_image_for_time_hourly(theme_data, current_time)` function in `kwallpaper/wallpaper_changer.py`
- Fallback logic in monitor mode (lines 993-998) to call hourly function when Astral fails
- 16 test functions in `tests/test_astral_time_detection.py` for each timing in table
- Edge case tests for overflow, empty image lists, invalid times
- Updated README.md documenting hourly fallback behavior

### Definition of Done
- [ ] `select_image_for_time_hourly()` exists and returns correct timing table value (1-16) for each of 16 timings
- [ ] Monitor mode uses hourly fallback when Astral ImportError + ValueError
- [ ] ValueError raised when timing table value (1-16) exceeds available images
- [ ] All 16 hourly tests pass
- [ ] All existing tests still pass (no regressions)
- [ ] README documents hourly fallback

### Must Have
- **16-timing table**: Exact mappings (04:30→1, 06:15→2, 06:30→3, 07:30→4, 10:00→5, 12:00→6, 14:00→7, 16:00→8, 17:00→9, 18:00→10, 18:30→11, 18:45→12, 19:00→13, 20:00→14, 22:30→15, 01:00→16)
- **Fallback trigger**: When Astral ImportError (not installed) OR ValueError (any Astral failure)
- **Overflow error**: ValueError with descriptive message when timing table value (1-16) > available images
- **Return value**: Function returns the timing table value (1-16), monitor mode looks up in appropriate image list
- **TDD workflow**: Red tests → Green implementation → Refactor if needed
- **Backward compatible**: No breaking changes to existing config or CLI

### Must NOT Have (Guardrails)
- **DO NOT** modify `detect_time_of_day_sun()` function
- **DO NOT** modify `select_image_for_time()` function
- **DO NOT** add new time-of-day categories (keep 4: night, sunrise, day, sunset)
- **DO NOT** add timezone-aware logic to hourly fallback (keep simple hour-based)
- **DO NOT** make timing table configurable (hardcoded in function)
- **DO NOT** add "smart" interpolation between images
- **DO NOT** modify existing monitor mode logic beyond adding fallback trigger

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest already set up)
- **User wants tests**: YES (TDD)
- **Framework**: pytest

### If TDD Enabled

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure:**
1. **RED**: Write failing test first
   - Test file: `tests/test_astral_time_detection.py`
   - Test command: `pytest tests/test_astral_time_detection.py -v`
   - Expected: FAIL (test expects function to exist or return specific value)
2. **GREEN**: Implement minimum code to pass
   - Command: `pytest tests/test_astral_time_detection.py -v`
   - Expected: PASS
3. **REFACTOR**: Clean up while keeping green
   - Command: `pytest tests/test_astral_time_detection.py -v`
   - Expected: PASS (still)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Implement select_image_for_time_hourly() function
└── Task 2: Modify monitor mode to use hourly fallback

Wave 2 (After Wave 1):
└── Task 3: Write 16+ edge case tests

Wave 3 (After Wave 2):
└── Task 4: Update README documentation
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | None |
| 2 | 1 | 3, 4 | None |
| 3 | 2 | 4 | None |
| 4 | 3 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | delegate_task(category="unspecified-high", load_skills=[], run_in_background=true) |
| 2 | 3 | delegate_task(category="unspecified-high", load_skills=[], run_in_background=false) |
| 3 | 4 | delegate_task(category="writing", load_skills=[], run_in_background=false) |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [ ] 1. Implement select_image_for_time_hourly() Function

  **What to do**:
  - Add new `select_image_for_time_hourly()` function in `kwallpaper/wallpaper_changer.py`:
    - **Function signature**: `def select_image_for_time_hourly(theme_data: dict, current_time: datetime) -> int:`
    - **Use theme_data parameter directly** (like select_image_for_time() does):
      ```python
      # theme_data is already loaded dict - do NOT load theme.json internally
      # Extract image lists from theme_data
      sunrise_list = theme_data.get('sunriseImageList', [])
      day_list = theme_data.get('dayImageList', [])
      sunset_list = theme_data.get('sunsetImageList', [])
      night_list = theme_data.get('nightImageList', [])
      ```
    - **Define FALLBACK_TIMINGS** (16 entries):
      ```python
      FALLBACK_TIMINGS = {
          (4, 30): 1,   # 04:30 - night start
          (20, 0): 14,  # 20:00 - night start
          (22, 30): 15, # 22:30 - night mid
          (1, 0): 16,   # 01:00 - night end
          (6, 15): 2,   # 06:15 - sunrise start
          (6, 30): 3,   # 06:30 - sunrise mid
          (7, 30): 4,   # 07:30 - sunrise/day transition
          (10, 0): 5,   # 10:00 - day start
          (12, 0): 6,   # 12:00 - day mid
          (14, 0): 7,   # 14:00 - day late
          (16, 0): 8,   # 16:00 - day before sunset
          (17, 0): 9,   # 17:00 - day/sunset transition
          (18, 0): 10,  # 18:00 - sunset start
          (18, 30): 11, # 18:30 - sunset mid
          (18, 45): 12, # 18:45 - sunset late
          (19, 0): 13,  # 19:00 - sunset end
      }
      ```
    - **Calculate timing value** (returns 1-16):
      ```python
      hour = current_time.hour
      minute = current_time.minute
      current_time_key = (hour, minute)

      # Find timing table value (returns 1-16) for current time
      sorted_times = sorted(FALLBACK_TIMINGS.keys())
      for t in reversed(sorted_times):
          if t <= current_time_key:
              timing_value = FALLBACK_TIMINGS[t]
              break
      else:
          # Time before first entry (04:30), return 1
          timing_value = FALLBACK_TIMINGS[(4, 30)]

      # Determine which image list to use based on timing value
      if timing_value in [1, 2, 3, 4]:
          image_list = theme_data.get('sunriseImageList', [])
      elif timing_value in [5, 6, 7, 8, 9]:
          image_list = theme_data.get('dayImageList', [])
      elif timing_value in [10, 11, 12, 13]:
          image_list = theme_data.get('sunsetImageList', [])
      else:  # timing_value in [14, 15, 16]
          image_list = theme_data.get('nightImageList', [])

      # Check if requested image exists
      if timing_value > len(image_list):
          raise ValueError(
              f"Image index {timing_value} exceeds available images in "
              f"image list: {len(image_list)} images available"
          )

      return timing_value  # Returns 1-16, monitor mode looks up in appropriate list
      ```

  - **Must NOT do**:
    - Modify existing `detect_time_of_day_sun()` or `select_image_for_time()` functions
    - Add timezone conversion logic
    - Add interpolation between images
    - Add configurable timing table
    - Do NOT load theme.json internally (function receives theme_data dict parameter)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Moderate complexity - datetime math, JSON parsing, timing table logic, error handling
  - **Skills**: `[]`
    - No special skills needed - Python datetime manipulation and JSON handling

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (alone)
  - **Blocks**: Task 2 (monitor mode needs this function)
  - **Blocked By**: None (can start immediately)

  **References**:
  - **Pattern References**:
    - `kwallpaper/wallpaper_changer.py:993-998` - Current monitor mode loop (exception handling pattern)
    - `kwallpaper/wallpaper_changer.py:419-523` - `select_image_for_time()` (what exceptions it might raise - ImportError and ValueError)
    - `kwallpaper/wallpaper_changer.py:966` - How theme_data is loaded in monitor mode

  - **WHY References Matter**:
    - `kwallpaper/wallpaper_changer.py:993-998` - This is the monitor mode loop that needs modification - look at the existing try/except pattern and where the `select_image_for_time()` call is made, then add nested try/except blocks for ImportError and ValueError to catch Astral failures and trigger hourly fallback
    - `kwallpaper/wallpaper_changer.py:419-523` - This shows `select_image_for_time()` raises both ImportError (line 444) and ValueError (line 448), so we need to catch both exceptions
    - `kwallpaper/wallpaper_changer.py:966` - This shows how theme_data is loaded and passed to `select_image_for_time()`

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Function exists: `select_image_for_time_hourly(theme_data, current_time)`
  - [ ] FALLBACK_TIMINGS dict contains all 16 entries
  - [ ] Function returns correct timing table value (1-16) for each of 16 timings
  - [ ] Function raises ValueError when timing value (1-16) exceeds available images

  **Automated Verification**:

  ```bash
  # Verify function exists
  python -c "from kwallpaper.wallpaper_changer import select_image_for_time_hourly; print('✓ Function exists')"

  # Verify FALLBACK_TIMINGS has 16 entries
  python -c "
  from kwallpaper.wallpaper_changer import select_image_for_time_hourly
  import inspect
  source = inspect.getsource(select_image_for_time_hourly)
  assert 'FALLBACK_TIMINGS' in source, 'Missing FALLBACK_TIMINGS'
  assert '04:30' in source or '04, 30' in source or '4, 30' in source, 'Missing 04:30 entry'
  assert '19:00' in source or '19, 0' in source or '19, 0' in source, 'Missing 19:00 entry'
  print('✓ FALLBACK_TIMINGS defined with all 16 entries')
  "

  # Test 04:30 → returns 1
  python -c "
  from kwallpaper.wallpaper_changer import select_image_for_time_hourly
  from datetime import datetime
  import json
  import tempfile
  from pathlib import Path

  # Create temp theme with sunrise images
  theme_data = {
      'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg'],
      'dayImageList': ['5.jpeg'],
      'sunsetImageList': ['10.jpeg'],
      'nightImageList': ['14.jpeg']
  }

  with tempfile.TemporaryDirectory() as tmpdir:
      theme_path = Path(tmpdir) / 'theme'
      theme_path.mkdir()
      with open(theme_path / 'theme.json', 'w') as f:
          json.dump(theme_data, f)

      result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 4, 30))
      assert result == 1, f'Expected 1 at 04:30, got {result}'
      print('✓ 04:30 → returns 1')
  "

  # Test 01:00 → returns 16
  python -c "
  from kwallpaper.wallpaper_changer import select_image_for_time_hourly
  from datetime import datetime
  import json
  import tempfile
  from pathlib import Path

  theme_data = {
      'sunriseImageList': ['1.jpeg'],
      'dayImageList': ['5.jpeg'],
      'sunsetImageList': ['10.jpeg'],
      'nightImageList': ['14.jpeg']
  }

  with tempfile.TemporaryDirectory() as tmpdir:
      theme_path = Path(tmpdir) / 'theme'
      theme_path.mkdir()
      with open(theme_path / 'theme.json', 'w') as f:
          json.dump(theme_data, f)

      result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 1, 0))
      assert result == 16, f'Expected 16 at 01:00, got {result}'
      print('✓ 01:00 → returns 16')
  "

  # Test overflow error
  python -c "
  from kwallpaper.wallpaper_changer import select_image_for_time_hourly
  from datetime import datetime
  import json
  import tempfile
  from pathlib import Path

  # Theme with only 5 images, requesting image 16
  theme_data = {
      'sunriseImageList': ['1.jpeg', '2.jpeg', '3.jpeg', '4.jpeg', '5.jpeg'],
      'dayImageList': ['5.jpeg'],
      'sunsetImageList': ['10.jpeg'],
      'nightImageList': ['14.jpeg']
  }

  with tempfile.TemporaryDirectory() as tmpdir:
      theme_path = Path(tmpdir) / 'theme'
      theme_path.mkdir()
      with open(theme_path / 'theme.json', 'w') as f:
          json.dump(theme_data, f)

      try:
          result = select_image_for_time_hourly(theme_data, datetime(2026, 2, 2, 16, 0))
          print('✗ Should have raised ValueError')
          exit(1)
      except ValueError as e:
          assert 'exceeds available images' in str(e).lower(), f'Wrong error message: {e}'
          print('✓ Raises ValueError on overflow')
  "
  ```

  **Evidence to Capture**:
  - [ ] Terminal output showing all 5 verification commands succeed

  **Commit**: YES
  - Message: `feat(astral): add hourly fallback image selection`
  - Files: `kwallpaper/wallpaper_changer.py`
  - Pre-commit: `python -c "from kwallpaper.wallpaper_changer import select_image_for_time_hourly; print('✓ Function exists')"`

---

- [ ] 2. Modify Monitor Mode to Use Hourly Fallback

  **What to do**:
  - Update `run_change_command()` function in `kwallpaper/wallpaper_changer.py` (lines 993-998):
    - Add try/except block around `select_image_for_time()` call
    - If `select_image_for_time()` raises `ImportError` (Astral not installed):
      - Call `select_image_for_time_hourly(theme_data, current_time)`
    - If `select_image_for_time()` raises `ValueError` (any Astral failure):
      - Call `select_image_for_time_hourly(theme_data, current_time)`
    - If both fail, log error and return False
  - Update exception handling to catch both ImportError and ValueError

  **Current Code (lines 993-998)**:
  ```python
  try:
      new_image_index = select_image_for_time(theme_data, current_time)
      if new_image_index != last_image_index:
          need_new_image = True
  except Exception:
      need_new_image = False
  ```

  **Updated Code**:
  ```python
  try:
      new_image_index = select_image_for_time(theme_data, current_time)
      if new_image_index != last_image_index:
          need_new_image = True
  except ImportError:
      # Astral not installed - use hourly fallback
      print("Astral not available, using hourly fallback")
      try:
          new_image_index = select_image_for_time_hourly(theme_data, current_time)
          if new_image_index != last_image_index:
              need_new_image = True
      except Exception as e:
          print(f"Hourly fallback failed: {e}")
          need_new_image = False
  except ValueError:
      # Astral library available but failed (e.g., polar region, invalid location)
      print("Astral time selection failed, using hourly fallback")
      try:
          new_image_index = select_image_for_time_hourly(theme_data, current_time)
          if new_image_index != last_image_index:
              need_new_image = True
      except Exception as e:
          print(f"Hourly fallback failed: {e}")
          need_new_image = False
  except Exception as e:
      print(f"Error selecting image for time: {e}")
      need_new_image = False
  ```

  **Must NOT do**:
  - Modify `select_image_for_time()` function logic
  - Add new CLI parameters
  - Change existing error handling patterns beyond adding try/except for hourly fallback

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Moderate complexity - understanding monitor mode loop, exception handling, integration with new function
  - **Skills**: `[]`
    - No special skills needed - Python exception handling and understanding existing codebase

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3 (tests depend on this integration)
  - **Blocked By**: Task 1 (function must exist) | Yes

  **References**:
  - **Pattern References**:
    - `kwallpaper/wallpaper_changer.py:993-998` - Current monitor mode loop (exception handling pattern)
    - `kwallpaper/wallpaper_changer.py:419-523` - `select_image_for_time()` (what exceptions it might raise - ImportError and ValueError)
    - `kwallpaper/wallpaper_changer.py:966` - How theme_data is loaded in monitor mode

  - **WHY References Matter**:
    - `kwallpaper/wallpaper_changer.py:993-998` - This is the monitor mode loop that needs modification - look at the existing try/except pattern and where the `select_image_for_time()` call is made, then add nested try/except blocks for ImportError and ValueError to catch Astral failures and trigger hourly fallback
    - `kwallpaper/wallpaper_changer.py:419-523` - This shows `select_image_for_time()` raises both ImportError (line 444) and ValueError (line 448), so we need to catch both exceptions
    - `kwallpaper/wallpaper_changer.py:966` - This shows how theme_data is loaded and passed to `select_image_for_time()`

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Monitor mode catches ImportError and calls hourly fallback
  - [ ] Monitor mode catches ValueError (any Astral failure) and calls hourly fallback
  - [ ] Both fallback attempts log appropriate messages
  - [ ] If both fail, monitor mode returns False

  **Automated Verification**:

  ```bash
  # Verify monitor mode has hourly fallback for ImportError
  grep -n "except ImportError" kwallpaper/wallpaper_changer.py
  # Assert: Output shows "except ImportError" line
  # Expected: Line shows ImportError handling

  # Verify monitor mode has hourly fallback for ValueError
  grep -n "except ValueError" kwallpaper/wallpaper_changer.py
  # Assert: Output shows "except ValueError" line
  # Expected: Line shows ValueError handling

  # Verify monitor mode calls select_image_for_time_hourly
  grep -n "select_image_for_time_hourly" kwallpaper/wallpaper_changer.py
  # Assert: Output shows line number (e.g., "998:    new_image_index = select_image_for_time_hourly(...)")
  # Expected: Line shows the new function call
  ```

  **Evidence to Capture**:
  - [ ] Terminal output showing grep results

  **Commit**: NO | YES (groups with Task 1)
  - Message: `feat(astral): integrate hourly fallback in monitor mode`
  - Files: `kwallpaper/wallpaper_changer.py`
  - Pre-commit: `grep -c "select_image_for_time_hourly" kwallpaper/wallpaper_changer.py`

---

- [ ] 3. Write Tests for Hourly Fallback

  **What to do**:
  - Add new test functions to `tests/test_astral_time_detection.py`:
    - **16 timing tests**:
      - `test_select_image_for_time_hourly_0430()`: Test returns 1 at 04:30
      - `test_select_image_for_time_hourly_0615()`: Test returns 2 at 06:15
      - `test_select_image_for_time_hourly_0630()`: Test returns 3 at 06:30
      - `test_select_image_for_time_hourly_0730()`: Test returns 4 at 07:30
      - `test_select_image_for_time_hourly_1000()`: Test returns 5 at 10:00
      - `test_select_image_for_time_hourly_1200()`: Test returns 6 at 12:00
      - `test_select_image_for_time_hourly_1400()`: Test returns 7 at 14:00
      - `test_select_image_for_time_hourly_1600()`: Test returns 8 at 16:00
      - `test_select_image_for_time_hourly_1700()`: Test returns 9 at 17:00
      - `test_select_image_for_time_hourly_1800()`: Test returns 10 at 18:00
      - `test_select_image_for_time_hourly_1830()`: Test returns 11 at 18:30
      - `test_select_image_for_time_hourly_1845()`: Test returns 12 at 18:45
      - `test_select_image_for_time_hourly_1900()`: Test returns 13 at 19:00
      - `test_select_image_for_time_hourly_2000()`: Test returns 14 at 20:00
      - `test_select_image_for_time_hourly_2230()`: Test returns 15 at 22:30
      - `test_select_image_for_time_hourly_0100()`: Test returns 16 at 01:00
    - **Edge case tests**:
      - `test_select_image_for_time_hourly_overflow_valueerror()`: Test ValueError when image index > available images
      - `test_select_image_for_time_hourly_before_first_entry()`: Test time before 04:30 (should return 1)
      - `test_select_image_for_time_hourly_empty_image_list()`: Test with empty image list
      - `test_select_image_for_time_hourly_invalid_time_00_00()`: Test invalid midnight time
    - **Integration tests** (OPTIONAL - mark as nice-to-have if too complex):
      - `test_monitor_mode_uses_hourly_fallback()` - Test monitor mode integration

  **Test Patterns to Follow**:
  - Use `tempfile.TemporaryDirectory()` for theme JSON creation (pattern from lines 50-71)
  - Create theme data directly with dict (no mocking needed)
  - Use `pytest.raises(ValueError)` for error tests
  - Assert specific timing value returned (1-16)

  **Must NOT do**:
  - Modify existing functions (tests only)
  - Add new test infrastructure (use existing pytest setup)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Test logic requires understanding of timing table, datetime comparisons, and error handling
  - **Skills**: `[]`
    - No special skills needed - Python testing and datetime math

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (alone)
  - **Blocks**: Task 4 (documentation depends on tests)
  - **Blocked By**: Task 2 (function must exist) | Yes

  **References**:
  - **Pattern References**:
    - `tests/test_astral_time_detection.py:50-71` - Temp config pattern for testing
    - `tests/test_astral_time_detection.py:398-766` - Existing `select_image_for_time()` tests (reference patterns)
    - `tests/test_astral_time_detection.py:771-817` - Existing 4-period detection tests

  - **WHY References Matter**:
    - `tests/test_astral_time_detection.py:50-71` - Use this pattern for creating temp theme JSON files in tests (tempfile.NamedTemporaryFile with json.dump)
    - `tests/test_astral_time_detection.py:398-766` - Look at existing `select_image_for_time()` tests to understand how they mock the function and assert return values

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] All 16 timing tests pass
  - [ ] All edge case tests pass
  - [ ] All existing tests still pass (no regressions)

  **Automated Verification**:

  ```bash
  # Run all hourly fallback tests
  pytest tests/test_astral_time_detection.py -v -k "hourly"
  # Assert: All tests PASS
  # Expected: "PASSED" for each hourly test

  # Run all tests to check for regressions
  pytest tests/test_astral_time_detection.py -v
  # Assert: All tests PASS
  # Expected: All tests PASSED, no failures

  # Verify 16 tests created
  pytest tests/test_astral_time_detection.py -v -k "hourly" --collect-only
  # Assert: Shows 16+ test functions
  # Expected: 16+ tests collected
  ```

  **Evidence to Capture**:
  - [ ] Terminal output showing all tests pass
  - [ ] Exit code 0

  **Commit**: NO | YES (groups with Task 4)
  - Message: `test(astral): add hourly fallback tests`
  - Files: `tests/test_astral_time_detection.py`
  - Pre-commit: `pytest tests/test_astral_time_detection.py -v`

---

- [ ] 4. Update README Documentation

  **What to do**:
  - Update `README.md` to document hourly fallback behavior:
    - Add section "Hourly Fallback" after "Time-of-Day Categories" (around line 86)
    - Document 16-timing table (04:30→1, 06:15→2, ..., 01:00→16)
    - Explain when hourly fallback is used (Astral ImportError OR ValueError)
    - Explain error handling (ValueError on image index overflow)
    - Add usage example showing hourly fallback behavior
  - Ensure documentation is clear and complete

  **Must NOT do**:
  - Modify code (documentation only)
  - Add new CLI commands or parameters
  - Change existing feature descriptions

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation writing task
  - **Skills**: `[]`
    - No special skills needed - clear and concise writing

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (final)
  - **Blocks**: None (final task)
  - **Blocked By**: Task 3 (tests should exist for documentation examples)

  **References**:
  - **Documentation References**:
    - `README.md:Time-of-Day Categories` - Existing time-of-day documentation (follow same format)
    - `README.md:FAQ` - FAQ section (use same tone and structure)

  - **WHY Reference Matters**:
    - `README.md:Time-of-Day Categories` - Use this section as template for documenting hourly fallback (same heading format, same tone)

  **Acceptance Criteria**:

  **Automated Verification**:

  ```bash
  # Verify hourly fallback is documented in README
  grep -i "hourly" README.md
  # Assert: Output shows hourly fallback documentation
  # Expected: Contains "hourly" in README

  # Verify timing table is documented
  grep -E "04:30|06:15|19:00" README.md
  # Assert: Output shows timing table entries
  # Expected: Contains timing table examples

  # Verify explanation of fallback trigger
  grep -i "astral not available" README.md || grep -i "astral library" README.md
  # Assert: Output shows fallback trigger explanation
  # Expected: Contains explanation of when hourly fallback is used
  ```

  **Evidence to Capture**:
  - [ ] Terminal output showing grep results
  - [ ] README content updated

  **Commit**: YES
  - Message: `docs(astral): document hourly fallback image selection`
  - Files: `README.md`
  - Pre-commit: `grep -c "hourly" README.md`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(astral): add hourly fallback image selection` | wallpaper_changer.py | function exists |
| 2 | `feat(astral): integrate hourly fallback in monitor mode` | wallpaper_changer.py | grep shows calls |
| 3 | `test(astral): add hourly fallback tests` | test_astral_time_detection.py | pytest passes |
| 4 | `docs(astral): document hourly fallback image selection` | README.md | grep shows docs |

---

## Success Criteria

### Verification Commands
```bash
# Verify hourly fallback function exists
python -c "from kwallpaper.wallpaper_changer import select_image_for_time_hourly; print('✓ Function exists')"

# Verify all hourly tests pass
pytest tests/test_astral_time_detection.py -v -k "hourly"

# Verify no regressions
pytest tests/test_astral_time_detection.py -v

# Verify documentation updated
grep -i "hourly" README.md
```

### Final Checklist
- [ ] All "Must Have" criteria met
- [ ] All "Must NOT Have" criteria absent
- [ ] All 16 hourly tests pass
- [ ] All edge case tests pass
- [ ] All existing tests still pass
- [ ] README documents hourly fallback

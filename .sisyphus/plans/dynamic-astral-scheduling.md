# kwallpaper Dynamic Astral-Based Scheduling

## TL;DR

> **Quick Summary**: Redesign `select_image_for_time()` to calculate all 16 image time slots dynamically from the 4 astral anchors (dawn/sunrise/sunset/dusk) with configurable durations (20/6/6/20 min), elevation-based adjustments (+4° for sunrise/sunset, -2° for post-sunset), ensuring seasonal adaptation and maintaining backward compatibility with hourly fallback.

> **Deliverables**:
> - Updated `select_image_for_time()` with dynamic astral-based calculations
> - Helper functions for elevation-based time calculations
> - Comprehensive pytest test suite for edge cases (polar regions, timezone transitions, missing data)
> - Backward-compatible hourly fallback when astral unavailable

> **Estimated Effort**: Large
> **Parallel Execution**: NO - sequential
> **Critical Path**: Helper functions → `select_image_for_time()` update → Tests → Edge case verification

---

## Context

### Original Request
Redesign image selection logic to anchor images to astronomical events (dawn, sunrise, sunset, dusk) calculated by astral library. Use solar elevation for seasonal accuracy instead of fixed time buffers.

### Interview Summary
**Key Discussions**:
- Current implementation uses fixed 45-minute buffers for dawn/dusk
- User wants to simplify: use only 4 astral times as anchors (dawn, sunrise, sunset, dusk)
- Use simple time-based scheduling instead of elevation-based complexity
- Calculate durations dynamically based on astral times
- Dawn (Image 2): 20 minutes (average), Sunrise (Image 3): 6 minutes (average)
- Sunset (Image 11): 6 minutes (average), Dusk (Image 13): 20 minutes (average)
- Image 9: 30 minutes (last day image, late day before pre-sunset)
- Image 1: Starts 15 minutes before dawn (ends at dawn - 15 min)
- Night images (14-16, 1): Evenly spaced between dusk and dawn
- Day images (5-9): Evenly spaced between Image 4 end and Image 10 start
- Image 4: Post-sunrise (time_at_elevation(+4°))
- Image 10: Pre-sunset (time_at_elevation(+4°))
- Image 12: Post-sunset (time_at_elevation(-2°))

**User Decisions**:
1. Use ONLY 4 astral times as anchors (dawn, sunrise, sunset, dusk)
2. Day images evenly spaced between Image 4 end and Image 10 start
3. Night images evenly spaced between dusk and dawn
4. Image 1: Early morning sunlight (before dawn)
5. Image 9: Late day before pre-sunset (30 min duration)
6. Average durations: 6 min for sunrise/sunset, 20 min for dawn/dusk
7. TDD approach with pytest

### Metis Review
**Identified Gaps** (addressed):
- **Seasonal adaptation**: Added dynamic duration calculations based on astral times
- **Polar regions**: Added fallback to hourly when sunrise/sunset missing
- **Timezone handling**: Specified timezone-aware datetimes (always UTC for astral)
- **Boundary conditions**: Specified < (not <=) for period starts
- **Image count validation**: Added validation for missing images
- **Missing elevation data**: Added fallback to nearest achievable elevation or next category

---

## Work Objectives

### Core Objective
Replace hardcoded time-based logic with dynamic astral-based scheduling that calculates all 16 image time slots from dawn/sunrise/sunset/dusk anchors, with configurable durations and elevation-based adjustments, while maintaining backward compatibility with hourly fallback.

### Concrete Deliverables
- Updated `kwallpaper/wallpaper_changer.py` with dynamic `select_image_for_time()` function
- Helper functions for elevation-based time calculations
- Config file with configurable duration constants (optional)
- Comprehensive test suite with edge case coverage
- Backward-compatible behavior (hourly fallback when astral unavailable)

### Definition of Done
- [ ] All tests pass (comprehensive edge case coverage)
- [ ] Dynamic scheduling works for all seasons (winter/summer)
- [ ] Polar region fallback tested and working
- [ ] Timezone transitions handled correctly (DST)
- [ ] Elevation-based transitions work for images 4, 10, 12
- [ ] Backward compatibility verified (existing configs work without errors)
- [ ] Performance meets requirement (< 50ms per call)
- [ ] All acceptance criteria are executable pytest commands

### Must Have
- Dynamic astral-based scheduling using dawn/sunrise/sunset/dusk anchors
- Configurable duration constants (dawn=20, sunrise=6, sunset=6, dusk=20, image_9=30)
- Elevation-based time calculations for images 4 (+4°), 10 (+4°), 12 (-2°)
- Comprehensive TDD test suite covering all edge cases
- Backward-compatible hourly fallback when astral unavailable
- Timezone-aware datetimes (always UTC for astral calculations)

### Must NOT Have (Guardrails)
- **NO** breaking changes to the 4 time categories (night/sunrise/day/sunset)
- **NO** modification of the hourly fallback table (16 fixed time points)
- **NO** change to image numbering scheme (1-16)
- **NO** change to existing config file schema (location, timezone)
- **NO** CLI command modifications (extract, change, list)
- **NO** elevation-based transitions for images other than 4, 10, 12
- **NO** new features like GUI or web interface
- **NO** support for animated/video wallpapers

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> This is NOT conditional — it applies to EVERY task, regardless of test strategy.
>
> **FORBIDDEN** — acceptance criteria that require:
> - "User manually tests..." / "사용자가 직접 테스트..."
> - "User visually confirms..." / "사용자가 눈으로 확인..."
> - "User interacts with..." / "사용자가 직접 조작..."
> - "Ask user to verify..." / "사용자에게 확인 요청..."
> - ANY step where a human must perform an action
>
> **ALL verification is executed by the agent** using tools (Playwright, interactive_bash, curl, etc.). No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD)
- **Framework**: pytest

### If TDD Enabled

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure**:
1. **RED**: Write failing test first
   - Test file: `[path].test.py`
   - Test command: `pytest [file]`
   - Expected: FAIL (test exists, implementation doesn't)
2. **GREEN**: Implement minimum code to pass
   - Command: `pytest [file]`
   - Expected: PASS
3. **REFACTOR**: Clean up while keeping green
   - Command: `pytest [file]`
   - Expected: PASS (still)

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

> Whether TDD is enabled or not, EVERY task MUST include Agent-Executed QA Scenarios.
> - **With TDD**: QA scenarios complement unit tests at integration/E2E level
> - **Without TDD**: QA scenarios are the PRIMARY verification method
>
> These describe how the executing agent DIRECTLY verifies the deliverable
> by running it — opening browsers, executing commands, sending API requests.
> The agent performs what a human tester would do, but automated via tools.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Frontend/UI** | Playwright (playwright skill) | Navigate, interact, assert DOM, screenshot |
| **TUI/CLI** | interactive_bash (tmux) | Run command, send keystrokes, validate output |
| **API/Backend** | Bash (curl/httpie) | Send requests, parse responses, assert fields |
| **Library/Module** | Bash (bun/node REPL) | Import, call functions, compare output |
| **Config/Infra** | Bash (shell commands) | Apply config, run state checks, validate |

**Each Scenario MUST Follow This Format:**

```
Scenario: [Descriptive name — what user action/flow is being verified]
  Tool: [Playwright / interactive_bash / Bash]
  Preconditions: [What must be true before this scenario runs]
  Steps:
    1. [Exact action with specific selector/command/endpoint]
    2. [Next action with expected intermediate state]
    3. [Assertion with exact expected value]
  Expected Result: [Concrete, observable outcome]
  Failure Indicators: [What would indicate failure]
  Evidence: [Screenshot path / output capture / response body path]
```

**Scenario Detail Requirements:**
- **Selectors**: Specific CSS selectors (`.login-button`, not "the login button")
- **Data**: Concrete test data (`"test@example.com"`, not `"[email]"`)
- **Assertions**: Exact values (`text contains "Welcome back"`, not "verify it works")
- **Timing**: Include wait conditions where relevant (`Wait for .dashboard (timeout: 10s)`)
- **Negative Scenarios**: At least ONE failure/error scenario per feature
- **Evidence Paths**: Specific file paths (`.sisyphus/evidence/task-N-scenario-name.png`)

**Anti-patterns (NEVER write scenarios like this):**
- ❌ "Verify the login page works correctly"
- ❌ "Check that the API returns the right data"
- ❌ "Test the form validation"
- ❌ "User opens browser and confirms..."

**Write scenarios like this instead:**
- ✅ `Navigate to /login → Fill input[name="email"] with "test@example.com" → Fill input[name="password"] with "ValidPass123!" → Click button[type="submit"] → Wait for /dashboard → Assert h1 contains "Welcome back"`
- ✅ `POST /api/users {"name":"Test","email":"new@test.com"} → Assert status 201 → Assert response.id is UUID → GET /api/users/{id} → Assert name equals "Test"`
- ✅ `Run ./cli --config test.yaml → Wait for "Loaded" in stdout → Send "q" → Assert exit code 0 → Assert stdout contains "Goodbye"`

**Evidence Requirements:**
- Screenshots: `.sisyphus/evidence/` for all UI verifications
- Terminal output: Captured for CLI/TUI verifications
- Response bodies: Saved for API verifications
- All evidence referenced by specific file path in acceptance criteria

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.

```
Wave 1 (Start Immediately):
└── Task 1: Helper functions (elevation time calculations, image spacing)

Wave 2 (After Wave 1):
├── Task 2: Update `select_image_for_time()` with dynamic logic
└── Task 3: Update duration constants

Wave 3 (After Wave 2):
└── Task 4: Comprehensive edge case tests

Wave 4 (After Wave 3):
└── Task 5: Integration verification

Critical Path: Task 1 → Task 2 → Task 4 → Task 5
Parallel Speedup: N/A (sequential due to dependencies)
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | None (sequential) |
| 2 | 1 | 4 | None (sequential) |
| 3 | 2 | 4 | None (sequential) |
| 4 | 2, 3 | 5 | None (sequential) |
| 5 | 4 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1 | delegate_task(category="ultrabrain", load_skills=["oracle"], subagent_type="sisphus-junior") |
| 2 | 2, 3 | delegate_task(category="ultrabrain", load_skills=["oracle"], subagent_type="sisphus-junior") |
| 3 | 4 | delegate_task(category="ultrabrain", load_skills=["oracle"], subagent_type="sisphus-junior") |
| 4 | 5 | delegate_task(category="visual-engineering", load_skills=["frontend-ui-ux"], subagent_type="sisphus-junior") |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [ ] 1. Implement helper functions for elevation-based time calculations

  **What to do**:
  - Add `calculate_elevation_time()` function using `time_at_elevation()` from astral
  - Add `calculate_image_spacing()` function for evenly spacing images
  - Add `get_period_duration()` helper for dawn/sunrise/sunset/dusk periods
  - Handle edge cases: polar regions, missing data, negative durations
  - Use timezone-aware datetimes (always UTC for astral calculations)

  **Must NOT do**:
  - Don't modify existing `select_image_for_time()` logic yet
  - Don't change the 4 time categories (night/sunrise/day/sunset)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `ultrabrain`
    - Reason: Complex time calculations and edge case handling require strong reasoning
  - **Skills**: `oracle`
    - `oracle`: Expert reasoning for complex time calculations, edge cases, and algorithm design
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed - this is backend logic, not UI
    - `git-master`: Not needed - no code modifications yet

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: None (sequential)
  - **Blocks**: Tasks 2, 3
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `kwallpaper/wallpaper-changer.py:259-358` - `detect_time_of_day_sun()` function (see how to get astral times)
  - `kwallpaper/wallpaper-changer.py:654-896` - `select_image_for_time()` function (see current time-based logic)
  - `kwallpaper/wallpaper-changer.py:899-917` - `detect_time_of_day_hour()` function (see how to handle time ranges)

  **API/Type References** (contracts to implement against):
  - `kwallpaper/wallpaper-changer.py:259-358` - `detect_time_of_day_sun()` signature and return values
  - `kwallpaper/wallpaper-changer.py:654-896` - `select_image_for_time()` signature and return value
  - `kwallpaper/wallpaper-changer.py:654-896` - Use timezone-aware datetime (datetime with timezone.utc)

  **Test References** (testing patterns to follow):
  - `.sisyphus/drafts/image-selection-redesign.md` - Schedule requirements and edge cases

  **Documentation References** (specs and requirements):
  - `README.md:Time-of-Day Categories` - Current time ranges (night/sunrise/day/sunset)
  - `README.md:Hourly Fallback` - Hourly table structure (keep unchanged)

  **External References** (libraries and frameworks):
  - Astral library: `time_at_elevation()` - Use for elevation-based time calculations
  - `timezone.utc` - Always use UTC for astral calculations, never system timezone

  **WHY Each Reference Matters** (explain the relevance):
  - Don't just list files - explain what pattern/information the executor should extract
  - Bad: `kwallpaper/wallpaper-changer.py:259` (vague, which function?)
  - Good: `kwallpaper/wallpaper-changer.py:259-358` - `detect_time_of_day_sun()` shows how to get dawn/sunrise/sunset/dusk times from astral, use this pattern for helper functions

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_helper_functions.py
  - [ ] Test covers: `calculate_elevation_time()` returns correct time for +4° and -2°
  - [ ] Test covers: `calculate_image_spacing()` evenly spaces images across period
  - [ ] Test covers: `get_period_duration()` handles overnight crossing (dusk to next dawn)
  - [ ] Test covers: Elevation calculation fails gracefully and returns None
  - [ ] Test covers: Polar region (latitude 70°) returns None for sunrise/sunset
  - [ ] `bun test tests/test_helper_functions.py` → PASS (all tests passing)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real selectors/data + evidence path.

  **Example — Helper Functions (Bash):**

  ```
  Scenario: Calculate elevation time for +4° after sunrise
    Tool: Bash (Python)
    Preconditions: Astral library installed, location configured
    Steps:
      1. python3 -c "
         from astral import LocationInfo
         from astral.sun import sun
         from astral.sun import time_at_elevation
         location = LocationInfo('Phoenix', 'AZ', 'America/Phoenix', 33.4484, -112.074)
         today = datetime.now().date()
         sunrise = sun(location.observer, date=today)['sunrise']
         elevation_time = time_at_elevation(location.observer, sunrise, 4)
         print(f'Elevation +4° time: {elevation_time}')
         "
      2. Assert: Output shows time after sunrise (e.g., 10:02)
      3. Repeat for -2° elevation after sunset
      4. Assert: Output shows time before dusk (e.g., 18:28)
    Expected Result: Elevation time calculated correctly (after sunrise for +4°, before dusk for -2°)
    Failure Indicators: Output shows time before sunrise or after dusk
    Evidence: Terminal output captured in /tmp/elevation_calculation.txt
  ```

  ```
  Scenario: Polar region returns None for sunrise/sunset
    Tool: Bash (Python)
    Preconditions: Astral library installed, location at latitude 70°
    Steps:
      1. python3 -c "
         from astral import LocationInfo
         from astral.sun import sun
         location = LocationInfo('Arctic', 'Circle', 'Europe/Stockholm', 70.0, 20.0)
         today = datetime.now().date()
         sun_data = sun(location.observer, date=today)
         print(f'Verified sunrise={sun_data[\"sunrise\"]}, sunset={sun_data[\"sunset\"]}')
         "
      2. Assert: sunrise and sunset are None (polar region)
    Expected Result: Polar region returns None for sunrise/sunset
    Failure Indicators: sunrise/sunset are not None
    Evidence: Terminal output captured in /tmp/polar_region.txt
  ```

  **Evidence to Capture:**
  - [ ] Python execution outputs for elevation calculations
  - [ ] Terminal output for polar region test
  - [ ] Each evidence file named: task-1-{scenario-slug}.{ext}

  **Commit**: YES | NO (groups with N)
  - Message: `refactor: add helper functions for elevation-based time calculations`
  - Files: `kwallpaper/wallpaper-changer.py`
  - Pre-commit: `pytest tests/test_helper_functions.py -v`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `refactor: add helper functions for elevation-based time calculations` | `kwallpaper/wallpaper-changer.py` | bun test tests/test_helper_functions.py |

---

## Success Criteria

### Verification Commands
```bash
# Test helper functions
bun test tests/test_helper_functions.py -v

# Test dynamic scheduling
bun test tests/test_dynamic_scheduling.py -v

# Test polar region fallback
bun test tests/test_polar_regions.py -v

# Test timezone transitions
bun test tests/test_timezone_transitions.py -v

# Test elevation-based transitions
bun test tests/test_elevation_transitions.py -v

# Test backward compatibility
bun test tests/test_backward_compatibility.py -v

# Performance test
python3 -c "from kwallpaper import wallpaper_changer; import time; start = time.time(); wc.select_image_for_time(theme_data, datetime.now()); print(f'Execution time: {time.time() - start:.3f}s')" < 50ms
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Backward compatibility verified
- [ ] Performance meets requirement
- [ ] Seasonal adaptation tested (winter/summer scenarios)
- [ ] Edge cases handled (polar regions, DST, missing data)

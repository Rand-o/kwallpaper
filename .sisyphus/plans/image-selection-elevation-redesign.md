# kwallpaper Image Selection Redesign - Elevation-Based Transitions

## TL;DR

> **Quick Summary**: Redesign image selection to use `time_at_elevation()` from the astral library for images 4 and 12, replacing fixed 45-minute buffers with configurable solar elevation angles (+4° for post-sunrise/pre-sunset, -2° for post-sunset). Add elevation_angle_* fields to config.json with graceful fallback to old logic.

> **Deliverables**:
> - Updated `select_image_for_time()` function with elevation-based transitions
> - Config file with elevation_angle_* fields (optional)
> - Comprehensive TDD tests with polar region fallback
> - Backward-compatible behavior for existing configs

> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential
> **Critical Path**: Config fields → Elevation lookup → Image selection → Tests → Fallback logic

---

## Context

### Original Request
Redesign the image selection logic to anchor specific images to astronomical events (dawn, sunrise, sunset, dusk) calculated by the astral library. Use solar elevation for seasonal accuracy instead of fixed time buffers.

### Interview Summary
**Key Discussions**:
- Current implementation uses fixed 45-minute buffers for dawn/dusk (not astronomically accurate)
- Use `time_at_elevation()` for inverse lookup (astral's optimized implementation)
- Add elevation_angle_* fields to config.json location section
- Graceful fallback to old 45-minute buffer logic when elevation_angle_* missing
- Elevation values: +4° for images 4/10, -2° for image 12

**User Decisions**:
1. Constants location: Config file (add elevation_angle_* fields to location section)
2. Inverse lookup: Use time_at_elevation() directly (not custom binary search)
3. Transitions: Elevation-based for images 4 and 12 (configurable)
4. Fallback behavior: Graceful fallback to old logic when config missing
5. Elevation values: README defaults (4°, 4°, -2°)
6. Test strategy: YES (TDD with pytest)

### Metis Review
**Identified Gaps** (addressed):
- Binary search vs time_at_elevation(): Decided to use time_at_elevation() directly
- Backward compatibility: Added graceful fallback logic
- Elevation values: Confirmed +4° for images 4/10, -2° for image 12
- Guardrails: No breaking changes to detect_time_of_day_sun(), CLI, or hourly fallback

---

## Work Objectives

### Core Objective
Replace fixed 45-minute buffers with solar elevation-based transitions for images 4 and 12, using `time_at_elevation()` from the astral library, while maintaining backward compatibility with existing config files.

### Concrete Deliverables
- Updated `kwallpaper/wallpaper-changer.py` with elevation-based logic
- Config file schema with optional `elevation_angle_*` fields
- Comprehensive test suite with polar region fallback
- Backward-compatible behavior (no breaking changes)

### Definition of Done
- [ ] All tests pass (34/34, including new tests)
- [ ] Backward compatibility verified (existing configs work without errors)
- [ ] Elevation-based transitions work for images 4 and 12
- [ ] Polar region fallback tested and working
- [ ] Config validation handles missing elevation_angle_* fields gracefully
- [ ] Performance meets requirement (< 50ms per call)

### Must Have
- Elevation-based transitions for images 4 and 12 using `time_at_elevation()`
- Optional elevation_angle_* fields in config.json with sensible defaults
- Graceful fallback to old 45-minute buffer logic when config missing
- Comprehensive TDD test suite covering all edge cases

### Must NOT Have (Guardrails)
- **NO breaking changes** to `detect_time_of_day_sun()`, CLI functions, or `select_image_for_time_hourly()`
- **NO elevation-based transitions** for images other than 4 and 12
- **NO change** to the 4-category time-of-day detection (night/sunrise/day/sunset)
- **NO removal** of the 45-minute buffer fallback for non-configured images
- **NO new CLI commands** or changes to existing CLI behavior

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
└── Task 1: Config schema update

Wave 2 (After Wave 1):
├── Task 2: Elevation lookup function
├── Task 3: Image selection update
└── Task 4: Polar region fallback

Wave 3 (After Wave 2):
└── Task 5: Comprehensive tests

Wave 4 (After Wave 3):
└── Task 6: Integration verification

Critical Path: Task 1 → Task 2 → Task 3 → Task 5 → Task 6
Parallel Speedup: N/A (sequential due to dependencies)
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3, 4 | None (sequential) |
| 2 | 1 | 3, 4 | None (sequential) |
| 3 | 2 | 5 | None (sequential) |
| 4 | 2 | 5 | None (sequential) |
| 5 | 3, 4 | 6 | None (sequential) |
| 6 | 5 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1 | delegate_task(category="quick", load_skills=[], subagent_type="sisphus-junior") |
| 2 | 2, 3, 4 | dispatch parallel after Wave 1 completes |
| 3 | 5 | final integration task |
| 4 | 6 | final verification task |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [ ] 1. Add elevation_angle_* fields to config schema with validation

  **What to do**:
  - Add `elevation_angle_post_sunrise`, `elevation_angle_pre_sunset`, `elevation_angle_post_sunset` to `DEFAULT_CONFIG` in `wallpaper_changer.py`
  - Add validation in `validate_config()` to ensure values are between -90 and 90
  - Add defaults: 4, 4, -2 (matching README values)
  - Handle missing fields gracefully (use old logic)

  **Must NOT do**:
  - Don't require these fields (they're optional)
  - Don't change existing config structure

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Simple config updates, no complex logic
  - **Skills**: []
    - No special skills needed for config file changes

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: None (sequential)
  - **Blocks**: Tasks 2, 3, 4
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `kwallpaper/wallpaper-changer.py:51-57` - DEFAULT_CONFIG structure (see current location fields)
  - `kwallpaper/wallpaper-changer.py:104-145` - validate_config() function (see how to add field validation)
  - `kwallpaper/wallpaper-changer.py:61-90` - load_config() and save_config() functions

  **API/Type References** (contracts to implement against):
  - `kwallpaper/wallpaper-changer.py:51-57` - DEFAULT_CONFIG (add new fields here)
  - `kwallpaper/wallpaper-changer.py:104-145` - validate_config() (add validation for new fields)

  **Test References** (testing patterns to follow):
  - `.sisyphus/drafts/image-selection-redesign.md` - Config schema requirements

  **Documentation References** (specs and requirements):
  - `.sisyphus/drafts/image-selection-redesign.md` - Config field descriptions

  **External References** (libraries and frameworks):
  - `requirements.txt` - No new dependencies needed (astral already installed)

  **WHY Each Reference Matters** (explain the relevance):
  - Don't just list files - explain what pattern/information the executor should extract
  - Bad: `kwallpaper/wallpaper-changer.py:51-57` (vague, which constants?)
  - Good: `kwallpaper/wallpaper-changer.py:51-57` - DEFAULT_CONFIG contains location section with latitude/longitude/timezone; add elevation_angle_* fields here following the same pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_config_elevation_fields.py
  - [ ] Test covers: elevation_angle_* fields are optional and have sensible defaults
  - [ ] Test covers: values are validated to be between -90 and 90
  - [ ] Test covers: missing elevation_angle_* fields don't break existing configs
  - [ ] bun test tests/test_config_elevation_fields.py → PASS (all tests passing)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real selectors/data + evidence path.

  **Example — Config Update (Bash):**

  ```
  Scenario: Config file with elevation_angle_* fields loads successfully
    Tool: Bash (cat)
    Preconditions: Config file exists at ~/.config/wallpaper-changer/config.json
    Steps:
      1. cat ~/.config/wallpaper-changer/config.json
      2. Verify the file contains "elevation_angle_post_sunrise": 4
      3. Verify the file contains "elevation_angle_pre_sunset": 4
      4. Verify the file contains "elevation_angle_post_sunset": -2
    Expected Result: All three fields present with correct values
    Failure Indicators: Any field missing or with wrong value
    Evidence: Response body captured in /tmp/config_output.txt
  ```

  ```
  Scenario: Config file without elevation_angle_* fields loads without error
    Tool: Bash (Python)
    Preconditions: Config file exists but doesn't have elevation_angle_* fields
    Steps:
      1. python3 -c "from kwallpaper import wallpaper_changer; wc.load_config('~/.config/wallpaper-changer/config.json')"
      2. Verify no exceptions are raised
    Expected Result: Config loads successfully, uses old logic for images 4/12
    Failure Indicators: KeyError or ValueError raised
    Evidence: Exit code 0, no error output
  ```

  ```
  Scenario: Config file with invalid elevation_angle_* values is rejected
    Tool: Bash (Python)
    Preconditions: Config file exists with elevation_angle_* = -100
    Steps:
      1. Create config with "elevation_angle_post_sunrise": -100
      2. python3 -c "from kwallpaper import wallpaper_changer; wc.load_config('invalid_config.json')"
      3. Verify ValueError is raised with "elevation_angle" in message
    Expected Result: Validation fails with clear error message
    Failure Indicators: Config loads without error or wrong error message
    Evidence: Traceback captured in /tmp/validation_error.txt
  ```

  **Evidence to Capture:**
  - [ ] Config file outputs captured
  - [ ] Python execution outputs for validation tests
  - [ ] Each evidence file named: task-1-{scenario-slug}.{ext}

  **Commit**: YES | NO (groups with N)
  - Message: `feat(config): add elevation_angle_* fields with validation`
  - Files: `kwallpaper/wallpaper-changer.py`
  - Pre-commit: `pytest tests/test_config_elevation_fields.py -v`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(config): add elevation_angle_* fields with validation` | `kwallpaper/wallpaper-changer.py` | bun test tests/test_config_elevation_fields.py |

---

## Success Criteria

### Verification Commands
```bash
# Test config with elevation fields
bun test tests/test_config_elevation_fields.py -v

# Test backward compatibility
bun test tests/test_backward_compatibility.py -v

# Test polar region fallback
bun test tests/test_polar_fallback.py -v

# Test elevation-based transitions
bun test tests/test_elevation_transitions.py -v

# Test performance
python3 -c "from kwallpaper import wallpaper_changer; import time; start = time.time(); wc.select_image_for_time(theme_data, datetime.now()); print(f'Execution time: {time.time() - start:.3f}s')" < 50ms
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Backward compatibility verified
- [ ] Performance meets requirement

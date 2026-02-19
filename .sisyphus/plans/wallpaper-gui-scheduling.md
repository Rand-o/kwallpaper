# KDE Wallpaper Changer - GUI with Scheduling

## TL;DR

> **Quick Summary**: Build a PyQt6 GUI application that uses APScheduler to run two background tasks: the `cycle` command every 1 minute and the `change` command daily at 00:00. The GUI provides a control panel with start/stop controls, schedule display, and status logs.
>
> **Deliverables**:
> - `wallpaper_gui.py`: PyQt6 GUI application
> - Extended `config.json`: Added scheduling configuration
> - Updated `requirements.txt`: APScheduler and PyQt6 dependencies
> - Comprehensive tests for GUI and scheduler integration
>
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (GUI setup → Scheduler integration → Testing)
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## Context

### Original Request
Add scheduling functionality to wallpaper-cli.py:
- `cycle` command: Run every 1 minute
- `change` command: Run every day at 12 AM
- Bundle as a GUI application without managing timer files manually

### Interview Summary
**Key Discussions**:
- User wants to avoid systemd timer files and wants a GUI app
- Recommended approach: PyQt6 GUI + APScheduler for background tasks
- Architecture: Main GUI thread + BackgroundScheduler in separate thread
- Configuration: Add to existing config.json file

**Research Findings**:
- APScheduler BackgroundScheduler runs in separate thread (daemon=True)
- PyQt6 is native to KDE Plasma with excellent integration
- Use signals/slots for communication between scheduler and GUI
- Memory management: Proper shutdown on app exit
- Error handling: try/except around scheduler tasks with logging

### Current Implementation
- `wallpaper_cli.py`: CLI entry point
- `kwallpaper/wallpaper_changer.py`: Core functionality
- Existing commands: `cycle`, `change`, `--monitor`
- Dependencies: `astral>=2.2`

---

## Work Objectives

### Core Objective
Create a PyQt6 GUI application that uses APScheduler to automatically run wallpaper-changing tasks at specified intervals (1 minute for `cycle`, daily at 00:00 for `change`).

### Concrete Deliverables
- PyQt6 GUI application with control panel
- APScheduler integration for background task scheduling
- Extended configuration file with scheduling settings
- Comprehensive test suite
- Updated documentation

### Definition of Done
- [ ] GUI application launches and displays control panel
- [ ] Start/Stop buttons control scheduler state
- [ ] Cycle task runs every 1 minute
- [ ] Change task runs daily at 00:00
- [ ] Status logs show scheduler events
- [ ] All tests pass (unit + integration + UI tests)
- [ ] Application handles errors gracefully
- [ ] Configuration file updated with scheduling settings

### Must Have
- PyQt6 GUI for user interface
- APScheduler for background task scheduling
- Two scheduled tasks: 1-minute cycle and daily at 00:00
- Control panel with start/stop functionality
- Status logging and error handling
- Backward compatibility with existing CLI

### Must NOT Have (Guardrails)
- NO systemd timer files (user explicitly wants to avoid this)
- NO manual timer file management
- NO breaking changes to existing CLI functionality
- NO memory leaks in scheduler
- NO unhandled exceptions in background tasks

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
> by running it — launching the GUI, executing commands, checking logs.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **GUI Application** | Playwright (playwright skill) | Launch application, interact with UI, assert visual elements, capture screenshots |
| **Scheduler Integration** | Bash (pytest) | Run scheduler tests, verify task execution times |
| **Configuration** | Bash (jq/python) | Load config, validate schema, check values |

**Each Scenario MUST Follow This Format:**

```
Scenario: [Descriptive name — what user action/flow is being verified]
  Tool: [Playwright / pytest / Bash]
  Preconditions: [What must be true before this scenario runs]
  Steps:
    1. [Exact action with specific selector/command/endpoint]
    2. [Next action with expected intermediate state]
    3. [Assertion with exact expected value]
  Expected Result: [Concrete, observable outcome]
  Failure Indicators: [What would indicate failure]
  Evidence: [Screenshot path / test output path]
```

**Scenario Detail Requirements:**
- **Selectors**: Specific PyQt6 widget names (e.g., QPushButton#startButton, QLabel#statusLabel)
- **Data**: Concrete test data (config paths, schedule times)
- **Assertions**: Exact values (scheduler running state, log messages)
- **Timing**: Include wait conditions where relevant (scheduler start delay)
- **Negative Scenarios**: At least ONE failure/error scenario per feature
- **Evidence Paths**: Specific file paths (`.sisyphus/evidence/task-N-scenario-name.png`)

**Anti-patterns (NEVER write scenarios like this):**
- ❌ "Verify the GUI starts correctly"
- ❌ "Check that the scheduler runs tasks"
- ❌ "Test the configuration file"

**Write scenarios like this instead:**
- ✅ `Launch GUI application → Assert title contains "Wallpaper Changer" → Click Start button → Assert status label contains "Scheduler running" → Verify cycle task runs within 1 minute → Assert log shows "Cycle task executed"`
- ✅ `Start scheduler → Wait 65 seconds → Verify change task executed at 00:00 → Assert log shows "Change task executed at 00:00"`

**Evidence Requirements:**
- Screenshots: `.sisyphus/evidence/` for UI scenarios
- Test output: `.sisyphus/evidence/test-output.txt` for pytest
- Config files: `.sisyphus/evidence/config.json` for config scenarios
- All evidence referenced by specific file path in acceptance criteria

---

## Execution Strategy

### Parallel Execution Waves

No parallel execution — all tasks must be sequential due to dependencies.

```
Wave 1 (Start Immediately):
└── Task 1: Project setup and dependencies

Wave 2 (After Wave 1):
├── Task 2: Configuration extension
└── Task 3: Core scheduler module

Wave 3 (After Wave 2):
└── Task 4: GUI application

Wave 4 (After Wave 3):
└── Task 5: Testing

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 5
Parallel Speedup: N/A (sequential)
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3, 4, 5 | None |
| 2 | 1 | 3, 4, 5 | None |
| 3 | 2 | 4, 5 | None |
| 4 | 3 | 5 | None |
| 5 | 4 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1 | task(category="quick", load_skills=[], run_in_background=false) |
| 2 | 2, 3 | task(category="unspecified-high", load_skills=[], run_in_background=false) |
| 3 | 4 | task(category="visual-engineering", load_skills=["frontend-ui-ux"], run_in_background=false) |
| 4 | 5 | task(category="unspecified-high", load_skills=[], run_in_background=false) |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [ ] 1. Add APScheduler and PyQt6 dependencies to requirements.txt

  **What to do**:
  - Add `apscheduler>=3.10.0` to requirements.txt
  - Add `PyQt6>=6.6.0` to requirements.txt
  - Add `PySide6>=6.6.0` to requirements.txt
  - Verify installation works with `pip install -r requirements.txt`
  - Write test to verify dependencies are installed

  **Must NOT do**:
  - Modify existing CLI functionality
  - Change existing dependencies

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file modification, no complex logic
  - **Skills**: []
    - No specific skills needed
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed (no git operations)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: All downstream tasks
  - **Blocked By**: None (can start immediately)

  **References**:
  - `requirements.txt`: Current dependencies file
  - Official docs: `https://apscheduler.readthedocs.io/` - APScheduler installation
  - Official docs: `https://www.riverbankcomputing.com/static/Docs/PyQt6/` - PyQt6 installation

  **WHY Each Reference Matters**:
  - `requirements.txt`: Target file to modify
  - APScheduler docs: Verify correct version and installation
  - PyQt6 docs: Verify compatibility with KDE Plasma

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_dependencies.py
  - [ ] Test checks: APScheduler import successful
  - [ ] Test checks: PyQt6 import successful
  - [ ] Test checks: PySide6 import successful
  - [ ] `pytest tests/test_dependencies.py` → PASS (3 tests, 0 failures)

  **Agent-Executed QA Scenarios**:

  **Scenario: Dependencies installed successfully**
    Tool: Bash (pip/pytest)
    Preconditions: Python 3.8+, virtual environment activated
    Steps:
      1. `pip install -r requirements.txt`
      2. `python3 -c "import apscheduler; import PyQt6; import PySide6; print('All dependencies installed')"`
      3. `pytest tests/test_dependencies.py -v`
    Expected Result: All imports successful, tests pass
    Failure Indicators: ImportError, test failures
    Evidence: `.sisyphus/evidence/task-1-dependencies-install.log`

  **Scenario: Invalid dependencies rejected**
    Tool: Bash (pip)
    Preconditions: Fresh virtual environment
    Steps:
      1. `pip install -r requirements.txt`
      2. Run pytest with missing dependencies
      3. Verify error messages
    Expected Result: Installation fails with clear error messages
    Failure Indicators: Installation succeeds with wrong versions
    Evidence: `.sisyphus/evidence/task-1-dependencies-error.log`

  **Evidence to Capture**:
  - [ ] Installation log in .sisyphus/evidence/
  - [ ] Test output captured
  - [ ] Each evidence file named: task-1-{scenario-slug}.log

  **Commit**: YES
  - Message: `chore: add APScheduler and PyQt6 dependencies`
  - Files: `requirements.txt`
  - Pre-commit: `pytest tests/test_dependencies.py`

- [ ] 2. Extend config.json with scheduling settings

  **What to do**:
  - Read existing config.json structure
  - Add scheduling configuration section:
    ```json
    {
      "interval": 60,
      "daily_change_time": "00:00",
      "run_cycle": true,
      "run_daily_change": true
    }
    ```
  - Update existing config.json in place
  - Write test to verify config validation
  - Write test to verify config can be loaded

  **Must NOT do**:
  - Change existing config fields
  - Remove existing required fields

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration file modification
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 3 (scheduler module)
  - **Blocked By**: Task 1 (dependencies need to be installed first)

  **References**:
  - `~/.config/wallpaper-changer/config.json`: Existing configuration file (or create default)
  - `README.md:Configuration`: Existing config documentation

  **WHY Each Reference Matters**:
  - `config.json`: Target file to modify
  - `README.md`: Existing config structure for consistency

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_config_scheduling.py
  - [ ] Test covers: Config loads with scheduling settings
  - [ ] Test covers: Config validates required scheduling fields
  - [ ] Test covers: Default values applied if missing
  - [ ] `pytest tests/test_config_scheduling.py` → PASS (3 tests, 0 failures)

  **Agent-Executed QA Scenarios**:

  **Scenario: Config loads with scheduling settings**
    Tool: Bash (python)
    Preconditions: config.json exists with scheduling section
    Steps:
      1. `python3 -c "from kwallpaper.config import load_config; config = load_config(); print(config.get('scheduling'))"`
      2. Verify output contains: interval, daily_change_time, run_cycle, run_daily_change
    Expected Result: Config loads successfully with all scheduling fields
    Failure Indicators: ImportError, KeyError for scheduling fields
    Evidence: `.sisyphus/evidence/task-2-config-load.log`

  **Scenario: Missing scheduling fields use defaults**
    Tool: Bash (python)
    Preconditions: config.json missing scheduling section
    Steps:
      1. Create minimal config.json without scheduling
      2. Load config and verify defaults applied
      3. Verify default values: interval=60, daily_change_time="00:00", run_cycle=true, run_daily_change=true
    Expected Result: Defaults applied when fields missing
    Failure Indicators: KeyError or missing fields
    Evidence: `.sisyphus/evidence/task-2-config-defaults.log`

  **Evidence to Capture**:
  - [ ] Config loading output captured
  - [ ] Default values verified in output
  - [ ] Each evidence file named: task-2-{scenario-slug}.log

  **Commit**: YES
  - Message: `feat: add scheduling configuration to config.json`
  - Files: `config.json`
  - Pre-commit: `pytest tests/test_config_scheduling.py`

- [ ] 3. Create scheduler module for background task management

  **What to do**:
  - Create `kwallpaper/scheduler.py` module
  - Implement `SchedulerManager` class with:
    - `__init__(config_path)`: Load config, initialize BackgroundScheduler
    - `start()`: Start scheduler, add cycle task (1 minute), add change task (daily 00:00)
    - `stop()`: Shutdown scheduler gracefully
    - `add_job(name, func, trigger)`: Add new scheduled job
    - `remove_job(name)`: Remove scheduled job
  - Implement `run_cycle_task()`: Wrapper for existing `run_cycle_command()`
  - Implement `run_change_task()`: Wrapper for existing `run_change_command()`
  - Add error handling and logging
  - Write comprehensive tests for scheduler

  **Must NOT do**:
  - Modify existing `wallpaper_changer.py` commands
  - Change command signatures
  - Add GUI-specific code

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex module with multiple classes and methods
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 4 (GUI application)
  - **Blocked By**: Task 2 (config must exist first)

  **References**:
  - `kwallpaper/wallpaper_changer.py:run_cycle_command()`: Existing cycle command implementation
  - `kwallpaper/wallpaper_changer.py:run_change_command()`: Existing change command implementation
  - `kwallpaper/wallpaper_changer.py:main()`: Command routing logic (for reference)
  - Official docs: `https://apscheduler.readthedocs.io/` - Scheduler API reference

  **WHY Each Reference Matters**:
  - `run_cycle_command()`: Task to be scheduled, must be called correctly
  - `run_change_command()`: Task to be scheduled, must be called correctly
  - `main()`: Command structure for consistency
  - APScheduler docs: Scheduler class usage patterns

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_scheduler.py
  - [ ] Test covers: Scheduler initializes with config
  - [ ] Test covers: Cycle task added with 1-minute interval
  - [ ] Test covers: Change task added with daily 00:00 trigger
  - [ ] Test covers: Scheduler starts and stops correctly
  - [ ] Test covers: Error handling in tasks
  - [ ] `pytest tests/test_scheduler.py` → PASS (5 tests, 0 failures)

  **Agent-Executed QA Scenarios**:

  **Scenario: Scheduler starts with configured tasks**
    Tool: Bash (pytest + python)
    Preconditions: Config file exists, APScheduler installed
    Steps:
      1. `python3 -c "from kwallpaper.scheduler import SchedulerManager; scheduler = SchedulerManager(); scheduler.start()"`
      2. Verify scheduler is running (check job list)
      3. Verify cycle task exists with interval=1 minute
      4. Verify change task exists with cron trigger at 00:00
      5. `scheduler.stop()`
    Expected Result: Scheduler starts with both tasks configured
    Failure Indicators: Scheduler doesn't start, tasks missing
    Evidence: `.sisyphus/evidence/task-3-scheduler-start.log`

  **Scenario: Scheduler stops gracefully**
    Tool: Bash (python)
    Preconditions: Scheduler running
    Steps:
      1. Start scheduler
      2. `scheduler.stop(wait=True)`
      3. Verify scheduler shutdown complete
    Expected Result: Scheduler stops without errors
    Failure Indicators: Timeout, error messages during shutdown
    Evidence: `.sisyphus/evidence/task-3-scheduler-stop.log`

  **Scenario: Cycle task runs every minute**
    Tool: Bash (pytest)
    Preconditions: Scheduler running, cycle task added
    Steps:
      1. Start scheduler with cycle task
      2. Wait 70 seconds
      3. Verify cycle task executed at least once
      4. Check logs for execution timestamps
    Expected Result: Cycle task executes approximately every minute
    Failure Indicators: Task doesn't execute, wrong interval
    Evidence: `.sisyphus/evidence/task-3-cycle-task.log`

  **Scenario: Change task runs daily at 00:00**
    Tool: Bash (pytest)
    Preconditions: Scheduler running, change task added
    Steps:
      1. Start scheduler with change task
      2. Set system time to 00:00 (using TZ environment variable)
      3. Wait for next trigger
      4. Verify change task executed at 00:00
      5. Check logs for execution timestamp
    Expected Result: Change task executes at 00:00 daily
    Failure Indicators: Task doesn't execute at correct time
    Evidence: `.sisyphus/evidence/task-3-change-task.log`

  **Evidence to Capture**:
  - [ ] Test output captured
  - [ ] Scheduler logs captured
  - [ ] Each evidence file named: task-3-{scenario-slug}.log

  **Commit**: YES
  - Message: `feat: add scheduler module for background task management`
  - Files: `kwallpaper/scheduler.py`, `tests/test_scheduler.py`
  - Pre-commit: `pytest tests/test_scheduler.py`

- [ ] 4. Build PyQt6 GUI application with control panel

  **What to do**:
  - Create `wallpaper_gui.py` main application file
  - Implement `WallpaperGUI` class with PyQt6 widgets:
    - Main window with title "KDE Wallpaper Changer"
    - Start/Stop button for scheduler control
    - Status label showing scheduler state
    - Schedule display (cycle: every 1 minute, change: daily at 00:00)
    - Log area displaying scheduler events
  - Integrate with `SchedulerManager`:
    - Connect Start button to `scheduler.start()`
    - Connect Stop button to `scheduler.stop()`
    - Update status label on scheduler state changes
    - Append log messages to log area
  - Handle application close event to shutdown scheduler
  - Add error handling and user feedback
  - Write comprehensive GUI and integration tests

  **Must NOT do**:
  - Modify existing `wallpaper_changer.py` commands
  - Change scheduler module behavior
  - Add GUI-specific configuration to main config file

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: GUI development requires UI/UX design skills
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Design and implement PyQt6 GUI with proper layout, styling, and user experience
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed (PyQt6 GUI testing, not web)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 5 (testing)
  - **Blocked By**: Task 3 (scheduler module must exist first)

  **References**:
  - `kwallpaper/scheduler.py`: Scheduler manager to integrate with
  - `kwallpaper/wallpaper_changer.py`: Existing command functions
  - Official docs: `https://www.riverbankcomputing.com/static/Docs/PyQt6/` - PyQt6 widgets and signals/slots
  - Official docs: `https://www.riverbankcomputing.com/static/Docs/PyQt6/signals_slots.html` - Signal/slot architecture

  **WHY Each Reference Matters**:
  - `scheduler.py`: Main scheduler class to integrate
  - `wallpaper_changer.py`: Command functions to call
  - PyQt6 docs: Widget API, signals/slots for GUI-scheduler communication

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_gui.py
  - [ ] Test covers: GUI launches successfully
  - [ ] Test covers: Start button starts scheduler
  - [ ] Test covers: Stop button stops scheduler
  - [ ] Test covers: Status label updates correctly
  - [ ] Test covers: Log area displays events
  - [ ] Test covers: Scheduler shutdown on app exit
  - [ ] `pytest tests/test_gui.py` → PASS (5 tests, 0 failures)

  **Agent-Executed QA Scenarios**:

  **Scenario: GUI launches with control panel**
    Tool: Playwright (playwright skill)
    Preconditions: PyQt6 installed, scheduler module available
    Steps:
      1. Launch GUI: `python3 wallpaper_gui.py &`
      2. Wait for window to appear (timeout: 5s)
      3. Assert window title contains "KDE Wallpaper Changer"
      4. Assert Start button exists and is visible
      5. Assert Stop button exists and is visible
      6. Assert status label exists and is visible
      7. Assert schedule display exists and shows correct info
      8. Assert log area exists and is visible
      9. Screenshot: `.sisyphus/evidence/task-4-gui-launch.png`
    Expected Result: GUI launches with all control panel elements
    Failure Indicators: Window doesn't appear, missing buttons
    Evidence: `.sisyphus/evidence/task-4-gui-launch.png`

  **Scenario: Start button starts scheduler**
    Tool: Playwright (playwright skill)
    Preconditions: GUI running, scheduler stopped
    Steps:
      1. Launch GUI
      2. Click Start button
      3. Wait for status label update (timeout: 3s)
      4. Assert status label contains "Scheduler running"
      5. Assert log area contains "Scheduler started"
      6. Screenshot: `.sisyphus/evidence/task-4-start-success.png`
    Expected Result: Scheduler starts, status updates, log entry added
    Failure Indicators: Status doesn't change, no log entry
    Evidence: `.sisyphus/evidence/task-4-start-success.png`

  **Scenario: Stop button stops scheduler**
    Tool: Playwright (playwright skill)
    Preconditions: GUI running, scheduler running
    Steps:
      1. Launch GUI
      2. Click Start button (optional, ensure scheduler running)
      3. Click Stop button
      4. Wait for status label update (timeout: 3s)
      5. Assert status label contains "Scheduler stopped"
      6. Assert log area contains "Scheduler stopped"
      7. Screenshot: `.sisyphus/evidence/task-4-stop-success.png`
    Expected Result: Scheduler stops, status updates, log entry added
    Failure Indicators: Status doesn't change, no log entry
    Evidence: `.sisyphus/evidence/task-4-stop-success.png`

  **Scenario: Scheduler shutdown on app exit**
    Tool: Playwright (playwright skill)
    Preconditions: GUI running, scheduler running
    Steps:
      1. Launch GUI
      2. Click Start button
      3. Wait for scheduler to start
      4. Close GUI (click close button or Alt+F4)
      5. Wait for process to exit (timeout: 5s)
      6. Verify scheduler shutdown (check logs or process state)
      7. Screenshot: `.sisyphus/evidence/task-4-exit-shutdown.png`
    Expected Result: GUI closes, scheduler shuts down gracefully
    Failure Indicators: Process hangs, scheduler doesn't shutdown
    Evidence: `.sisyphus/evidence/task-4-exit-shutdown.png`

  **Scenario: Log area displays scheduler events**
    Tool: Playwright (playwright skill)
    Preconditions: GUI running, scheduler started
    Steps:
      1. Launch GUI
      2. Click Start button
      3. Wait 5 seconds
      4. Assert log area contains "Scheduler started"
      5. Assert log area contains "Cycle task scheduled"
      6. Assert log area contains "Change task scheduled"
      7. Screenshot: `.sisyphus/evidence/task-4-log-display.png`
    Expected Result: Log area shows scheduler events
    Failure Indicators: Log area empty or missing entries
    Evidence: `.sisyphus/evidence/task-4-log-display.png`

  **Evidence to Capture**:
  - [ ] Screenshots in .sisyphus/evidence/ for all UI scenarios
  - [ ] Terminal output for GUI launch/capture
  - [ ] Each evidence file named: task-4-{scenario-slug}.png

  **Commit**: YES
  - Message: `feat: add PyQt6 GUI application with control panel`
  - Files: `wallpaper_gui.py`, `tests/test_gui.py`
  - Pre-commit: `pytest tests/test_gui.py`

- [ ] 5. Run comprehensive test suite and integration testing

  **What to do**:
  - Run all tests: `pytest tests/ -v`
  - Run tests with coverage: `pytest tests/ --cov=kwallpaper --cov-report=html`
  - Verify all tests pass (64 existing + new tests)
  - Check code coverage (target: ≥80%)
  - Run GUI tests with Playwright
  - Fix any failing tests
  - Update documentation if needed
  - Verify end-to-end workflow

  **Must NOT do**:
  - Modify code to pass tests (fix bugs instead)
  - Skip tests even if they fail

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Testing requires thorough verification
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None (final task)
  - **Blocked By**: Task 4 (GUI must exist first)

  **References**:
  - `tests/`: Existing test directory
  - `README.md:Development`: Testing documentation
  - Official docs: `https://docs.pytest.org/` - pytest usage

  **WHY Each Reference Matters**:
  - `tests/`: All tests to run
  - `README.md`: Testing instructions for verification

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] All new tests pass
  - [ ] All existing tests still pass (64 tests)
  - [ ] Total tests: 69+ passing
  - [ ] Coverage ≥80%
  - [ ] No test failures

  **Agent-Executed QA Scenarios**:

  **Scenario: All tests pass**
    Tool: Bash (pytest)
    Preconditions: All code written, dependencies installed
    Steps:
      1. `pytest tests/ -v`
      2. Verify exit code is 0
      3. Verify all tests pass
      4. Verify coverage report generated
    Expected Result: All tests pass, coverage ≥80%
    Failure Indicators: Test failures, low coverage
    Evidence: `.sisyphus/evidence/task-5-all-tests-pass.log`

  **Scenario: GUI tests pass**
    Tool: Playwright (playwright skill)
    Preconditions: GUI built, PyQt6 installed
    Steps:
      1. `pytest tests/test_gui.py -v`
      2. Verify all GUI tests pass
      3. Capture screenshots for evidence
    Expected Result: All GUI tests pass
    Failure Indicators: GUI test failures
    Evidence: `.sisyphus/evidence/task-5-gui-tests-pass.log`

  **Scenario: Integration test - full workflow**
    Tool: Playwright (playwright skill) + Bash
    Preconditions: GUI running, scheduler available, test theme exists
    Steps:
      1. Launch GUI
      2. Click Start button
      3. Verify scheduler state (status label)
      4. Wait 1 minute for cycle task execution
      5. Verify cycle task executed (check logs)
      6. Verify wallpaper changed (check system)
      7. Click Stop button
      8. Verify scheduler stopped (status label)
      9. Verify no more execution
      10. Close GUI
      11. Screenshot: `.sisyphus/evidence/task-5-integration-workflow.png`
    Expected Result: Full workflow works end-to-end
    Failure Indicators: Tasks don't execute, GUI issues
    Evidence: `.sisyphus/evidence/task-5-integration-workflow.png`

  **Evidence to Capture**:
  - [ ] Test output in .sisyphus/evidence/
  - [ ] Coverage report in .sisyphus/evidence/
  - [ ] Screenshots for GUI integration tests
  - [ ] Each evidence file named: task-5-{scenario-slug}.log or .png

  **Commit**: YES
  - Message: `test: run comprehensive test suite and integration testing`
  - Files: `.sisyphus/evidence/`
  - Pre-commit: `pytest tests/ --cov=kwallpaper --cov-report=html`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `chore: add APScheduler and PyQt6 dependencies` | requirements.txt | pip install -r requirements.txt |
| 2 | `feat: add scheduling configuration to config.json` | config.json | pytest tests/test_config_scheduling.py |
| 3 | `feat: add scheduler module for background task management` | kwallpaper/scheduler.py, tests/test_scheduler.py | pytest tests/test_scheduler.py |
| 4 | `feat: add PyQt6 GUI application with control panel` | wallpaper_gui.py, tests/test_gui.py | pytest tests/test_gui.py |
| 5 | `test: run comprehensive test suite and integration testing` | .sisyphus/evidence/ | pytest tests/ --cov=kwallpaper --cov-report=html |

---

## Success Criteria

### Verification Commands
```bash
# Run all tests with coverage
pytest tests/ --cov=kwallpaper --cov-report=html

# Test GUI application
pytest tests/test_gui.py -v

# Verify dependencies
python3 -c "import apscheduler; import PyQt6; import PySide6; print('All dependencies OK')"
```

### Final Checklist
- [ ] All "Must Have" present (GUI, APScheduler, two scheduled tasks, control panel, status logs)
- [ ] All "Must NOT Have" absent (no systemd timer files, no breaking changes)
- [ ] All tests pass (64 existing + 15+ new = 79+ tests)
- [ ] Code coverage ≥80%
- [ ] GUI launches and controls scheduler
- [ ] Cycle task runs every 1 minute
- [ ] Change task runs daily at 00:00
- [ ] Status logs display events
- [ ] Application handles errors gracefully
- [ ] Configuration file updated with scheduling settings
- [ ] Backward compatibility maintained with existing CLI

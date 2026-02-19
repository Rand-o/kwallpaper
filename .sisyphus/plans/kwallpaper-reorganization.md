# kwallpaper Directory Reorganization

## TL;DR

> **Move CLI/GUI entry points to project root** and **remove duplicate kwallpaper module from flatpak/**. Update flatpak manifest to reference root directory.
>
> **Deliverables**:
> - `wallpaper_cli.py` moved to root
> - `wallpaper_gui.py` moved to root
> - `flatpak/kwallpaper/` removed
> - Updated `top.spelunk.kwallpaper.json` manifest
> - `requirements.txt` updated if needed
> - `README.md` documentation updated
>
> **Estimated Effort**: Short
> **Parallel Execution**: YES - N waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4

---

## Context

### Original Request
Move `wallpaper_cli.py` and `wallpaper_gui.py` to the root directory, keep `kwallpaper/` in root, and update the flatpak manifest to reference files from the root instead of from within the flatpak directory.

### Interview Summary
**Key Decisions**:
- Keep `kwallpaper/` module at root (already correct)
- Move entry point scripts to root for easier access
- Remove duplicate `flatpak/kwallpaper/` directory to avoid confusion and redundancy
- Update flatpak manifest to reference root files

**Research Findings**:
- Current flatpak build copies files from `flatpak/` into build stage
- Manifest needs to reference correct source paths
- No additional dependencies needed

### Metis Review
**Identified Gaps** (addressed):
- File references in manifest need explicit update
- Build scripts may reference old paths
- Documentation may need updates to reflect new structure

---

## Work Objectives

### Core Objective
Reorganize kwallpaper project structure to have all Python files in the root directory, with flatpak manifest referencing root files, and remove duplicate kwallpaper module from flatpak/ directory.

### Concrete Deliverables
- `wallpaper_cli.py` at `/home/admin/llama-cpp/projects/kwallpaper/wallpaper_cli.py`
- `wallpaper_gui.py` at `/home/admin/llama-cpp/projects/kwallpaper/wallpaper_gui.py`
- `flatpak/kwallpaper/` directory removed
- `flatpak/top.spelunk.kwallpaper.json` updated with correct file references
- Any build scripts updated if they reference old paths

### Definition of Done
- [ ] `ls -la` shows `wallpaper_cli.py` and `wallpaper_gui.py` at root
- [ ] `ls -la flatpak/kwallpaper/` shows empty or removed
- [ ] `cat flatpak/top.spelunk.kwallapper.json` shows correct file paths
- [ ] `flatpak/build.sh` tests with new structure

### Must Have
- All Python files accessible from project root
- Flatpak bundle builds successfully
- No duplicate kwallpaper modules

### Must NOT Have (Guardrails)
- Do NOT remove `tests/` directory
- Do NOT modify `kwallpaper/` module files
- Do NOT break existing functionality
- Do NOT modify dependencies in `requirements.txt`

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (after)
- **Framework**: pytest
- **TDD**: NO - This is a reorganization/refactoring task

### QA Policy
Every task will include agent-executed QA scenarios. After reorganization, verify functionality:
- Frontend: Playwright opens GUI, navigates, interacts with elements
- CLI: Terminal runs CLI commands, validates outputs
- Flatpak: `flatpak build` command succeeds, app launches

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — file moves):
├── Task 1: Move CLI/GUI scripts to root [quick]
└── Task 2: Remove duplicate flatpak/kwallpaper directory [quick]

Wave 2 (After Wave 1 — manifest updates):
├── Task 3: Update flatpak manifest file references [unspecified-high]
└── Task 4: Verify build scripts and update if needed [unspecified-high]

Wave 3 (After Wave 2 — testing):
├── Task 5: Run existing test suite [deep]
├── Task 6: Test flatpak build process [deep]
└── Task 7: Manual verification (CLI/GUI/flatpak) [visual-engineering]

Wave FINAL (After ALL tasks — verification):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: File structure verification (unspecified-high)
├── Task F3: Flatpak build verification (deep)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → F1-F4
Parallel Speedup: ~57% faster than sequential
Max Concurrent: 2 (Waves 1 & 2)
```

### Dependency Matrix

- **1-2**: — — 3-4, 1
- **3**: — 1, 2 — 5, 6
- **4**: 1, 2 — 5, 6
- **5**: 3, 4 — 7
- **6**: 3, 4 — 7
- **7**: 5, 6 — F1-F4
- **F1**: — — F2-F4, 7
- **F2**: — — F3-F4, 7
- **F3**: 7 — F4
- **F4**: — — Final, 7

### Agent Dispatch Summary

- **1**: **2** — T1-T2 → `quick`
- **2**: **7** — T3 → `unspecified-high`, T4 → `unspecified-high`, T5 → `deep`, T6 → `deep`, T7 → `visual-engineering`
- **3**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `deep`, F4 → `deep`

---

## TODOs

- [ ] 1. Move wallpaper_cli.py and wallpaper_gui.py to project root

  **What to do**:
  - Move `flatpak/wallpaper_cli.py` to `wallpaper_cli.py` at root
  - Move `flatpak/wallpaper_gui.py` to `wallpaper_gui.py` at root
  - Verify files exist in both locations before deletion (backup first)
  - Update any imports in moved files if needed (should not need changes)

  **Must NOT do**:
  - Do NOT modify the content of the files, only move them
  - Do NOT remove files until verification is complete

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file operations, high certainty
  - **Skills**: []
    - No special skills needed for file moves

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 3, 4
  - **Blocked By**: None (can start immediately)

  **References**:

  - `flatpak/wallpaper_cli.py` - Source file to move
  - `flatpak/wallpaper_gui.py` - Source file to move

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Verify files exist at root
  ls -la /home/admin/llama-cpp/projects/kwallpaper/wallpaper_cli.py
  ls -la /home/admin/llama-cpp/projects/kwallpaper/wallpaper_gui.py
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: Files exist at root after move
    Tool: Bash (ls)
    Preconditions: None
    Steps:
      1. Run: ls -la /home/admin/llama-cpp/projects/kwallpaper/wallpaper_cli.py
      2. Run: ls -la /home/admin/llama-cpp/projects/kwallpaper/wallpaper_gui.py
    Expected Result: Both files exist with non-zero size
    Failure Indicators: Files not found or size is 0
    Evidence: .sisyphus/evidence/task-1-files-exist.txt
  ```

  **Commit**: YES
  - Message: `refactor: move CLI/GUI scripts to project root`
  - Files: `wallpaper_cli.py`, `wallpaper_gui.py` (from flatpak/)

- [ ] 2. Remove duplicate flatpak/kwallpaper directory

  **What to do**:
  - Remove the `flatpak/kwallpaper/` directory (duplicate of root kwallpaper/)
  - Verify `kwallpaper/` still exists at root
  - Check for any build artifacts or cached files in `flatpak/kwallpaper/` that need cleanup

  **Must NOT do**:
  - Do NOT remove root `kwallpaper/` directory
  - Do NOT remove files from `flatpak/` other than `kwallpaper/`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple directory removal, high certainty
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 3, 4
  - **Blocked By**: None (can start immediately)

  **References**:

  - `flatpak/kwallpaper/` - Directory to remove
  - `kwallpaper/` - Root directory to verify still exists

  **Acceptance Criteria**:

  ```bash
  # Verify root kwallpaper still exists
  ls -la /home/admin/llama-cpp/projects/kwallpaper/kwallpaper/
  # Verify flatpak/kwallapper is removed
  ls -la /home/admin/llama-cpp/projects/kwallpaper/flatpak/kwallpaper/ 2>&1 || echo "Directory not found (expected)"
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: Duplicate directory removed successfully
    Tool: Bash (ls)
    Preconditions: Task 1 completed successfully
    Steps:
      1. Run: ls -la /home/admin/llama-cpp/projects/kwallpaper/kwallpaper/
      2. Run: ls -la /home/admin/llama-cpp/projects/kwallpaper/flatpak/kwallpaper/ 2>&1 || echo "Directory not found"
    Expected Result: kwallpaper/ exists at root, flatpak/kwallpaper/ does not exist
    Failure Indicators: flatpak/kwallpaper/ still exists
    Evidence: .sisyphus/evidence/task-2-dir-removed.txt
  ```

  **Commit**: YES
  - Message: `refactor: remove duplicate kwallpaper from flatpak/`
  - Files: `flatpak/kwallpaper/` (removed)

- [ ] 3. Update flatpak manifest file references

  **What to do**:
  - Read `flatpak/top.spelunk.kwallpaper.json`
  - Find all references to `kwallpaper/` or `wallpaper_cli.py` or `wallpaper_gui.py`
  - Update paths to reference root directory:
    - `kwallpaper/` → should already be correct if referencing from flatpak root, but verify
    - `wallpaper_cli.py` → should be `wallpaper_cli.py` (from root)
    - `wallpaper_gui.py` → should be `wallpaper_gui.py` (from root)
  - Update any source-file references in the manifest

  **Must NOT do**:
  - Do NOT modify the Python files themselves
  - Do NOT modify manifest file structure (only paths)
  - Do NOT remove required files from manifest

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Manifest file, critical for flatpak build, requires precision
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5, 6
  - **Blocked By**: Tasks 1, 2

  **References**:

  - `flatpak/top.spelunk.kwallpaper.json` - Manifest file to update
  - `README.md` - May contain usage examples with file paths

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Verify manifest references updated
  grep -n "wallpaper_cli\|wallpaper_gui\|kwallpaper" /home/admin/llama-cpp/projects/kwallpaper/flatpak/top.spelunk.kwallpaper.json
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: Manifest references correct file paths
    Tool: Bash (grep)
    Preconditions: Task 1 and 2 completed
    Steps:
      1. Run: grep -n "wallpaper_cli\|wallpaper_gui" /home/admin/llama-cpp/projects/kwallpaper/flatpak/top.spelunk.kwallpaper.json
      2. Run: grep -n "kwallpaper" /home/admin/llama-cpp/projects/kwallpaper/flatpak/top.spelunk.kwallapper.json
    Expected Result: References point to root directory files, no references to flatpak/kwallpaper/
    Failure Indicators: References still point to flatpak/kwallpaper/ or missing
    Evidence: .sisyphus/evidence/task-3-manifest-updated.txt
  ```

  **Commit**: YES
  - Message: `refactor: update flatpak manifest to reference root files`
  - Files: `flatpak/top.spelunk.kwallapper.json`

- [ ] 4. Verify build scripts and update if needed

  **What to do**:
  - Check `flatpak/build.sh` for any hardcoded paths to kwallpaper/ or wallpaper scripts
  - Check `flatpak/build-manifest.sh` if exists
  - Update any build scripts if they reference old paths
  - Verify no other build artifacts or scripts reference the removed directory

  **Must NOT do**:
  - Do NOT remove or modify build scripts unless necessary
  - Do NOT modify the manifest file (Task 3 handles that)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Build scripts, critical for flatpak build, requires verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5, 6
  - **Blocked By**: Tasks 1, 2

  **References**:

  - `flatpak/build.sh` - Main build script
  - `flatpak/build-manifest.sh` - Build manifest script (if exists)

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Verify build scripts don't reference old paths
  grep -n "flatpak/kwallpaper\|flatpak/wallpaper_cli\|flatpak/wallpaper_gui" /home/admin/llama-cpp/projects/kwallpaper/flatpak/build*.sh || echo "No old path references found"
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: Build scripts updated or verified
    Tool: Bash (grep)
    Preconditions: Task 1, 2, and 3 completed
    Steps:
      1. Run: grep -n "flatpak/kwallpaper\|flatpak/wallpaper_cli\|flatpak/wallpaper_gui" /home/admin/llama-cpp/projects/kwallpaper/flatpak/build*.sh 2>&1 || echo "No old references"
    Expected Result: No references to flatpak/kwallpaper/ in build scripts
    Failure Indicators: Build scripts still reference removed directory
    Evidence: .sisyphus/evidence/task-4-build-scripts.txt
  ```

  **Commit**: YES
  - Message: `refactor: verify build scripts reference root files`
  - Files: `flatpak/build*.sh` (if updated)

- [ ] 5. Run existing test suite

  **What to do**:
  - Run pytest test suite to ensure no functionality broken by reorganization
  - Verify all tests pass
  - Check for any test files that may reference old paths

  **Must NOT do**:
  - Do NOT add new tests (this is a refactoring task)
  - Do NOT modify test files unless they reference old paths

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Test suite execution, needs to verify no regressions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 3, 4

  **References**:

  - `tests/` - Test directory
  - `pytest` - Test runner

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Run pytest suite
  cd /home/admin/llama-cpp/projects/kwallpaper && python -m pytest tests/ -v
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: All tests pass after reorganization
    Tool: Bash (pytest)
    Preconditions: Tasks 3, 4 completed
    Steps:
      1. Run: python -m pytest tests/ -v
    Expected Result: All tests pass (0 failures)
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-tests-pass.txt
  ```

  **Commit**: YES
  - Message: `test: verify suite passes after reorganization`
  - Files: No test files modified

- [ ] 6. Test flatpak build process

  **What to do**:
  - Run flatpak build command to verify manifest changes work correctly
  - Check for any build errors or missing file references
  - Verify build artifacts are created correctly

  **Must NOT do**:
  - Do NOT create final flatpak bundle (only test the build process)
  - Do NOT modify manifest after this task

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Flatpak build process, critical for packaging
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 3, 4

  **References**:

  - `flatpak/top.spelunk.kwallapper.json` - Updated manifest
  - `flatpak/build.sh` - Build script

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Test flatpak build
  cd /home/admin/llama-cpp/projects/kwallpaper/flatpak && flatpak-builder --stop-at=install build-files top.spelunk.kwallpaper.json
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: Flatpak build succeeds
    Tool: Bash (flatpak-builder)
    Preconditions: Tasks 3, 4 completed
    Steps:
      1. Run: cd flatpak && flatpak-builder --stop-at=install build-files top.spelunk.kwallapper.json
    Expected Result: Build completes successfully (exit code 0)
    Failure Indicators: Build errors or missing file references
    Evidence: .sisyphus/evidence/task-6-flatpak-build.txt
  ```

  **Commit**: YES
  - Message: `build: verify flatpak build succeeds after manifest update`
  - Files: No build artifacts committed

- [ ] 7. Manual verification (CLI/GUI/flatpak)

  **What to do**:
  - Verify `wallpaper_cli.py` can be executed from root
  - Verify `wallpaper_gui.py` can be executed from root
  - Verify flatpak app launches correctly
  - Check for any documentation updates needed

  **Must NOT do**:
  - Do NOT write new documentation (only verify existing is correct)
  - Do NOT modify any code files

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI/GUI verification, requires visual verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocked By**: Tasks 5, 6

  **References**:

  - `wallpaper_cli.py` - CLI entry point
  - `wallpaper_gui.py` - GUI entry point
  - `README.md` - Documentation

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.

  ```bash
  # Verify CLI can be imported/executed
  cd /home/admin/llama-cpp/projects/kwallpaper && python wallpaper_cli.py --help
  # Verify GUI can be imported
  python -c "import wallpaper_gui"
  ```

  **QA Scenarios**:

  ```plaintext
  Scenario: CLI and GUI accessible from root
    Tool: Bash (python)
    Preconditions: Tasks 5, 6 completed
    Steps:
      1. Run: python wallpaper_cli.py --help
      2. Run: python -c "import wallpaper_gui"
    Expected Result: CLI shows help, GUI imports successfully without errors
    Failure Indicators: Import errors or missing file errors
    Evidence: .sisyphus/evidence/task-7-manual-verify.txt
  ```

  **Commit**: YES
  - Message: `refactor: manual verification complete`
  - Files: No files modified

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. Verify all files moved correctly, manifest updated, build scripts verified, tests pass, flatpak builds. Check evidence files exist. Verify no files were removed that shouldn't be.
  Output: `Files Moved [N/N] | Manifest Updated [N/N] | Build Scripts [N/N] | Tests [N/N pass] | Flatpak Build [PASS/FAIL] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **File Structure Verification** — `unspecified-high`
  Use `tree` or `find` to compare expected vs actual structure. Verify:
  - `wallpaper_cli.py` and `wallpaper_gui.py` at root
  - `kwallpaper/` exists at root
  - `flatpak/kwallpaper/` does not exist
  - All other files unchanged
  Output: `Structure Compliance [N/N] | Files Present [N/N] | Files Missing [N/N] | VERDICT`

- [ ] F3. **Flatpak Build Verification** — `deep`
  Run complete flatpak build (or full install phase if time-limited). Verify:
  - Build completes without errors
  - All files are included in flatpak bundle
  - No missing file references
  - App can be launched
  Output: `Build Process [PASS/FAIL] | Bundle Created [YES/NO] | Files Included [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Compare actual changes to plan:
  - Did we move exactly the files specified? (NO extra files)
  - Did we remove exactly the files specified? (NO files left behind)
  - Did we update exactly what was specified? (NO extra changes)
  - No cross-task contamination (Task 3 didn't modify Task 1's files, etc.)
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1-2**: `refactor(scope): move CLI/GUI scripts to root and remove duplicate kwallpaper`
  - Files: `wallpaper_cli.py`, `wallpaper_gui.py`, `flatpak/kwallpaper/`
  - Pre-commit: Verify files exist at root, run pytest

---

## Success Criteria

### Verification Commands
```bash
# File structure verification
tree /home/admin/llama-cpp/projects/kwallpaper -L 2 -I '__pycache__|.git'

# CLI verification
python /home/admin/llama-cpp/projects/kwallpaper/wallpaper_cli.py --help

# GUI verification
python -c "import wallpaper_gui"

# Flatpak build verification
cd /home/admin/llama-cpp/projects/kwallpaper/flatpak && flatpak-builder --stop-at=install build-files top.spelunk.kwallapper.json

# Test suite
python -m pytest tests/ -v
```

### Final Checklist
- [ ] All files moved correctly to root
- [ ] Duplicate `flatpak/kwallpaper/` directory removed
- [ ] Flatpak manifest updated with correct paths
- [ ] Build scripts verified and updated if needed
- [ ] All tests pass
- [ ] Flatpak build completes successfully
- [ ] CLI and GUI accessible from root

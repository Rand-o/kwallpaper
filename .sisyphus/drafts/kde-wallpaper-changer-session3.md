# Draft: KDE Wallpaper Changer - Session 3

## Requirements (confirmed)
- Build Python CLI tool for Fedora 43 KDE that changes wallpaper from .ddw zip files
- Session 1 completed: Test infrastructure + Config management
- Session 2 is INCOMPLETE: Missing zip extraction, image selection, time-of-day filtering, wallpaper change
- Session 3 needed to complete remaining functionality

## Technical Decisions
- **Scope**: Complete missing Session 2 functionality (zip extraction, image selection, time-of-day filtering, wallpaper change)
- **Zip extraction**: Use Python zipfile module, extract to ~/.cache/wallpaper-changer/theme_<timestamp>/
- **Theme parsing**: Read theme.json from extracted directory
- **Time-of-day detection**: Simple system time comparison (hour-based) - NO external dependencies
  - Night: 0-4, Sunrise: 5-6, Day: 7-16, Sunset: 17-18
- **Image selection**: Read current index from config, increment, cycle
- **Wallpaper change**: Use kwriteconfig5 command (easiest for KDE Plasma)
  - Command: `kwriteconfig5 --file plasma-org.kde.plasma.desktop-appletsrc --group Wallpaper --group org.kde.image --key Image /path/to/image.jpg`

## Scope Boundaries
- INCLUDE: Zip extraction, image selection with time-of-day filtering, wallpaper change mechanism, CLI subcommands
- EXCLUDE: Flatpak packaging (explicitly excluded in Session 2)
- EXCLUDE: Retry mechanism
- EXCLUDE: Scheduler
- EXCLUDE: Astral library dependency (will use simple time comparison instead)

## Test Strategy Decision
- **Infrastructure exists**: YES (pytest from Session 1)
- **User wants tests**: YES (tests-after - will add tests after implementation)
- **Framework**: pytest
- **QA approach**: Tests-after with comprehensive manual verification

## Planning Complete (After Momus Review)

**Plan Generated**: kde-wallpaper-changer-session3.md
**Status**: ✅ REJECTED by Momus, ✅ CORRECTED and REGENERATED

### Momus Review Findings

**Critical Issues Fixed:**
1. ✅ Test files exist (not missing) - Both test_zip_extraction.py and test_image_selection.py exist and pass
2. ✅ Config structure corrected - No longer assumes `config["time_of_day_images"]` (this comes from theme.json)
3. ✅ Function signatures corrected - select_next_image() already exists with different signature (theme_path, config_path)
4. ✅ Functions to implement clarified - extract_theme() and select_next_image() already exist, need to add detect_time_of_day() and change_wallpaper()
5. ✅ CLI subcommands clarified - Add extract, change, list subcommands without removing existing arguments

**Scope Adjusted:**
- ✅ Keep existing functions: extract_theme(), select_next_image()
- ✅ Implement missing functions: detect_time_of_day(), change_wallpaper()
- ✅ Modify CLI to add subcommands: extract, change, list
- ✅ Update documentation to match actual codebase state

**Key Decisions Made**:
- **Scope**: Complete missing Session 2 functionality (zip extraction, image selection, time-of-day filtering, wallpaper change)
- **Zip extraction**: Use Python zipfile module, extract to ~/.cache/wallpaper-changer/theme_<timestamp>/
- **Theme parsing**: Read theme.json from extracted directory
- **Time-of-day detection**: Simple system time comparison (hour-based) - NO external dependencies
  - Night: 0-4, Sunrise: 5-6, Day: 7-16, Sunset: 17-18
- **Image selection**: Read current index from config, increment, cycle
- **Wallpaper change**: Use kwriteconfig5 command (easiest for KDE Plasma)
  - Command: `kwriteconfig5 --file plasma-org.kde.plasma.desktop-appletsrc --group Wallpaper --group org.kde.image --key Image /path/to/image.jpg`

**Scope**:
- IN: Zip extraction, image selection with time-of-day filtering, wallpaper change mechanism, CLI subcommands
- OUT: Flatpak packaging, retry mechanism, scheduler, Astral library

**Guardrails Applied**:
- Keep it simple - no external dependencies beyond Python stdlib
- Use kwriteconfig5 instead of DBus for simplicity
- Test-after approach (tests created after implementation)
- Manual verification for wallpaper changes

**Test Strategy**:
- Infrastructure exists: YES (pytest from Session 1)
- User wants tests: YES (tests-after)
- QA approach: Tests-after with comprehensive manual verification

**Decisions Needed**: None - all requirements clear

Plan saved to: `.sisyphus/plans/kde-wallpaper-changer-session3.md`
Draft updated: `.sisyphus/drafts/kde-wallpaper-changer-session3.md`

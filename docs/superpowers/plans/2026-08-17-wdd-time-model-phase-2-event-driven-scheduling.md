# WDD Time Model — Phase 2: Event-Driven Scheduling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use /skill:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scheduler wake only at exact wallpaper-change instants (one-shot `DateTrigger` + coarse safety net) in sun mode, keep legacy polling unchanged, and skip the wallpaper D-Bus call when the selected image is unchanged.

**Architecture:** A new pure-math function `next_change_time()` in `solarsegments.py` computes the next image boundary from Phase 1's `Segments` (night wrap is free: the next day's dawn is the `next_dawn` field of the current day's segments; an injected segments provider covers the degenerate delayed-run case). `SchedulerManager` arms a one-shot `DateTrigger` job (`cycle_task`) at that instant in sun mode plus a 600 s safety-net interval job (`safety_task`), re-arming the one-shot after every run (including lock-skipped runs and the safety ticks). Skip-if-unchanged lives in `cli.run_cycle_command`: the last-applied image path is persisted in config (`theme.last_applied_image`, written only after a successful apply) and the D-Bus call is skipped when the selected image equals it. Legacy mode (`suntime_model: "legacy"`, the default) keeps today's 60 s interval job.

**Tech Stack:** Python 3, APScheduler **3.11.2** (3.x API — `apscheduler.triggers.date.DateTrigger`), pytest, zoneinfo. No new dependencies.

**Roadmap:** `docs/superpowers/roadmaps/2026-08-17-wdd-time-model-roadmap.md`

**Phase:** Phase 2: Event-Driven Scheduling

---

## Context (read before starting)

**Repo state:** branch `main`, clean tree, `python -m pytest tests/ -q` → **156 passed** (verified 2026-08-17). Work from the repo root `/home/admin/llama-cpp/projects/kwallpaper`.

**PREREQUISITE — Phase 1 must be executed first.** The Phase 1 plan (`docs/superpowers/plans/2026-08-17-wdd-time-model-phase-1-sun-position-period-model.md`) creates `kwallpaper/solarsegments.py` and this phase builds on it. **`kwallpaper/solarsegments.py` does not exist yet** — every task in this plan that imports it will fail until Phase 1 is executed. Post-Phase-1 test baseline: **229 passed** (156 pre-existing + 73 new). All code in this plan is written against Phase 1's API exactly as specified there: `Segments` (frozen dataclass: `day`, `dawn`, `golden_hour_end`, `golden_hour`, `dusk`, `next_dawn`, `.complete` property), `solar_segments(day, tz, lat, lon)`, `segments_for_now(now, tz, lat, lon)`, `category_for(now, seg)`, `image_at(now, seg, theme_data) -> (category, image_value)`, `segments_for_config(config_path, now=None)`, `IncompleteSegmentsError(ValueError)`, and the private `_effective_windows(seg, theme_data)` (dedup-aware per-category windows — this plan reuses it).

**Verified facts (do not re-derive; checked against this repo on 2026-08-17):**

1. **APScheduler is 3.11.2** (`requirements.txt` pins `apscheduler>=3.10.0`; `python -c "import apscheduler; print(apscheduler.__version__)"` → `3.11.2`). Use the **3.x API** everywhere: `from apscheduler.triggers.date import DateTrigger`, `DateTrigger(run_date=None, timezone=None)`, `scheduler.add_job(func, trigger=..., id=..., name=..., replace_existing=True, misfire_grace_time=...)`. Do NOT use APScheduler 4.x API.
2. **Misfire grace is the trap.** Verified by probe: a `DateTrigger` job whose run time is 30 s in the past is **skipped** with APScheduler's default `misfire_grace_time` (1 s) — log line `Run time of job ... was missed`. With `misfire_grace_time=86400` the same job **fires immediately**. Therefore the one-shot is always armed with `misfire_grace_time=86400` so a late wake (suspend/resume, clock jump) fires at once instead of being dropped.
3. **One-shot jobs are consumed.** Verified by probe: after a `DateTrigger` job fires (or is skipped as misfire), APScheduler removes it; `get_jobs()` is empty afterwards. The re-arm (`add_job(..., replace_existing=True)`) must therefore happen **after every `_run_cycle_task` invocation — including runs that were skipped by the re-entrant lock** (the triggering one-shot was still consumed).
4. **Self re-arming works.** Verified by probe: a job that re-adds its own one-shot (1 s out) from inside the job body runs repeatedly on `BackgroundScheduler`; a `DateTrigger` job added **before** `scheduler.start()` fires at the right time. `start()` may arm the one-shot before `self.scheduler.start()`.
5. **Scheduler internals today** (`kwallpaper/scheduler.py`, 327 lines): `SchedulerManager` has `self._lock = threading.Lock()` acquired **non-blocking** in `_run_cycle_task` (line 137); the only job ID is `'cycle_task'` (interval, `scheduling.cycle_interval` seconds, default 60); `_run_cycle_task` runs `run_cycle_command` via `_run_cli_quietly` with `MockArgs(theme_path=None, config=self.config_path, time=None, monitor=False)`; `_get_config()` (lines 111–133) returns `{'interval', 'daily_shuffle_enabled', 'run_cycle', 'timezone'}` (plus a hardcoded fallback dict on config error); `start()` reuses an existing `BackgroundScheduler` instance and returns `False` when no task was added; `reload_cycle_interval()` (lines 230–253) re-adds the interval job and is called by the GUI on Settings save; `stop()` = `scheduler.shutdown(wait=wait)`.
6. **Daily shuffle check location:** it is the first thing inside `cli.run_cycle_command` (cli.py:289–296): `if config['scheduling']['daily_shuffle_enabled']:` then `if check_day_passed(load_theme_change_date(), get_current_date(tz)): return run_change_command(args)`. Because every scheduler job (one-shot, safety tick, legacy interval) calls `run_cycle_command`, the shuffle check runs on **every** scheduler run — this plan keeps that exactly (the safety tick goes through the same `_run_cycle_task`).
7. **`run_cycle_command` flow today** (cli.py:274–345): load config → shuffle check → `get_current_wallpaper()` → theme dir = `DEFAULT_THEMES_DIR / Path(current_wallpaper).parent.name` if it exists, else `DEFAULT_THEMES_DIR / config['theme']['last_applied']` if it exists, else error + return 1 → `select_image_for_time_cli(theme_dir, config_path)` (returns a **full path string**) → `change_wallpaper(path)` → prints `Changed wallpaper to <name>` (return 0) or `Failed to change wallpaper to <name>` (return 1).
8. **`run_change_command`** (cli.py:88–268) is an explicit user action and **always applies** — it has two apply sites: the `--time` branch (cli.py:172) and single-change mode (cli.py:243, which persists shuffle state via `commit_shuffle_state` only after success). It is also the target of the daily-shuffle path in `run_cycle_command`, so it must keep applying unconditionally.
9. **`core.apply_theme`** (core.py:277–349) step 5 (core.py:330–345) is the "persist after success" model: only after `set_wallpaper(image_path)` returns True does it reload config, set `theme.last_applied = name`, and `save_config`. This plan adds `theme.last_applied_image = image_path` to the same block.
10. **Config mechanics** (`kwallpaper/config.py`): `load_config` = `validate_config` (raises `ValueError("Config validation failed: ...")`) then `normalize_config`, which migrates legacy keys and **fills every missing key from `_default_config()` via `setdefault`** (config.py:108–110). **New fields that are simply absent from old configs need no migration code** — the default-fill loop supplies them (verified against config.py; same mechanism Phase 1 relies on for `suntime_model`). Validation helpers: `_require_positive_int`, `_require_bool`, `_require_str`, `_require_number` (all skip absent keys; present values must type-check).
11. **GUI caveat (do not fix in this phase):** `wallpaper_gui.py` `SettingsPage._save()` (wallpaper_gui.py:1255–1260) **replaces the whole `scheduling` section** on save, so `scheduling.safety_interval` (like Phase 1's `scheduling.suntime_model`) reverts to its default after a GUI Settings save. The `theme` section is untouched by the GUI, so `theme.last_applied_image` survives. Exposing these settings in the GUI is Phase 3.
12. **Phase 1 test-harness pattern (reuse it):** Phase 1's tests keep the sun math astral-free by monkeypatching `solarsegments.solar_segments` with a fake taking `(day, tz, lat, lon)` and returning synthetic `Segments` objects (see `tests/test_solarsegments.py` `_fake_segments`/`_syn_seg`). The new math tests in this plan use the same pattern. Existing scheduler tests (`tests/test_scheduler.py`) stub apscheduler when absent and patch `scheduler_module.BackgroundScheduler` / `scheduler_module.IntervalTrigger` with `MagicMock` — the new scheduler tests follow the same pattern and additionally patch `scheduler_module.next_change_time_for_config` and `scheduler_module.DateTrigger`.
13. **Concurrency model (verified by reading the code):** `SchedulerManager` is a single instance; APScheduler runs all jobs on its own thread pool. The non-blocking `threading.Lock` in `_run_cycle_task` is the only guard. When a one-shot fires while a previous run is still in progress, the late arrival takes the lock-skip path (DEBUG log) and **still re-arms**; the in-progress run re-arms in its `finally`. Both re-arms use `replace_existing=True`, so the last write wins — no duplicate `cycle_task` job, no crash. The two re-armed times are computed milliseconds apart and are identical in practice.
14. **Phase 1 window/dedup semantics (exact, from the Phase 1 plan):** `_effective_windows(seg, theme_data)` returns `{"day": (day_start, day_end), "night": (dusk, next_dawn)}` plus `"sunrise": (dawn, golden_hour_end)` unless `sunriseImageList == dayImageList` (both non-empty — then `day_start = dawn`), plus `"sunset": (golden_hour, dusk)` unless `sunsetImageList == dayImageList` (then `day_end = dusk`). **The dedup trigger is image-list equality, not a time comparison.** `image_at` computes `idx = int(((now - start) / (end - start) + 1e-9) * n)` clamped to `[0, n-1]` and returns `(category, image_list[idx])`. So for a normal day: sunrise `[dawn, ghe)`, day `[ghe, gh)`, sunset `[gh, dusk)`, night `[dusk, next_dawn)` — the night window ends at the **next day's dawn**, which is why the night wrap needs no next-day computation.

**Locked design decisions (do not revisit; each is load-bearing):**

1. **`next_change_time(now, seg, theme_data, current_image=None, next_segments_provider=None) -> datetime`** in `solarsegments.py`. Returns the first image boundary **strictly after** `now`. Night wrap needs no next-day computation: `seg.next_dawn` (the next day's dawn) is itself a boundary of this day's night window, so it is already in the boundary list. `next_segments_provider` (injected `Callable[[date], Segments]`) is used **only** when `now >= seg.next_dawn` (a delayed run past the night end): walk forward day by day, bounded to 8 days, raising `IncompleteSegmentsError` if the provider is missing or a walked day is incomplete. `current_image` (a theme.json list value, or `None`): when given and its display window still lies ahead of `now`, return that window's end (drift-robust re-arming); when the window has already ended (missed run), fall through to the first future boundary. Rationale: one pure, injectable, fully unit-testable function is the single source of truth for "when does the wallpaper next change."
2. **Job IDs `cycle_task` + `safety_task`.** Sun mode: `cycle_task` is a one-shot `DateTrigger(run_date=next, misfire_grace_time=86400)` and `safety_task` is `IntervalTrigger(seconds=safety_interval)` (default 600) — both run the same `_run_cycle_task` (so the safety tick also runs the daily shuffle check). Legacy mode: unchanged single `cycle_task` interval job; no `safety_task`. Re-arm sequence: `_rearm_next_change()` runs after **every** `_run_cycle_task` (lock-skip path and `finally`) and once from `start()`; it is a no-op when `self.scheduler is None` or the model is not `"sun"`. Rationale: APScheduler consumes one-shot jobs (verified fact 3), so the next wake must be re-armed by the application itself after each run.
3. **Last-applied image state = `theme.last_applied_image`** (config string, default `""`), written **only after a successful apply** in `run_cycle_command`, `run_change_command` (both apply sites), and `core.apply_theme` step 5 — mirroring the shuffle-list "persist after success" rule, so a failed change never advances the state. Skip check in `run_cycle_command` only: selected image `Path.resolve()`-equal to the persisted value → print `No change: already showing <name>` and return 0 with **no D-Bus call**. `run_change_command` never skips (explicit user action / daily shuffle). Rationale: state-based skip (not actual-wallpaper-based) matches the roadmap wording, is D-Bus-free, and is robust to D-Bus path normalization.
4. **Config fields:** `scheduling.safety_interval` (positive int, default 600, `_require_positive_int`) and `theme.last_applied_image` (string, default `""`, `_require_str`), both added to `_default_config()`. Old configs get the defaults via `normalize_config`'s setdefault fill — **no migration code** (verified fact 10). Rationale: minimal surface; `safety_interval` is the only new scheduling knob the roadmap asks for.
5. **Incomplete/polar segments in sun mode → fall back to the legacy-style interval.** `_rearm_next_change` catches **any** failure from `next_change_time_for_config` (`IncompleteSegmentsError`, no resolvable theme, empty category list) and arms `cycle_task` as `IntervalTrigger(seconds=cycle_interval)` with a WARNING log; the re-arm after the next run retries the sun model, so a polar day self-heals automatically. The scheduler never crashes. Rationale: a "skip with warning" design would freeze the wallpaper for the entire polar day; interval fallback keeps the wallpaper moving at worst-case 60 s cadence.

**Out of scope (roadmap Phase 3+ or explicitly deferred):** any GUI changes (Settings UI for `safety_interval`/model toggle, start-message wording — Phase 3), flipping the default to `"sun"` (Phase 4), OS-level system event hooks (Phase 5.6), polar segment collapse (Phase 5.1), manual overrides (Phase 5.2), removing any legacy code, changes to `suntime.py`, and all Phase 5 extras.

**Deviations from the roadmap (accepted, with rationale):**

- The roadmap's Phase 2 verification line says a manual wallpaper change is "reverted at the next safety tick." With the locked state-based skip (decision 3), a manual change is reverted at the **next image boundary** (the one-shot), which is the same instant the state-based skip would have applied the change anyway — and it is what the roadmap's own skip-if-unchanged line describes. The safety tick still reverts it if the boundary was missed (e.g. polar day fallback).
- The GUI start message (`wallpaper_gui.py:597`) hardcodes "60s" for the cycle interval; in sun mode the GUI will show the default wording until Phase 3 updates it. No GUI code is touched in this phase.

**File structure:**

| File | Action | Responsibility |
|------|--------|----------------|
| `kwallpaper/solarsegments.py` | Modify (append ~120 lines) | `next_change_time()` + private `_image_window()` / `_all_boundaries()` |
| `kwallpaper/config.py` | Modify (~6 lines) | `safety_interval` + `last_applied_image` defaults and validation |
| `kwallpaper/cli.py` | Modify (~90 lines) | `resolve_current_theme_dir()`, `_same_image_path()`, `_persist_last_applied_image()`, skip logic in `run_cycle_command`, persistence in `run_change_command` |
| `kwallpaper/core.py` | Modify (~45 lines) | `last_applied_image` in `apply_theme` step 5; `next_change_time_for_config()` seam |
| `kwallpaper/scheduler.py` | Modify (~120 lines) | `DateTrigger` import, `_get_config` fields, sun-mode `start()` wiring, `_rearm_next_change()`, re-arm in `_run_cycle_task`, `reload_cycle_interval()` sun branch |
| `tests/test_next_change_time.py` | Create (~330 lines) | `next_change_time` math + `next_change_time_for_config` seam + `resolve_current_theme_dir` |
| `tests/test_scheduler_eventdriven.py` | Create (~380 lines) | scheduler sun-mode wiring, re-arm sequence, fallback, skip-if-unchanged |
| `tests/test_config_validation.py` | Modify (~46 lines) | validation/normalization of the two new fields |
| `tests/test_scheduler.py` | Modify (1 stub block) | add `apscheduler.triggers.date` to the bare-environment stub (Task 6) |

---

## Task 1: Config fields — `scheduling.safety_interval` and `theme.last_applied_image`

**Files:**
- Modify: `kwallpaper/config.py` (4 small edits)
- Modify: `tests/test_config_validation.py` (append a test class)

- [ ] **Step 1: Write the failing tests**

Edit 1 — add one import. The file already imports `pytest`, `json`, `Path` and aliases `load_config`/`validate_config`/`save_config`/`normalize_config` from `wallpaper_changer` at module level, but `_default_config` is NOT re-exported by `wallpaper_changer` (its `kwallpaper.config` import list ends at `normalize_config`). Add this line after the existing `from kwallpaper import wallpaper_changer` line:

```python
from kwallpaper.config import _default_config
```

Edit 2 — append the test classes:

```python
class TestSafetyIntervalValidation:
    def test_validate_config_safety_interval_valid(self):
        config = _default_config()
        config["scheduling"]["safety_interval"] = 120
        validate_config(config)  # should not raise

    @pytest.mark.parametrize("bad", [0, -5, "600", None, True])
    def test_validate_config_safety_interval_invalid(self, bad):
        config = _default_config()
        config["scheduling"]["safety_interval"] = bad
        with pytest.raises(ValueError, match="safety_interval"):
            validate_config(config)

    def test_normalize_config_fills_missing_safety_interval(self):
        config = _default_config()
        del config["scheduling"]["safety_interval"]
        result = normalize_config(config)
        assert result["scheduling"]["safety_interval"] == 600

    def test_default_config_has_safety_interval_600(self):
        assert _default_config()["scheduling"]["safety_interval"] == 600


class TestLastAppliedImageValidation:
    def test_validate_config_last_applied_image_valid(self):
        config = _default_config()
        config["theme"]["last_applied_image"] = "/home/u/Pictures/wallpaper/sun_07.jpg"
        validate_config(config)  # should not raise

    @pytest.mark.parametrize("bad", [1, None, ["x"]])
    def test_validate_config_last_applied_image_invalid(self, bad):
        config = _default_config()
        config["theme"]["last_applied_image"] = bad
        with pytest.raises(ValueError, match="last_applied_image"):
            validate_config(config)

    def test_normalize_config_fills_missing_last_applied_image(self):
        config = _default_config()
        del config["theme"]["last_applied_image"]
        result = normalize_config(config)
        assert result["theme"]["last_applied_image"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_validation.py -q -k "SafetyInterval or LastAppliedImage"`
Expected: **11 failed, 2 passed** — the two `valid` tests pass trivially before implementation (validate_config ignores unknown keys); the 8 parametrized `invalid` cases fail (no raise) and the 3 default/normalize tests fail with KeyError. After implementation, all 13 must pass.

- [ ] **Step 3: Implement in `kwallpaper/config.py`**

Edit 1 — `_default_config()`, the `"scheduling"` dict (anchor: the block currently reading `"cycle_interval": 60,` / `"run_cycle": True,` / `"daily_shuffle_enabled": True,` around line 68–72). Add the new key after `daily_shuffle_enabled`:

```python
        "scheduling": {
            "cycle_interval": 60,            # seconds between cycle runs
            "run_cycle": True,
            "daily_shuffle_enabled": True,
            "safety_interval": 600,          # sun-mode safety-net tick (seconds)
        },
```

Edit 2 — `_default_config()`, the `"theme"` dict (anchor: `"last_applied": "",` around line 74). Add the new key:

```python
        "theme": {
            "last_applied": "",
            "last_applied_image": "",        # path of last successfully applied image
        },
```

Edit 3 — `validate_config()`, the scheduling block (anchor: the line `_require_positive_int(config, "scheduling.interval")` around line 342). Insert after it:

```python
    _require_positive_int(config, "scheduling.safety_interval")
```

Edit 4 — `validate_config()`, the theme block (anchor: the line `_require_str(config, "theme.last_applied")` around line 353). Insert after it:

```python
    _require_str(config, "theme.last_applied_image")
```

- [ ] **Step 4: Run the new tests plus the whole config test file**

Run: `python -m pytest tests/test_config_validation.py -q`
Expected: **all pass** (the 13 new + every pre-existing config test).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (post-Phase-1 baseline 229 + 13 = 242).

- [ ] **Step 6: Commit**

```bash
git add kwallpaper/config.py tests/test_config_validation.py
git commit -m "Add scheduling.safety_interval and theme.last_applied_image config fields"
```

---


## Task 2: `next_change_time()` math in `solarsegments.py`

**Files:**
- Modify: `kwallpaper/solarsegments.py` (extend the `typing` import; append ~120 lines at the end of the file)
- Create: `tests/test_next_change_time.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_next_change_time.py`:

```python
"""Tests for next_change_time() — the next wallpaper-change instant.

All tests use synthetic Segments (no astral calls).  The day under test is
2026-06-21 in America/Phoenix with boundaries dawn 05:00, golden-hour-end
05:15, golden-hour 06:00, dusk 18:00, and next_dawn 05:00 (2026-06-22).

THEME has 4/5/4/3 images in sunrise/day/sunset/night (all lists distinct,
so no dedup absorption).  The effective windows and their image
boundaries are:

    sunrise [05:00, 05:15):  05:00, 05:03:45, 05:07:30, 05:11:15, 05:15
    day     [05:15, 06:00):  05:15, 05:24, 05:33, 05:42, 05:51, 06:00
    sunset  [06:00, 18:00):  06:00, 09:00, 12:00, 15:00, 18:00
    night   [18:00, 05:00+1d): 18:00, 21:40, 01:20+1d, 05:00+1d
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from kwallpaper import cli as cli_module
from kwallpaper import core
from kwallpaper import solarsegments
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    next_change_time,
)

TZ = ZoneInfo("America/Phoenix")
D = date(2026, 6, 21)


def _syn_seg(day=D, complete=True):
    """Synthetic Segments with clean, hand-computable boundaries."""
    if not complete:
        return Segments(day=day, dawn=None, golden_hour_end=None,
                        golden_hour=None, dusk=None, next_dawn=None)
    return Segments(
        day=day,
        dawn=datetime(day.year, day.month, day.day, 5, 0, tzinfo=TZ),
        golden_hour_end=datetime(day.year, day.month, day.day, 5, 15, tzinfo=TZ),
        golden_hour=datetime(day.year, day.month, day.day, 6, 0, tzinfo=TZ),
        dusk=datetime(day.year, day.month, day.day, 18, 0, tzinfo=TZ),
        next_dawn=datetime(day.year, day.month, day.day, 5, 0, tzinfo=TZ)
        + timedelta(days=1),
    )


def _now(h, m, s=0, day=D):
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=TZ)


THEME = {
    "displayName": "Test",
    "imageFilename": "sun_*.jpg",
    "sunriseImageList": [1, 2, 3, 4],
    "dayImageList": [5, 6, 7, 8, 9],
    "sunsetImageList": [10, 11, 12, 13],
    "nightImageList": [14, 15, 16],
}


class TestNextChangeTimeMidSegment:
    """Within a segment: next change = the next image boundary."""

    def test_mid_sunrise(self):
        assert next_change_time(_now(5, 1), _syn_seg(), THEME) == _now(5, 3, 45)

    def test_exactly_at_boundary_is_strictly_after(self):
        # now == a boundary: that boundary is NOT returned (strictly after).
        assert next_change_time(_now(5, 15), _syn_seg(), THEME) == _now(5, 24)

    def test_last_sunrise_image(self):
        assert next_change_time(_now(5, 12), _syn_seg(), THEME) == _now(5, 15)

    def test_mid_day(self):
        assert next_change_time(_now(5, 30), _syn_seg(), THEME) == _now(5, 33)

    def test_last_day_image(self):
        assert next_change_time(_now(5, 55), _syn_seg(), THEME) == _now(6, 0)

    def test_mid_sunset(self):
        assert next_change_time(_now(9, 30), _syn_seg(), THEME) == _now(12, 0)

    def test_last_sunset_image(self):
        assert next_change_time(_now(17, 0), _syn_seg(), THEME) == _now(18, 0)

    def test_mid_night(self):
        assert next_change_time(_now(20, 0), _syn_seg(), THEME) == _now(21, 40)

    def test_late_night_image(self):
        # 01:00 is on the next calendar day but still inside THIS day's
        # night window [18:00, 05:00+1d).
        assert next_change_time(_now(1, 0, day=D + timedelta(days=1)),
                                _syn_seg(), THEME) == \
            datetime(2026, 6, 22, 1, 20, tzinfo=TZ)

    def test_last_night_image_wraps_to_next_dawn(self):
        # Night wrap: the next change is the next day's dawn — a field of
        # THIS day's Segments. No next-day computation needed.
        assert next_change_time(_now(2, 0, day=D + timedelta(days=1)),
                                _syn_seg(), THEME) == \
            datetime(2026, 6, 22, 5, 0, tzinfo=TZ)

    def test_just_before_next_dawn(self):
        assert next_change_time(_now(4, 59, day=D + timedelta(days=1)),
                                _syn_seg(), THEME) == \
            datetime(2026, 6, 22, 5, 0, tzinfo=TZ)


class TestNextChangeTimeDedup:
    """Dedup rule (Phase 1): absorption is triggered by image-list
    equality, not by time comparison."""

    def test_sunrise_absorbed_merges_sunrise_and_day(self):
        # sunriseImageList == dayImageList -> day window [dawn, gh)
        # = [05:00, 06:00) with 4 images -> 900s each:
        # 05:00, 05:15, 05:30, 05:45, 06:00
        theme = dict(THEME, sunriseImageList=[1, 2, 3, 4],
                     dayImageList=[1, 2, 3, 4])
        assert next_change_time(_now(5, 20), _syn_seg(), theme) == _now(5, 30)
        assert next_change_time(_now(5, 5), _syn_seg(), theme) == _now(5, 15)

    def test_sunset_absorbed_merges_sunset_into_day(self):
        # sunsetImageList == dayImageList -> day window [ghe, dusk)
        # = [05:15, 18:00) with 4 images -> 45900/4 = 11475s each.
        # (The day/sunset lists must stay DIFFERENT from the sunrise
        # list [1, 2, 3, 4], or sunrise would be absorbed too.)
        theme = dict(THEME, dayImageList=[10, 11, 12, 13],
                     sunsetImageList=[10, 11, 12, 13])
        expected = datetime(2026, 6, 21, 5, 15, tzinfo=TZ) + \
            timedelta(seconds=45900 / 4)
        assert next_change_time(_now(6, 0), _syn_seg(), theme) == expected

    def test_both_absorbed_single_day_window(self):
        # both lists equal to day -> day window [dawn, dusk)
        # = [05:00, 18:00) with 5 images -> 46800/5 = 9360s = 2h36m each:
        # 05:00, 07:36, 10:12, 12:48, 15:24, 18:00
        theme = dict(THEME, sunriseImageList=[1, 2, 3, 4, 5],
                     dayImageList=[1, 2, 3, 4, 5],
                     sunsetImageList=[1, 2, 3, 4, 5])
        assert next_change_time(_now(6, 0), _syn_seg(), theme) == _now(7, 36)
        assert next_change_time(_now(16, 0), _syn_seg(), theme) == _now(18, 0)


class TestNextChangeTimeCurrentImage:
    """current_image: the display window of the image that is actually
    up.  If its window still lies ahead of now, its end is the answer
    (drift-robust re-arming); a stale window falls through to the next
    future boundary."""

    def test_current_image_returns_its_window_end(self):
        # image 1 (sunrise[0]) displays [05:00, 05:03:45)
        assert next_change_time(_now(5, 1), _syn_seg(), THEME,
                                current_image=1) == _now(5, 3, 45)

    def test_current_image_later_than_naive_boundary(self):
        # now 05:30: naive answer is 05:33, but if image 7 (day[2],
        # window [05:33, 05:42)) is what's actually up, the next change
        # is 05:42.
        assert next_change_time(_now(5, 30), _syn_seg(), THEME,
                                current_image=7) == _now(5, 42)

    def test_stale_current_image_falls_to_next_boundary(self):
        # image 1's window ended at 05:03:45; now is 05:20 -> the missed
        # change is not returned, the next future boundary is.
        assert next_change_time(_now(5, 20), _syn_seg(), THEME,
                                current_image=1) == _now(5, 24)

    def test_current_image_not_in_theme_raises(self):
        with pytest.raises(ValueError, match="not in any segment list"):
            next_change_time(_now(5, 1), _syn_seg(), THEME, current_image=99)


class TestNextChangeTimeErrors:
    def test_incomplete_segments_raises(self):
        with pytest.raises(IncompleteSegmentsError):
            next_change_time(_now(5, 1), _syn_seg(complete=False), THEME)


class TestNextChangeTimeWalkForward:
    """now >= seg.next_dawn (a delayed run past the night end): walk
    forward day by day via the injected segments provider."""

    def test_now_past_next_dawn_walks_forward_with_provider(self):
        # now 06:00 on 2026-06-22 is past D's next_dawn (05:00 2026-06-22);
        # D has no future boundary, so the provider is asked for 2026-06-22
        # (same synthetic shape) -> first boundary after 06:00 is 09:00.
        asked = []

        def provider(day):
            asked.append(day)
            return _syn_seg(day)

        assert next_change_time(datetime(2026, 6, 22, 6, 0, tzinfo=TZ),
                                _syn_seg(), THEME,
                                next_segments_provider=provider) == \
            datetime(2026, 6, 22, 9, 0, tzinfo=TZ)
        assert asked == [date(2026, 6, 22)]

    def test_now_past_next_dawn_without_provider_raises(self):
        with pytest.raises(IncompleteSegmentsError):
            next_change_time(datetime(2026, 6, 22, 6, 0, tzinfo=TZ),
                             _syn_seg(), THEME)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_next_change_time.py -q`
Expected: **collection error** — `ImportError: cannot import name 'next_change_time' from 'kwallpaper.solarsegments'`.

- [ ] **Step 3: Implement in `kwallpaper/solarsegments.py`**

Edit 1 — extend the typing import (anchor: the line `from typing import Any, Dict, Optional, Tuple` that Phase 1 left at the top of the file):

```python
from typing import Any, Callable, Dict, List, Optional, Tuple
```

Edit 2 — append to the end of the file:

```python
def _image_window(seg: Segments, theme_data: Dict[str, Any],
                  image_value: int) -> Optional[Tuple[datetime, datetime]]:
    """Display window (start, end) of ``image_value``, or None when the
    value is not in any of the day's segment lists (after the dedup
    rule)."""
    for category, (start, end) in _effective_windows(seg, theme_data).items():
        image_list = theme_data.get(f"{category}ImageList", []) or []
        if image_value not in image_list:
            continue
        n = len(image_list)
        duration = (end - start).total_seconds() / n
        i = image_list.index(image_value)
        return (start + timedelta(seconds=i * duration),
                start + timedelta(seconds=(i + 1) * duration))
    return None


def _all_boundaries(seg: Segments, theme_data: Dict[str, Any]) -> List[datetime]:
    """Every image-change instant of the day: each effective window's
    start, its internal image boundaries, and its end.  Sorted
    ascending."""
    bounds: List[datetime] = []
    for category, (start, end) in _effective_windows(seg, theme_data).items():
        image_list = theme_data.get(f"{category}ImageList", []) or []
        if not image_list:
            continue
        n = len(image_list)
        duration = (end - start).total_seconds() / n
        for i in range(n + 1):
            bounds.append(start + timedelta(seconds=i * duration))
    return sorted(bounds)


def next_change_time(now: datetime, seg: Segments,
                     theme_data: Dict[str, Any],
                     current_image: Optional[int] = None,
                     next_segments_provider: Optional[Callable[[date], Segments]] = None
                     ) -> datetime:
    """The next wallpaper-change instant strictly after ``now``.

    The change instants are the image boundaries of the day's effective
    windows (dedup rule applied): within a segment that is the next
    image boundary; in the segment's last image that is the segment end;
    in the night segment's last image that is the next day's dawn
    (``seg.next_dawn`` — the night wrap needs no extra computation, the
    next day's dawn is already a field of this Segments object).

    Args:
        now: the reference instant (aware, or naive in the segment's tz).
        seg: the segments of the day that owns ``now`` (see
            ``segments_for_now``).  Must be complete.
        theme_data: the theme.json dict (four image lists).
        current_image: value of the image currently displayed (one of
            the theme.json list values), or None.  When given and its
            display window still lies ahead of ``now``, that window's
            end is returned — this keeps re-arming correct when ``now``
            has drifted slightly (delayed run, clock skew) but the
            current image is still up.  When the window has already
            ended (a missed run), the first future boundary is returned
            instead.
        next_segments_provider: called with a date to obtain that day's
            Segments.  Only needed when ``now`` is at/after
            ``seg.next_dawn`` (a delayed run past the night end): the
            function walks forward day by day until it finds a future
            boundary.  Pass a closure over ``solar_segments`` in
            production; tests pass fakes.

    Returns:
        The next change instant (timezone-aware).

    Raises:
        IncompleteSegmentsError: ``seg`` (or a walked-forward day) is
            incomplete, or no future boundary can be found.
        ValueError: ``current_image`` is not in any segment list.
    """
    if not seg.complete:
        raise IncompleteSegmentsError(
            f"sun segments incomplete for {seg.day}; cannot compute next change")
    if now.tzinfo is None:
        now = now.replace(tzinfo=seg.dawn.tzinfo)

    if current_image is not None:
        window = _image_window(seg, theme_data, current_image)
        if window is None:
            raise ValueError(
                f"image {current_image} is not in any segment list of {seg.day}")
        if window[1] > now:
            return window[1]
        # The current image's window has already ended (missed run or
        # clock jump): fall through to the next future boundary.

    future = [b for b in _all_boundaries(seg, theme_data) if b > now]
    if future:
        return min(future)

    # ``now`` is at/after this day's night end (a delayed run past
    # next_dawn): walk forward day by day via the injected provider.
    day = seg.day
    for _ in range(8):  # bounded: never walk more than a week
        day = day + timedelta(days=1)
        if next_segments_provider is None:
            raise IncompleteSegmentsError(
                f"next day's segments unavailable for {day} "
                "(pass next_segments_provider)")
        nseg = next_segments_provider(day)
        if not nseg.complete:
            raise IncompleteSegmentsError(f"sun segments incomplete for {day}")
        future = [b for b in _all_boundaries(nseg, theme_data) if b > now]
        if future:
            return min(future)
    raise IncompleteSegmentsError(f"no future boundary found after {now}")
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_next_change_time.py -q`
Expected: **21 passed**.

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (242 + 21 = 263).

- [ ] **Step 6: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_next_change_time.py
git commit -m "Add solarsegments.next_change_time (next wallpaper-change instant)"
```

---

## Task 3: `resolve_current_theme_dir()` in cli.py (extract + reuse)

**Files:**
- Modify: `kwallpaper/cli.py` (add `Optional` import; add helper before the CYCLE COMMAND section; refactor the theme-resolution block in `run_cycle_command`)
- Test: `tests/test_next_change_time.py` (append)

This task is a pure refactor for the scheduler seam: the theme-resolution logic currently inlined in `run_cycle_command` (cli.py:302–327) becomes `resolve_current_theme_dir(config)`, which `core.next_change_time_for_config` (Task 4) also calls, so the scheduler and the cycle command can never disagree about which theme the next run will use.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_next_change_time.py`:

```python
class TestResolveCurrentThemeDir:
    def test_prefers_wallpaper_theme(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        (themes / "Foo").mkdir(parents=True)
        monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
        monkeypatch.setattr(cli_module, "get_current_wallpaper",
                            lambda: str(themes / "Foo" / "sun_01.jpg"))
        config = {"theme": {"last_applied": "Bar"}}
        assert cli_module.resolve_current_theme_dir(config) == themes / "Foo"

    def test_falls_back_to_last_applied(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        (themes / "Bar").mkdir(parents=True)
        monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
        monkeypatch.setattr(cli_module, "get_current_wallpaper", lambda: None)
        config = {"theme": {"last_applied": "Bar"}}
        assert cli_module.resolve_current_theme_dir(config) == themes / "Bar"

    def test_none_when_nothing_resolves(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        themes.mkdir()
        monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
        monkeypatch.setattr(cli_module, "get_current_wallpaper", lambda: None)
        assert cli_module.resolve_current_theme_dir({"theme": {}}) is None
        assert cli_module.resolve_current_theme_dir({}) is None

    def test_ignores_nonexistent_dirs(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        themes.mkdir()
        monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
        monkeypatch.setattr(cli_module, "get_current_wallpaper",
                            lambda: "/nonexistent/Gone/sun_01.jpg")
        config = {"theme": {"last_applied": "AlsoGone"}}
        assert cli_module.resolve_current_theme_dir(config) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_next_change_time.py -q -k ResolveCurrentThemeDir`
Expected: **4 failed** — `AttributeError: module 'kwallpaper.cli' has no attribute 'resolve_current_theme_dir'`.

- [ ] **Step 3: Implement in `kwallpaper/cli.py`**

Edit 1 — imports (anchor: the line `from zoneinfo import ZoneInfo` near the top). Add after it:

```python
from typing import Optional
```

Edit 2 — add `save_config` to the config import (anchor: the block `from kwallpaper.config import (` … `)`):

```python
from kwallpaper.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_THEMES_DIR,
    load_config,
    save_config,
)
```

Edit 3 — add the helper. In the CYCLE COMMAND section, insert immediately after the section header comment (`# CYCLE COMMAND`) and before `def run_cycle_command`:

```python
def resolve_current_theme_dir(config: dict) -> Optional[Path]:
    """Resolve the theme directory the next cycle run will use.

    Prefers the theme of the current D-Bus wallpaper; falls back to the
    last-applied theme from config (covers the case where the wallpaper
    was changed outside kWallpaper, e.g. the user picked a solid colour
    or a random image in Plasma settings).  Returns None when neither
    resolves to an existing theme directory.
    """
    current_wallpaper = get_current_wallpaper()
    if current_wallpaper:
        # Extract theme name from the wallpaper path
        theme_name = Path(current_wallpaper).parent.name
        candidate = DEFAULT_THEMES_DIR / theme_name
        if candidate.exists():
            return candidate
    last_applied = config.get('theme', {}).get('last_applied', '')
    if last_applied:
        candidate = DEFAULT_THEMES_DIR / last_applied
        if candidate.exists():
            return candidate
    return None
```

Edit 4 — refactor `run_cycle_command`. Replace the inlined theme-resolution block (anchor: from `# Get current wallpaper path` through the line `theme_dir = candidate` in the last_applied fallback, i.e. the whole block ending just before `if theme_dir is None:`):

```python
        # Resolve the theme the run will use (current D-Bus wallpaper
        # first, then the last-applied theme from config).
        theme_dir = resolve_current_theme_dir(config)
```

The following `if theme_dir is None:` error block (print + `return 1`) stays exactly as it is.

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_next_change_time.py -q`
Expected: **25 passed** (21 + 4).

- [ ] **Step 5: Run the scheduler regression tests (they exercise the refactored `run_cycle_command`)**

Run: `python -m pytest tests/test_scheduler.py -q`
Expected: **all pass** — in particular `TestCycleDailyShuffle::test_no_theme_returns_error` (wallpaper None + no last_applied still returns 1 via the same error path) and `test_new_day_triggers_shuffle_on_cycle` (shuffle path returns before theme resolution).

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (263 + 4 = 267).

- [ ] **Step 7: Commit**

```bash
git add kwallpaper/cli.py tests/test_next_change_time.py
git commit -m "Extract cli.resolve_current_theme_dir (shared by cycle run and scheduler seam)"
```

---

## Task 4: `next_change_time_for_config()` seam in core.py

**Files:**
- Modify: `kwallpaper/core.py` (append one function at the end of the file)
- Test: `tests/test_next_change_time.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_next_change_time.py`:

```python
class TestNextChangeTimeForConfig:
    """The core seam the scheduler calls: config path -> next change time."""

    def _setup(self, tmp_path, monkeypatch, last_applied="TestTheme",
               complete=True):
        themes = tmp_path / "themes"
        t = themes / "TestTheme"
        t.mkdir(parents=True)
        (t / "theme.json").write_text(json.dumps(THEME))
        for i in range(1, 17):
            (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
        monkeypatch.setattr(cli_module, "get_current_wallpaper", lambda: None)
        monkeypatch.setattr(solarsegments, "solar_segments",
                            lambda day, tz, lat, lon: _syn_seg(day, complete))
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4484, "longitude": -112.074,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": True,
                           "suntime_model": "sun"},
            "theme": {"last_applied": last_applied},
        }))
        return str(cfg)

    def test_returns_next_boundary(self, tmp_path, monkeypatch):
        cfg = self._setup(tmp_path, monkeypatch)
        # now 05:30 -> image_at -> (day, 6); image 6's window is
        # [05:24, 05:33) -> next change 05:33.
        result = core.next_change_time_for_config(
            cfg, now=datetime(2026, 6, 21, 5, 30, tzinfo=TZ))
        assert result == datetime(2026, 6, 21, 5, 33, tzinfo=TZ)

    def test_no_theme_raises_value_error(self, tmp_path, monkeypatch):
        cfg = self._setup(tmp_path, monkeypatch, last_applied="")
        with pytest.raises(ValueError, match="no theme available"):
            core.next_change_time_for_config(
                cfg, now=datetime(2026, 6, 21, 5, 30, tzinfo=TZ))

    def test_incomplete_segments_raise(self, tmp_path, monkeypatch):
        cfg = self._setup(tmp_path, monkeypatch, complete=False)
        with pytest.raises(IncompleteSegmentsError):
            core.next_change_time_for_config(
                cfg, now=datetime(2026, 6, 21, 5, 30, tzinfo=TZ))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_next_change_time.py -q -k NextChangeTimeForConfig`
Expected: **3 failed** — `AttributeError: module 'kwallpaper.core' has no attribute 'next_change_time_for_config'`.

- [ ] **Step 3: Implement in `kwallpaper/core.py`**

Append to the end of the file (after `apply_theme`):

```python
def next_change_time_for_config(config_path: str,
                                now: Optional[datetime] = None) -> datetime:
    """Next wallpaper-change instant for the sun-position model.

    Resolves the theme the next cycle run will use (current D-Bus
    wallpaper first, then config ``theme.last_applied``), computes the
    sun segments for the configured location, and returns the next image
    boundary strictly after ``now`` (default: current time in the
    configured timezone).

    The function-level imports keep core and cli import-decoupled
    (cli already imports core inside functions; keeping the reverse
    direction function-level too avoids any import-order coupling).

    Raises:
        IncompleteSegmentsError: sun segments incomplete (polar
            day/night) — the caller (scheduler) falls back to the
            interval job.
        ValueError: no theme can be resolved, or the theme's image
            lists are inconsistent with the current time (empty
            category list).
    """
    from kwallpaper.cli import resolve_current_theme_dir
    from kwallpaper.selection import load_theme_data
    from kwallpaper.solarsegments import (
        image_at,
        next_change_time,
        segments_for_config,
    )

    config = load_config(config_path)
    tz = ZoneInfo(config.get('location', {}).get('timezone', 'UTC'))
    if now is None:
        now = datetime.now(tz)

    theme_dir = resolve_current_theme_dir(config)
    if theme_dir is None:
        raise ValueError(
            "no theme available (apply a theme first); cannot compute "
            "the next change time")
    theme_data = load_theme_data(theme_dir)
    seg = segments_for_config(config_path, now=now)
    _category, current_image = image_at(now, seg, theme_data)
    return next_change_time(now, seg, theme_data, current_image)
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_next_change_time.py -q`
Expected: **28 passed** (25 + 3).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (267 + 3 = 270).

- [ ] **Step 6: Commit**

```bash
git add kwallpaper/core.py tests/test_next_change_time.py
git commit -m "Add core.next_change_time_for_config (scheduler seam)"
```

---

## Task 5: Skip-if-unchanged + `last_applied_image` persistence

**Files:**
- Modify: `kwallpaper/cli.py` (add two private helpers; skip logic in `run_cycle_command`; persistence at both `run_change_command` apply sites)
- Modify: `kwallpaper/core.py` (`apply_theme` step 5)
- Create: `tests/test_scheduler_eventdriven.py` (file created here; scheduler tests appended in Tasks 6–7)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler_eventdriven.py`:

```python
"""Tests for Phase 2 event-driven scheduling.

Covers: skip-if-unchanged (Task 5), sun-mode start() wiring (Task 6),
and the re-arm sequence / interval fallback (Task 7).

The apscheduler guard mirrors tests/test_scheduler.py so the suite runs
in environments without apscheduler installed (the Flatpak bundles it).
"""
import json
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

if "apscheduler" not in sys.modules:
    try:
        import apscheduler  # noqa: F401
    except ImportError:
        _aps = types.ModuleType("apscheduler")
        _schedulers = types.ModuleType("apscheduler.schedulers")
        _background = types.ModuleType("apscheduler.schedulers.background")
        _triggers = types.ModuleType("apscheduler.triggers")
        _interval = types.ModuleType("apscheduler.triggers.interval")
        _date = types.ModuleType("apscheduler.triggers.date")
        _background.BackgroundScheduler = object
        _interval.IntervalTrigger = object
        _date.DateTrigger = object
        _schedulers.background = _background
        _triggers.interval = _interval
        _triggers.date = _date
        _aps.schedulers = _schedulers
        _aps.triggers = _triggers
        sys.modules.update({
            "apscheduler": _aps,
            "apscheduler.schedulers": _schedulers,
            "apscheduler.schedulers.background": _background,
            "apscheduler.triggers": _triggers,
            "apscheduler.triggers.interval": _interval,
            "apscheduler.triggers.date": _date,
        })

from kwallpaper import cli as cli_module
from kwallpaper import core as core_module
from kwallpaper import scheduler as scheduler_module
from kwallpaper.scheduler import SchedulerManager

TZ = ZoneInfo("America/Phoenix")
FIXED_NEXT = datetime(2026, 8, 18, 12, 0, tzinfo=TZ)


def _make_manager(cfg, running=True):
    mgr = SchedulerManager(config_path=cfg)
    mgr._is_running = running
    return mgr


def _write_cycle_env(tmp_path, monkeypatch):
    """Theme dir + config for run_cycle_command / run_change_command
    tests.  Returns (cfg_path, selected_image_path).  The selected image
    is pinned by patching select_image_for_time_cli, so no real image
    selection or D-Bus call happens."""
    themes = tmp_path / "themes"
    t = themes / "TestTheme"
    t.mkdir(parents=True)
    (t / "theme.json").write_text(json.dumps({
        "displayName": "Test",
        "imageFilename": "sun_*.jpg",
        "sunriseImageList": [1, 2, 3, 4],
        "dayImageList": [5, 6, 7, 8, 9],
        "sunsetImageList": [10, 11, 12, 13],
        "nightImageList": [14, 15, 16],
    }))
    for i in range(1, 17):
        (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
    monkeypatch.setattr(cli_module, "get_current_wallpaper", lambda: None)
    monkeypatch.setattr(cli_module, "check_day_passed", lambda *a: False)
    monkeypatch.setattr(cli_module, "select_image_for_time_cli",
                        lambda theme, cfg: str(t / "sun_07.jpg"))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True},
        "theme": {"last_applied": "TestTheme", "last_applied_image": ""},
    }))
    return str(cfg), str(t / "sun_07.jpg")


class TestSkipIfUnchanged:
    def test_cycle_skips_when_unchanged(self, tmp_path, monkeypatch, capsys):
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        data = json.loads(Path(cfg).read_text())
        data["theme"]["last_applied_image"] = selected
        Path(cfg).write_text(json.dumps(data))
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 0
        assert calls == []  # no D-Bus call at all
        out = capsys.readouterr().out
        assert "No change: already showing sun_07.jpg" in out

    def test_cycle_applies_and_persists(self, tmp_path, monkeypatch, capsys):
        # Empty last_applied_image (fresh install) -> apply + persist.
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 0
        assert calls == [selected]
        out = capsys.readouterr().out
        assert "Changed wallpaper to sun_07.jpg" in out
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == selected

    def test_cycle_failed_change_does_not_persist(self, tmp_path, monkeypatch):
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        monkeypatch.setattr(cli_module, "change_wallpaper", lambda p: False)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 1
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == ""

    def test_change_command_persists_after_success(self, tmp_path, monkeypatch):
        # run_change_command is an explicit user action: it always
        # applies, and it persists the last-applied image on success.
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        t = tmp_path / "themes" / "TestTheme"
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        monkeypatch.setattr(cli_module, "resolve_theme_path", lambda p: p)
        monkeypatch.setattr(cli_module, "detect_time_of_day_sun",
                            lambda *a, **k: "day")
        args = SimpleNamespace(theme_path=str(t), config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_change_command(args) == 0
        assert calls == [selected]
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == selected

    def test_apply_theme_persists_last_applied_image(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        t = themes / "TestTheme"
        t.mkdir(parents=True)
        (t / "theme.json").write_text(json.dumps({
            "displayName": "Test",
            "imageFilename": "sun_*.jpg",
            "sunriseImageList": [1, 2, 3, 4],
            "dayImageList": [5, 6, 7, 8, 9],
            "sunsetImageList": [10, 11, 12, 13],
            "nightImageList": [14, 15, 16],
        }))
        for i in range(1, 17):
            (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": False},
        }))
        monkeypatch.setattr(core_module, "set_wallpaper", lambda p: True)
        monkeypatch.setattr(core_module, "detect_time_of_day_sun",
                            lambda *a, **k: "day")
        monkeypatch.setattr(core_module, "select_image_for_time_cli",
                            lambda theme, cfg_path: str(t / "sun_07.jpg"))
        monkeypatch.setattr(core_module, "load_config",
                            lambda p: json.loads(Path(p).read_text()))
        monkeypatch.setattr(core_module, "save_config",
                            lambda p, c: Path(p).write_text(json.dumps(c)))

        result = core_module.apply_theme(str(t), str(cfg))
        assert result.success
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == str(t / "sun_07.jpg")

    def test_apply_theme_failed_wallpaper_does_not_persist(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        t = themes / "TestTheme"
        t.mkdir(parents=True)
        (t / "theme.json").write_text(json.dumps({
            "displayName": "Test",
            "imageFilename": "sun_*.jpg",
            "sunriseImageList": [1, 2, 3, 4],
            "dayImageList": [5, 6, 7, 8, 9],
            "sunsetImageList": [10, 11, 12, 13],
            "nightImageList": [14, 15, 16],
        }))
        for i in range(1, 17):
            (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": False},
        }))
        monkeypatch.setattr(core_module, "set_wallpaper", lambda p: False)
        monkeypatch.setattr(core_module, "load_config",
                            lambda p: json.loads(Path(p).read_text()))
        monkeypatch.setattr(core_module, "save_config",
                            lambda p, c: Path(p).write_text(json.dumps(c)))

        result = core_module.apply_theme(str(t), str(cfg))
        assert not result.success
        saved = json.loads(Path(cfg).read_text())
        assert saved.get("theme", {}).get("last_applied_image", "") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q`
Expected: **4 failed, 2 passed** — `test_cycle_failed_change_does_not_persist` and `test_apply_theme_failed_wallpaper_does_not_persist` already pass (nothing persists state today, so a failed change leaves the config untouched); the skip test fails because `run_cycle_command` still calls `change_wallpaper` (assert `calls == []` fails); the three success-path persistence tests fail because nothing writes `last_applied_image`. After implementation, all 6 must pass.

- [ ] **Step 3: Implement in `kwallpaper/cli.py`**

Edit 1 — add the two private helpers. Insert them in the CYCLE COMMAND section, after `resolve_current_theme_dir` (added in Task 3) and before `def run_cycle_command`:

```python
def _same_image_path(a: str, b: str) -> bool:
    """True when both non-empty paths point at the same file (resolved)."""
    if not a or not b:
        return False
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def _persist_last_applied_image(config_path: str, image_path: str) -> None:
    """Persist ``theme.last_applied_image`` after a successful wallpaper
    change.

    Mirrors the shuffle-list "persist after success" rule: a failed
    change never updates the state, so the next run retries the same
    image.  Persistence failure is non-fatal (the wallpaper is already
    up); the worst case is one extra D-Bus call on the next run.
    """
    try:
        config = load_config(config_path)
        config.setdefault('theme', {})['last_applied_image'] = image_path
        save_config(config_path, config)
    except Exception as e:
        print(f"Warning: failed to persist last-applied image: {e}",
              file=sys.stderr)
```

Edit 2 — skip logic + persistence in `run_cycle_command`. Replace the block (anchor: `# Select image for current time` through the `return 1` of its else branch):

```python
        # Select image for current time
        image_path = select_image_for_time_cli(str(theme_dir), str(config_path_obj))
        image_path_obj = Path(image_path)

        # Skip-if-unchanged: no D-Bus call when the selected image is the
        # one we last applied (persisted in config; survives restarts).
        # The daily-shuffle path above (run_change_command) always applies.
        last_applied_image = config.get('theme', {}).get('last_applied_image', '')
        if _same_image_path(last_applied_image, str(image_path_obj)):
            print(f"No change: already showing {image_path_obj.name}")
            return 0

        if change_wallpaper(str(image_path_obj)):
            print(f"Changed wallpaper to {image_path_obj.name}")
            _persist_last_applied_image(str(config_path_obj), str(image_path_obj))
            return 0
        else:
            print(f"Failed to change wallpaper to {image_path_obj.name}", file=sys.stderr)
            return 1
```

Edit 3 — `run_change_command`, the `--time` branch (anchor: the block `if change_wallpaper(image_path):` / `print("Wallpaper changed successfully!")` / `return 0` inside `if args.time:`). Insert the persistence call:

```python
                if change_wallpaper(image_path):
                    _persist_last_applied_image(str(config_path_obj), image_path)
                    print("Wallpaper changed successfully!")
                    return 0
```

Edit 4 — `run_change_command`, single-change mode (anchor: `if change_wallpaper(image_path):` followed by the comment `# Persist shuffle state only now that the wallpaper is up, so a`). Insert the persistence call as the first statement of the success branch:

```python
        if change_wallpaper(image_path):
            # Persist the last-applied image now that the wallpaper is up
            # (skip-if-unchanged state; "persist after success" rule).
            _persist_last_applied_image(str(config_path_obj), image_path)
            # Persist shuffle state only now that the wallpaper is up, so a
            # failed change doesn't advance the list (the next run retries
            # the same theme instead of skipping it).
            if not args.theme_path:
```

- [ ] **Step 4: Implement in `kwallpaper/core.py`**

Edit — `apply_theme` step 5 (anchor: `config.setdefault('theme', {})['last_applied'] = name`). Add the new line after it:

```python
        config = load_config(str(cfg_path))
        config.setdefault('theme', {})['last_applied'] = name
        # Last-applied image path (skip-if-unchanged state); persisted
        # only now that the wallpaper is up ("persist after success").
        config.setdefault('theme', {})['last_applied_image'] = image_path
        save_config(str(cfg_path), config)
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q`
Expected: **6 passed**.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (270 + 6 = 276). Note: the pre-existing `tests/test_core_api.py` apply_theme tests must still pass — they assert on `theme.last_applied` and the success/failure of `ApplyResult`, neither of which changes.

- [ ] **Step 7: Commit**

```bash
git add kwallpaper/cli.py kwallpaper/core.py tests/test_scheduler_eventdriven.py
git commit -m "Skip wallpaper D-Bus call when selected image is unchanged; persist last-applied image"
```

---

## Task 6: Scheduler sun-mode `start()` wiring (one-shot + safety net)

**Files:**
- Modify: `kwallpaper/scheduler.py` (imports; `_get_config`; `start()`; new `_rearm_next_change()`)
- Modify: `tests/test_scheduler.py` (complete the apscheduler stub — one block, see Step 3 Edit 5)
- Test: `tests/test_scheduler_eventdriven.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scheduler_eventdriven.py`:

```python
@pytest.fixture
def cfg_sun(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True, "suntime_model": "sun"},
    }))
    return str(p)


@pytest.fixture
def cfg_legacy(tmp_path):
    # No suntime_model key: normalize_config fills "legacy" (the default).
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True},
    }))
    return str(p)


class TestSunModeStart:
    def test_sun_mode_start_arms_one_shot_and_safety(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT) as nct:
            assert mgr.start() is True
            calls = {c.kwargs.get("id"): c
                     for c in bs.return_value.add_job.call_args_list}
            assert set(calls) == {"cycle_task", "safety_task"}
            # safety net: 600s interval (default)
            safety = calls["safety_task"]
            assert safety.kwargs["trigger"] is it.return_value
            assert it.call_args.kwargs.get("seconds") == 600
            # one-shot: DateTrigger at the computed instant, 1-day grace
            one = calls["cycle_task"]
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT
            assert one.kwargs["misfire_grace_time"] == 86400
            assert one.kwargs["replace_existing"] is True
            nct.assert_called_once_with(cfg_sun)
        mgr.scheduler = None
        mgr._is_running = False

    def test_legacy_mode_start_unchanged(self, cfg_legacy):
        mgr = _make_manager(cfg_legacy, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config") as nct:
            assert mgr.start() is True
            calls = {c.kwargs.get("id"): c
                     for c in bs.return_value.add_job.call_args_list}
            assert set(calls) == {"cycle_task"}
            assert it.call_args.kwargs.get("seconds") == 60
            assert calls["cycle_task"].kwargs["trigger"] is it.return_value
            dt.assert_not_called()
            nct.assert_not_called()
        mgr.scheduler = None
        mgr._is_running = False

    def test_sun_mode_custom_safety_interval(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": True,
                           "suntime_model": "sun", "safety_interval": 120},
        }))
        mgr = _make_manager(str(p), running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            assert mgr.start() is True
            assert it.call_args.kwargs.get("seconds") == 120
        mgr.scheduler = None
        mgr._is_running = False

    def test_sun_mode_run_cycle_disabled_no_jobs(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": False,
                           "daily_shuffle_enabled": True,
                           "suntime_model": "sun"},
        }))
        mgr = _make_manager(str(p), running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "IntervalTrigger"):
            assert mgr.start() is False
            bs.return_value.add_job.assert_not_called()
        mgr.scheduler = None
        mgr._is_running = False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q -k SunModeStart`
Expected: **4 failed** — sun mode currently arms the 60 s interval job (no `safety_task`, no `DateTrigger`), and `next_change_time_for_config` is not imported by the scheduler module (`AttributeError` in the patch target).

- [ ] **Step 3: Implement in `kwallpaper/scheduler.py`**

Edit 1 — imports (anchor: the `try:` block importing `BackgroundScheduler`/`IntervalTrigger`):

```python
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    DateTrigger = None
    IntervalTrigger = None

from kwallpaper.config import load_config, DEFAULT_CONFIG_PATH
from kwallpaper.core import next_change_time_for_config
from kwallpaper.cli import run_cycle_command
```

(No circular import: `core` imports `selection`/`suntime`/`config` at module level, none of which import `scheduler`; `cli` is already imported by `scheduler` today.)

Edit 2 — `_get_config()`. Add the two new keys to both returned dicts (anchor: the success dict starting `'interval': scheduling.get('cycle_interval', 60),` and the fallback dict starting `'interval': 60,`):

```python
            return {
                'interval': scheduling.get('cycle_interval', 60),
                'safety_interval': scheduling.get('safety_interval', 600),
                'suntime_model': scheduling.get('suntime_model', 'legacy'),
                'daily_shuffle_enabled': scheduling.get('daily_shuffle_enabled', True),
                'run_cycle': scheduling.get('run_cycle', True),
                'timezone': location.get('timezone', 'UTC'),
            }
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            return {
                'interval': 60,
                'safety_interval': 600,
                'suntime_model': 'legacy',
                'daily_shuffle_enabled': True,
                'run_cycle': True,
                'timezone': 'UTC',
            }
```

Edit 3 — `start()`. Replace the block starting at `interval = config.get('interval', 60)` (inclusive) through the `self.log(f"Added cycle task: ...")` line with the sun/legacy split:

```python
            interval = config.get('interval', 60)
            if config.get('run_cycle', True):
                if config.get('suntime_model') == 'sun':
                    # Event-driven: one-shot at the exact next change
                    # (armed by _rearm_next_change, re-armed after every
                    # run) plus a coarse safety-net interval job for
                    # clock jumps, resume-from-sleep, missed runs and the
                    # daily shuffle check.
                    safety = config.get('safety_interval', 600)
                    self.scheduler.add_job(
                        self._run_cycle_task,
                        trigger=IntervalTrigger(seconds=safety),
                        id='safety_task',
                        name='Cycle Safety Net Task',
                        replace_existing=True,
                    )
                    self._tasks['safety'] = {'interval': safety,
                                             'type': 'interval'}
                    self.log(f"Added safety-net task: runs every {safety} "
                             "seconds (includes daily shuffle check)")
                    self._rearm_next_change()
                else:
                    self.scheduler.add_job(
                        self._run_cycle_task,
                        trigger=IntervalTrigger(seconds=interval),
                        id='cycle_task',
                        name='Cycle Wallpaper Task',
                        replace_existing=True
                    )
                    self._tasks['cycle'] = {'interval': interval,
                                            'type': 'interval'}
                    self.log(f"Added cycle task: runs every {interval} seconds"
                             " (includes daily shuffle check)")
```

Edit 4 — add `_rearm_next_change()`. Insert it after the `_run_cycle_task` method and before the `# ── lifecycle ──` section header:

```python
    def _rearm_next_change(self) -> None:
        """Re-arm the one-shot cycle job at the next image boundary.

        Sun mode only (no-op for the legacy model, whose interval job
        never needs re-arming).  Called after every cycle run — one-shot
        or safety tick — and once from start().

        When the next change time cannot be computed (incomplete sun
        segments — polar day/night — or no resolvable theme), the cycle
        job falls back to the legacy-style interval trigger for the next
        run; the re-arm after that run retries the sun model, so a polar
        day self-heals once the segments are complete again.
        """
        if self.scheduler is None:
            return
        config = self._get_config()
        if config.get('suntime_model') != 'sun':
            return
        try:
            next_dt = next_change_time_for_config(self.config_path)
        except Exception as e:
            self.log(
                f"Could not compute next change time ({e}); "
                f"falling back to {config.get('interval', 60)}s interval "
                "until the next run",
                logging.WARNING)
            self.scheduler.add_job(
                self._run_cycle_task,
                trigger=IntervalTrigger(seconds=config.get('interval', 60)),
                id='cycle_task',
                name='Cycle Wallpaper Task (interval fallback)',
                replace_existing=True,
            )
            self._tasks['cycle'] = {
                'interval': config.get('interval', 60),
                'type': 'interval-fallback'}
            return
        # A generous misfire grace (1 day) makes a late one-shot — e.g.
        # after suspend/resume — fire immediately instead of being
        # dropped (APScheduler's default grace is 1 second).
        self.scheduler.add_job(
            self._run_cycle_task,
            trigger=DateTrigger(run_date=next_dt),
            id='cycle_task',
            name='Cycle Wallpaper Task (next change)',
            replace_existing=True,
            misfire_grace_time=86400,
        )
        self._tasks['cycle'] = {'next_change': next_dt.isoformat(),
                                'type': 'date'}
        self.log(f"Next wallpaper change at {next_dt.isoformat()}")
```

Edit 5 — `tests/test_scheduler.py`: complete the apscheduler stub. This file is imported before `tests/test_scheduler_eventdriven.py` (alphabetical order), so in a bare environment (no apscheduler installed) its stub runs first. It is missing `apscheduler.triggers.date`, which makes `kwallpaper.scheduler`'s `from apscheduler.triggers.date import DateTrigger` fail at import time and leave `APScheduler_AVAILABLE = False` for the whole test session — the `TestSunModeStart` tests above would then fail because `start()` returns False. Replace the whole stub block (anchor: from `if "apscheduler" not in sys.modules:` through its closing `})`) with:

```python
if "apscheduler" not in sys.modules:
    try:
        import apscheduler  # noqa: F401
    except ImportError:
        _aps = types.ModuleType("apscheduler")
        _schedulers = types.ModuleType("apscheduler.schedulers")
        _background = types.ModuleType("apscheduler.schedulers.background")
        _triggers = types.ModuleType("apscheduler.triggers")
        _interval = types.ModuleType("apscheduler.triggers.interval")
        _date = types.ModuleType("apscheduler.triggers.date")
        _background.BackgroundScheduler = object
        _interval.IntervalTrigger = object
        _date.DateTrigger = object
        _schedulers.background = _background
        _triggers.interval = _interval
        _triggers.date = _date
        _aps.schedulers = _schedulers
        _aps.triggers = _triggers
        sys.modules.update({
            "apscheduler": _aps,
            "apscheduler.schedulers": _schedulers,
            "apscheduler.schedulers.background": _background,
            "apscheduler.triggers": _triggers,
            "apscheduler.triggers.interval": _interval,
            "apscheduler.triggers.date": _date,
        })
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q`
Expected: **10 passed** (6 from Task 5 + 4 new).

- [ ] **Step 5: Run the pre-existing scheduler tests (legacy path must be untouched)**

Run: `python -m pytest tests/test_scheduler.py -q`
Expected: **all pass** — `test_only_cycle_task_is_scheduled` (legacy config → single 60 s/1 s interval job, no DateTrigger), `test_cycle_task_skipped_when_disabled`, and the `TestCycleDailyShuffle` class all still green.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (276 + 4 = 280).

- [ ] **Step 7: Commit**

```bash
git add kwallpaper/scheduler.py tests/test_scheduler.py tests/test_scheduler_eventdriven.py
git commit -m "Schedule one-shot DateTrigger + safety-net interval in sun mode"
```

---

## Task 7: Re-arm sequence, interval fallback, and `reload_cycle_interval()`

**Files:**
- Modify: `kwallpaper/scheduler.py` (`_run_cycle_task`; `reload_cycle_interval`)
- Test: `tests/test_scheduler_eventdriven.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scheduler_eventdriven.py`:

```python
class TestRearmSequence:
    def test_run_rearms_one_shot(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT) as nct, \
             patch.object(scheduler_module, "run_cycle_command",
                          return_value=0):
            mgr._run_cycle_task()
            nct.assert_called_once_with(cfg_sun)
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT
            ids = [c.kwargs.get("id")
                   for c in mgr.scheduler.add_job.call_args_list]
            assert ids == ["cycle_task"]

    def test_lock_skipped_run_still_rearms(self, cfg_sun):
        # The triggering one-shot was consumed by APScheduler even though
        # the run was skipped by the lock — the re-arm must still happen.
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        lock = MagicMock()
        lock.acquire.return_value = False
        mgr._lock = lock
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            mgr._run_cycle_task()
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT

    def test_incomplete_segments_interval_fallback(self, cfg_sun):
        from kwallpaper.solarsegments import IncompleteSegmentsError
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        messages = []
        mgr.log_callback = messages.append
        with patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          side_effect=IncompleteSegmentsError("polar day")), \
             patch.object(scheduler_module, "run_cycle_command",
                          return_value=0):
            mgr._run_cycle_task()
            assert it.call_args.kwargs.get("seconds") == 60
            dt.assert_not_called()
            ids = [c.kwargs.get("id")
                   for c in mgr.scheduler.add_job.call_args_list]
            assert ids == ["cycle_task"]
            assert any("falling back" in m for m in messages)

    def test_legacy_run_does_not_rearm(self, cfg_legacy):
        mgr = _make_manager(cfg_legacy, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "run_cycle_command",
                          return_value=0), \
             patch.object(scheduler_module,
                          "next_change_time_for_config") as nct:
            mgr._run_cycle_task()
            nct.assert_not_called()
            mgr.scheduler.add_job.assert_not_called()

    def test_reload_interval_sun_mode_rearms(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            assert mgr.reload_cycle_interval() is True
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT

    def test_safety_tick_runs_shuffle_check(self, cfg_sun):
        # The safety tick runs the same _run_cycle_task, so the daily
        # shuffle check (first thing inside run_cycle_command) still runs
        # on every tick.
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(cli_module, "run_change_command",
                          return_value=0) as change, \
             patch.object(cli_module, "check_day_passed",
                          lambda *a: True), \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            mgr._run_cycle_task()
            change.assert_called_once()
            called_args = change.call_args.args[0]
            assert called_args.config == cfg_sun
            assert called_args.theme_path is None
            assert called_args.time is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q -k RearmSequence`
Expected: **4 failed, 2 passed** — `test_legacy_run_does_not_rearm` and `test_safety_tick_runs_shuffle_check` already pass (legacy mode never re-arms today, and the shuffle check is inside `run_cycle_command` today); the other four fail because `_run_cycle_task` does not re-arm and `reload_cycle_interval` has no sun branch.

- [ ] **Step 3: Implement in `kwallpaper/scheduler.py`**

Edit 1 — `_run_cycle_task()`. Replace the method body (anchor: the whole method from `def _run_cycle_task(self) -> None:` through its `finally:` block):

```python
    def _run_cycle_task(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.log("Cycle task skipped: previous run still in progress",
                     logging.DEBUG)
            # The one-shot (if any) that triggered this run has already
            # been consumed by APScheduler; re-arm it even though the
            # actual cycle run was skipped by the lock.
            self._rearm_next_change()
            return
        try:
            class MockArgs:
                theme_path = None
                config = self.config_path
                time = None
                monitor = False
            result, output = _run_cli_quietly(run_cycle_command, MockArgs())
            if result != 0:
                detail = f": {output}" if output else ""
                self.log(f"Cycle task failed with exit code {result}{detail}",
                         logging.ERROR)
            else:
                self.log("Cycle task completed", logging.DEBUG)
        except Exception as e:
            self.log(f"Cycle task error: {e}", logging.ERROR)
            logger.debug("Cycle task traceback", exc_info=True)
        finally:
            self._lock.release()
            # Sun mode: re-arm the one-shot at the next change instant.
            # Legacy mode: no-op (the interval job keeps running).
            self._rearm_next_change()
```

Edit 2 — `reload_cycle_interval()`. Insert the sun branch at the top of the `try:` block (anchor: `config = self._get_config()` inside the method):

```python
        try:
            config = self._get_config()
            if config.get('suntime_model') == 'sun':
                # Sun mode: re-arm the one-shot from the (possibly
                # changed) config.  An interval fallback armed during
                # incomplete segments picks up the new cycle_interval on
                # the next re-arm.
                self._rearm_next_change()
                return True
            interval = config.get('interval', 60)
```

(The rest of the legacy branch — `if 'cycle' in self._tasks:` re-add — stays exactly as it is.)

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -q`
Expected: **16 passed** (10 + 6).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **all pass, zero failures** (280 + 6 = 286).

- [ ] **Step 6: Commit**

```bash
git add kwallpaper/scheduler.py tests/test_scheduler_eventdriven.py
git commit -m "Re-arm one-shot after every cycle run; sun-mode reload + interval fallback"
```

---

## Task 8: Full-suite verification and manual smoke test

**Files:** none (verification only — no code changes, no commit)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: **286 passed, 0 failed** (229 post-Phase-1 baseline + 57 new: 13 config + 21 math + 4 resolve + 3 seam + 6 skip/persist + 4 start wiring + 6 re-arm/fallback). If the exact new-test count differs from the per-task expectations above, the hard requirement is: **every pre-existing test passes and there are zero failures/errors**.

- [ ] **Step 2: Verify no stray source changes**

Run: `git status --porcelain`
Expected: clean tree (all work committed in Tasks 1–7).

- [ ] **Step 3: Manual smoke test (optional — requires a live Plasma session with D-Bus)**

Only run this if a Plasma session is available; otherwise record it as skipped (the unit tests cover the logic).

1. Set the model to sun: `python3 -c "import json,pathlib; p=pathlib.Path.home()/'.config/kwallpaper/config.json'; c=json.loads(p.read_text()); c.setdefault('scheduling',{})['suntime_model']='sun'; p.write_text(json.dumps(c, indent=2)); print('set sun')"`
2. Start the scheduler and watch the log:
   `python3 -c "from kwallpaper.scheduler import SchedulerManager; import time; m=SchedulerManager(); print(m.start()); time.sleep(15)"`
   Expected log lines: `Added safety-net task: runs every 600 seconds (includes daily shuffle check)` and `Next wallpaper change at <ISO timestamp>` (a future instant matching the next image boundary for the current theme).
3. Confirm the one-shot fires at the computed instant (or force it by temporarily setting the theme's image lists so the next boundary is < 2 minutes away): log shows `Cycle task completed` (or `No change: already showing ...` from the skip path) followed by a new `Next wallpaper change at ...` line — the re-arm.
4. Restore the default: `python3 -c "import json,pathlib; p=pathlib.Path.home()/'.config/kwallpaper/config.json'; c=json.loads(p.read_text()); c['scheduling']['suntime_model']='legacy'; p.write_text(json.dumps(c, indent=2)); print('restored legacy')"`

- [ ] **Step 4: Sanity-check the legacy default is untouched**

Run: `python3 -c "from kwallpaper.config import _default_config; d=_default_config(); assert d['scheduling']['suntime_model'] == 'legacy'; assert d['scheduling']['safety_interval'] == 600; assert d['theme']['last_applied_image'] == ''; print('defaults OK')"`
Expected: `defaults OK`.

---

## Self-review notes (completed before saving)

1. **Spec coverage (roadmap Phase 2):** one-shot at exact change time ✓ (Tasks 2, 6), safety net ✓ (Task 6), re-arm after every run incl. lock-skip ✓ (Task 7), legacy unchanged ✓ (Task 6 tests + pre-existing suite), skip-if-unchanged ✓ (Task 5), `safety_interval` config ✓ (Task 1), polar/incomplete fallback ✓ (Task 7), daily shuffle on every run ✓ (Task 7 test), no new dependencies ✓, GUI untouched ✓.
2. **Placeholder scan:** every step has complete code or an exact command; no TODOs, no "similar to", no "add error handling".
3. **Name/type consistency:** `next_change_time(now, seg, theme_data, current_image=None, next_segments_provider=None)` used identically in solarsegments, core, and tests; `next_change_time_for_config(config_path, now=None)` identical in core and scheduler; job IDs `cycle_task`/`safety_task` consistent; config keys `scheduling.safety_interval`/`theme.last_applied_image` consistent across config.py, cli.py, core.py, scheduler.py, and all tests.
4. **Contradiction check:** "strictly after now" semantics consistent between `next_change_time` docstring, tests (`test_exactly_at_boundary_is_strictly_after`), and the re-arm flow; "persist after success" consistent across all three write sites; decision 5 (interval fallback) implemented exactly as specified in `_rearm_next_change` and pinned by `test_incomplete_segments_interval_fallback`.

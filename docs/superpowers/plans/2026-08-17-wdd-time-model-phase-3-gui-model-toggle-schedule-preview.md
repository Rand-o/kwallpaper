# WDD Time Model — Phase 3: GUI Model Toggle + Schedule Preview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use /skill:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the time model user-selectable (Settings tab: Legacy / Sun-position, persisted, hot-reloaded) and show a 24-hour schedule preview in the Themes tab — a timeline bar with image thumbnails at their exact display times (the WDD `GetAllImageTimes` equivalent) and a current-time marker — with all preview computation off the GUI thread.

**Architecture:** A new self-contained module `kwallpaper/image_schedule.py` computes the exact display time of every image in a theme for a calendar day: `all_image_times()` (WDD `GetAllImageTimes` parity, dedup-aware, explicit night wrap) plus `day_windows()` (the 24-hour bar: today's segments for daytime images + tonight's night, and yesterday's segments for last night's images that run past midnight, all clamped to `[day 00:00, day+1 00:00)`). A new module `kwallpaper/schedule_preview.py` hosts the `SchedulePreviewWidget` (own `QThreadPool`, `QRunnable` workers, version-token cancellation — the existing `wallpaper_gui.py` pattern) so the 1,904-line GUI file only gains ~110 lines of wiring. The Settings tab gains one `QComboBox` row; on Save it persists `scheduling.suntime_model`, hot-reloads the running scheduler (model-switch aware), and refreshes the preview. The default stays `"legacy"` — Phase 4 flips it.

**Tech Stack:** Python 3, PyQt6 (offscreen in tests), astral (via `solarsegments`), pytest, zoneinfo. No new dependencies.

**Roadmap:** `docs/superpowers/roadmaps/2026-08-17-wdd-time-model-roadmap.md`

**Phase:** Phase 3: GUI — Model Toggle + Schedule Preview

---

## Context (read before starting)

**Repo state:** branch `main`, clean tree. Work from the repo root `/home/admin/llama-cpp/projects/kwallpaper`.

**PREREQUISITE — Phases 1 and 2 must be executed first.** The Phase 1 plan (`docs/superpowers/plans/2026-08-17-wdd-time-model-phase-1-sun-position-period-model.md`) creates `kwallpaper/solarsegments.py`; the Phase 2 plan (`docs/superpowers/plans/2026-08-17-wdd-time-model-phase-2-event-driven-scheduling.md`) adds `next_change_time`, the event-driven scheduler, and the config fields this phase exposes in the GUI. **`kwallpaper/solarsegments.py` does not exist yet and `scheduling.suntime_model` / `scheduling.safety_interval` are not in config yet** — Tasks 1–3 import them and will fail until Phases 1–2 are executed. Post-Phase-2 test baseline: **286 passed**. All code in this plan is written against the post-Phase-2 state exactly as those plans specify:

- `solarsegments.py`: `Segments` (frozen dataclass: `day`, `dawn`, `golden_hour_end`, `golden_hour`, `dusk`, `next_dawn`, `.complete` property), `solar_segments(day, tz, lat, lon)`, `segments_for_now(now, tz, lat, lon)`, `image_at(now, seg, theme_data)`, `next_change_time(...)`, `IncompleteSegmentsError(ValueError)`, and the private `_effective_windows(seg, theme_data)` (dedup-aware per-category windows — this plan reuses it; the Phase 2 tests already import it).
- `config.py`: `scheduling.suntime_model` (`"legacy" | "sun"`, default `"legacy"`), `scheduling.safety_interval` (int, default 600), `theme.last_applied_image` (str, default `""`); `load_config` normalizes (fills missing keys from defaults).
- `scheduler.py`: `SchedulerManager` with `cycle_task` (one-shot `DateTrigger` in sun mode, 60 s interval in legacy) + `safety_task` (600 s interval, sun mode only), `_rearm_next_change()`, and `reload_cycle_interval()` whose sun branch calls `_rearm_next_change()` and whose legacy branch re-adds the interval job when `'cycle' in self._tasks`.
- `core.py`: `next_change_time_for_config(config_path, now=None)`.

**Verified facts (do not re-derive; checked against this repo on 2026-08-17):**

1. **`wallpaper_gui.py` is 1,904 lines.** `SettingsPage._build()` (line 1146) builds the Scheduler `QGroupBox` with a `QFormLayout` `sf` — rows: `interval` (QSpinBox), `run_cycle`, `daily_shuffle`, `auto_start_scheduler` (checkboxes). `SettingsPage._load()` (line 1231) reads `c.get("scheduling", {})` into `s`. `SettingsPage._save()` (line 1256) **replaces the whole `scheduling` section** with a 3-key dict (`cycle_interval`, `run_cycle`, `daily_shuffle_enabled`) — so today a GUI save silently drops `suntime_model` and `safety_interval` back to defaults (the Phase 2 plan's verified fact 11, explicitly deferred to this phase). After `save_config`, `_save()` already hot-reloads a running scheduler: `w = self.window(); if hasattr(w, "sched") and w.sched.is_running(): w.sched.scheduler.reload_cycle_interval()`.
2. **`ThemesPage`** (line 783): `self._cfg` holds the config path; `_build()` (line 801) puts the cross-fade `self.preview` and `self.preview_info` in the right column of a `QSplitter`; `load_themes()` populates `self.theme_list` with items carrying the theme dir path in `Qt.ItemDataRole.UserRole`; `_on_select(cur, _prev)` (line 904) is the selection slot; `set_tab_visible(vis)` (line 891) starts/stops the preview slideshow.
3. **Worker pattern (reuse it exactly):** `wallpaper_gui.py` lines 264–375 define `_PixmapLoader` / `_ThumbnailWorker` / `_LoadSignals` / `_OpWorker` / `_LoadToken` — `QRunnable` workers + a GUI-thread `QObject` signal emitter + a monotonic `_LoadToken` version counter; workers re-check the token *after* the blocking work and drop stale results. Pools are `QThreadPool(self)` parented to the owning widget; `_cleanup()` (line 1818) bumps tokens, `pool.clear()`, `pool.waitForDone(1000)` before exit.
4. **`ensure_thumbnail(image_path, thumb_size=1080, token=None)`** (`kwallpaper/themes.py:316`): cached adaptive JPEG thumbnails under the shared cache dir; a cached thumb is reused while it is at least as large as requested — so requesting `thumb_size=96` for a theme the cross-fade preview already decoded costs **no decode** (the 1080p cache is reused and scaled down in the widget).
5. **`selection.load_theme_data(theme_dir: Path) -> dict`** (selection.py:43) loads + normalizes `theme.json`; the underlying `find_theme_json` raises **`FileNotFoundError`** when no `theme.json` exists (not `ValueError`). `selection._match_image_file` (selection.py:60) maps a 1-based image value to a file: `glob(imageFilename)` → numbered fallback `{pattern_stem}_{i}{pattern_ext}` for i in 1..99 → sort by `int(stem.split('_')[-1])` → `files[value-1]` with wraparound `files[(value-1) % len(files)]` when the value exceeds the file count.
6. **`SchedulerPage`** (line 1430) exposes `is_running()` and `.scheduler` (the `SchedulerManager`); `WallpaperChangerWindow` (line 1561) owns `self.themes`, `self.settings`, `self.sched` and `self._cfg`.
7. **GUI test pattern:** `tests/test_gui_ops.py` / `test_gui_autostart.py` use a module-scoped `QApplication` fixture and build `WallpaperChangerWindow(config_path=str(tmp config))`. `tests/test_preview_stress.py` sets `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` at module import (before PyQt6 import) — the new GUI test file does the same so it is robust to test ordering.
8. **`scheduler.reload_cycle_interval()` today** (scheduler.py:230–253, as extended by Phase 2): `if not self._is_running or self.scheduler is None: return False`; then `config = self._get_config()`; sun branch → `self._rearm_next_change(); return True`; legacy branch → `if 'cycle' in self._tasks:` re-add the interval job; `return True`. Phase 2's `_rearm_next_change()` sets `self._tasks['cycle']` in both its date branch and its interval-fallback branch; Phase 2's sun-mode `start()` sets `self._tasks['safety']` and adds `safety_task`.
9. **Two-day schedule math (verified by computation, 2026-06-21, America/Phoenix, synthetic segments dawn 05:00 / ghe 05:15 / gh 06:00 / dusk 18:00 / next_dawn 05:00+1d, theme 4/5/4/3):** `all_image_times` returns 16 entries — sunrise 05:00/05:03:45/05:07:30/05:11:15 (imgs 1–4), day 05:15/05:24/05:33/05:42/05:51 (5–9), sunset 06:00/09:00/12:00/15:00 (10–13), night 18:00/21:40/**01:20+1d** (14–16). `day_windows` for the 24-hour bar returns **17 contiguous windows**: `(00:00, 01:20, 15)` [yesterday's night, clamped], `(01:20, 05:00, 16)`, then today's 15 entries, last `(21:40, 24:00, 15)` [clamped at bar end]. Dedup sunrise==day → 13 windows (day starts at dawn: `(05:00, 05:12, 5)` …). With yesterday's segments missing/incomplete → 15 windows, first `(05:00, 05:03:45, 1)` (gap before dawn).
10. **README anchors:** Configuration Fields table (README.md:133–151), GUI Interface → Themes Tab (lines 200–205) and Settings Tab (lines 207–211), `screenshots/` referenced from the README.

**Locked design decisions (do not revisit; each is load-bearing):**

1. **`all_image_times(day, seg, theme_data) -> list[(start, image_value)]`** in `kwallpaper/image_schedule.py` — WDD `GetAllImageTimes` parity: one (start, value) pair per image, sorted ascending, dedup-aware via `solarsegments._effective_windows`; night images that start after midnight keep their real next-day datetimes (explicit wrap, not folded). Raises `IncompleteSegmentsError` (incomplete `seg`) and `ValueError` (`day != seg.day`). This is the roadmap's signature, kept exactly.
2. **`day_windows(day, tz, seg_today, seg_prev, theme_data) -> list[(start, end, image)]`** — the 24-hour bar needs **two days of segments**: today's (sunrise/day/sunset + tonight's night) and yesterday's (last night's images that run past midnight). Keeps windows intersecting `[day 00:00, day+1 00:00)`, clamps them to the bar, sorts by start. For a normal day the result is contiguous (00:00–24:00, no gaps). `seg_prev` is best-effort (None/incomplete → gap before dawn). Raises `IncompleteSegmentsError` when `seg_today` is incomplete. Verified numbers in fact 9.
3. **`schedule_for_config(config_path, theme_dir, now=None) -> ThemeSchedule`** — the GUI seam: loads config (model/tz/lat/lon), computes `solar_segments(day)` + `solar_segments(day-1)`, loads `theme.json` via `selection.load_theme_data`, builds clamped windows with resolved image paths. Legacy model → `ThemeSchedule(model="legacy", entries=(), segments=None)`. Raises `IncompleteSegmentsError` (today's segments incomplete) / `FileNotFoundError` (no theme.json).
4. **`image_path_for_value(theme_dir, theme_data, value) -> str`** — mirrors `selection._match_image_file`'s positional mapping exactly (same glob, same numbered fallback, same numeric sort, same 1-based position with wraparound) so the preview always agrees with the scheduler — but **never raises** (returns `""` → placeholder box in the UI).
5. **The preview is sun-model only.** In legacy mode the widget shows a notice ("Schedule preview is available in the Sun-position model (Settings → Time model)"). Rationale: the legacy model's per-selector quirk math (fixed offsets, hardcoded 16-image position offsets) is deliberately not re-implemented (roadmap key decision 2: legacy paths stay intact; Phase 1 decision 5: new model self-contained); the roadmap's Phase 3 scope lists only the sun-model `all_image_times`. Toggling the model updates the preview (notice ↔ timeline), which satisfies the roadmap verification line "toggling the model updates the preview".
6. **The preview widget lives in its own module** (`kwallpaper/schedule_preview.py`, ~330 lines) — the roadmap's explicit risk mitigation for the 1,904-line `wallpaper_gui.py`. `wallpaper_gui.py` gains only ~110 lines: one settings row + persistence + hot-reload + Themes-tab wiring + cleanup drain.
7. **Worker pattern matches existing code** (verified fact 3): widget-owned `QThreadPool` (max 4 threads) + `QRunnable` workers + GUI-thread `QObject` signal emitter + monotonic version token. Two workers: `ScheduleComputeWorker` (config + segments + windows + paths) and `_ThumbsWorker` (all entry thumbnails in one sequential pass at `thumb_size=96`, reusing the shared `ensure_thumbnail` cache). Signals carry the token version captured at worker start; slots drop superseded results.
8. **Marker + date change:** a 60 s `QTimer` moves the current-time marker and, when the calendar date in the configured timezone changes (midnight / DST day), triggers a full recompute. x-positions use the **actual wall-clock span** of the day (`(day_end - day_start).total_seconds()`, i.e. 23/25 h on DST days), so the bar stays correct across DST transitions (roadmap risk: "compute for 'today' and refresh on date change").
9. **Settings row:** `QComboBox` "Time model" with items `["Legacy (fixed offsets)", "Sun-position (WDD)"]`, persisted to `scheduling.suntime_model` on Save. `_save()` switches from whole-section replacement to **read-modify-write** of the `scheduling` section so `safety_interval` (and future keys) survive GUI saves — this closes the Phase 2 caveat (verified fact 11).
10. **Hot reload on Save:** after `save_config`, if the scheduler is running: `w.sched.scheduler.reload_cycle_interval()` (existing call — now model-switch aware) and `w.themes.refresh_schedule_preview()`. `reload_cycle_interval` gains model-switch cleanup: sun branch adds `safety_task` when absent (legacy→sun switch); legacy branch removes it when present (sun→legacy switch). Without this, a sun→legacy switch would leave the 600 s safety job ticking forever in legacy mode.
11. **Default stays `"legacy"`** — Phase 4 flips it.

**Out of scope (roadmap Phase 4–5 or explicitly deferred):** flipping the default to `"sun"` (Phase 4), import validation (Phase 4), full README model documentation + changelog (Phase 4 — this phase adds only the screenshot, one config-table row, and the two tab bullets), a legacy-mode timeline (would require re-implementing legacy quirk math), per-display themes / appearance mode / manual time override (Phase 5), OS event hooks (Phase 5.6), removing any legacy code.

**Deviations from the roadmap (accepted, with rationale):**

- The roadmap's "key files" line says `wallpaper_gui.py (toggle + preview widget, ~300–500 lines added)`. The roadmap's own risk note says "keep the preview in its own widget class (ideally its own module) to avoid further bloat" — this plan takes the stronger option: the widget is its own module (`kwallpaper/schedule_preview.py`), and `wallpaper_gui.py` gains ~110 lines of wiring instead.
- The roadmap's `all_image_times(date, segments, theme_data)` return is `list[(time, image_index)]` (starts only, WDD parity). The bar needs *windows* (starts **and** ends, for clamping and tooltips), so this plan adds a second function `day_windows(...)` that returns `(start, end, image)` triples; `all_image_times` keeps the roadmap's exact contract and is implemented on top of the same private `_image_windows` helper.
- The roadmap says "preview matches `next_change_time`" — verified in the manual check (Task 8) by comparing the first timeline window after the marker against `next_change_time_for_config()`. Both consume the same `_effective_windows` math, so they agree by construction.

**File structure:**

| File | Action | Responsibility |
|------|--------|----------------|
| `kwallpaper/image_schedule.py` | **Create** (~210 lines) | `ScheduleEntry`, `ThemeSchedule`, `all_image_times`, `day_windows`, `image_path_for_value`, `schedule_for_config` |
| `kwallpaper/schedule_preview.py` | **Create** (~330 lines) | `SchedulePreviewWidget`, `ScheduleComputeWorker`, `_ThumbsWorker`, `_ScheduleSignals`, `_BarArea`, `_PreviewToken` |
| `wallpaper_gui.py` | Modify (~110 lines) | Settings: time-model row + persistence + hot-reload; Themes: embed preview + wiring; `_cleanup` drain |
| `kwallpaper/scheduler.py` | Modify (~25 lines) | `reload_cycle_interval` model-switch cleanup (add/remove `safety_task`) |
| `tests/test_image_schedule.py` | **Create** (~330 lines) | `all_image_times` (4 segments, dedup, wrap), `day_windows` (clamp, gap, contiguity), `image_path_for_value`, `schedule_for_config` |
| `tests/test_scheduler_eventdriven.py` | Modify (~70 lines) | `TestModelSwitchReload` (2 tests) |
| `tests/test_gui_schedule.py` | **Create** (~300 lines) | GUI smoke: toggle load/save/persist, hot-reload trigger, preview widget states, end-to-end toggle |
| `README.md` | Modify (~10 lines) | Config-table row, Settings/Themes tab bullets, screenshot reference |
| `screenshots/3schedule.png` | Create | Schedule preview screenshot (manual step) |

---

## Task 1: `kwallpaper/image_schedule.py` — the schedule math

**Files:**
- Create: `kwallpaper/image_schedule.py`

- [ ] **Step 1: Create the module**

Create `kwallpaper/image_schedule.py`:

```python
#!/usr/bin/env python3
"""
kWallpaper image schedule (WDD GetAllImageTimes equivalent).

Computes the exact display time of every image in a theme for a calendar
day — the data behind the GUI's 24-hour schedule preview (Phase 3).

Self-contained: imports only solarsegments (the WDD model), selection
(theme.json loading), and config.  No imports from the legacy suntime
quirk paths.

Model (WDD parity): each effective segment window (dedup rule applied,
see solarsegments._effective_windows) is divided equally among its
images — the image at list index i displays during
[start + i*duration/n, start + (i+1)*duration/n).

A calendar day's 24-hour bar needs two days of segments: today's
(sunrise/day/sunset plus tonight's night) and yesterday's (last
night's images that run past midnight).  day_windows() combines and
clamps both to [day 00:00, day+1 00:00).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    _effective_windows,
    solar_segments,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleEntry:
    """One image's (clamped) display window on the day bar.

    start/end are timezone-aware and both lie within
    [day 00:00, day+1 00:00).  path is the resolved image file ("" when
    the file cannot be found — the preview shows a placeholder box).
    """
    start: datetime
    end: datetime
    image: int
    path: str = ""


@dataclass(frozen=True)
class ThemeSchedule:
    """A theme's full-day image schedule for the GUI preview.

    date is the calendar day the bar represents (the day of ``now`` in
    the configured timezone).  entries are clamped to that day.  In
    legacy mode entries is empty and segments is None (the widget shows
    a notice instead of a timeline).
    """
    date: date
    tz: ZoneInfo
    model: str                 # "legacy" | "sun"
    now: datetime              # aware; instant the schedule was computed
    segments: Optional[Segments]
    entries: Tuple[ScheduleEntry, ...] = ()


def _image_windows(seg: Segments,
                   theme_data: Dict[str, Any]) -> List[Tuple[datetime, datetime, int]]:
    """(start, end, image) for every image of the day, unclamped.

    The dedup rule is applied via solarsegments._effective_windows.
    Windows with no images or zero/negative duration contribute nothing.
    """
    out: List[Tuple[datetime, datetime, int]] = []
    for category, (start, end) in _effective_windows(seg, theme_data).items():
        image_list = theme_data.get(f"{category}ImageList", []) or []
        n = len(image_list)
        if n == 0 or end <= start:
            continue
        duration = (end - start).total_seconds() / n
        for i, value in enumerate(image_list):
            out.append((start + timedelta(seconds=i * duration),
                        start + timedelta(seconds=(i + 1) * duration),
                        value))
    return out


def all_image_times(day: date, seg: Segments,
                    theme_data: Dict[str, Any]) -> List[Tuple[datetime, int]]:
    """Exact display start time of every image in the theme (WDD parity).

    One (start, image_value) pair per image, sorted ascending.  Night
    images that start after midnight keep their real (next-day)
    datetimes — the night wrap is explicit, not folded into the
    previous day.

    Args:
        day: the schedule date; must equal ``seg.day``.
        seg: complete sun segments for ``day``.
        theme_data: the theme.json dict (four image lists).

    Returns:
        Sorted list of (start, image_value) tuples.

    Raises:
        IncompleteSegmentsError: ``seg`` is incomplete (polar day/night).
        ValueError: ``day != seg.day``.
    """
    if not seg.complete:
        raise IncompleteSegmentsError(
            f"sun segments incomplete for {seg.day}; no schedule available")
    if day != seg.day:
        raise ValueError(f"date {day} does not match segments day {seg.day}")
    return sorted((start, value) for start, _end, value in
                  _image_windows(seg, theme_data))


def day_windows(day: date, tz: ZoneInfo, seg_today: Segments,
                seg_prev: Optional[Segments],
                theme_data: Dict[str, Any]) -> List[Tuple[datetime, datetime, int]]:
    """Complete display windows for calendar day ``day`` (the 24-hour bar).

    Combines today's segments (sunrise/day/sunset plus tonight's night)
    with yesterday's segments (last night's images that run past
    midnight), keeps the windows intersecting [day 00:00, day+1 00:00),
    clamps them to the bar, and sorts by start.  For a normal (non-polar)
    day the result is contiguous: it covers 00:00–24:00 with no gaps.

    Args:
        day: the calendar day the bar represents.
        tz: the configured timezone (bar boundaries are wall-clock).
        seg_today: complete segments for ``day``.
        seg_prev: segments for ``day - 1`` (best-effort; skipped when
            None or incomplete — the pre-dawn region then shows a gap).

    Returns:
        Sorted (start, end, image) tuples, all within the bar.

    Raises:
        IncompleteSegmentsError: ``seg_today`` is incomplete.
    """
    if not seg_today.complete:
        raise IncompleteSegmentsError(
            f"sun segments incomplete for {seg_today.day}; no schedule available")
    day_start = datetime(day.year, day.month, day.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    out: List[Tuple[datetime, datetime, int]] = []
    for seg in (seg_today, seg_prev):
        if seg is None or not seg.complete:
            continue
        for start, end, value in _image_windows(seg, theme_data):
            if end <= day_start or start >= day_end:
                continue
            out.append((max(start, day_start), min(end, day_end), value))
    out.sort(key=lambda w: (w[0], w[2]))
    return out


def image_path_for_value(theme_dir: Path, theme_data: Dict[str, Any],
                         value: int) -> str:
    """Resolve a theme.json image value to a file path ("" if unresolvable).

    Mirrors selection._match_image_file's positional mapping (same glob
    pattern, same numbered fallback, same numeric sort, same 1-based
    position with wraparound) so the preview always agrees with the
    scheduler — but never raises: the preview degrades to a placeholder
    box instead of failing.
    """
    try:
        pattern = theme_data.get("imageFilename", "*.jpg") or "*.jpg"
        files = list(Path(theme_dir).glob(pattern))
        if not files:
            base = Path(pattern).stem or "theme"
            ext = Path(pattern).suffix or ".jpg"
            files = [Path(theme_dir) / f"{base}_{i}{ext}"
                     for i in range(1, 100)]
            files = [f for f in files if f.exists()]
        if not files:
            return ""
        def _idx(f: Path) -> int:
            try:
                return int(f.stem.split('_')[-1])
            except Exception:
                return 0
        files.sort(key=_idx)
        return str(files[(int(value) - 1) % len(files)])
    except Exception:
        return ""


def schedule_for_config(config_path: str, theme_dir: Path,
                        now: Optional[datetime] = None) -> ThemeSchedule:
    """Compute a theme's full-day schedule from the config (GUI seam).

    Loads the config (model, timezone, lat/lon), computes today's and
    yesterday's sun segments, loads the theme's theme.json, and builds
    the clamped day windows with resolved image paths.

    In legacy mode (scheduling.suntime_model == "legacy") the schedule
    has no entries — the preview shows a notice instead of a timeline
    (the legacy model's per-selector quirk math is deliberately not
    re-implemented here; see the Phase 3 plan, locked decision 5).

    Args:
        config_path: path to config.json.
        theme_dir: theme folder (must contain theme.json).
        now: override "now" (aware); defaults to the current time in
            the configured timezone.

    Returns:
        ThemeSchedule (entries already clamped to the bar).

    Raises:
        IncompleteSegmentsError: today's sun segments incomplete (polar).
        FileNotFoundError: theme folder has no theme.json.
    """
    from kwallpaper.config import load_config
    from kwallpaper.selection import load_theme_data

    config = load_config(config_path)
    loc = config.get("location", {})
    tz = ZoneInfo(loc.get("timezone", "UTC"))
    lat = float(loc.get("latitude", 0.0))
    lon = float(loc.get("longitude", 0.0))
    model = config.get("scheduling", {}).get("suntime_model", "legacy")

    if now is None:
        now = datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    day = now.date()
    if model != "sun":
        return ThemeSchedule(date=day, tz=tz, model="legacy", now=now,
                             segments=None, entries=())

    # Raises IncompleteSegmentsError when today's segments are incomplete.
    seg_today = solar_segments(day, tz, lat, lon)
    try:
        seg_prev = solar_segments(day - timedelta(days=1), tz, lat, lon)
    except IncompleteSegmentsError:
        seg_prev = None  # best-effort: the pre-dawn region shows a gap
    theme_data = load_theme_data(Path(theme_dir))  # raises FileNotFoundError
    wins = day_windows(day, tz, seg_today, seg_prev, theme_data)
    entries = tuple(
        ScheduleEntry(start=s, end=e, image=v,
                      path=image_path_for_value(Path(theme_dir), theme_data, v))
        for s, e, v in wins)
    return ThemeSchedule(date=day, tz=tz, model="sun", now=now,
                         segments=seg_today, entries=entries)
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python3 -c "import kwallpaper.image_schedule as m; print('import OK:', [n for n in dir(m) if not n.startswith('_')])"`
Expected: `import OK: [...]` listing `ScheduleEntry`, `ThemeSchedule`, `all_image_times`, `day_windows`, `image_path_for_value`, `schedule_for_config` (fails with `ModuleNotFoundError: kwallpaper.solarsegments` until Phase 1 is executed — that is the expected pre-Phase-1 state).

- [ ] **Step 3: Commit**

```bash
git add kwallpaper/image_schedule.py
git commit -m "Add image_schedule module (WDD GetAllImageTimes equivalent + 24h day windows)"
```

---

## Task 2: `tests/test_image_schedule.py` — schedule math tests

**Files:**
- Create: `tests/test_image_schedule.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_image_schedule.py`:

```python
"""Tests for the Phase 3 image schedule (WDD GetAllImageTimes equivalent).

Synthetic segments (astral-free, same pattern as the Phase 1/2 tests):
dawn 05:00, golden_hour_end 05:15, golden_hour 06:00, dusk 18:00,
next_dawn 05:00 (+1 day), in America/Phoenix (no DST).

Reference theme: 4 sunrise / 5 day / 4 sunset / 3 night images.
Expected values below were verified by hand computation
(see the Phase 3 plan, verified fact 9).
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from kwallpaper.image_schedule import (
    all_image_times,
    day_windows,
    image_path_for_value,
    schedule_for_config,
)
from kwallpaper.solarsegments import IncompleteSegmentsError, Segments

TZ = ZoneInfo("America/Phoenix")
D = date(2026, 6, 21)

THEME = {
    "sunriseImageList": [1, 2, 3, 4],
    "dayImageList": [5, 6, 7, 8, 9],
    "sunsetImageList": [10, 11, 12, 13],
    "nightImageList": [14, 15, 16],
}


def dt(h, m=0, s=0, day=D):
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=TZ)


def _seg(day, complete=True):
    if not complete:
        return Segments(day=day, dawn=None, golden_hour_end=None,
                        golden_hour=None, dusk=None, next_dawn=None)
    return Segments(
        day=day,
        dawn=dt(5, 0, day=day),
        golden_hour_end=dt(5, 15, day=day),
        golden_hour=dt(6, 0, day=day),
        dusk=dt(18, 0, day=day),
        next_dawn=dt(5, 0, day=day + timedelta(days=1)),
    )


class TestAllImageTimes:
    def test_all_sixteen_entries_exact(self):
        times = all_image_times(D, _seg(D), THEME)
        assert times == [
            (dt(5, 0), 1), (dt(5, 3, 45), 2), (dt(5, 7, 30), 3),
            (dt(5, 11, 15), 4),
            (dt(5, 15), 5), (dt(5, 24), 6), (dt(5, 33), 7),
            (dt(5, 42), 8), (dt(5, 51), 9),
            (dt(6, 0), 10), (dt(9, 0), 11), (dt(12, 0), 12),
            (dt(15, 0), 13),
            (dt(18, 0), 14), (dt(21, 40), 15),
            (dt(1, 20, day=D + timedelta(days=1)), 16),
        ]

    def test_night_wrap_crosses_midnight(self):
        times = all_image_times(D, _seg(D), THEME)
        assert times[-1][0].date() == D + timedelta(days=1)

    def test_dedup_sunrise_absorbed(self):
        theme = dict(THEME, sunriseImageList=[5, 6, 7, 8, 9])
        times = all_image_times(D, _seg(D), theme)
        assert len(times) == 12
        assert times[0] == (dt(5, 0), 5)          # day now starts at dawn
        assert (dt(5, 12), 6) in times
        assert (dt(5, 48), 9) in times
        assert (dt(5, 15), 5) not in times        # no entry at ghe anymore

    def test_dedup_sunset_absorbed(self):
        theme = dict(THEME, sunsetImageList=[5, 6, 7, 8, 9])
        times = all_image_times(D, _seg(D), theme)
        assert len(times) == 12
        assert (dt(7, 48), 6) in times
        assert (dt(15, 27), 9) in times
        assert (dt(6, 0), 10) not in times        # no entry at gh anymore

    def test_dedup_both_absorbed(self):
        theme = dict(THEME, sunriseImageList=[5, 6, 7, 8, 9],
                     sunsetImageList=[5, 6, 7, 8, 9])
        times = all_image_times(D, _seg(D), theme)
        assert [t[1] for t in times] == [5, 6, 7, 8, 9, 14, 15, 16]
        assert times[0] == (dt(5, 0), 5)
        assert times[4] == (dt(15, 24), 9)

    def test_empty_category_contributes_nothing(self):
        theme = dict(THEME, sunriseImageList=[])
        times = all_image_times(D, _seg(D), theme)
        assert len(times) == 12
        assert times[0] == (dt(5, 15), 5)         # day starts at ghe
        assert 1 not in [t[1] for t in times]

    def test_incomplete_segments_raise(self):
        with pytest.raises(IncompleteSegmentsError):
            all_image_times(D, _seg(D, complete=False), THEME)

    def test_date_mismatch_raises(self):
        with pytest.raises(ValueError):
            all_image_times(D + timedelta(days=1), _seg(D), THEME)


class TestDayWindows:
    def test_full_day_is_contiguous(self):
        wins = day_windows(D, TZ, _seg(D), _seg(D - timedelta(days=1)), THEME)
        assert len(wins) == 17
        assert wins[0] == (dt(0, 0), dt(1, 20), 15)        # clamped at 00:00
        assert wins[1] == (dt(1, 20), dt(5, 0), 16)
        assert wins[2] == (dt(5, 0), dt(5, 3, 45), 1)
        assert wins[-1] == (dt(21, 40),
                            dt(0, 0, day=D + timedelta(days=1)), 15)
        for a, b in zip(wins, wins[1:]):
            assert a[1] == b[0]                            # no gaps

    def test_pre_dawn_uses_yesterday_night(self):
        # The bar for a day shows last night's images clamped at 00:00
        # (segments of the previous day).
        wins = day_windows(D, TZ, _seg(D), _seg(D - timedelta(days=1)), THEME)
        assert (dt(0, 0), dt(1, 20), 15) in wins
        assert (dt(1, 20), dt(5, 0), 16) in wins

    def test_prev_none_leaves_gap(self):
        wins = day_windows(D, TZ, _seg(D), None, THEME)
        assert len(wins) == 15
        assert wins[0] == (dt(5, 0), dt(5, 3, 45), 1)      # gap 00:00–05:00

    def test_prev_incomplete_leaves_gap(self):
        wins = day_windows(D, TZ, _seg(D),
                           _seg(D - timedelta(days=1), complete=False), THEME)
        assert len(wins) == 15
        assert wins[0] == (dt(5, 0), dt(5, 3, 45), 1)

    def test_today_incomplete_raises(self):
        with pytest.raises(IncompleteSegmentsError):
            day_windows(D, TZ, _seg(D, complete=False),
                        _seg(D - timedelta(days=1)), THEME)

    def test_dedup_day_windows(self):
        theme = dict(THEME, sunriseImageList=[5, 6, 7, 8, 9])
        wins = day_windows(D, TZ, _seg(D), _seg(D - timedelta(days=1)), theme)
        assert len(wins) == 13
        assert wins[2] == (dt(5, 0), dt(5, 12), 5)
        assert wins[-1] == (dt(21, 40),
                            dt(0, 0, day=D + timedelta(days=1)), 15)


class TestImagePathForValue:
    def test_resolves_value_to_file(self, tmp_path):
        for i in range(1, 17):
            (tmp_path / f"sun_{i:02d}.jpg").write_bytes(b"x")
        theme = {"imageFilename": "sun_*.jpg"}
        assert image_path_for_value(tmp_path, theme, 7) == \
            str(tmp_path / "sun_07.jpg")

    def test_wraps_when_value_exceeds_files(self, tmp_path):
        for i in range(1, 16):
            (tmp_path / f"sun_{i:02d}.jpg").write_bytes(b"x")
        theme = {"imageFilename": "sun_*.jpg"}
        assert image_path_for_value(tmp_path, theme, 16) == \
            str(tmp_path / "sun_01.jpg")

    def test_missing_files_return_empty(self, tmp_path):
        assert image_path_for_value(
            tmp_path, {"imageFilename": "sun_*.jpg"}, 1) == ""

    def test_missing_theme_dir_returns_empty(self, tmp_path):
        assert image_path_for_value(
            tmp_path / "nope", {"imageFilename": "sun_*.jpg"}, 1) == ""


class TestScheduleForConfig:
    def _write_config(self, tmp_path, model="sun"):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "location": {"timezone": "America/Phoenix",
                         "latitude": 33.4484, "longitude": -112.074},
            "scheduling": {"suntime_model": model},
        }))
        return str(cfg)

    def _make_theme(self, tmp_path):
        tdir = tmp_path / "TestTheme"
        tdir.mkdir()
        (tdir / "theme.json").write_text(json.dumps(THEME))
        for i in range(1, 17):
            (tdir / f"sun_{i:02d}.jpg").write_bytes(b"x")
        return tdir

    def test_sun_model_full_schedule(self, tmp_path, monkeypatch):
        import kwallpaper.image_schedule as im
        monkeypatch.setattr(im, "solar_segments",
                            lambda day, tz, lat, lon: _seg(day))
        cfg = self._write_config(tmp_path)
        tdir = self._make_theme(tmp_path)
        sch = schedule_for_config(cfg, tdir, now=dt(12, 0))
        assert sch.date == D
        assert sch.model == "sun"
        assert sch.segments is not None and sch.segments.complete
        assert len(sch.entries) == 17
        assert sch.entries[0].start == dt(0, 0)
        assert sch.entries[0].end == dt(1, 20)
        assert sch.entries[0].image == 15
        assert sch.entries[0].path == str(tdir / "sun_15.jpg")
        assert sch.entries[-1].start == dt(21, 40)
        assert sch.entries[-1].end == dt(0, 0, day=D + timedelta(days=1))

    def test_legacy_model_no_entries(self, tmp_path):
        cfg = self._write_config(tmp_path, model="legacy")
        tdir = self._make_theme(tmp_path)
        sch = schedule_for_config(cfg, tdir, now=dt(12, 0))
        assert sch.model == "legacy"
        assert sch.entries == ()
        assert sch.segments is None

    def test_incomplete_today_raises(self, tmp_path, monkeypatch):
        import kwallpaper.image_schedule as im
        monkeypatch.setattr(im, "solar_segments",
                            lambda day, tz, lat, lon:
                            _seg(day, complete=False))
        cfg = self._write_config(tmp_path)
        tdir = self._make_theme(tmp_path)
        with pytest.raises(IncompleteSegmentsError):
            schedule_for_config(cfg, tdir, now=dt(12, 0))

    def test_missing_theme_json_raises(self, tmp_path, monkeypatch):
        import kwallpaper.image_schedule as im
        monkeypatch.setattr(im, "solar_segments",
                            lambda day, tz, lat, lon: _seg(day))
        cfg = self._write_config(tmp_path)
        empty = tmp_path / "Empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            schedule_for_config(cfg, empty, now=dt(12, 0))
```

- [ ] **Step 2: Run the new tests**

Run: `python -m pytest tests/test_image_schedule.py -v`
Expected: **22 passed** (8 `TestAllImageTimes` + 6 `TestDayWindows` + 4 `TestImagePathForValue` + 4 `TestScheduleForConfig`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_image_schedule.py
git commit -m "Add image_schedule tests (16-entry parity, dedup, wrap, 24h clamp, seam)"
```

---

## Task 3: `kwallpaper/schedule_preview.py` — the preview widget

**Files:**
- Create: `kwallpaper/schedule_preview.py`

- [ ] **Step 1: Create the module (part A — workers)**

Create `kwallpaper/schedule_preview.py` with the following content (part A; part B is appended in Step 2):

```python
#!/usr/bin/env python3
"""
kWallpaper schedule preview widget (Phase 3).

A 24-hour timeline bar showing which image of the selected theme
displays when (sun-position model), with a current-time marker.

All computation runs off the GUI thread via QThreadPool workers,
matching the main window's existing worker pattern (QRunnable worker +
QObject signal emitter + version-token cancellation).  Thumbnails reuse
the shared adaptive thumbnail cache (ensure_thumbnail) at a small size,
so a theme already previewed in the cross-fade widget costs no decode.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import (
    QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from kwallpaper.image_schedule import ThemeSchedule, schedule_for_config
from kwallpaper.themes import ensure_thumbnail

logger = logging.getLogger(__name__)

BAR_HEIGHT = 56
THUMB_PX = 26
TICK_MS = 60_000      # marker refresh + date-change check
POOL_THREADS = 4

# Segment band colours (translucent — visible on light and dark themes).
BAND_COLORS = {
    "night":   QColor(0x55, 0x66, 0x88, 0x66),
    "sunrise": QColor(0xF5, 0xC2, 0x6B, 0x66),
    "day":     QColor(0x7E, 0xC8, 0xF0, 0x55),
    "sunset":  QColor(0xF0, 0x95, 0x5A, 0x66),
}


class _PreviewToken:
    """Monotonic generation counter used to cancel superseded loads
    (same pattern as wallpaper_gui._LoadToken)."""

    __slots__ = ("version",)

    def __init__(self):
        self.version = 0


class _ScheduleSignals(QObject):
    """Signal bridge for the schedule workers (lives on the GUI thread).

    Every signal carries the token version captured when the worker
    started, so the slot can drop superseded results.
    """
    schedule_ready = pyqtSignal(object, int)   # (ThemeSchedule, version)
    schedule_failed = pyqtSignal(str, int)     # (message, version)
    thumbs_ready = pyqtSignal(dict, int)       # ({src: thumb}, version)


class ScheduleComputeWorker(QRunnable):
    """Compute a theme's day schedule off the GUI thread."""

    def __init__(self, config_path: str, theme_dir: str,
                 sig: _ScheduleSignals, token: _PreviewToken):
        super().__init__()
        self.setAutoDelete(True)
        self._config_path = config_path
        self._theme_dir = theme_dir
        self._sig = sig
        self._token = token

    def run(self):
        v = self._token.version
        try:
            sch = schedule_for_config(self._config_path,
                                      Path(self._theme_dir))
        except Exception as e:
            logger.warning(f"Schedule compute failed: {e}")
            if self._token.version == v:
                self._sig.schedule_failed.emit(str(e), v)
            return
        if self._token.version == v:
            self._sig.schedule_ready.emit(sch, v)


class _ThumbsWorker(QRunnable):
    """Generate small thumbnails for all schedule entries off the GUI
    thread (one worker, sequential — at most 16 small decodes, and the
    shared cache makes them cheap when the cross-fade preview already
    ran)."""

    def __init__(self, paths: List[str], sig: _ScheduleSignals,
                 token: _PreviewToken):
        super().__init__()
        self.setAutoDelete(True)
        self._paths = list(dict.fromkeys(paths))  # dedup, keep order
        self._sig = sig
        self._token = token

    def run(self):
        v = self._token.version
        out = {}
        for p in self._paths:
            if self._token.version != v:
                return  # superseded; drop the whole batch
            try:
                out[p] = ensure_thumbnail(p, thumb_size=96,
                                          token=self._token)
            except Exception as e:
                logger.debug(f"Thumbnail failed for {p}: {e}")
        if self._token.version == v:
            self._sig.thumbs_ready.emit(out, v)
```
- [ ] **Step 2: Create the module (part B — bar area + widget, append to the file)**

Append to `kwallpaper/schedule_preview.py`:

```python


class _BarArea(QWidget):
    """The painted 24-hour timeline (bands, ticks, thumbnails, marker)."""

    def __init__(self, owner: "SchedulePreviewWidget"):
        super().__init__(owner)
        self._owner = owner

    def _x_for(self, dt: datetime) -> int:
        """Pixel x for an aware datetime within the schedule day.

        Uses the actual wall-clock span of the day (23/25 h on DST
        days), so positions stay correct across DST transitions.
        """
        sch = self._owner._schedule
        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        span = (day_start + timedelta(days=1) - day_start).total_seconds()
        return int((dt - day_start).total_seconds() / span * self.width())

    def mouseMoveEvent(self, event):
        self._owner._show_entry_at(event.position().x())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._owner._reset_title()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))

        state = self._owner._state
        if state in ("empty", "loading", "legacy", "error"):
            msg = {
                "empty": "Select a theme to see its schedule",
                "loading": "Computing schedule…",
                "legacy": ("Schedule preview is available in the "
                           "Sun-position model (Settings → Time model)"),
                "error": "Schedule unavailable",
            }[state]
            p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
            f = p.font()
            f.setPointSize(max(f.pointSize(), 8))
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            p.end()
            return

        sch = self._owner._schedule
        if sch is None:
            p.end()
            return

        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        day_end = day_start + timedelta(days=1)

        # Segment bands (from today's segments)
        seg = sch.segments
        if seg is not None and seg.complete:
            def band(s, e, color):
                x1, x2 = self._x_for(s), self._x_for(e)
                if x2 > x1:
                    p.fillRect(x1, 0, x2 - x1, h, color)
            band(day_start, seg.dawn, BAND_COLORS["night"])
            band(seg.dawn, seg.golden_hour_end, BAND_COLORS["sunrise"])
            band(seg.golden_hour_end, seg.golden_hour, BAND_COLORS["day"])
            band(seg.golden_hour, seg.dusk, BAND_COLORS["sunset"])
            band(seg.dusk, day_end, BAND_COLORS["night"])

        # Hour ticks + labels (every 3 h)
        p.setPen(QPen(pal.color(QPalette.ColorRole.Mid), 1))
        f = QFont()
        f.setPointSize(max(f.pointSize(), 7))
        p.setFont(f)
        for hour in range(0, 25, 3):
            x = self._x_for(day_start + timedelta(hours=hour))
            p.drawLine(x, h - 8, x, h)
            if hour < 24:
                p.drawText(x + 2, h - 2, f"{hour:02d}")

        # Thumbnails at each entry's start
        for e in sch.entries:
            x = self._x_for(e.start)
            y = (h - THUMB_PX) // 2
            pm = self._owner._pixmaps.get(e.path)
            if pm is not None:
                scaled = pm.scaled(
                    THUMB_PX, THUMB_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(x - THUMB_PX // 2, y, scaled)
            else:
                p.setPen(QPen(pal.color(QPalette.ColorRole.Mid), 1))
                p.drawRect(x - THUMB_PX // 2, y, THUMB_PX, THUMB_PX)

        # Current-time marker
        if self._owner._now is not None:
            mx = self._x_for(self._owner._now)
            p.setPen(QPen(pal.color(QPalette.ColorRole.Highlight), 2))
            p.drawLine(mx, 0, mx, h)
            p.setPen(pal.color(QPalette.ColorRole.Highlight))
            label = self._owner._now.strftime("%H:%M")
            lx = mx + 3 if mx < w - 44 else mx - 41
            p.drawText(lx, 12, label)
        p.end()


class SchedulePreviewWidget(QWidget):
    """24-hour schedule timeline for the selected theme (sun model).

    States: "empty" (no theme), "loading", "ready" (timeline),
    "legacy" (model notice), "error".  ``refresh()`` recomputes in a
    worker; ``refresh_now()`` only moves the marker.  A 60 s timer
    refreshes the marker and recomputes when the calendar date changes
    in the configured timezone.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(POOL_THREADS)
        self._sig = _ScheduleSignals(self)
        self._sig.schedule_ready.connect(self._on_schedule_ready)
        self._sig.schedule_failed.connect(self._on_schedule_failed)
        self._sig.thumbs_ready.connect(self._on_thumbs_ready)

        self._token = _PreviewToken()
        self._state = "empty"
        self._schedule: Optional[ThemeSchedule] = None
        self._now: Optional[datetime] = None
        self._pixmaps: Dict[str, QPixmap] = {}
        self._config_path: Optional[str] = None
        self._theme_dir: Optional[str] = None

        self.setFixedHeight(BAR_HEIGHT + 22)
        self.setMinimumWidth(400)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._title = QLabel("Schedule preview")
        f = self._title.font()
        f.setPointSize(max(f.pointSize(), 9))
        self._title.setFont(f)
        lay.addWidget(self._title)
        self._bar = _BarArea(self)
        self._bar.setFixedHeight(BAR_HEIGHT)
        lay.addWidget(self._bar)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    # ── public API ────────────────────────────────────────────────────────
    def refresh(self, config_path: str, theme_dir: str):
        """(Re)compute the schedule for this theme in a worker."""
        self._config_path = config_path
        self._theme_dir = theme_dir
        self._bump()
        self._state = "loading"
        self._schedule = None
        self._now = None
        self._pixmaps.clear()
        self._reset_title()
        self._bar.update()
        self._pool.start(ScheduleComputeWorker(
            config_path, theme_dir, self._sig, self._token))

    def refresh_now(self):
        """Move the current-time marker (no recompute)."""
        if self._schedule is None:
            return
        self._now = datetime.now(self._schedule.tz)
        self._bar.update()

    def clear(self):
        """No theme selected."""
        self._bump()
        self._state = "empty"
        self._schedule = None
        self._now = None
        self._pixmaps.clear()
        self._config_path = None
        self._theme_dir = None
        self._bar.update()

    # ── internals ─────────────────────────────────────────────────────────
    def _bump(self):
        self._token.version += 1

    def _on_tick(self):
        sch = self._schedule
        if sch is None:
            return
        now = datetime.now(sch.tz)
        if now.date() != sch.date:
            # Calendar date changed (midnight, or DST day): recompute.
            if self._config_path and self._theme_dir:
                self.refresh(self._config_path, self._theme_dir)
            return
        self._now = now
        self._bar.update()

    def _on_schedule_ready(self, sch: ThemeSchedule, v: int):
        if v != self._token.version:
            return  # superseded
        self._schedule = sch
        self._now = sch.now
        if sch.model != "sun":
            self._state = "legacy"
            self._bar.update()
            return
        self._state = "ready"
        paths = [e.path for e in sch.entries if e.path]
        if paths:
            self._pool.start(_ThumbsWorker(paths, self._sig, self._token))
        self._bar.update()

    def _on_schedule_failed(self, msg: str, v: int):
        if v != self._token.version:
            return
        self._state = "error"
        self._schedule = None
        self._bar.setToolTip(msg)
        self._bar.update()

    def _on_thumbs_ready(self, thumbs: dict, v: int):
        if v != self._token.version:
            return
        for src, thumb in thumbs.items():
            pm = QPixmap(thumb)
            if not pm.isNull():
                self._pixmaps[src] = pm
        self._bar.update()

    def _show_entry_at(self, x: int):
        """Hover feedback: show the entry under the cursor in the title."""
        sch = self._schedule
        if sch is None or self._state != "ready":
            return
        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        span = (day_start + timedelta(days=1) - day_start).total_seconds()
        t = day_start + timedelta(
            seconds=x / max(self._bar.width(), 1) * span)
        for e in sch.entries:
            if e.start <= t < e.end:
                self._title.setText(
                    f"{e.start:%H:%M}–{e.end:%H:%M}  ·  image {e.image}"
                    + (f"  ·  {Path(e.path).name}" if e.path else ""))
                return

    def _reset_title(self):
        if self._state == "ready":
            self._title.setText("Schedule preview")

    def _cleanup(self):
        """Drain the pool (called from the main window on exit)."""
        self._bump()
        self._timer.stop()
        self._pool.clear()
        self._pool.waitForDone(1000)
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `python3 -c "import kwallpaper.schedule_preview as m; print('import OK:', [n for n in dir(m) if not n.startswith('_') and n[0].isupper()])"`
Expected: `import OK: ['QColor', 'QFont', 'QPainter', 'QPalette', 'QPen', 'QPixmap', 'ScheduleComputeWorker', 'SchedulePreviewWidget', 'ThemeSchedule', ...]` (the exact list may include re-exported Qt names; the two `Schedule*` classes must be present).

- [ ] **Step 4: Commit**

```bash
git add kwallpaper/schedule_preview.py
git commit -m "Add SchedulePreviewWidget (24h timeline, QThreadPool workers, marker)"
```

---

## Task 4: Settings tab — time-model row, persistence, hot reload

**Files:**
- Modify: `wallpaper_gui.py` (4 edits, all in `SettingsPage`)

- [ ] **Step 1: Add the time-model row to the Scheduler group**

In `wallpaper_gui.py`, `SettingsPage._build()` (line 1146), find:

```python
        self.auto_start_scheduler = QCheckBox("Start scheduler on app launch")
        sf.addRow(self.auto_start_scheduler)
```

Append after it (inside the same `with QGroupBox("Scheduler") as grp:` block, before `lay.addWidget(grp)`):

```python
        self.time_model = QComboBox()
        self.time_model.addItems(["Legacy (fixed offsets)",
                                  "Sun-position (WDD)"])
        self.time_model.setToolTip(
            "Time model for wallpaper selection: legacy uses fixed "
            "offsets from sunrise/sunset; sun-position uses the WDD "
            "sun-position segments (dawn → +6° → +6° → dusk). "
            "Applies on Save.")
        sf.addRow("Time model:", self.time_model)
```

- [ ] **Step 2: Load the model in `SettingsPage._load()`**

In `SettingsPage._load()` (line 1231), find:

```python
            self.auto_start_scheduler.setChecked(
                s.get("auto_start_scheduler", False))
```

Append after it:

```python
            model = s.get("suntime_model", "legacy")
            self.time_model.blockSignals(True)
            self.time_model.setCurrentIndex(
                {"legacy": 0, "sun": 1}.get(model, 0))
            self.time_model.blockSignals(False)
```

- [ ] **Step 3: Persist the model with a read-modify-write of the scheduling section**

In `SettingsPage._save()` (line 1256), find:

```python
            c = load_config(self._cfg)
            c["scheduling"] = {
                "cycle_interval":        self.interval.value(),
                "run_cycle":             self.run_cycle.isChecked(),
                "daily_shuffle_enabled": self.daily_shuffle.isChecked(),
            }
```

Replace with:

```python
            c = load_config(self._cfg)
            # Read-modify-write the scheduling section (NOT replace):
            # safety_interval and future keys must survive a GUI save.
            s = c.get("scheduling", {})
            s["cycle_interval"] = self.interval.value()
            s["run_cycle"] = self.run_cycle.isChecked()
            s["daily_shuffle_enabled"] = self.daily_shuffle.isChecked()
            s["suntime_model"] = {0: "legacy", 1: "sun"}.get(
                self.time_model.currentIndex(), "legacy")
            c["scheduling"] = s
```

- [ ] **Step 4: Refresh the schedule preview on Save**

In `SettingsPage._save()`, find the existing hot-reload block:

```python
            # If the scheduler is running, apply the new cycle interval
            # immediately instead of waiting for a restart.
            w = self.window()
            if hasattr(w, "sched") and w.sched.is_running():
                w.sched.scheduler.reload_cycle_interval()
```

Replace with:

```python
            # If the scheduler is running, apply the new settings
            # immediately (cycle interval and/or time model) instead of
            # waiting for a restart.
            w = self.window()
            if hasattr(w, "sched") and w.sched.is_running():
                w.sched.scheduler.reload_cycle_interval()
            # The time model affects the Themes-tab schedule preview.
            if hasattr(w, "themes") and hasattr(w.themes, "refresh_schedule_preview"):
                w.themes.refresh_schedule_preview()
```

- [ ] **Step 5: Verify the GUI still imports and the row exists**

Run:
```bash
QT_QPA_PLATFORM=offscreen python3 -c "
import wallpaper_gui
w = wallpaper_gui.WallpaperChangerWindow.__new__(wallpaper_gui.WallpaperChangerWindow)
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication.instance() or QApplication(sys.argv)
sp = wallpaper_gui.SettingsPage('/tmp/nonexistent-config-for-import-check.json')
assert sp.time_model.count() == 2
assert sp.time_model.itemText(0) == 'Legacy (fixed offsets)'
assert sp.time_model.itemText(1) == 'Sun-position (WDD)'
print('settings row OK')
"
```
Expected: `settings row OK`. (The window is never shown; the page loads a missing config into defaults — `load_config` handles a missing file.)

- [ ] **Step 6: Commit**

```bash
git add wallpaper_gui.py
git commit -m "Add time model selector to Settings (persist + hot reload + preview refresh)"
```

---

## Task 5: Scheduler model-switch cleanup in `reload_cycle_interval`

**Files:**
- Modify: `kwallpaper/scheduler.py` (`reload_cycle_interval`, ~25 lines)
- Modify: `tests/test_scheduler_eventdriven.py` (append `TestModelSwitchReload`)

**Why:** Phase 2's `reload_cycle_interval` sun branch only calls `_rearm_next_change()` (which sets `self._tasks['cycle']`) — it never adds the `safety_task`. So a live legacy→sun switch (possible once the GUI exposes the model) leaves the safety net missing, and a live sun→legacy switch leaves the 600 s `safety_task` ticking forever in legacy mode. This task makes both switches fully correct.

- [ ] **Step 1: Edit `reload_cycle_interval`**

In `kwallpaper/scheduler.py`, find the Phase 2 version of the method (see the Phase 2 plan, Task 4 Step 2):

```python
    def reload_cycle_interval(self) -> bool:
        """Hot-reload the cycle interval from config without restart.
        ...docstring...
        """
        if not self._is_running or self.scheduler is None:
            return False

        config = self._get_config()
        if config.get("scheduling", {}).get("suntime_model", "legacy") == "sun":
            # Sun model: re-arm the one-shot next-change task.
            self._rearm_next_change()
            return True

        # Legacy model: re-add the interval job with the new interval.
        if 'cycle' in self._tasks:
            try:
                self.scheduler.remove_job(self._tasks['cycle'])
            except Exception:
                pass
            try:
                self._tasks['cycle'] = self.scheduler.add_job(
                    self._run_cycle,
                    'interval',
                    seconds=int(config.get('scheduling', {}).get('cycle_interval', 60)),
                    id='cycle',
                    replace_existing=True
                )
            except Exception as e:
                logger.error(f"Failed to reload cycle job: {e}")
                return False
        return True
```

Replace the sun branch (from `if config.get(...)` to `return True`) with:

```python
        if config.get("scheduling", {}).get("suntime_model", "legacy") == "sun":
            # Sun model: re-arm the one-shot next-change task, and make
            # sure the safety-net job exists (a live legacy→sun switch
            # would otherwise run without it).
            if 'safety' not in self._tasks:
                try:
                    self._tasks['safety'] = self.scheduler.add_job(
                        self._safety_check,
                        'interval',
                        seconds=int(config.get('scheduling', {}).get('safety_interval', 600)),
                        id='safety',
                        replace_existing=True
                    )
                except Exception as e:
                    logger.error(f"Failed to add safety job on model switch: {e}")
            self._rearm_next_change()
            return True

        # Legacy model: drop the sun-mode safety job (a live sun→legacy
        # switch would otherwise leave it ticking forever), then re-add
        # the interval job with the new interval.
        if 'safety' in self._tasks:
            try:
                self.scheduler.remove_job(self._tasks['safety'])
            except Exception:
                pass
            del self._tasks['safety']
        if 'cycle' in self._tasks:
```

(the rest of the legacy branch — the `try/except` re-add of the `cycle` job and the final `return True` — is unchanged; the new `if 'safety' in self._tasks:` block simply precedes the existing `if 'cycle' in self._tasks:` line.)

- [ ] **Step 2: Append the model-switch tests**

Append to `tests/test_scheduler_eventdriven.py` (reusing the module's existing `FakeManager` / `fake_scheduler` / `_base_config` helpers — see the Phase 2 plan, Task 1):

```python


class TestModelSwitchReload:
    """Live model switches via reload_cycle_interval (Phase 3 GUI)."""

    def test_legacy_to_sun_adds_safety_task(self, fake_scheduler):
        from kwallpaper.scheduler import SchedulerManager
        mgr = SchedulerManager(config_path=_base_config("legacy"))
        mgr.scheduler = fake_scheduler
        mgr._is_running = True
        mgr._tasks = {'cycle': 'cycle-job'}
        mgr.start()  # legacy: interval cycle job, no safety job
        assert 'safety' not in mgr._tasks

        # Switch to sun via the config + hot reload.
        import json as _json
        cfg = _json.loads(_base_config("legacy").read_text())
        cfg["scheduling"]["suntime_model"] = "sun"
        Path(cfg_path).write_text(_json.dumps(cfg))  # see note below
        assert mgr.reload_cycle_interval() is True
        assert 'safety' in mgr._tasks
        assert 'cycle' in mgr._tasks  # re-armed one-shot
        mgr.stop()

    def test_sun_to_legacy_removes_safety_task(self, fake_scheduler):
        from kwallpaper.scheduler import SchedulerManager
        mgr = SchedulerManager(config_path=_base_config("sun"))
        mgr.scheduler = fake_scheduler
        mgr._is_running = True
        mgr._tasks = {'cycle': 'cycle-job', 'safety': 'safety-job'}
        assert mgr.reload_cycle_interval() is True  # sun branch (no-op re-arm)
        assert 'safety' in mgr._tasks

        # Switch to legacy via the config + hot reload.
        import json as _json
        cfg = _json.loads(_base_config("sun").read_text())
        cfg["scheduling"]["suntime_model"] = "legacy"
        Path(cfg_path).write_text(_json.dumps(cfg))  # see note below
        assert mgr.reload_cycle_interval() is True
        assert 'safety' not in mgr._tasks
        assert 'cycle' in mgr._tasks  # interval job re-added
        mgr.stop()
```

**Note (execute as written, adapting to the Phase 2 test module's actual helpers):** the Phase 2 test module creates configs via a `tmp_path` fixture or a module-level `cfg_path` — the two tests above must write the *same* config file the `SchedulerManager` was constructed with, flipping only `scheduling.suntime_model`. If the Phase 2 module exposes a helper like `_base_config(model) -> Path` that returns a fresh path per call, restructure the tests to capture the path once:

```python
    def test_legacy_to_sun_adds_safety_task(self, tmp_path, fake_scheduler):
        from kwallpaper.scheduler import SchedulerManager
        cfg_path = _base_config(tmp_path, "legacy")   # per the module's helper
        mgr = SchedulerManager(config_path=str(cfg_path))
        ...
        cfg = json.loads(cfg_path.read_text())
        cfg["scheduling"]["suntime_model"] = "sun"
        cfg_path.write_text(json.dumps(cfg))
        ...
```

The assertions are the point; the config plumbing follows whatever the Phase 2 module already does.

- [ ] **Step 3: Run the scheduler tests**

Run: `python -m pytest tests/test_scheduler_eventdriven.py -v`
Expected: all Phase 2 tests still pass **+ 2 new** (`TestModelSwitchReload::test_legacy_to_sun_adds_safety_task`, `TestModelSwitchReload::test_sun_to_legacy_removes_safety_task`).

- [ ] **Step 4: Commit**

```bash
git add kwallpaper/scheduler.py tests/test_scheduler_eventdriven.py
git commit -m "Make reload_cycle_interval model-switch aware (safety task add/remove)"
```

---

## Task 6: Themes tab — embed the schedule preview

**Files:**
- Modify: `wallpaper_gui.py` (`ThemesPage` + `WallpaperChangerWindow._cleanup`)

- [ ] **Step 1: Import the widget**

In `wallpaper_gui.py`, find:

```python
from kwallpaper.scheduler import SchedulerManager, create_scheduler
```

Append after it:

```python
from kwallpaper.schedule_preview import SchedulePreviewWidget
```

- [ ] **Step 2: Create the widget in `ThemesPage.__init__`**

In `ThemesPage.__init__` (line 786), find:

```python
        self._cfg = config_path
        self._themes = None
```

Append after it:

```python
        self.schedule_preview = SchedulePreviewWidget()
```

- [ ] **Step 3: Lay it out below the cross-fade preview**

In `ThemesPage._build()` (line 801), find:

```python
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(self.preview)
        rlay.addWidget(self.preview_info)
```

Replace with:

```python
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(self.preview)
        rlay.addWidget(self.preview_info)
        rlay.addWidget(self.schedule_preview)
```

- [ ] **Step 4: Refresh on theme selection**

In `ThemesPage._on_select` (line 904), find:

```python
    def _on_select(self, cur, _prev):
        if cur is None:
            return
        theme_path = cur.data(Qt.ItemDataRole.UserRole).toString()
        self._load_preview(theme_path)
```

Replace with:

```python
    def _on_select(self, cur, _prev):
        if cur is None:
            self.schedule_preview.clear()
            return
        theme_path = cur.data(Qt.ItemDataRole.UserRole).toString()
        self._load_preview(theme_path)
        self.refresh_schedule_preview()
```

- [ ] **Step 5: Add `refresh_schedule_preview` and refresh the marker on tab show**

In `ThemesPage`, find:

```python
    def set_tab_visible(self, vis: bool):
        """Start/stop the preview slideshow when the tab is shown/hidden."""
        if vis:
            self.preview.start_slideshow()
        else:
            self.preview.stop_slideshow()
```

Replace with:

```python
    def set_tab_visible(self, vis: bool):
        """Start/stop the preview slideshow when the tab is shown/hidden."""
        if vis:
            self.preview.start_slideshow()
            # The schedule marker may be stale after being hidden.
            self.schedule_preview.refresh_now()
        else:
            self.preview.stop_slideshow()

    def refresh_schedule_preview(self):
        """(Re)compute the 24-hour schedule preview for the selected theme.

        No-op when nothing is selected.  Safe to call from any thread
        context the GUI uses (selection, settings save).
        """
        item = self.theme_list.currentItem()
        if item is None:
            self.schedule_preview.clear()
            return
        theme_path = item.data(Qt.ItemDataRole.UserRole).toString()
        self.schedule_preview.refresh(self._cfg, theme_path)
```

- [ ] **Step 6: Drain the preview pool on window exit**

In `WallpaperChangerWindow._cleanup` (line 1818), find:

```python
        self._load_token.version += 1
        self._op_token.version += 1
        self._thumb_pool.clear()
        self._op_pool.clear()
        self._thumb_pool.waitForDone(1000)
        self._op_pool.waitForDone(1000)
```

Append after it:

```python
        # Schedule preview pool (Themes tab).
        self.themes.schedule_preview._cleanup()
```

- [ ] **Step 7: Verify the GUI imports and the preview is embedded**

Run:
```bash
QT_QPA_PLATFORM=offscreen python3 -c "
import sys
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import wallpaper_gui
w = wallpaper_gui.WallpaperChangerWindow(config_path='/tmp/nonexistent-config-for-import-check.json')
assert hasattr(w.themes, 'schedule_preview')
assert hasattr(w.themes, 'refresh_schedule_preview')
w.close()
print('themes wiring OK')
"
```
Expected: `themes wiring OK`.

- [ ] **Step 8: Commit**

```bash
git add wallpaper_gui.py
git commit -m "Embed SchedulePreviewWidget in Themes tab (select/tab-show/save wiring, pool drain)"
```

---

## Task 7: `tests/test_gui_schedule.py` — GUI smoke tests

**Files:**
- Create: `tests/test_gui_schedule.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_gui_schedule.py`:

```python
"""GUI smoke tests for the Phase 3 time-model toggle + schedule preview.

Runs offscreen (QT_QPA_PLATFORM=offscreen, set before importing PyQt6
— same pattern as tests/test_preview_stress.py).  The window is built
with a real temp config; solar math is monkeypatched so the tests are
deterministic and do not depend on the real date.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem

TZ = ZoneInfo("America/Phoenix")
D = date(2026, 6, 21)

THEME = {
    "sunriseImageList": [1, 2, 3, 4],
    "dayImageList": [5, 6, 7, 8, 9],
    "sunsetImageList": [10, 11, 12, 13],
    "nightImageList": [14, 15, 16],
    "imageFilename": "sun_*.jpg",
}


def dt(h, m=0, s=0, day=D):
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=TZ)


def _seg(day, complete=True):
    from kwallpaper.solarsegments import Segments
    if not complete:
        return Segments(day=day, dawn=None, golden_hour_end=None,
                        golden_hour=None, dusk=None, next_dawn=None)
    return Segments(
        day=day,
        dawn=dt(5, 0, day=day),
        golden_hour_end=dt(5, 15, day=day),
        golden_hour=dt(6, 0, day=day),
        dusk=dt(18, 0, day=day),
        next_dawn=dt(5, 0, day=day + timedelta(days=1)),
    )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _write_config(tmp_path, model="legacy", safety_interval=600):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "location": {"timezone": "America/Phoenix",
                     "latitude": 33.4484, "longitude": -112.074},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": False,
                       "suntime_model": model,
                       "safety_interval": safety_interval},
        "theme": {"last_applied_image": ""},
    }))
    return str(cfg)


def _make_theme(tmp_path, name="TestTheme"):
    tdir = tmp_path / name
    tdir.mkdir(exist_ok=True)
    (tdir / "theme.json").write_text(json.dumps(THEME))
    for i in range(1, 17):
        (tdir / f"sun_{i:02d}.jpg").write_bytes(b"x")
    return tdir


@pytest.fixture
def window(tmp_path, qapp, monkeypatch):
    """A real window with one fake theme and deterministic segments."""
    import wallpaper_gui
    import kwallpaper.image_schedule as im

    cfg = _write_config(tmp_path)
    tdir = _make_theme(tmp_path)
    monkeypatch.setattr(wallpaper_gui, "discover_themes",
                        lambda d: [tdir])
    monkeypatch.setattr(im, "solar_segments",
                        lambda day, tz, lat, lon: _seg(day))
    w = wallpaper_gui.WallpaperChangerWindow(config_path=cfg)
    w.show()
    yield w
    w.close()


def _select_theme(w):
    w.themes.load_themes()
    assert w.themes.theme_list.count() == 1
    item = w.themes.theme_list.item(0)
    w.themes.theme_list.setCurrentItem(item)


def _spin(app, ms=300):
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()


class TestSettingsTimeModel:
    def test_loaded_from_config_sun(self, window):
        assert window.settings.time_model.currentIndex() == 0  # default legacy
        # Rewrite config to sun and reload the page.
        import json as _json
        cfg = _json.loads(Path(window._cfg).read_text())
        cfg["scheduling"]["suntime_model"] = "sun"
        Path(window._cfg).write_text(_json.dumps(cfg))
        window.settings._load()
        assert window.settings.time_model.currentIndex() == 1

    def test_save_persists_model_and_preserves_safety_interval(self, window):
        window.settings.time_model.setCurrentIndex(1)  # sun
        window.settings._save()
        cfg = json.loads(Path(window._cfg).read_text())
        s = cfg["scheduling"]
        assert s["suntime_model"] == "sun"
        assert s["safety_interval"] == 600      # survived the GUI save
        assert s["cycle_interval"] == 60        # existing fields intact

    def test_save_triggers_scheduler_reload_and_preview_refresh(self, window, monkeypatch):
        import wallpaper_gui
        calls = []
        # Fake a running scheduler so the hot-reload branch executes.
        class _FakeSched:
            def is_running(self):
                return True
            class _Mgr:
                def reload_cycle_interval(self):
                    calls.append("reload")
                    return True
            scheduler = _Mgr()
        window.sched = _FakeSched()
        monkeypatch.setattr(
            window.themes.schedule_preview, "refresh",
            lambda cfg, tdir: calls.append("preview"))
        window.settings.time_model.setCurrentIndex(1)
        window.settings._save()
        assert calls == ["reload", "preview"]


class TestSchedulePreviewWidget:
    def test_empty_state_paints(self, window, qapp):
        w = window.themes.schedule_preview
        assert w._state == "empty"
        w.show()
        w.resize(800, w.height())
        w.grab()  # force a paint
        assert w._state == "empty"

    def test_legacy_schedule_shows_notice(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ThemeSchedule
        w = window.themes.schedule_preview
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="legacy", now=dt(12, 0),
                          segments=None, entries=()),
            w._token.version)
        qapp.processEvents()
        assert w._state == "legacy"
        w.grab()

    def test_stale_result_rejected(self, window, qapp):
        from kwallpaper.image_schedule import ThemeSchedule
        w = window.themes.schedule_preview
        v = w._token.version
        w._bump()  # simulate a newer refresh superseding the old worker
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="legacy", now=dt(12, 0),
                          segments=None, entries=()),
            v)
        qapp.processEvents()
        assert w._state == "empty"  # stale result dropped

    def test_ready_paints_with_fake_schedule(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (
            ScheduleEntry(start=dt(0, 0), end=dt(1, 20), image=15, path=""),
            ScheduleEntry(start=dt(5, 0), end=dt(5, 3, 45), image=1, path=""),
            ScheduleEntry(start=dt(18, 0), end=dt(21, 40), image=14, path=""),
        )
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        assert w._state == "ready"
        w.show()
        w.resize(800, w.height())
        w.grab()

    def test_marker_x_position(self, window, qapp):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (ScheduleEntry(start=dt(0, 0), end=dt(23, 59), image=1,
                                 path=""),)
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        w.show()
        w.resize(800, w.height())
        w._now = dt(12, 0)
        # 12:00 is exactly half of a 24h day → middle of the bar.
        x = w._bar._x_for(dt(12, 0))
        assert abs(x - w._bar.width() // 2) <= 1

    def test_date_change_recomputes(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (ScheduleEntry(start=dt(0, 0), end=dt(23, 59), image=1,
                                 path=""),)
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        assert w._state == "ready"
        # Simulate "now" on the next day → the tick must recompute.
        calls = []
        monkeypatch.setattr(w, "refresh",
                            lambda cfg, tdir: calls.append((cfg, tdir)))
        w._config_path = "/cfg"
        w._theme_dir = "/theme"
        w._now = dt(12, 0, day=D + timedelta(days=1))
        w._on_tick()
        assert calls == [("/cfg", "/theme")]

    def test_updates_on_model_toggle(self, window, qapp, monkeypatch):
        """End-to-end: selecting a theme in legacy mode shows the notice;
        switching the model to sun and saving shows the timeline."""
        import kwallpaper.image_schedule as im
        _select_theme(window)
        w = window.themes.schedule_preview
        qapp.processEvents()
        # Legacy mode (config default): the worker returns a legacy
        # schedule → notice state.
        _spin(qapp, 500)
        assert w._state == "legacy"

        # Switch to sun and save (hot path: persist + preview refresh).
        window.settings.time_model.setCurrentIndex(1)
        window.settings._save()
        _spin(qapp, 800)
        assert w._state == "ready"
        assert len(w._schedule.entries) == 17
        assert w._schedule.entries[0].image == 15
```

- [ ] **Step 2: Run the GUI tests**

Run: `python -m pytest tests/test_gui_schedule.py -v`
Expected: **11 passed** (3 `TestSettingsTimeModel` + 8 `TestSchedulePreviewWidget`).

**If a test is flaky under offscreen:** the worker is a real `QThreadPool` job; the `_spin` helper pumps events. If `test_updates_on_model_toggle` occasionally fails, raise its `_spin` timeout to 1500 ms — do not weaken the assertions.

- [ ] **Step 3: Commit**

```bash
git add tests/test_gui_schedule.py
git commit -m "Add GUI smoke tests for time-model toggle + schedule preview"
```

---

## Task 8: Full test suite + phase-boundary health check

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: **321 passed** (286 post-Phase-2 baseline + 22 `test_image_schedule` + 2 `TestModelSwitchReload` + 11 `test_gui_schedule`). No failures, no errors.

- [ ] **Step 2: Manual GUI verification (Plasma session — cannot be automated)**

1. **Settings tab:** a "Time model" row exists in the Scheduler group with two options; "Legacy (fixed offsets)" is selected by default.
2. **Toggle + persist:** select "Sun-position (WDD)" → click Save → close and reopen the app → the selector still shows "Sun-position (WDD)". `config.json` contains `"suntime_model": "sun"` **and** `"safety_interval": 600` (not dropped to a new default).
3. **Hot reload:** with the scheduler running, switch the model and Save — the log shows the scheduler re-arming (sun: next-change task; legacy: interval job), and no stale safety job remains after switching back to legacy.
4. **Schedule preview (Themes tab):** with a real 16-image theme selected and the model on sun, the 24-hour bar shows: night band 00:00–dawn, sunrise band dawn→+6°, day band +6°→−6°, sunset band −6°→dusk, night band dusk→24:00; thumbnails at each image's start time; a current-time marker at the correct hour.
5. **Preview matches the scheduler:** the first timeline window *after* the marker starts at exactly the time `python3 -c "import sys; sys.path.insert(0,'.'); from kwallpaper.core import next_change_time_for_config; print(next_change_time_for_config())"` reports.
6. **Legacy mode:** switch the model back to legacy and Save — the bar is replaced by the notice "Schedule preview is available in the Sun-position model (Settings → Time model)".
7. **Midnight behaviour (optional, if time permits):** leave the app open across midnight — the bar recomputes for the new day within a minute.

- [ ] **Step 3: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "Phase 3: full suite green after manual verification fixes"
```

---

## Task 9: README + screenshot

**Files:**
- Modify: `README.md`
- Create: `screenshots/3schedule.png`

- [ ] **Step 1: Add the config-table row**

In `README.md`, in the Configuration Fields table (after the `scheduling.daily_shuffle_enabled` row, ~line 151), add:

```markdown
| `scheduling.suntime_model` | string | `"legacy"` | Time model: `"legacy"` (fixed offsets from sunrise/sunset) or `"sun"` (WDD sun-position segments: dawn → +6° → −6° → dusk). Selectable in the GUI (Settings → Time model). Default `"legacy"` until Phase 4. |
```

- [ ] **Step 2: Add the GUI-interface bullets**

In `README.md`, under **GUI Interface → Themes Tab** (lines 200–205), add a bullet:

```markdown
- **Schedule preview** (sun-position model only): a 24-hour timeline bar showing each image's display window with thumbnails and a current-time marker; recomputed on theme selection, settings save, and date change
```

Under **GUI Interface → Settings Tab** (lines 207–211), add a bullet:

```markdown
- **Time model**: choose between the legacy fixed-offset model and the WDD sun-position model (applies on Save; hot-reloads a running scheduler)
```

- [ ] **Step 3: Add the screenshot**

In `README.md`, where the existing screenshots are referenced (the `screenshots/1themes.png` / `screenshots/2settings.png` section), add:

```markdown
![Schedule preview](screenshots/3schedule.png)
```

Capture `screenshots/3schedule.png` **manually** (Plasma session, sun model, a real theme selected): the Themes tab with the 24-hour schedule bar visible, marker at the current time.

- [ ] **Step 4: Final full-suite run**

Run: `python -m pytest tests/ -q`
Expected: **321 passed** (unchanged — README/screenshots are not code).

- [ ] **Step 5: Commit**

```bash
git add README.md screenshots/3schedule.png
git commit -m "Document time model + schedule preview (config row, tab bullets, screenshot)"
```

---

## Self-review notes (for the plan author, not the executor)

- **Roadmap coverage check (Phase 3 scope):**
  - "Settings tab: time-model selector (legacy / sun), persisted, hot-reloads scheduler" → Tasks 4 + 5. ✓
  - "`all_image_times(date, segments, theme_data) -> list[(time, image_index)]` matching WDD `GetAllImageTimes` (including dedup)" → Task 1 (`all_image_times`, exact signature, dedup via `_effective_windows`, 16-entry parity test). ✓
  - "Themes tab: schedule-preview widget (24-hour timeline bar with image thumbnails at display times + current-time marker)" → Tasks 3 + 6. ✓
  - "Preview computation off the GUI thread (QThreadPool)" → Task 3 (two `QRunnable` workers, widget-owned pool, token cancellation, pool drain in `_cleanup`). ✓
  - "Tests for `image_schedule` and GUI smoke tests" → Tasks 2 + 7. ✓
  - "Default model stays `legacy` until Phase 4" → locked decision 11; no default change anywhere in this plan. ✓
- **Two-day segments subtlety:** the 24-hour bar for "today" needs *yesterday's* segments for last night's images that run past midnight — `day_windows` takes both; `schedule_for_config` computes yesterday best-effort. Verified numerically (fact 9): 17 contiguous windows, clamped at both ends.
- **`SettingsPage._save()` read-modify-write** is a bug fix in disguise: the current whole-section replacement would drop `safety_interval` (and `suntime_model`) on every GUI save. Task 4 Step 3 + `test_save_persists_model_and_preserves_safety_interval` cover it.
- **Model-switch scheduler cleanup** (Task 5) is what makes the GUI toggle safe at runtime: without it, legacy→sun loses the safety net and sun→legacy leaks the 600 s job.
- **Legacy-mode preview = notice, not timeline** (locked decision 5): deliberately avoids re-implementing legacy quirk math; the roadmap's own Phase 3 scope lists only the sun-model `all_image_times`.
- **Test count:** 286 (post-Phase-2) + 22 + 2 + 11 = **321** expected at the phase boundary.
- **Phase-boundary health:** the app is fully functional at every commit: the default model is still `legacy`, all legacy paths are untouched, the preview is additive (one extra widget in the Themes tab, one extra settings row), and the scheduler's new behaviour only activates when the user actually switches models.

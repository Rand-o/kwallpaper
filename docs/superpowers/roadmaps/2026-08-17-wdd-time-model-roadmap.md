# WDD-Style Time Model Roadmap

> **For agentic workers:** Use /skill:writing-plans to create one detailed implementation plan per phase. Start with Phase 1 and proceed sequentially unless the user explicitly changes the order.

**Goal:** kWallpaper selects and schedules wallpaper images using WinDynamicDesktop's sun-position-based segment model (dawn → sun +6° → sun +6° → dusk) with event-driven scheduling that changes the wallpaper only at exact change instants.

**Design Spec:** No separate spec file yet — the design rationale from the WDD research is summarized in the "Design Summary" section below. Extract a formal spec from it if desired before Phase 1.

**Planning Strategy:** The work is split into 5 ordered phases (Phase 5 is a menu of optional extras). Every phase is deliberately sized to be planned and executed within a single **131k context window**: each phase touches at most 3–4 focused modules plus a bounded test suite (estimates per phase below). The new model ships behind a config option (`scheduling.suntime_model`, default `"legacy"`) so that **every phase boundary leaves the app fully functional and the existing 134 tests green**. The default flips to the new model only in Phase 4, after the GUI exposes it and it has been exercised.

---

## Design Summary (from WDD research)

**Reference:** [github.com/t1m0thyj/WinDynamicDesktop](https://github.com/t1m0thyj/WinDynamicDesktop) — `SolarScheduler.cs`, `SunriseSunset.cs`, `EventScheduler.cs`, `ThemeShuffler.cs`, `ThemeJsonValidator.cs`, wiki "Creating custom themes".

### The WDD time model

Solar boundaries derived from **sun position only** (no arbitrary minute offsets):

| Boundary | Definition |
|---|---|
| `dawn` | Civil twilight, sun at −6° |
| `golden_hour_end` | Sun crossing **+6° above** horizon (morning) |
| `golden_hour` | Sun crossing **+6° above** horizon (evening) |
| `dusk` | Civil twilight, sun at −6° |

Four segments:

| Segment | Start | End |
|---|---|---|
| Sunrise | dawn | golden_hour_end |
| Day | golden_hour_end | golden_hour |
| Sunset | golden_hour | dusk |
| Night | dusk | **next day's** dawn |

Image→time mapping for `.ddw` themes (theme.json holds four image lists + `imageFilename` pattern; **no timestamps in the format**):

- Each segment is divided equally among its images: image *i* displays during `[start + i·(duration/n), start + (i+1)·(duration/n))`
- **Dedup rule:** if `dayImageList == sunriseImageList`, the sunrise segment is skipped (same for sunset vs day) — prevents showing the same image twice back-to-back
- `GetAllImageTimes()` computes the exact display time of every image in the theme (drives the preview UI)

WDD scheduler: computes the **exact next change time**, arms a one-shot timer for that instant, keeps a coarse background timer as safety net, reacts to system events (resume, unlock, time change), and **only calls the wallpaper API when the image actually changed**.

### Why our current model differs (Phoenix, 2026-06-21, real numbers)

Sun: dawn 04:49 · sunrise 05:19 · +6° 05:54 · sunset 19:41 · +6° 19:05 · dusk 20:10

| Segment | kWallpaper today (fixed offsets) | WDD (sun position) |
|---|---|---|
| Sunrise (4 imgs) | 04:19 → 06:04 (105 min) | 04:49 → 05:54 (65 min) |
| Day (5 imgs) | 06:04 → 19:25 | 05:54 → 19:05 |
| Sunset (4 imgs) | 19:25 → 20:10 (45 min) | 19:05 → 20:10 (65 min) |
| Night (3 imgs) | 20:10 → 04:19 | 20:10 → 04:49 |

Today we show sunrise images **30 min before civil dawn (still dark)** and sunset images **76 min before dusk (sun still up)**; the transition segments are asymmetric (105/45 min). WDD's are symmetric and aligned with the physical twilight window.

### Key implementation fact (verified in this repo)

`astral` 3.2 (already a dependency) supports the +6° crossings via **negative depression**:

```python
sun.dawn(loc.observer, date, tzinfo=tz, depression=-6)  # → 05:54 (sun +6° morning)
sun.dusk(loc.observer, date, tzinfo=tz, depression=-6)  # → 19:05 (sun +6° evening)
```

**No new dependency is required.**

### Key decisions

1. New model behind `scheduling.suntime_model`: `"legacy"` (initial default) | `"sun"`. Flip default in Phase 4.
2. Legacy code paths stay intact and pinned by existing tests until (optionally) removed in Phase 4.
3. Event-driven scheduling keeps a coarse **safety-net tick** (default 600 s) for clock jumps, resume-from-sleep, missed runs, and the daily shuffle check.
4. **Skip re-apply** when the selected image equals the last-applied image (stops the per-minute D-Bus hammering).
5. The new model lives in a **new self-contained module** (`solarsegments.py`), not by mutating the legacy quirk paths in `suntime.py`.

---

## Phase 1: Sun-Position Period Model (core math)

**Outcome:** A new `suntime` model that computes WDD's four segments from astral values and selects the correct image for any given time, selectable via config (`suntime_model: "sun"`), with a dedicated test suite. Default remains `"legacy"`, so out-of-the-box behavior is unchanged.

**Why now:** Everything downstream (scheduler, GUI preview) consumes the period model. Building it first, behind a config flag, gives later phases a stable interface without touching legacy behavior.

**Scope:**
- New module `kwallpaper/solarsegments.py`:
  - `solar_segments(date, tz, lat, lon) -> Segments` — dawn, golden_hour_end, golden_hour, dusk via astral (civil ±6°, +6° via negative depression); missing values represented explicitly (polar/edge cases)
  - `category_for(now, segments) -> str` — night/sunrise/day/sunset classification
  - `image_at(now, segments, theme_data) -> (category, image_index)` — equal spacing within the segment + WDD dedup rule + night wrap-around (dusk → next dawn)
- Config: new `scheduling.suntime_model` field (`"legacy" | "sun"`, default `"legacy"`); validation + legacy-config migration
- `selection.py`: route `select_image_for_time_cli` / `select_image_for_specific_time` to the new model when configured
- `core.py` `apply_theme`: uses the routed selection (no behavior change on default)
- New test suite `tests/test_solarsegments.py`: Phoenix 2026-06-21 reference boundaries, 24 h category sweep, image spacing per segment, dedup rule, night wrap, missing-value fallbacks

**Out of scope:** Scheduler changes, GUI, default flip, legacy removal, polar handling, manual override.

**Key files/areas likely affected:**
- `kwallpaper/solarsegments.py` (new, ~200–300 lines)
- `kwallpaper/selection.py` (routing, ~50 lines changed)
- `kwallpaper/config.py` (new field + validation, ~30 lines)
- `kwallpaper/core.py` (minor, ~10 lines)
- `tests/test_solarsegments.py` (new, ~400–600 lines)

**Dependencies:** None (first phase).

**Verification:**
- `pytest tests/ -v` fully green (legacy tests untouched; new tests pass)
- Manual: with `suntime_model: "sun"`, CLI selection at known times matches the Phoenix reference table above

**Phase boundary health:** Default behavior is byte-identical (legacy model untouched); new code is dormant unless the config flag is set. All tests green.

**Risks:**
- astral negative-depression edge cases at high latitudes → return explicit missing values and fall back to the legacy model for that day; full polar handling deferred to Phase 5
- Timezone/DST edge cases in boundary math → reuse existing `_normalize_now`/`_fix_next_day` patterns; pin with tests

**Context notes (≤131k):** `suntime.py` (712 lines, read-only reference) + `selection.py` (382) + `config.py` (353) + new module + new tests ≈ **35–45k tokens**. Keep the new module self-contained (no imports from the legacy quirk paths) so the detailed plan stays focused.

---

## Phase 2: Event-Driven Scheduling

**Outcome:** The scheduler computes the exact next wallpaper-change time and wakes only at that instant (plus a coarse safety net), and skips the D-Bus call when the selected image is unchanged. Works with both time models.

**Why now:** Depends on the Phase 1 model (next-change time is derived from segments). Keeps the app fully functional on the legacy model, where it degrades gracefully to today's polling behavior.

**Scope:**
- `next_change_time(now, segments, theme_data, current_image) -> datetime` in `solarsegments.py`: the next image boundary within the current segment, or the segment end, or the next day's first boundary (accounting for dedup)
- `scheduler.py`:
  - For `suntime_model: "sun"`: replace the fixed interval job with a **one-shot `DateTrigger`** at the computed next-change time, re-armed after each run
  - Keep a coarse **safety-net interval job** (default 600 s, configurable) for clock jumps, resume-from-sleep, missed runs, and the daily shuffle check
  - For `suntime_model: "legacy"`: keep today's interval job (default 60 s) unchanged
  - Track last-applied image path; **skip `change_wallpaper` when unchanged**
- `cli.py` `run_cycle_command`: honor skip-if-unchanged; report "no change" distinctly in the event log
- Tests: next-change-time math (all four segments, night wrap, dedup), skip-if-unchanged, safety-net re-arm, shuffle check still fires on the safety tick

**Out of scope:** GUI changes, default flip, OS-level system-event hooks (logind/clock signals) — the safety net covers those coarsely (exact hooks are a Phase 5 option).

**Key files/areas likely affected:**
- `kwallpaper/solarsegments.py` (`next_change_time`, ~80–120 lines added)
- `kwallpaper/scheduler.py` (trigger logic, ~100–150 lines changed)
- `kwallpaper/cli.py` (`run_cycle_command`, ~50 lines)
- `kwallpaper/core.py` (last-applied tracking, ~30 lines)
- `tests/test_next_change_time.py`, `tests/test_scheduler_eventdriven.py` (new)

**Dependencies:** Phase 1.

**Verification:**
- Full test suite green
- Manual: run scheduler with `suntime_model: "sun"` — event log shows a wake at the exact boundary, no D-Bus calls between changes, a manual wallpaper change is reverted on the next safety tick

**Phase boundary health:** Legacy users see today's behavior; sun-model users get event-driven behavior. No half-migrated state.

**Risks:**
- Timer drift / missed wake (suspend) → safety net catches it (same robustness class as today's 60 s poll)
- DateTrigger re-arm races → the existing re-entrant lock already serializes runs; keep it
- Skip-if-unchanged delays reverting a user's manual wallpaper change (up to one safety-net interval) → document it; default safety net 600 s

**Context notes (≤131k):** `scheduler.py` (327) + `core.py` (349) + `cli.py` (784, partial) + model additions + new tests ≈ **30–40k tokens**.

---

## Phase 3: GUI — Model Toggle + Schedule Preview

**Outcome:** The Settings tab exposes the time model (Legacy / Sun-position); the Themes tab shows a **schedule preview**: a 24-hour timeline of which image displays when for the selected theme (the WDD `GetAllImageTimes` equivalent), with a marker at the current time.

**Why now:** Makes the new model user-selectable and visible. The preview is the highest-value WDD UI feature and is cheap once the model exists.

**Scope:**
- Settings tab: time-model selector (legacy / sun), persisted to config, hot-reloads the scheduler
- New `kwallpaper/image_schedule.py`: `all_image_times(date, segments, theme_data) -> list[(time, image_index)]` (WDD `GetAllImageTimes` parity, including dedup)
- Themes tab: schedule-preview widget — 24 h timeline bar with image thumbnails positioned at their display times + current-time marker
- All preview computation off the GUI thread (`QThreadPool` worker, matching existing patterns)
- Tests: `image_schedule` (times for all four segments, dedup, wrap); GUI smoke tests for the toggle

**Out of scope:** Per-display themes, appearance mode, manual time override (Phase 5).

**Key files/areas likely affected:**
- `wallpaper_gui.py` (toggle + preview widget, ~300–500 lines added)
- `kwallpaper/image_schedule.py` (new, ~100–150 lines)
- `tests/test_image_schedule.py`, `tests/test_gui_schedule.py` (new)

**Dependencies:** Phase 1 (model); Phase 2 recommended so the preview matches scheduler behavior.

**Verification:**
- Full suite green; GUI manual: toggling the model updates the preview; current-time marker is correct; preview matches `next_change_time`
- Screenshot added to README

**Phase boundary health:** Purely additive GUI plus read-only schedule computation. App fully functional.

**Risks:**
- `wallpaper_gui.py` is already ~1,900 lines → keep the preview in its own widget class (ideally its own module) to avoid further bloat
- Preview accuracy across DST days → compute for "today" and refresh on date change

**Context notes (≤131k):** `wallpaper_gui.py` (1,904 lines ≈ 25k tokens) + new widget + new module + tests ≈ **40–50k tokens** — the tightest phase, still within budget. Keep the detailed plan scoped to exactly one widget plus one settings row.

---

## Phase 4: Default Flip + Import Validation + Docs

**Outcome:** `suntime_model` defaults to `"sun"`; theme import validates that every referenced image exists (WDD-style strict validation); README/changelog document the new model and behavior changes.

**Why now:** After the GUI exposes the model and it has been exercised, flip the default. Import validation is a small, independent correctness win (WDD rejects themes with missing referenced images; we currently only discover this at selection time).

**Scope:**
- Config default flip to `"sun"`; migration note for existing configs (explicit legacy values preserved)
- Import validation in `core.py import_theme` / `themes.py`: verify every image number in all four lists exists on disk against the `imageFilename` pattern; reject with a clear message listing missing images
- README: document the sun-position model, the config option, the schedule preview, and the event-driven scheduler
- Changelog entry (visible behavior change: transition images shift by up to ~30–75 min)
- Optional sub-step (only if the user confirms): deprecate/remove the legacy model paths and their tests

**Out of scope:** All Phase 5 extras.

**Key files/areas likely affected:**
- `kwallpaper/config.py`, `kwallpaper/core.py`, `kwallpaper/themes.py`
- `README.md`, changelog section
- `tests/` (validation tests; legacy-test removal only if confirmed)

**Dependencies:** Phase 3.

**Verification:**
- Full suite green
- Importing a theme with a missing referenced image fails with a clear, actionable message
- Fresh install (no config) uses the sun model end-to-end

**Phase boundary health:** Default behavior intentionally changes to the new model; the legacy model remains available via config as an escape hatch.

**Risks:**
- Users who relied on the legacy timing → changelog + config escape hatch; no data migration needed (model choice is config-only)

**Context notes (≤131k):** Small phase — config, import path, docs, tests ≈ **15–25k tokens**.

---

## Phase 5 (optional): WDD Extras — each an independent mini-phase

Each item below is standalone and can be planned/executed on its own (pick as needed; none is required for parity on the core time model):

| # | Item | WDD reference | Depends on |
|---|---|---|---|
| 5.1 | **Polar handling** — PolarDay / PolarNight / CivilPolarDay / CivilPolarNight segment collapse | `SunriseSunset.cs` polar branches | Phase 1 |
| 5.2 | **Manual sunrise/sunset override** — Settings fields for manual times + transition duration; model uses them instead of astral when set | `GetUserProvidedSolarData` | Phase 1 (+ Phase 3 for the UI) |
| 5.3 | **Shuffle period expansion** — hourly / 12 h / 2-day / weekly / monthly + favorites + history (no repeat until exhausted); exact next-shuffle time | `ThemeShuffler.cs` | Phase 2 |
| 5.4 | **Appearance mode (Auto/Light/Dark)** — 2-segment collapse: day = sunrise→sunset, night = sunset→next sunrise, using day/night lists only | `CalcNextUpdateTime` `preferSegment2` | Phase 1 (+ Phase 3 for the UI) |
| 5.5 | **Per-display themes** — assign different themes per screen (D-Bus code already loops screens); GUI picker | `EventScheduler` displayEvents | Phase 3 |
| 5.6 | **OS system-event hooks** — logind resume / clock-change signals trigger immediate re-evaluation (replaces the coarse safety net) | `EventScheduler` SystemEvents | Phase 2 |

**Verification (per item):** full suite green + a manual check specific to the item.

**Context notes (≤131k):** each item touches 1–3 modules plus tests ≈ **10–30k tokens** individually.

---

## Phase ordering summary

```
Phase 1  Sun-position model (config-gated, default legacy)     ~35–45k ctx
   │
Phase 2  Event-driven scheduling + skip-if-unchanged           ~30–40k ctx
   │
Phase 3  GUI: model toggle + schedule preview                  ~40–50k ctx
   │
Phase 4  Default flip to "sun" + import validation + docs      ~15–25k ctx
   │
Phase 5  Optional WDD extras (5.1–5.6, independent)            ~10–30k ctx each
```

Every phase leaves the project functional with green tests; the user-visible behavior only changes when the config flag is set (Phases 1–3) or when the default flips (Phase 4).

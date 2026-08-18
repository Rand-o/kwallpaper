# WDD Time Model — Phase 1: Sun-Position Period Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use /skill:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a WDD-style sun-position segment model (dawn → sun +6° → sun +6° → dusk) to kWallpaper, selectable via `scheduling.suntime_model: "sun"`, with the default remaining `"legacy"` so out-of-the-box behavior is byte-identical.

**Architecture:** A new self-contained module `kwallpaper/solarsegments.py` computes the four WDD segments from astral values (no imports from the legacy `suntime.py`) and selects images by equal spacing within each segment, applying WDD's dedup rule. The two public selection entry points in `selection.py` (`select_image_for_time_cli`, `select_image_for_specific_time`) route to the new model when the config flag is set, falling back to the legacy model on any failure (polar incomplete segments, astral unavailable). `core.py apply_theme` needs no changes — it delegates image selection to those two routed entry points.

**Tech Stack:** Python 3, astral 3.2 (existing dependency; `depression=-6` gives the +6° crossings), pytest, zoneinfo. No new dependencies.

**Roadmap:** `docs/superpowers/roadmaps/2026-08-17-wdd-time-model-roadmap.md`

**Phase:** Phase 1: Sun-Position Period Model (core math)

---

## Context (read before starting)

**Repo state:** branch `main`, clean tree, `python -m pytest tests/ -q` → **156 passed** (the roadmap's "134" is stale; use 156 as the baseline). Work from the repo root `/home/admin/llama-cpp/projects/kwallpaper`.

**Verified facts (do not re-derive; they were checked against astral 3.2 in this repo):**

1. **astral 3.2 API:** `astral.sun.dawn(observer, date=day, tzinfo=tz)` = civil twilight (sun −6°). Passing `depression=-6` (negative = *above* horizon) returns the sun **+6° crossing**: `dawn(..., depression=-6)` → morning +6°, `dusk(..., depression=-6)` → evening +6°.
2. **Polar behavior:** when a crossing does not exist for a day (polar day/night), astral **raises `ValueError` — it does not return `None`**. Every astral call must be wrapped in try/except → `None`. At 78°N (Arctic/Longyearbyen, 78.22, 15.65) all five boundaries are `None` in both June and December. At 66°N (Atlantic/Reykjavik, 66.0, −18.0) in June: `dawn` and `dusk` are `None` but both +6° crossings exist.
3. **Phoenix reference values (2026-06-21, 33.4484, −112.074, America/Phoenix), pinned to the second:** dawn `04:49:43.543358`, +6° AM `05:54:55.713299`, +6° PM `19:05:26.557453`, dusk `20:10:38.578189`, next dawn `2026-06-22 04:49:57.566256`. (Roadmap HH:MM: dawn 04:49, +6° 05:54, +6° 19:05, dusk 20:10.)
4. **Legacy quirks stay untouched.** `kwallpaper/suntime.py` (712 lines) is read-only for this phase. Legacy index math for `select_image_for_time_cli` with a 16-image theme (all four lists `[1..16]`, `imageFilename: "sun_*.jpg"`) on 2026-06-21 Phoenix is: 04:30→`sun_02.jpg`, 05:30→`sun_11.jpg`, 12:00→`sun_12.jpg`, 23:00→`sun_06.jpg`, 00:00→`sun_08.jpg`, 03:00→`sun_14.jpg`. These are *verified* expected values for the default-model routing tests — do not "fix" them.
5. **Test-harness footgun #1 (isinstance):** `suntime.time_of_day_for` does `isinstance(x, datetime)`, where `datetime` resolves to the **module global** of `suntime`. If you patch `suntime.datetime` with a `datetime` *subclass*, plain `datetime` instances **fail** the isinstance check and the function returns `"night"` for everything. Therefore the routing tests patch `suntime.datetime` with a subclass **and** make the fake sun values instances of that same subclass (see `_FixedDT` / `_fake_sun` in Task 7).
6. **Test-harness footgun #2 (import namespaces):** `selection.py` does `from kwallpaper.suntime import ... _real_sun_data ...`, so it holds its **own reference**. Patching only `suntime._real_sun_data` leaves `selection._sun_for_config` calling the real astral. Patch **both** `suntime._real_sun_data` and `selection._real_sun_data` (see `_patch_time_and_sun` in Task 7).
7. **`apply_theme` is covered by selection routing.** `core.apply_theme` calls `select_image_for_specific_time` / `select_image_for_time_cli` for image selection; its own `detect_time_of_day_*` calls feed an unused `tod` variable (plus the backup-file side effect). So Phase 1 makes **zero changes to `core.py`** — Task 10 pins the transparency with a test.
8. **Config mechanics:** `load_config` = `validate_config` (raises `ValueError("Config validation failed: ...")`) then `normalize_config` (migrates legacy keys, fills missing keys from `_default_config()` via `setdefault`). A new field that is simply absent from old configs needs **no explicit migration code** — the default-fill loop supplies it. Validation of present values follows the existing `_require_*` helpers in `config.py`.

**Out of scope (later phases — do not implement):** event-driven scheduling (Phase 2), GUI toggle/preview (Phase 3), default flip to `"sun"` (Phase 4), polar segment collapse (Phase 5.1), manual overrides (Phase 5.2). Full polar *handling* is out of scope; Phase 1 only requires that polar days produce incomplete segments and fall back to legacy.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `kwallpaper/solarsegments.py` | **Create** (~230 lines) | Self-contained WDD model: `Segments`, `solar_segments`, `segments_for_now`, `category_for`, `image_at`, `segments_for_config`, `IncompleteSegmentsError` |
| `kwallpaper/config.py` | Modify (~15 lines) | `scheduling.suntime_model` default (`"legacy"`) + validation |
| `kwallpaper/selection.py` | Modify (~40 lines) | Route `select_image_for_time_cli` / `select_image_for_specific_time` to the sun model when configured |
| `tests/test_solarsegments.py` | **Create** (~550 lines) | Model tests (boundaries, categories, spacing, dedup, wrap, polar) + routing/fallback/apply_theme tests |
| `tests/test_config_validation.py` | Modify (~35 lines) | `suntime_model` validation + default-fill tests |
| `kwallpaper/core.py`, `kwallpaper/suntime.py`, `kwallpaper/wallpaper_changer.py` | **No changes** | — |

---

### Task 1: `Segments` dataclass + `solar_segments()` (astral boundary math)

**Files:**
- Create: `kwallpaper/solarsegments.py`
- Test: `tests/test_solarsegments.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_solarsegments.py`:

```python
"""Tests for the WDD-style sun-position segment model (phase 1).

Reference geometry: Phoenix (33.4484, -112.074, America/Phoenix),
2026-06-21.  Boundary values are pinned against astral 3.2 and must not
drift without an intentional astral upgrade.
"""
from datetime import date, datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from kwallpaper.solarsegments import solar_segments

TZ = ZoneInfo("America/Phoenix")
LAT, LON = 33.4484, -112.074
DAY = date(2026, 6, 21)


def test_phoenix_reference_boundaries():
    """Pin the Phoenix 2026-06-21 reference values from the roadmap."""
    seg = solar_segments(DAY, TZ, LAT, LON)
    assert seg.day == DAY
    assert seg.dawn.strftime("%H:%M") == "04:49"
    assert seg.golden_hour_end.strftime("%H:%M") == "05:54"
    assert seg.golden_hour.strftime("%H:%M") == "19:05"
    assert seg.dusk.strftime("%H:%M") == "20:10"
    assert seg.next_dawn.strftime("%H:%M") == "04:49"
    assert seg.next_dawn.date() == date(2026, 6, 22)
    assert seg.complete is True


def test_polar_day_all_boundaries_missing():
    """78N summer (polar day): no civil or +6 degree crossings."""
    seg = solar_segments(DAY, ZoneInfo("Arctic/Longyearbyen"), 78.22, 15.65)
    assert (seg.dawn, seg.golden_hour_end, seg.golden_hour,
            seg.dusk, seg.next_dawn) == (None, None, None, None, None)
    assert seg.complete is False


def test_polar_night_all_boundaries_missing():
    """78N winter (polar night): everything missing as well."""
    seg = solar_segments(date(2026, 12, 21),
                         ZoneInfo("Arctic/Longyearbyen"), 78.22, 15.65)
    assert seg.complete is False


def test_high_latitude_partial_boundaries():
    """66N summer: civil dawn/dusk never happen, +6 deg crossings do."""
    seg = solar_segments(DAY, ZoneInfo("Atlantic/Reykjavik"), 66.0, -18.0)
    assert seg.dawn is None
    assert seg.dusk is None
    assert seg.golden_hour_end is not None
    assert seg.golden_hour is not None
    assert seg.complete is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'kwallpaper.solarsegments'`

- [ ] **Step 3: Write minimal implementation**

Create `kwallpaper/solarsegments.py`:

```python
#!/usr/bin/env python3
"""
kWallpaper sun-position segment model (WDD-style).

Computes WinDynamicDesktop's four sun segments from astral values:

    dawn (sun -6 deg) -> golden_hour_end (sun +6 deg) ->
    golden_hour (sun +6 deg) -> dusk (sun -6 deg) -> next day's dawn

and selects the theme image for a given time by dividing each segment
equally among its images.

This module is self-contained: it imports nothing from kwallpaper.suntime
(the legacy model) and vice versa.  The model is selected via the
``scheduling.suntime_model`` config field ("legacy" | "sun").  When the
segments are incomplete (polar day/night, astral failure) callers fall
back to the legacy model.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class IncompleteSegmentsError(ValueError):
    """Sun segments are incomplete (polar day/night or edge case)."""


@dataclass(frozen=True)
class Segments:
    """The four WDD sun segments for one day.

    All boundaries are timezone-aware datetimes in the segment day's
    timezone, or None when the crossing does not exist that day
    (polar day/night).
    """

    day: date
    dawn: Optional[datetime]              # sun at -6 deg (civil twilight)
    golden_hour_end: Optional[datetime]   # sun crossing +6 deg (morning)
    golden_hour: Optional[datetime]       # sun crossing +6 deg (evening)
    dusk: Optional[datetime]              # sun at -6 deg (civil twilight)
    next_dawn: Optional[datetime]         # following day's dawn (night end)

    @property
    def complete(self) -> bool:
        """True when all five boundaries exist and are strictly ordered."""
        return (
            self.dawn is not None
            and self.golden_hour_end is not None
            and self.golden_hour is not None
            and self.dusk is not None
            and self.next_dawn is not None
            and self.dawn < self.golden_hour_end
            < self.golden_hour
            < self.dusk
            < self.next_dawn
        )


def _astral_boundary(fn, observer, day, tz, **kwargs) -> Optional[datetime]:
    """Call an astral sun function; None when the crossing is missing.

    astral raises (ValueError) when a sun crossing does not exist for
    the given day (polar day/night); we normalize that to None.
    """
    try:
        return fn(observer, date=day, tzinfo=tz, **kwargs)
    except Exception:
        logger.debug("astral crossing missing: %s %s %s",
                     getattr(fn, "__name__", fn), day, kwargs, exc_info=True)
        return None


def solar_segments(day: date, tz: ZoneInfo, lat: float,
                   lon: float) -> Segments:
    """Compute the WDD segments for ``day`` at (lat, lon) in timezone ``tz``.

    Boundaries:
      dawn            sun at -6 deg  (astral dawn, civil twilight)
      golden_hour_end sun at +6 deg  (astral dawn with depression=-6)
      golden_hour     sun at +6 deg  (astral dusk with depression=-6)
      dusk            sun at -6 deg  (astral dusk, civil twilight)
      next_dawn       following day's dawn (end of the night segment)

    Missing crossings (polar day/night) are returned as None, never
    raised.
    """
    import astral
    from astral import sun as _sun

    location = astral.LocationInfo("kwallpaper", "default", tz.key, lat, lon)
    observer = location.observer
    return Segments(
        day=day,
        dawn=_astral_boundary(_sun.dawn, observer, day, tz),
        golden_hour_end=_astral_boundary(_sun.dawn, observer, day, tz,
                                         depression=-6),
        golden_hour=_astral_boundary(_sun.dusk, observer, day, tz,
                                     depression=-6),
        dusk=_astral_boundary(_sun.dusk, observer, day, tz),
        next_dawn=_astral_boundary(_sun.dawn, observer,
                                   day + timedelta(days=1), tz),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_solarsegments.py
git commit -m "Add solarsegments: Segments + solar_segments (WDD sun-position model)"
```

---

### Task 2: `segments_for_now()` (day selection + night wrap)

**Files:**
- Modify: `kwallpaper/solarsegments.py` (append)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_solarsegments.py`, replace the import line:

```python
from kwallpaper.solarsegments import solar_segments
```

with:

```python
from kwallpaper.solarsegments import segments_for_now, solar_segments
```

Append these tests:

```python
def test_for_now_early_morning_uses_previous_day():
    """03:00 is still inside the previous day's night segment."""
    now = datetime(2026, 6, 21, 3, 0, tzinfo=TZ)
    seg = segments_for_now(now, TZ, LAT, LON)
    assert seg.day == date(2026, 6, 20)
    assert seg.dawn <= now < seg.next_dawn


def test_for_now_midday_uses_same_day():
    now = datetime(2026, 6, 21, 8, 0, tzinfo=TZ)
    assert segments_for_now(now, TZ, LAT, LON).day == DAY


def test_for_now_evening_uses_same_day():
    now = datetime(2026, 6, 21, 21, 0, tzinfo=TZ)
    assert segments_for_now(now, TZ, LAT, LON).day == DAY


def test_for_now_naive_now_is_assumed_local():
    seg = segments_for_now(datetime(2026, 6, 21, 3, 0), TZ, LAT, LON)
    assert seg.day == date(2026, 6, 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: collection error — `ImportError: cannot import name 'segments_for_now'`

- [ ] **Step 3: Write minimal implementation**

Append to `kwallpaper/solarsegments.py`:

```python
def segments_for_now(now: datetime, tz: ZoneInfo,
                     lat: float, lon: float) -> Segments:
    """Segments for the day that owns ``now``.

    The night segment runs from dusk to the *next* day's dawn, so times
    before dawn belong to the previous day's segments.  Naive ``now``
    values are assumed to be in ``tz``.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    today = solar_segments(now.date(), tz, lat, lon)
    if today.dawn is not None and now < today.dawn:
        return solar_segments(now.date() - timedelta(days=1), tz, lat, lon)
    return today
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_solarsegments.py
git commit -m "Add solarsegments.segments_for_now with pre-dawn day selection"
```

---

### Task 3: `category_for()` (night/sunrise/day/sunset classification)

**Files:**
- Modify: `kwallpaper/solarsegments.py` (append)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_solarsegments.py`, replace the import line:

```python
from kwallpaper.solarsegments import segments_for_now, solar_segments
```

with:

```python
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    category_for,
    segments_for_now,
    solar_segments,
)
```

Append these tests:

```python
def _phoenix_seg():
    return solar_segments(DAY, TZ, LAT, LON)


def _at(h: int, m: int, day: int = 21) -> datetime:
    return datetime(2026, 6, day, h, m, tzinfo=TZ)


@pytest.mark.parametrize("pick,expected", [
    (lambda s: s.dawn - timedelta(seconds=1), "night"),
    (lambda s: s.dawn, "sunrise"),
    (lambda s: s.golden_hour_end - timedelta(seconds=1), "sunrise"),
    (lambda s: s.golden_hour_end, "day"),
    (lambda s: s.golden_hour - timedelta(seconds=1), "day"),
    (lambda s: s.golden_hour, "sunset"),
    (lambda s: s.dusk - timedelta(seconds=1), "sunset"),
    (lambda s: s.dusk, "night"),
    (lambda s: s.next_dawn - timedelta(seconds=1), "night"),
    (lambda s: s.next_dawn, "night"),
])
def test_category_boundaries(pick, expected):
    seg = _phoenix_seg()
    assert category_for(pick(seg), seg) == expected


def test_category_named_times():
    seg = _phoenix_seg()
    pre_dawn = _at(3, 0)
    assert category_for(pre_dawn, segments_for_now(pre_dawn, TZ, LAT, LON)) == "night"
    assert category_for(_at(12, 0), seg) == "day"
    assert category_for(_at(23, 0), seg) == "night"


def test_category_24h_sweep_block_sequence():
    """A 10-minute sweep from dawn to next dawn yields exactly
    sunrise -> day -> sunset -> night, in order, with no repeats."""
    seg = _phoenix_seg()
    t = seg.dawn
    seq = []
    while t < seg.next_dawn:
        seq.append(category_for(t, seg))
        t += timedelta(minutes=10)
    blocks = []
    for c in seq:
        if not blocks or blocks[-1] != c:
            blocks.append(c)
    assert blocks == ["sunrise", "day", "sunset", "night"]


def test_category_incomplete_raises():
    polar = solar_segments(DAY, ZoneInfo("Arctic/Longyearbyen"), 78.22, 15.65)
    now = datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("Arctic/Longyearbyen"))
    with pytest.raises(IncompleteSegmentsError):
        category_for(now, polar)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: collection error — `ImportError: cannot import name 'category_for'`

- [ ] **Step 3: Write minimal implementation**

Append to `kwallpaper/solarsegments.py`:

```python
def category_for(now: datetime, seg: Segments) -> str:
    """Classify ``now`` as night/sunrise/day/sunset.

    Each segment is inclusive at its start and exclusive at its end:
      [dawn, golden_hour_end)         sunrise
      [golden_hour_end, golden_hour)  day
      [golden_hour, dusk)             sunset
      [dusk, next_dawn)               night
    Times outside [dawn, next_dawn) are night as well.

    Raises:
        IncompleteSegmentsError: when ``seg.complete`` is False.
    """
    if not seg.complete:
        raise IncompleteSegmentsError(
            f"sun segments incomplete for {seg.day}; fall back to legacy model")
    if now.tzinfo is None:
        now = now.replace(tzinfo=seg.dawn.tzinfo)
    if now < seg.dawn or now >= seg.next_dawn:
        return "night"
    if now < seg.golden_hour_end:
        return "sunrise"
    if now < seg.golden_hour:
        return "day"
    if now < seg.dusk:
        return "sunset"
    return "night"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_solarsegments.py
git commit -m "Add solarsegments.category_for with boundary-pinned classification"
```

---
### Task 4: `image_at()` (equal spacing + WDD dedup + night wrap)

**Files:**
- Modify: `kwallpaper/solarsegments.py` (append)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_solarsegments.py`, replace the import block:

```python
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    category_for,
    segments_for_now,
    solar_segments,
)
```

with:

```python
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    category_for,
    image_at,
    segments_for_now,
    solar_segments,
)
```

Append these tests:

```python
#: WDD-style theme: 4 sunrise, 5 day, 4 sunset, 3 night images.
THEME = {
    "sunriseImageList": [1, 2, 3, 4],
    "dayImageList": [5, 6, 7, 8, 9],
    "sunsetImageList": [10, 11, 12, 13],
    "nightImageList": [14, 15, 16],
}


def _syn_seg(dawn="05:00", ghe="06:00", gh="18:00",
             dusk="19:00") -> Segments:
    """Synthetic segments with clean hour boundaries (no astral needed)."""
    def t(hhmm, off=0):
        h, m = map(int, hhmm.split(":"))
        return datetime(2026, 6, 21, h, m, tzinfo=TZ) + timedelta(days=off)
    return Segments(day=DAY, dawn=t(dawn), golden_hour_end=t(ghe),
                    golden_hour=t(gh), dusk=t(dusk), next_dawn=t(dawn, 1))


S = _syn_seg()


@pytest.mark.parametrize("hhmm,day,expected", [
    # sunrise: [05:00, 06:00), 4 images -> 15 min each
    ("05:00", 21, ("sunrise", 1)),
    ("05:14", 21, ("sunrise", 1)),
    ("05:15", 21, ("sunrise", 2)),
    ("05:30", 21, ("sunrise", 3)),
    ("05:45", 21, ("sunrise", 4)),
    ("05:59", 21, ("sunrise", 4)),
    # day: [06:00, 18:00), 5 images -> 2h24m each
    ("06:00", 21, ("day", 5)),
    ("08:24", 21, ("day", 6)),
    ("10:48", 21, ("day", 7)),
    ("13:12", 21, ("day", 8)),
    ("15:36", 21, ("day", 9)),
    ("17:59", 21, ("day", 9)),
    # sunset: [18:00, 19:00), 4 images -> 15 min each
    ("18:00", 21, ("sunset", 10)),
    ("18:30", 21, ("sunset", 12)),
    ("18:45", 21, ("sunset", 13)),
    # night: [19:00, next 05:00), 3 images -> 4h each, wraps midnight
    ("19:00", 21, ("night", 14)),
    ("22:20", 21, ("night", 15)),
    ("01:40", 22, ("night", 16)),
    ("04:59", 22, ("night", 16)),
])
def test_image_spacing_per_segment(hhmm, day, expected):
    h, m = map(int, hhmm.split(":"))
    assert image_at(datetime(2026, 6, day, h, m, tzinfo=TZ), S, THEME) == expected


def test_image_real_data_probes():
    """Equal spacing against the real Phoenix 2026-06-21 segments
    (pinned against astral 3.2)."""
    seg = _phoenix_seg()
    assert image_at(_at(12, 0), seg, THEME) == ("day", 7)
    assert image_at(_at(23, 0), seg, THEME) == ("night", 14)
    assert image_at(_at(0, 0, 22), seg, THEME) == ("night", 15)
    assert image_at(_at(3, 0, 22), seg, THEME) == ("night", 16)
    pre_dawn = _at(4, 30)
    assert image_at(pre_dawn, segments_for_now(pre_dawn, TZ, LAT, LON),
                    THEME) == ("night", 16)
    assert image_at(_at(5, 0), seg, THEME) == ("sunrise", 1)
    assert image_at(_at(19, 30), seg, THEME) == ("sunset", 11)


def test_dedup_sunrise_list_equals_day_list():
    """When sunriseImageList == dayImageList the sunrise segment is
    absorbed into day: day images span [dawn, golden_hour)."""
    theme = dict(THEME, sunriseImageList=[5, 6, 7, 8, 9])
    assert image_at(_at(5, 30), S, theme) == ("day", 5)
    assert image_at(_at(8, 0), S, theme) == ("day", 6)
    assert image_at(_at(12, 0), S, theme) == ("day", 7)
    assert image_at(_at(16, 0), S, theme) == ("day", 9)
    # sunset segment unaffected
    assert image_at(_at(18, 30), S, theme) == ("sunset", 12)
    # category_for is astronomical and unaffected by dedup
    assert category_for(_at(5, 30), S) == "sunrise"


def test_dedup_sunset_list_equals_day_list():
    theme = dict(THEME, sunsetImageList=[5, 6, 7, 8, 9])
    # sunrise segment unaffected
    assert image_at(_at(5, 30), S, theme) == ("sunrise", 3)
    # day now spans [golden_hour_end, dusk)
    assert image_at(_at(17, 0), S, theme) == ("day", 9)
    assert image_at(_at(18, 30), S, theme) == ("day", 9)


def test_dedup_both_lists_equal_day_list():
    theme = dict(THEME, sunriseImageList=[5, 6, 7, 8, 9],
                 sunsetImageList=[5, 6, 7, 8, 9])
    assert image_at(_at(5, 30), S, theme) == ("day", 5)
    assert image_at(_at(12, 0), S, theme) == ("day", 7)
    assert image_at(_at(18, 30), S, theme) == ("day", 9)


def test_image_empty_category_list_raises():
    theme = dict(THEME, sunriseImageList=[])
    with pytest.raises(ValueError, match="No images available in sunrise"):
        image_at(_at(5, 30), S, theme)


def test_image_incomplete_segments_raises():
    polar = solar_segments(DAY, ZoneInfo("Arctic/Longyearbyen"), 78.22, 15.65)
    now = datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("Arctic/Longyearbyen"))
    with pytest.raises(IncompleteSegmentsError):
        image_at(now, polar, THEME)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: collection error — `ImportError: cannot import name 'image_at'`

- [ ] **Step 3: Write minimal implementation**

First, extend the typing import at the top of `kwallpaper/solarsegments.py`:

```python
from typing import Any, Dict, Optional, Tuple
```

(replacing `from typing import Optional`)

Then append to `kwallpaper/solarsegments.py`:

```python
def _effective_windows(seg: Segments,
                       theme_data: Dict[str, Any]) -> Dict[str, Tuple[datetime, datetime]]:
    """Image-selection windows per category, applying the WDD dedup rule.

    If ``sunriseImageList == dayImageList`` (non-empty), the sunrise
    segment is absorbed into day (day starts at dawn instead of
    golden_hour_end); same for sunset vs day (day ends at dusk instead
    of golden_hour).  This prevents showing the same image twice
    back-to-back across a segment boundary.
    """
    sunrise_list = theme_data.get("sunriseImageList", []) or []
    sunset_list = theme_data.get("sunsetImageList", []) or []
    day_list = theme_data.get("dayImageList", []) or []

    day_start = seg.golden_hour_end
    day_end = seg.golden_hour
    sunrise_absorbed = bool(sunrise_list) and sunrise_list == day_list
    sunset_absorbed = bool(sunset_list) and sunset_list == day_list
    if sunrise_absorbed:
        day_start = seg.dawn
    if sunset_absorbed:
        day_end = seg.dusk

    windows: Dict[str, Tuple[datetime, datetime]] = {
        "day": (day_start, day_end),
        "night": (seg.dusk, seg.next_dawn),
    }
    if not sunrise_absorbed:
        windows["sunrise"] = (seg.dawn, seg.golden_hour_end)
    if not sunset_absorbed:
        windows["sunset"] = (seg.golden_hour, seg.dusk)
    return windows


def image_at(now: datetime, seg: Segments,
             theme_data: Dict[str, Any]) -> Tuple[str, int]:
    """Select (category, image_value) for ``now``.

    The effective window of each category is divided equally among its
    images: image at list index *i* displays during
    ``[start + i*duration/n, start + (i+1)*duration/n)``.  Returns the
    raw value from the category's image list (an int index for standard
    themes).

    Raises:
        IncompleteSegmentsError: when ``seg.complete`` is False.
        ValueError: when ``now`` falls in a category whose image list
            is empty, or outside all segment windows.
    """
    if not seg.complete:
        raise IncompleteSegmentsError(
            f"sun segments incomplete for {seg.day}; fall back to legacy model")
    if now.tzinfo is None:
        now = now.replace(tzinfo=seg.dawn.tzinfo)
    for category, (start, end) in _effective_windows(seg, theme_data).items():
        if start <= now < end:
            image_list = theme_data.get(f"{category}ImageList", []) or []
            if not image_list:
                raise ValueError(
                    f"No images available in {category} category")
            duration = (end - start).total_seconds()
            elapsed = (now - start).total_seconds()
            position = elapsed / duration
            idx = int((position + 1e-9) * len(image_list))
            idx = max(0, min(idx, len(image_list) - 1))
            return category, image_list[idx]
    raise ValueError(f"now {now} outside all segment windows of {seg.day}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: 46 passed

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_solarsegments.py
git commit -m "Add solarsegments.image_at: equal spacing, WDD dedup, night wrap"
```

---

### Task 5: Config — `scheduling.suntime_model` field

**Files:**
- Modify: `kwallpaper/config.py` (`_default_config` scheduling section, new `_require_suntime_model` helper after `_require_number`, `validate_config` scheduling block)
- Test: `tests/test_config_validation.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_config_validation.py`, add `import copy` to the top imports (after `import json`), then append:

```python
def test_validate_config_suntime_model_valid():
    config = {
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True,
                       "suntime_model": "sun"},
    }
    validate_config(config)


def test_validate_config_suntime_model_legacy_valid():
    validate_config({"scheduling": {"suntime_model": "legacy"}})


@pytest.mark.parametrize("value", ["Solar", "SUN", "solar", 1, None, True,
                                   ["sun"]])
def test_validate_config_suntime_model_invalid(value):
    config = {"scheduling": {"suntime_model": value}}
    with pytest.raises(ValueError, match="suntime_model"):
        validate_config(config)


def test_normalize_config_fills_missing_suntime_model():
    """Legacy configs without the field get the default 'legacy'."""
    config = {"scheduling": {"cycle_interval": 120, "run_cycle": False}}
    loaded = normalize_config(copy.deepcopy(config))
    assert loaded["scheduling"]["suntime_model"] == "legacy"


def test_normalize_config_preserves_explicit_suntime_model():
    config = {"scheduling": {"suntime_model": "sun"}}
    loaded = normalize_config(copy.deepcopy(config))
    assert loaded["scheduling"]["suntime_model"] == "sun"


def test_default_config_has_suntime_model_legacy():
    from kwallpaper.config import _default_config
    assert _default_config()["scheduling"]["suntime_model"] == "legacy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_validation.py -v -k suntime_model`
Expected: the `invalid` (7 params), `fills_missing`, and `default_config` tests FAIL (validation accepts anything; `KeyError: 'suntime_model'`); the 2 valid tests pass

- [ ] **Step 3: Write minimal implementation**

In `kwallpaper/config.py`, three edits:

Edit 1 — in `_default_config()`, add the field to the `scheduling` section:

```python
        "scheduling": {
            "cycle_interval": 60,            # seconds between cycle runs
            "run_cycle": True,
            "daily_shuffle_enabled": True,
            "suntime_model": "legacy",       # legacy | sun
        },
```

Edit 2 — add this helper immediately after `_require_number` (before `validate_config`):

```python
def _require_suntime_model(config: Dict[str, Any]) -> None:
    section = config.get("scheduling")
    if not isinstance(section, dict) or "suntime_model" not in section:
        return
    if section["suntime_model"] not in ("legacy", "sun"):
        raise ValueError(
            "Config validation failed: 'scheduling.suntime_model' must be "
            "'legacy' or 'sun'")
```

Edit 3 — in `validate_config`, inside the `# scheduling` block, add the call after the `_require_bool(config, "scheduling.auto_start_on_launch")` line:

```python
    _require_suntime_model(config)
```

Note: no explicit migration code is needed — configs missing the field are filled with `"legacy"` by the existing default-fill loop in `normalize_config` (that is the "legacy-config migration" for this field).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_validation.py -v`
Expected: all pass (previously-passing tests still pass)

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/config.py tests/test_config_validation.py
git commit -m "Add scheduling.suntime_model config field (legacy|sun, default legacy)"
```

---

### Task 6: `segments_for_config()` (config → segments seam)

**Files:**
- Modify: `kwallpaper/solarsegments.py` (append)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_solarsegments.py`, replace the import block:

```python
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    category_for,
    image_at,
    segments_for_now,
    solar_segments,
)
```

with:

```python
import json

from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    category_for,
    image_at,
    segments_for_config,
    segments_for_now,
    solar_segments,
)
```

(Keep the existing `from datetime import ...`, `import pytest`, `from zoneinfo import ZoneInfo` lines above it.)

Append these tests:

```python
def _write_config(tmp_path, model=None):
    """Write a valid v2 config; optionally set scheduling.suntime_model."""
    sched = {"cycle_interval": 60, "run_cycle": True,
             "daily_shuffle_enabled": True}
    if model is not None:
        sched["suntime_model"] = model
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "version": 2,
        "appearance": {"theme_mode": "light"},
        "autostart": {"enabled": True, "start_scheduler_on_launch": False},
        "location": {"latitude": 33.4484, "longitude": -112.074,
                     "timezone": "America/Phoenix"},
        "scheduling": sched,
        "theme": {"last_applied": ""},
    }))
    return cfg


def test_segments_for_config_phoenix(tmp_path):
    cfg = _write_config(tmp_path)
    now = datetime(2026, 6, 21, 12, 0, tzinfo=TZ)
    seg = segments_for_config(str(cfg), now=now)
    assert seg.day == DAY
    assert seg.dawn.strftime("%H:%M") == "04:49"
    assert seg.complete is True


def test_segments_for_config_pre_dawn_previous_day(tmp_path):
    cfg = _write_config(tmp_path)
    now = datetime(2026, 6, 21, 3, 0, tzinfo=TZ)
    assert segments_for_config(str(cfg), now=now).day == date(2026, 6, 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solarsegments.py -v -k segments_for_config`
Expected: collection error — `ImportError: cannot import name 'segments_for_config'`

- [ ] **Step 3: Write minimal implementation**

Append to `kwallpaper/solarsegments.py`:

```python
def segments_for_config(config_path: str,
                        now: Optional[datetime] = None) -> Segments:
    """Segments for the configured location at ``now``.

    Loads latitude/longitude/timezone from the config file (normalized
    to defaults by ``load_config``).  ``now`` defaults to the current
    time in the configured timezone.
    """
    from kwallpaper.config import load_config

    config = load_config(config_path)
    loc = config.get("location", {})
    tz = ZoneInfo(loc.get("timezone", "America/Phoenix"))
    lat = float(loc.get("latitude", 33.4484))
    lon = float(loc.get("longitude", -112.074))
    if now is None:
        now = datetime.now(tz)
    return segments_for_now(now, tz, lat, lon)
```

(The `load_config` import is deferred so `solarsegments` stays importable without pulling the config module at import time.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: 48 passed

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/solarsegments.py tests/test_solarsegments.py
git commit -m "Add solarsegments.segments_for_config (config -> segments seam)"
```

---
### Task 7: Route `select_image_for_time_cli` to the sun model

**Files:**
- Modify: `kwallpaper/selection.py` (imports; `select_image_for_time_cli` config/now block + sun branch)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_solarsegments.py`, replace the import block:

```python
import json

from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    category_for,
    image_at,
    segments_for_config,
    segments_for_now,
    solar_segments,
)
```

with:

```python
import json
from pathlib import Path

from kwallpaper import selection, suntime
from kwallpaper import solarsegments
from kwallpaper.solarsegments import (
    IncompleteSegmentsError,
    Segments,
    category_for,
    image_at,
    segments_for_config,
    segments_for_now,
    solar_segments,
)
```

Append these helpers and tests:

```python
def _write_theme(tmp_path, n=16):
    """Theme dir with n images sun_01.jpg..sun_NN.jpg, all four lists [1..n]."""
    t = tmp_path / "theme"
    t.mkdir()
    (t / "theme.json").write_text(json.dumps({
        "displayName": "WDD",
        "imageFilename": "sun_*.jpg",
        "sunriseImageList": list(range(1, n + 1)),
        "dayImageList": list(range(1, n + 1)),
        "sunsetImageList": list(range(1, n + 1)),
        "nightImageList": list(range(1, n + 1)),
    }))
    for i in range(1, n + 1):
        (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    return t


class _FixedDT(datetime):
    """datetime stand-in with a controllable 'now'.

    IMPORTANT: when patching ``suntime.datetime`` (or
    ``selection.datetime``) with this subclass, the fake sun values must
    be ``_FixedDT`` instances: ``suntime.time_of_day_for`` does
    ``isinstance(x, datetime)`` and ``datetime`` resolves to the patched
    module global, so plain datetimes would fail the check.
    """
    FIXED = None

    @classmethod
    def now(cls, tz=None):
        return cls.FIXED if tz is None else cls.FIXED.astimezone(tz)


def _fake_sun():
    """Fixed 2026-06-21 Phoenix sun values (as _FixedDT instances)."""
    def t(hh, mm, ss, us):
        return _FixedDT(2026, 6, 21, hh, mm, ss, us, tzinfo=TZ)
    return {
        "dawn": t(4, 49, 43, 543358),
        "sunrise": t(5, 19, 14, 465394),
        "sunset": t(19, 41, 7, 732335),
        "dusk": t(20, 10, 38, 578189),
    }


def _fake_segments(day, tz, lat, lon):
    """Uniform synthetic segments (identical boundaries every day)."""
    def at(hh, mm, ss, us, d):
        return datetime(d.year, d.month, d.day, hh, mm, ss, us, tzinfo=tz)
    return Segments(
        day=day,
        dawn=at(4, 49, 43, 543358, day),
        golden_hour_end=at(5, 54, 55, 713299, day),
        golden_hour=at(19, 5, 26, 557453, day),
        dusk=at(20, 10, 38, 578189, day),
        next_dawn=at(4, 49, 43, 543358, day + timedelta(days=1)),
    )


def _patch_time_and_sun(monkeypatch, hh, mm, use_sun_model):
    """Freeze 'now' at 2026-06-21 hh:mm Phoenix and pin sun values.

    Patches BOTH the suntime and selection namespaces because
    selection.py imports _real_sun_data into its own namespace.
    """
    _FixedDT.FIXED = _FixedDT(2026, 6, 21, hh, mm, tzinfo=TZ)
    fake_sun = _fake_sun()
    fake_sun_data = lambda tz, lat, lon, date=None: dict(fake_sun)
    monkeypatch.setattr(selection, "datetime", _FixedDT)
    monkeypatch.setattr(suntime, "datetime", _FixedDT)
    monkeypatch.setattr(suntime, "_real_sun_data", fake_sun_data)
    monkeypatch.setattr(selection, "_real_sun_data", fake_sun_data)
    monkeypatch.setattr("kwallpaper.backup.save_daily_backup_schedule",
                        lambda *a, **k: None)
    if use_sun_model:
        monkeypatch.setattr(solarsegments, "solar_segments", _fake_segments)


@pytest.mark.parametrize("hhmm,expected", [
    ("04:30", "sun_16.jpg"),
    ("05:30", "sun_01.jpg"),
    ("12:00", "sun_08.jpg"),
    ("03:00", "sun_13.jpg"),
])
def test_cli_sun_model_selection(tmp_path, monkeypatch, hhmm, expected):
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path, model="sun")
    h, m = map(int, hhmm.split(":"))
    _patch_time_and_sun(monkeypatch, h, m, use_sun_model=True)
    result = selection.select_image_for_time_cli(str(t), str(cfg))
    assert Path(result).name == expected


@pytest.mark.parametrize("hhmm,expected", [
    ("04:30", "sun_02.jpg"),
    ("05:30", "sun_11.jpg"),
    ("12:00", "sun_12.jpg"),
    ("23:00", "sun_06.jpg"),
    ("00:00", "sun_08.jpg"),
    ("03:00", "sun_14.jpg"),
])
def test_cli_default_model_is_legacy(tmp_path, monkeypatch, hhmm, expected):
    """No suntime_model field -> legacy model, byte-identical results."""
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path)  # no suntime_model
    h, m = map(int, hhmm.split(":"))
    _patch_time_and_sun(monkeypatch, h, m, use_sun_model=False)
    result = selection.select_image_for_time_cli(str(t), str(cfg))
    assert Path(result).name == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_solarsegments.py -v -k "cli_sun_model or cli_default_model"`
Expected: the 4 `cli_sun_model` tests FAIL (sun_02/sun_11/sun_12/sun_14 returned instead of sun_16/sun_01/sun_08/sun_13 — the flag is ignored); the 6 `cli_default_model` tests PASS (they pin current behavior)

- [ ] **Step 3: Write minimal implementation**

In `kwallpaper/selection.py`, two edits:

Edit 1 — add the import after the `from kwallpaper.suntime import (...)` block:

```python
from kwallpaper.solarsegments import image_at, segments_for_config
```

Edit 2 — in `select_image_for_time_cli`, replace:

```python
    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        # Fallback to UTC if timezone not available
        now = datetime.now(ZoneInfo('UTC'))

    # Get time-of-day category
    time_of_day = detect_time_of_day_sun(config_path, now=now)
```

with:

```python
    try:
        config = load_config(config_path)
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        # Fallback to UTC if timezone not available
        config = {}
        now = datetime.now(ZoneInfo('UTC'))

    # Sun-position model (WDD-style): routed by scheduling.suntime_model.
    # NOTE: no fallback yet — added in Task 9.
    if config.get('scheduling', {}).get('suntime_model') == 'sun':
        seg = segments_for_config(config_path, now=now)
        _category, image_index = image_at(now, seg, theme_data)
        return _match_image_file(theme_path_obj, image_index, theme_data)

    # Get time-of-day category
    time_of_day = detect_time_of_day_sun(config_path, now=now)
```

(The `config = {}` in the except path is required: `config` would otherwise be unbound when the exception fires, and the new branch reads it unconditionally.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: all pass (58 = 48 + 10)

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/selection.py tests/test_solarsegments.py
git commit -m "Route select_image_for_time_cli to sun model when suntime_model=sun"
```

---

### Task 8: Route `select_image_for_specific_time` to the sun model

**Files:**
- Modify: `kwallpaper/selection.py` (`select_image_for_specific_time`)
- Test: `tests/test_solarsegments.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_solarsegments.py`:

```python
@pytest.mark.parametrize("hhmm,expected", [
    ("04:30", "sun_16.jpg"),
    ("05:30", "sun_01.jpg"),
    ("12:00", "sun_08.jpg"),
    ("03:00", "sun_13.jpg"),
])
def test_specific_time_sun_model_selection(tmp_path, monkeypatch, hhmm,
                                           expected):
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path, model="sun")
    h, m = map(int, hhmm.split(":"))
    _patch_time_and_sun(monkeypatch, h, m, use_sun_model=True)
    result = selection.select_image_for_specific_time(hhmm, str(t), str(cfg))
    assert Path(result).name == expected


@pytest.mark.parametrize("hhmm,expected", [
    ("04:30", "sun_02.jpg"),
    ("05:30", "sun_11.jpg"),
    ("12:00", "sun_12.jpg"),
    ("23:00", "sun_06.jpg"),
    ("00:00", "sun_08.jpg"),
    ("03:00", "sun_14.jpg"),
])
def test_specific_time_default_model_is_legacy(tmp_path, monkeypatch, hhmm,
                                               expected):
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path)  # no suntime_model
    h, m = map(int, hhmm.split(":"))
    _patch_time_and_sun(monkeypatch, h, m, use_sun_model=False)
    result = selection.select_image_for_specific_time(hhmm, str(t), str(cfg))
    assert Path(result).name == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_solarsegments.py -v -k specific_time`
Expected: the 4 `sun_model` tests FAIL (legacy results returned); the 6 `default_model` tests PASS

- [ ] **Step 3: Write minimal implementation**

In `kwallpaper/selection.py`, in `select_image_for_specific_time`:

Edit 1 — in the config-loading block, initialize `config` on failure (replace the inner `except Exception:` body):

```python
        try:
            config = load_config(config_path)
            timezone = config.get('location', {}).get(
                'timezone', 'America/Los_Angeles')
        except Exception:
            config = {}
            timezone = 'America/Los_Angeles'
```

Edit 2 — immediately after `theme_data = load_theme_data(theme_path_obj)`, insert:

```python
    # Sun-position model (WDD-style): routed by scheduling.suntime_model.
    # NOTE: no fallback yet — added in Task 9.
    if config.get('scheduling', {}).get('suntime_model') == 'sun':
        seg = segments_for_config(config_path, now=now)
        _category, image_index = image_at(now, seg, theme_data)
        return _match_image_file(theme_path_obj, image_index, theme_data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: all pass (68 = 58 + 10)

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/selection.py tests/test_solarsegments.py
git commit -m "Route select_image_for_specific_time to sun model when suntime_model=sun"
```

---

### Task 9: Legacy fallback when sun segments are incomplete

**Files:**
- Modify: `kwallpaper/selection.py` (wrap both sun branches in try/except)
- Test: `tests/test_solarsegments.py` (append)

The sun branches added in Tasks 7–8 currently raise `IncompleteSegmentsError` (polar day/night) or `ValueError` (empty image list) — with `suntime_model: "sun"`, a polar user would get a broken cycle. Wrap both branches so **any** failure (incomplete segments, empty list, astral unavailable, config hiccup) falls back to the legacy model for that selection, with a warning log.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_solarsegments.py`:

```python
def _polar_segments(day, tz, lat, lon):
    return Segments(day=day, dawn=None, golden_hour_end=None,
                    golden_hour=None, dusk=None, next_dawn=None)


def test_cli_sun_model_incomplete_falls_back_to_legacy(tmp_path, monkeypatch):
    """Polar/incomplete segments -> legacy model for that day."""
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path, model="sun")
    _patch_time_and_sun(monkeypatch, 12, 0, use_sun_model=False)
    monkeypatch.setattr(solarsegments, "solar_segments", _polar_segments)
    result = selection.select_image_for_time_cli(str(t), str(cfg))
    assert Path(result).name == "sun_12.jpg"  # legacy 12:00 result


def test_specific_time_sun_model_incomplete_falls_back_to_legacy(
        tmp_path, monkeypatch):
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path, model="sun")
    _patch_time_and_sun(monkeypatch, 12, 0, use_sun_model=False)
    monkeypatch.setattr(solarsegments, "solar_segments", _polar_segments)
    result = selection.select_image_for_specific_time("12:00", str(t),
                                                      str(cfg))
    assert Path(result).name == "sun_12.jpg"  # legacy 12:00 result


def test_cli_sun_model_empty_image_list_falls_back_to_legacy(
        tmp_path, monkeypatch):
    """Empty category list in the sun model -> legacy model, not crash."""
    t = _write_theme(tmp_path)
    (t / "theme.json").write_text(json.dumps({
        "displayName": "WDD",
        "imageFilename": "sun_*.jpg",
        "sunriseImageList": [],
        "dayImageList": list(range(1, 17)),
        "sunsetImageList": list(range(1, 17)),
        "nightImageList": list(range(1, 17)),
    }))
    cfg = _write_config(tmp_path, model="sun")
    _patch_time_and_sun(monkeypatch, 5, 30, use_sun_model=True)
    result = selection.select_image_for_time_cli(str(t), str(cfg))
    assert Path(result).name == "sun_11.jpg"  # legacy 05:30 result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_solarsegments.py -v -k "falls_back"`
Expected: 3 failed — `IncompleteSegmentsError` / `ValueError` propagate out of the selection functions

- [ ] **Step 3: Write minimal implementation**

In `kwallpaper/selection.py`, replace the sun branch in `select_image_for_time_cli` (from Task 7) with:

```python
    # Sun-position model (WDD-style): routed by scheduling.suntime_model.
    # Any failure (polar incomplete segments, empty image list, astral
    # unavailable) falls back to the legacy model below.
    if config.get('scheduling', {}).get('suntime_model') == 'sun':
        try:
            seg = segments_for_config(config_path, now=now)
            _category, image_index = image_at(now, seg, theme_data)
            return _match_image_file(theme_path_obj, image_index, theme_data)
        except Exception as e:
            logger.warning(
                "Sun-position model failed (%s); falling back to legacy", e)
```

and the sun branch in `select_image_for_specific_time` (from Task 8) with:

```python
    # Sun-position model (WDD-style): routed by scheduling.suntime_model.
    # Any failure (polar incomplete segments, empty image list, astral
    # unavailable) falls back to the legacy model below.
    if config.get('scheduling', {}).get('suntime_model') == 'sun':
        try:
            seg = segments_for_config(config_path, now=now)
            _category, image_index = image_at(now, seg, theme_data)
            return _match_image_file(theme_path_obj, image_index, theme_data)
        except Exception as e:
            logger.warning(
                "Sun-position model failed (%s); falling back to legacy", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_solarsegments.py -v`
Expected: all pass (71 = 68 + 3)

- [ ] **Step 5: Commit**

```bash
git add kwallpaper/selection.py tests/test_solarsegments.py
git commit -m "Fall back to legacy model when sun-position model fails"
```

---

### Task 10: `apply_theme` transparency + full-suite verification

**Files:**
- Test: `tests/test_solarsegments.py` (append)
- No production code changes in this task — `core.apply_theme` delegates image selection to the two routed entry points, so routing is transparent to it. This task pins that with tests.

- [ ] **Step 1: Write the tests**

In `tests/test_solarsegments.py`, replace the import line:

```python
from kwallpaper import selection, suntime
```

with:

```python
from kwallpaper import core, selection, suntime
```

Append these tests:

```python
def _patch_apply_theme_env(monkeypatch, tmp_path, cfg):
    """Patch core's collaborators; return a list capturing applied paths."""
    applied = []
    monkeypatch.setattr(core, "set_wallpaper",
                        lambda p: applied.append(p) or True)
    monkeypatch.setattr(core, "load_config",
                        lambda p: json.loads(Path(p).read_text()))
    monkeypatch.setattr(core, "save_config", lambda p, c: None)
    monkeypatch.setattr(core, "discover_themes",
                        lambda: [("theme", str(Path(cfg).parent / "theme"))])
    return applied


def test_apply_theme_routes_to_sun_model(tmp_path, monkeypatch):
    """apply_theme picks the sun-model image when configured; no core.py
    changes needed because it delegates to the routed entry points."""
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path, model="sun")
    data = json.loads(cfg.read_text())
    data["scheduling"]["daily_shuffle_enabled"] = False
    cfg.write_text(json.dumps(data))

    _patch_time_and_sun(monkeypatch, 12, 0, use_sun_model=True)
    applied = _patch_apply_theme_env(monkeypatch, tmp_path, cfg)

    result = core.apply_theme("theme", str(cfg))
    assert result.success
    assert Path(applied[0]).name == "sun_08.jpg"


def test_apply_theme_default_model_is_legacy(tmp_path, monkeypatch):
    t = _write_theme(tmp_path)
    cfg = _write_config(tmp_path)
    data = json.loads(cfg.read_text())
    data["scheduling"]["daily_shuffle_enabled"] = False
    cfg.write_text(json.dumps(data))

    _patch_time_and_sun(monkeypatch, 12, 0, use_sun_model=False)
    applied = _patch_apply_theme_env(monkeypatch, tmp_path, cfg)

    result = core.apply_theme("theme", str(cfg))
    assert result.success
    assert Path(applied[0]).name == "sun_12.jpg"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_solarsegments.py -v -k apply_theme`
Expected: 2 passed (they pass immediately — this is a transparency pin, not a new feature; if `test_apply_theme_routes_to_sun_model` fails, re-check that `core.apply_theme` still delegates to `select_image_for_time_cli`/`select_image_for_specific_time` rather than doing its own image math)

- [ ] **Step 3: Run the FULL test suite**

Run: `python -m pytest tests/ -q`
Expected: **156 + 73 = 229 passed** (156 pre-existing + 73 new tests across tasks 1–10: 4+4+13+25+2+10+10+3+2; if the exact new-test count differs, the requirement is: all pre-existing 156 pass and zero failures/errors)

- [ ] **Step 4: Commit**

```bash
git add tests/test_solarsegments.py
git commit -m "Pin apply_theme transparency to sun-model routing"
```

---

## Final verification (after Task 10)

- [ ] **Full suite green:** `python -m pytest tests/ -q` → all pass, zero failures
- [ ] **Manual smoke test (real astral, today's date):**

```bash
cd /home/admin/llama-cpp/projects/kwallpaper
python - <<'EOF'
from datetime import datetime
from zoneinfo import ZoneInfo
from kwallpaper.solarsegments import segments_for_now, category_for

tz = ZoneInfo("America/Phoenix")
now = datetime.now(tz)
seg = segments_for_now(now, tz, 33.4484, -112.074)
print("day:", seg.day)
print("dawn:", seg.dawn)
print("+6 AM:", seg.golden_hour_end)
print("+6 PM:", seg.golden_hour)
print("dusk:", seg.dusk)
print("next dawn:", seg.next_dawn)
print("complete:", seg.complete)
print("category now:", category_for(now, seg))
EOF
```

Expected: five sensible boundary times for today (dawn < +6 AM < +6 PM < dusk < next dawn), `complete: True`, and a category consistent with the local time of day.

- [ ] **Config backward-compat check:** load an old config (no `suntime_model`) and confirm `load_config` returns `scheduling.suntime_model == "legacy"` (covered by `test_normalize_config_fills_missing_suntime_model`).

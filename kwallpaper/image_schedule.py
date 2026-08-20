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

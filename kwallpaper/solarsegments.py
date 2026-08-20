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
from typing import Any, Callable, Dict, List, Optional, Tuple
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

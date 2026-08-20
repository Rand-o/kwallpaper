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

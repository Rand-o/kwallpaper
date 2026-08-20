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

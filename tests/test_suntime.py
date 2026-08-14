"""Tests pinning the unified suntime period model (phase 3).

These pin the *deliberate* differences between the four legacy time-math
copies, now collapsed into kwallpaper.suntime:

- category detection boundaries (period_boundaries / time_of_day_for)
- file-selector period math (image_period): day ends at dusk - 45 min
- index-selector period math (index_period): day ends at raw sunset,
  sunrise fallback ends at 06:45
"""
from datetime import datetime, timedelta, timezone

import pytest

from kwallpaper import suntime
from kwallpaper.suntime import (
    DURATION_DAWN_MINUTES,
    DURATION_DUSK_MINUTES,
    DURATION_IMAGE_9_MINUTES,
    DURATION_SUNRISE_MINUTES,
    DURATION_SUNSET_MINUTES,
    TRANSITION_OFFSET_MINUTES,
    index_period,
    image_index_for,
    image_period,
    period_boundaries,
    time_of_day_for,
)

TZ = timezone.utc


def _sun(dawn="07:07", sunrise="07:30", sunset="17:00", dusk="17:23",
         day=20260210):
    """Build a sun dict with tz-aware UTC datetimes (winter-day geometry)."""
    import calendar
    y, m, d = day // 10000, (day // 100) % 100, day % 100

    def t(hhmm):
        h, mi = map(int, hhmm.split(":"))
        return datetime(y, m, d, h, mi, tzinfo=TZ)

    return {
        "dawn": t(dawn),
        "sunrise": t(sunrise),
        "sunset": t(sunset),
        "dusk": t(dusk),
    }


def _at(hhmm, day=20260210):
    y, m, d = day // 10000, (day // 100) % 100, day % 100
    h, mi = map(int, hhmm.split(":"))
    return datetime(y, m, d, h, mi, tzinfo=TZ)


class TestConstants:
    def test_transition_offset(self):
        assert TRANSITION_OFFSET_MINUTES == 45

    def test_duration_constants(self):
        assert DURATION_DAWN_MINUTES == 30
        assert DURATION_SUNRISE_MINUTES == 6
        assert DURATION_SUNSET_MINUTES == 6
        assert DURATION_DUSK_MINUTES == 30
        assert DURATION_IMAGE_9_MINUTES == 30


class TestPeriodBoundaries:
    def test_boundaries(self):
        sun = _sun()
        b = period_boundaries(sun)
        assert b["night_end"] == sun["dawn"] - timedelta(minutes=30)
        assert b["sunrise_end"] == sun["sunrise"] + timedelta(minutes=45)
        assert b["dusk_start"] == sun["dusk"] - timedelta(minutes=45)
        assert b["night_spans_midnight"] is True  # dawn-30 < dusk

    def test_no_midnight_span(self):
        # dawn after dusk (e.g. summer in the southern hemisphere)
        sun = _sun(dawn="20:00", sunrise="20:30", sunset="07:00", dusk="07:23")
        b = period_boundaries(sun)
        assert b["night_spans_midnight"] is False


class TestTimeOfDayFor:
    def test_night(self):
        assert time_of_day_for(_at("03:00"), _sun()) == "night"

    def test_sunrise_start(self):
        assert time_of_day_for(_at("06:37"), _sun()) == "sunrise"

    def test_sunrise_end_boundary(self):
        # sunrise + 45 min is still sunrise (inclusive)
        assert time_of_day_for(_at("08:15"), _sun()) == "sunrise"

    def test_day(self):
        assert time_of_day_for(_at("08:16"), _sun()) == "day"
        assert time_of_day_for(_at("12:00"), _sun()) == "day"

    def test_day_ends_before_dusk_start(self):
        assert time_of_day_for(_at("16:37"), _sun()) == "day"

    def test_sunset(self):
        assert time_of_day_for(_at("16:38"), _sun()) == "sunset"
        assert time_of_day_for(_at("17:23"), _sun()) == "sunset"

    def test_after_dusk_is_night(self):
        assert time_of_day_for(_at("17:24"), _sun()) == "night"

    def test_none_values_fallback(self):
        sun = _sun()
        assert time_of_day_for(_at("12:00"), {**sun, "dawn": None}) == "night"
        assert time_of_day_for(_at("12:00"), {**sun, "sunrise": None}) == "sunrise"
        assert time_of_day_for(_at("12:00"), {**sun, "sunset": None}) == "day"
        assert time_of_day_for(_at("12:00"), {**sun, "dusk": None}) == "sunset"


class TestImagePeriodVsIndexPeriod:
    """Pin the deliberate differences between the file-selector and
    index-selector period math."""

    def test_day_file_uses_dusk_minus_45(self):
        sun = _sun()
        start, end = image_period("day", _at("12:00"), sun)
        assert end == sun["dusk"] - timedelta(minutes=45)

    def test_day_index_uses_raw_sunset(self):
        sun = _sun()
        start, end = index_period("day", _at("12:00"), sun)
        assert end == sun["sunset"]

    def test_day_start_matches(self):
        sun = _sun()
        fstart, _ = image_period("day", _at("12:00"), sun)
        istart, _ = index_period("day", _at("12:00"), sun)
        assert fstart == istart == sun["sunrise"] + timedelta(minutes=45)

    def test_sunrise_fallback_ends(self):
        now = _at("05:30")
        fstart, fend = image_period("sunrise", now, None)
        istart, iend = index_period("sunrise", now, None)
        # file selector falls back to 06:00, index selector to 06:45
        assert fend.hour == 6 and fend.minute == 0
        assert iend.hour == 6 and iend.minute == 45
        assert fstart == istart  # both 05:15

    def test_sunset_file_starts_at_dusk_minus_45(self):
        sun = _sun()
        start, end = image_period("sunset", _at("17:00"), sun)
        assert start == sun["dusk"] - timedelta(minutes=45)
        assert end == sun["dusk"]

    def test_sunset_index_starts_at_sunset(self):
        sun = _sun()
        start, end = index_period("sunset", _at("17:00"), sun)
        assert start == sun["sunset"]
        assert end == sun["dusk"]

    def test_night_periods_match(self):
        sun = _sun()
        fstart, fend = image_period("night", _at("03:00"), sun)
        istart, iend = index_period("night", _at("03:00"), sun)
        assert fstart == istart == sun["dusk"]
        # Night spans midnight: period end is dawn-30min on the NEXT day
        assert fend == iend == sun["dawn"] - timedelta(minutes=30) + timedelta(days=1)


class TestImageIndexFor:
    def test_sunrise_index_math(self):
        sun = _sun()
        # sunrise period: 06:37 -> 08:15 (100 min)
        at = _at("07:30")  # 53 min in -> position 0.53 -> idx 1 of [2,3,4] => 3
        assert image_index_for("sunrise", at, sun, [2, 3, 4]) == 3

    def test_day_index_offset_5(self):
        sun = _sun()
        # day period (index variant): 08:15 -> 17:00 (525 min)
        at = _at("08:15")  # position 0 -> 0 + 5 = 5
        assert image_index_for("day", at, sun, [5, 6, 7, 8, 9]) == 5

    def test_sunset_index_offset_10(self):
        sun = _sun()
        # index variant: sunset period starts at raw sunset (17:00)
        at = _at("17:00")  # position 0 -> 0 + 10 = 10
        assert image_index_for("sunset", at, sun, [10, 11, 12, 13]) == 10

    def test_night_old_format(self):
        sun = _sun()
        # night: 17:23 -> 06:37 next day (674 min); first 3 images over
        # 644 min (period minus 30). 00:00 is ~457 min in -> 0.71 -> 16
        assert image_index_for("night", _at("00:00"), sun,
                               [14, 15, 16, 1]) == 16
        # 18:00 is 37 min in -> 0.057 -> 14
        assert image_index_for("night", _at("18:00"), sun,
                               [14, 15, 16, 1]) == 14
        # 02:00 -> (now+1d - dusk) = 8h37m / 10h44m = 0.651 -> 16
        assert image_index_for("night", _at("02:00"), sun,
                               [14, 15, 16, 1]) == 16
        # 20:00 -> 2h37m / 10h44m = 0.243 -> 14
        assert image_index_for("night", _at("20:00"), sun,
                               [14, 15, 16, 1]) == 14
        # 06:30 is inside the night period (before 06:37) => image 16
        assert image_index_for("night", _at("06:30"), sun,
                               [14, 15, 16, 1]) == 16

    def test_night_new_format_thirds(self):
        sun = _sun()
        # new format [14,15,16]: thirds of the full period
        assert image_index_for("night", _at("18:00"), sun,
                               [14, 15, 16]) == 14
        # 00:00 -> 457/674 = 0.678 -> image 15 (thirds: <0.333=14, <0.666=15)
        assert image_index_for("night", _at("00:00"), sun,
                               [14, 15, 16]) == 15
        # 03:00 -> 577/674 = 0.856 -> 16
        assert image_index_for("night", _at("03:00"), sun,
                               [14, 15, 16]) == 16
        # 06:30 is inside the night period (before 06:37) -> 16
        assert image_index_for("night", _at("06:30"), sun,
                               [14, 15, 16]) == 16

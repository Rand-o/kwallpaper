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

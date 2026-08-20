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

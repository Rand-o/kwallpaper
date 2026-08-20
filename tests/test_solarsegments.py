"""Tests for the WDD-style sun-position segment model (phase 1).

Reference geometry: Phoenix (33.4484, -112.074, America/Phoenix),
2026-06-21.  Boundary values are pinned against astral 3.2 and must not
drift without an intentional astral upgrade.
"""
from datetime import date, datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

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

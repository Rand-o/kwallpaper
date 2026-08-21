"""GUI smoke tests for the Phase 3 time-model toggle + schedule preview.

Runs offscreen (QT_QPA_PLATFORM=offscreen, set before importing PyQt6
— same pattern as tests/test_preview_stress.py).  The window is built
with a real temp config; solar math is monkeypatched so the tests are
deterministic and do not depend on the real date.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem

TZ = ZoneInfo("America/Phoenix")
D = date(2026, 6, 21)

THEME = {
    "sunriseImageList": [1, 2, 3, 4],
    "dayImageList": [5, 6, 7, 8, 9],
    "sunsetImageList": [10, 11, 12, 13],
    "nightImageList": [14, 15, 16],
    "imageFilename": "sun_*.jpg",
}


def dt(h, m=0, s=0, day=D):
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=TZ)


def _seg(day, complete=True):
    from kwallpaper.solarsegments import Segments
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


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _write_config(tmp_path, model="legacy", safety_interval=600):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "location": {"timezone": "America/Phoenix",
                     "latitude": 33.4484, "longitude": -112.074},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": False,
                       "suntime_model": model,
                       "safety_interval": safety_interval},
        # Disable the 1 s auto-start timer: its QTimer.singleShot
        # outlives window close and would fire (starting a real
        # scheduler) mid-suite, racing with tests that swap
        # window.sched for a fake.
        "autostart": {"start_scheduler_on_launch": False},
        "theme": {"last_applied_image": ""},
    }))
    return str(cfg)


def _make_theme(tmp_path, name="TestTheme"):
    tdir = tmp_path / name
    tdir.mkdir(exist_ok=True)
    (tdir / "theme.json").write_text(json.dumps(THEME))
    for i in range(1, 17):
        (tdir / f"sun_{i:02d}.jpg").write_bytes(b"x")
    return tdir


@pytest.fixture
def window(tmp_path, qapp, monkeypatch):
    """A real window with one fake theme and deterministic segments."""
    import wallpaper_gui
    import kwallpaper.image_schedule as im

    cfg = _write_config(tmp_path)
    tdir = _make_theme(tmp_path)
    monkeypatch.setattr(wallpaper_gui, "discover_themes",
                        lambda: [(tdir.name, str(tdir))])
    monkeypatch.setattr(im, "solar_segments",
                        lambda day, tz, lat, lon: _seg(day))
    w = wallpaper_gui.WallpaperChangerWindow(config_path=cfg)
    w.show()
    yield w
    w.close()


def _select_theme(w):
    w.themes.load_themes()
    assert w.themes.theme_list.count() == 1
    item = w.themes.theme_list.item(0)
    w.themes.theme_list.setCurrentItem(item)


def _spin(app, ms=300):
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()


class TestSettingsTimeModel:
    def test_loaded_from_config_sun(self, window):
        assert window.settings.time_model.currentIndex() == 0  # default legacy
        # Rewrite config to sun and reload the page.
        import json as _json
        cfg = _json.loads(Path(window._cfg).read_text())
        cfg["scheduling"]["suntime_model"] = "sun"
        Path(window._cfg).write_text(_json.dumps(cfg))
        window.settings._load()
        assert window.settings.time_model.currentIndex() == 1

    def test_save_persists_model_and_preserves_safety_interval(self, window):
        window.settings.time_model.setCurrentIndex(1)  # sun
        window.settings._save()
        cfg = json.loads(Path(window._cfg).read_text())
        s = cfg["scheduling"]
        assert s["suntime_model"] == "sun"
        assert s["safety_interval"] == 600      # survived the GUI save
        assert s["cycle_interval"] == 60        # existing fields intact

    def test_save_triggers_scheduler_reload_and_preview_refresh(self, window, monkeypatch):
        import wallpaper_gui
        calls = []
        # Fake a running scheduler so the hot-reload branch executes.
        class _FakeSched:
            def is_running(self):
                return True
            def start(self):
                pass
            def stop(self):
                pass
            class _Mgr:
                def reload_cycle_interval(self):
                    calls.append("reload")
                    return True
                def stop(self, wait=True):
                    pass
            scheduler = _Mgr()
        window.sched = _FakeSched()
        monkeypatch.setattr(
            window.themes.schedule_preview, "refresh",
            lambda cfg, tdir: calls.append("preview"))
        window.settings.time_model.setCurrentIndex(1)
        window.settings._save()
        assert calls == ["reload", "preview"]


class TestSegmentType:
    def test_mapping(self):
        from kwallpaper.schedule_preview import segment_type_for
        from kwallpaper.solarsegments import Segments
        # Realistic geometry: morning golden ends 06:27, evening
        # golden starts 18:35, dusk 19:19.
        seg = Segments(day=D, dawn=dt(5, 28), golden_hour_end=dt(6, 27),
                       golden_hour=dt(18, 35), dusk=dt(19, 19),
                       next_dawn=dt(5, 28, day=D + timedelta(days=1)))
        assert segment_type_for(dt(0, 0), seg) == "night"
        assert segment_type_for(dt(4, 59), seg) == "night"
        assert segment_type_for(dt(5, 28), seg) == "sunrise"
        assert segment_type_for(dt(6, 26), seg) == "sunrise"
        assert segment_type_for(dt(6, 27), seg) == "day"
        assert segment_type_for(dt(12, 0), seg) == "day"
        assert segment_type_for(dt(18, 35), seg) == "sunset"
        assert segment_type_for(dt(19, 18), seg) == "sunset"
        assert segment_type_for(dt(19, 19), seg) == "night"   # dusk
        assert segment_type_for(dt(23, 59), seg) == "night"

    def test_incomplete_segments_neutral(self):
        from kwallpaper.schedule_preview import segment_type_for
        assert segment_type_for(dt(12, 0), _seg(D, complete=False)) == "day"
        assert segment_type_for(dt(12, 0), None) == "day"


class TestSchedulePreviewWidget:
    def test_empty_state_paints(self, window, qapp):
        w = window.themes.schedule_preview
        # The window auto-selects the first theme on load; let that
        # worker settle, then force the no-selection state to test the
        # empty notice.
        _spin(qapp, 300)
        w.clear()
        assert w._state == "empty"
        w.show()
        w.resize(800, w.height())
        w.grab()  # force a paint
        assert w._state == "empty"

    def test_legacy_schedule_shows_notice(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ThemeSchedule
        w = window.themes.schedule_preview
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="legacy", now=dt(12, 0),
                          segments=None, entries=()),
            w._token.version)
        qapp.processEvents()
        assert w._state == "legacy"
        w.grab()

    def test_stale_result_rejected(self, window, qapp):
        from kwallpaper.image_schedule import ThemeSchedule
        w = window.themes.schedule_preview
        # Let the auto-selection worker settle, then establish a known
        # empty baseline (the window auto-selects a theme on load).
        _spin(qapp, 300)
        w.clear()
        v = w._token.version
        w._bump()  # simulate a newer refresh superseding the old worker
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="legacy", now=dt(12, 0),
                          segments=None, entries=()),
            v)
        qapp.processEvents()
        assert w._state == "empty"  # stale result dropped

    def test_ready_paints_with_fake_schedule(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (
            ScheduleEntry(start=dt(0, 0), end=dt(1, 20), image=15, path=""),
            ScheduleEntry(start=dt(5, 0), end=dt(5, 3, 45), image=1, path=""),
            ScheduleEntry(start=dt(18, 0), end=dt(21, 40), image=14, path=""),
        )
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        assert w._state == "ready"
        w.show()
        w.resize(800, w.height())
        w.grab()

    def test_footer_shows_now_when_ready(self, window, qapp):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (
            ScheduleEntry(start=dt(0, 0), end=dt(1, 20), image=15, path=""),
            ScheduleEntry(start=dt(5, 0), end=dt(5, 3, 45), image=1, path=""),
            ScheduleEntry(start=dt(18, 0), end=dt(21, 40), image=14, path=""),
        )
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        w.show()
        w.resize(800, w.height())
        qapp.processEvents()
        # Force now into a known window (18:00–21:40, image 14).
        w._now = dt(19, 0)
        w._update_footer()
        assert "Now:" in w._foot.text()
        assert "image 14" in w._foot.text()

    def test_hover_updates_footer(self, window, qapp):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (ScheduleEntry(start=dt(0, 0), end=dt(23, 59), image=7,
                                 path=""),)
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        w.show()
        w.resize(800, w.height())
        qapp.processEvents()
        # Hover mid-bar → the single all-day entry.
        w._show_entry_at(w._bar.width() // 2)
        assert "image 7" in w._foot.text()
        assert "00:00" in w._foot.text()
        # Leave → back to the Now line.
        w._reset_footer()
        assert "Now:" in w._foot.text()

    def test_marker_x_position(self, window, qapp):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (ScheduleEntry(start=dt(0, 0), end=dt(23, 59), image=1,
                                 path=""),)
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        w.show()
        w.resize(800, w.height())
        w._now = dt(12, 0)
        # 12:00 is exactly half of a 24h day → middle of the bar.
        x = w._bar._x_for(dt(12, 0))
        assert abs(x - w._bar.width() // 2) <= 1

    def test_date_change_recomputes(self, window, qapp, monkeypatch):
        from kwallpaper.image_schedule import ScheduleEntry, ThemeSchedule
        w = window.themes.schedule_preview
        entries = (ScheduleEntry(start=dt(0, 0), end=dt(23, 59), image=1,
                                 path=""),)
        w._on_schedule_ready(
            ThemeSchedule(date=D, tz=TZ, model="sun", now=dt(12, 0),
                          segments=_seg(D), entries=entries),
            w._token.version)
        qapp.processEvents()
        assert w._state == "ready"
        # Simulate "now" on the next day → the tick must recompute.
        calls = []
        monkeypatch.setattr(w, "refresh",
                            lambda cfg, tdir: calls.append((cfg, tdir)))
        w._config_path = "/cfg"
        w._theme_dir = "/theme"
        w._now = dt(12, 0, day=D + timedelta(days=1))
        w._on_tick()
        assert calls == [("/cfg", "/theme")]

    def test_updates_on_model_toggle(self, window, qapp, monkeypatch):
        """End-to-end: selecting a theme in legacy mode shows the notice;
        switching the model to sun and saving shows the timeline."""
        import kwallpaper.image_schedule as im
        _select_theme(window)
        w = window.themes.schedule_preview
        qapp.processEvents()
        # Legacy mode (config default): the worker returns a legacy
        # schedule → notice state.
        _spin(qapp, 500)
        assert w._state == "legacy"

        # Switch to sun and save (hot path: persist + preview refresh).
        window.settings.time_model.setCurrentIndex(1)
        window.settings._save()
        _spin(qapp, 1500)
        assert w._state == "ready"
        assert len(w._schedule.entries) == 17
        assert w._schedule.entries[0].image == 15

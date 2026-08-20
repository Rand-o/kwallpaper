"""Tests for Phase 2 event-driven scheduling.

Covers: skip-if-unchanged (Task 5), sun-mode start() wiring (Task 6),
and the re-arm sequence / interval fallback (Task 7).

The apscheduler guard mirrors tests/test_scheduler.py so the suite runs
in environments without apscheduler installed (the Flatpak bundles it).
"""
import json
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

if "apscheduler" not in sys.modules:
    try:
        import apscheduler  # noqa: F401
    except ImportError:
        _aps = types.ModuleType("apscheduler")
        _schedulers = types.ModuleType("apscheduler.schedulers")
        _background = types.ModuleType("apscheduler.schedulers.background")
        _triggers = types.ModuleType("apscheduler.triggers")
        _interval = types.ModuleType("apscheduler.triggers.interval")
        _date = types.ModuleType("apscheduler.triggers.date")
        _background.BackgroundScheduler = object
        _interval.IntervalTrigger = object
        _date.DateTrigger = object
        _schedulers.background = _background
        _triggers.interval = _interval
        _triggers.date = _date
        _aps.schedulers = _schedulers
        _aps.triggers = _triggers
        sys.modules.update({
            "apscheduler": _aps,
            "apscheduler.schedulers": _schedulers,
            "apscheduler.schedulers.background": _background,
            "apscheduler.triggers": _triggers,
            "apscheduler.triggers.interval": _interval,
            "apscheduler.triggers.date": _date,
        })

from kwallpaper import cli as cli_module
from kwallpaper import core as core_module
from kwallpaper import scheduler as scheduler_module
from kwallpaper.scheduler import SchedulerManager

TZ = ZoneInfo("America/Phoenix")
FIXED_NEXT = datetime(2026, 8, 18, 12, 0, tzinfo=TZ)


def _make_manager(cfg, running=True):
    mgr = SchedulerManager(config_path=cfg)
    mgr._is_running = running
    return mgr


def _write_cycle_env(tmp_path, monkeypatch):
    """Theme dir + config for run_cycle_command / run_change_command
    tests.  Returns (cfg_path, selected_image_path).  The selected image
    is pinned by patching select_image_for_time_cli, so no real image
    selection or D-Bus call happens."""
    themes = tmp_path / "themes"
    t = themes / "TestTheme"
    t.mkdir(parents=True)
    (t / "theme.json").write_text(json.dumps({
        "displayName": "Test",
        "imageFilename": "sun_*.jpg",
        "sunriseImageList": [1, 2, 3, 4],
        "dayImageList": [5, 6, 7, 8, 9],
        "sunsetImageList": [10, 11, 12, 13],
        "nightImageList": [14, 15, 16],
    }))
    for i in range(1, 17):
        (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    monkeypatch.setattr(cli_module, "DEFAULT_THEMES_DIR", themes)
    monkeypatch.setattr(cli_module, "get_current_wallpaper", lambda: None)
    monkeypatch.setattr(cli_module, "check_day_passed", lambda *a: False)
    monkeypatch.setattr(cli_module, "select_image_for_time_cli",
                        lambda theme, cfg: str(t / "sun_07.jpg"))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True},
        "theme": {"last_applied": "TestTheme", "last_applied_image": ""},
    }))
    return str(cfg), str(t / "sun_07.jpg")


class TestSkipIfUnchanged:
    def test_cycle_skips_when_unchanged(self, tmp_path, monkeypatch, capsys):
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        data = json.loads(Path(cfg).read_text())
        data["theme"]["last_applied_image"] = selected
        Path(cfg).write_text(json.dumps(data))
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 0
        assert calls == []  # no D-Bus call at all
        out = capsys.readouterr().out
        assert "No change: already showing sun_07.jpg" in out

    def test_cycle_applies_and_persists(self, tmp_path, monkeypatch, capsys):
        # Empty last_applied_image (fresh install) -> apply + persist.
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 0
        assert calls == [selected]
        out = capsys.readouterr().out
        assert "Changed wallpaper to sun_07.jpg" in out
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == selected

    def test_cycle_failed_change_does_not_persist(self, tmp_path, monkeypatch):
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        monkeypatch.setattr(cli_module, "change_wallpaper", lambda p: False)
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_cycle_command(args) == 1
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == ""

    def test_change_command_persists_after_success(self, tmp_path, monkeypatch):
        # run_change_command is an explicit user action: it always
        # applies, and it persists the last-applied image on success.
        cfg, selected = _write_cycle_env(tmp_path, monkeypatch)
        t = tmp_path / "themes" / "TestTheme"
        calls = []
        monkeypatch.setattr(cli_module, "change_wallpaper",
                            lambda p: calls.append(p) or True)
        monkeypatch.setattr(cli_module, "resolve_theme_path", lambda p: p)
        monkeypatch.setattr(cli_module, "detect_time_of_day_sun",
                            lambda *a, **k: "day")
        args = SimpleNamespace(theme_path=str(t), config=cfg, time=None,
                               monitor=False)
        assert cli_module.run_change_command(args) == 0
        assert calls == [selected]
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == selected

    def test_apply_theme_persists_last_applied_image(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        t = themes / "TestTheme"
        t.mkdir(parents=True)
        (t / "theme.json").write_text(json.dumps({
            "displayName": "Test",
            "imageFilename": "sun_*.jpg",
            "sunriseImageList": [1, 2, 3, 4],
            "dayImageList": [5, 6, 7, 8, 9],
            "sunsetImageList": [10, 11, 12, 13],
            "nightImageList": [14, 15, 16],
        }))
        for i in range(1, 17):
            (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": False},
        }))
        monkeypatch.setattr(core_module, "set_wallpaper", lambda p: True)
        monkeypatch.setattr(core_module, "detect_time_of_day_sun",
                            lambda *a, **k: "day")
        monkeypatch.setattr(core_module, "select_image_for_time_cli",
                            lambda theme, cfg_path: str(t / "sun_07.jpg"))
        monkeypatch.setattr(core_module, "load_config",
                            lambda p: json.loads(Path(p).read_text()))
        monkeypatch.setattr(core_module, "save_config",
                            lambda p, c: Path(p).write_text(json.dumps(c)))

        result = core_module.apply_theme(str(t), str(cfg))
        assert result.success
        saved = json.loads(Path(cfg).read_text())
        assert saved["theme"]["last_applied_image"] == str(t / "sun_07.jpg")

    def test_apply_theme_failed_wallpaper_does_not_persist(self, tmp_path, monkeypatch):
        themes = tmp_path / "themes"
        t = themes / "TestTheme"
        t.mkdir(parents=True)
        (t / "theme.json").write_text(json.dumps({
            "displayName": "Test",
            "imageFilename": "sun_*.jpg",
            "sunriseImageList": [1, 2, 3, 4],
            "dayImageList": [5, 6, 7, 8, 9],
            "sunsetImageList": [10, 11, 12, 13],
            "nightImageList": [14, 15, 16],
        }))
        for i in range(1, 17):
            (t / f"sun_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": False},
        }))
        monkeypatch.setattr(core_module, "set_wallpaper", lambda p: False)
        monkeypatch.setattr(core_module, "load_config",
                            lambda p: json.loads(Path(p).read_text()))
        monkeypatch.setattr(core_module, "save_config",
                            lambda p, c: Path(p).write_text(json.dumps(c)))

        result = core_module.apply_theme(str(t), str(cfg))
        assert not result.success
        saved = json.loads(Path(cfg).read_text())
        assert saved.get("theme", {}).get("last_applied_image", "") == ""


@pytest.fixture
def cfg_sun(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True, "suntime_model": "sun"},
    }))
    return str(p)


@pytest.fixture
def cfg_legacy(tmp_path):
    # Explicit legacy model (Phase 4: the default is now "sun").
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "version": 2,
        "location": {"latitude": 33.4, "longitude": -112.0,
                     "timezone": "America/Phoenix"},
        "scheduling": {"cycle_interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": True,
                       "suntime_model": "legacy"},
    }))
    return str(p)


class TestSunModeStart:
    def test_sun_mode_start_arms_one_shot_and_safety(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT) as nct:
            assert mgr.start() is True
            calls = {c.kwargs.get("id"): c
                     for c in bs.return_value.add_job.call_args_list}
            assert set(calls) == {"cycle_task", "safety_task"}
            # safety net: 600s interval (default)
            safety = calls["safety_task"]
            assert safety.kwargs["trigger"] is it.return_value
            assert it.call_args.kwargs.get("seconds") == 600
            # one-shot: DateTrigger at the computed instant, 1-day grace
            one = calls["cycle_task"]
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT
            assert one.kwargs["misfire_grace_time"] == 86400
            assert one.kwargs["replace_existing"] is True
            nct.assert_called_once_with(cfg_sun)
        mgr.scheduler = None
        mgr._is_running = False

    def test_legacy_mode_start_unchanged(self, cfg_legacy):
        mgr = _make_manager(cfg_legacy, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config") as nct:
            assert mgr.start() is True
            calls = {c.kwargs.get("id"): c
                     for c in bs.return_value.add_job.call_args_list}
            assert set(calls) == {"cycle_task"}
            assert it.call_args.kwargs.get("seconds") == 60
            assert calls["cycle_task"].kwargs["trigger"] is it.return_value
            dt.assert_not_called()
            nct.assert_not_called()
        mgr.scheduler = None
        mgr._is_running = False

    def test_sun_mode_custom_safety_interval(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": True,
                           "daily_shuffle_enabled": True,
                           "suntime_model": "sun", "safety_interval": 120},
        }))
        mgr = _make_manager(str(p), running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            assert mgr.start() is True
            assert it.call_args.kwargs.get("seconds") == 120
        mgr.scheduler = None
        mgr._is_running = False

    def test_sun_mode_run_cycle_disabled_no_jobs(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({
            "version": 2,
            "location": {"latitude": 33.4, "longitude": -112.0,
                         "timezone": "America/Phoenix"},
            "scheduling": {"cycle_interval": 60, "run_cycle": False,
                           "daily_shuffle_enabled": True,
                           "suntime_model": "sun"},
        }))
        mgr = _make_manager(str(p), running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs, \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "IntervalTrigger"):
            assert mgr.start() is False
            bs.return_value.add_job.assert_not_called()
        mgr.scheduler = None
        mgr._is_running = False


class TestRearmSequence:
    def test_run_rearms_one_shot(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT) as nct, \
             patch.object(scheduler_module, "run_cycle_command",
                          return_value=0):
            mgr._run_cycle_task()
            nct.assert_called_once_with(cfg_sun)
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT
            ids = [c.kwargs.get("id")
                   for c in mgr.scheduler.add_job.call_args_list]
            assert ids == ["cycle_task"]

    def test_lock_skipped_run_still_rearms(self, cfg_sun):
        # The triggering one-shot was consumed by APScheduler even though
        # the run was skipped by the lock — the re-arm must still happen.
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        lock = MagicMock()
        lock.acquire.return_value = False
        mgr._lock = lock
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            mgr._run_cycle_task()
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT

    def test_incomplete_segments_interval_fallback(self, cfg_sun):
        from kwallpaper.solarsegments import IncompleteSegmentsError
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        messages = []
        mgr.log_callback = messages.append
        with patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          side_effect=IncompleteSegmentsError("polar day")), \
             patch.object(scheduler_module, "run_cycle_command",
                          return_value=0):
            mgr._run_cycle_task()
            assert it.call_args.kwargs.get("seconds") == 60
            dt.assert_not_called()
            ids = [c.kwargs.get("id")
                   for c in mgr.scheduler.add_job.call_args_list]
            assert ids == ["cycle_task"]
            assert any("falling back" in m for m in messages)

    def test_legacy_run_does_not_rearm(self, cfg_legacy):
        mgr = _make_manager(cfg_legacy, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "run_cycle_command",
                          return_value=0), \
             patch.object(scheduler_module,
                          "next_change_time_for_config") as nct:
            mgr._run_cycle_task()
            nct.assert_not_called()
            mgr.scheduler.add_job.assert_not_called()

    def test_reload_interval_sun_mode_rearms(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(scheduler_module, "DateTrigger") as dt, \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            assert mgr.reload_cycle_interval() is True
            assert dt.call_args.kwargs.get("run_date") is FIXED_NEXT

    def test_safety_tick_runs_shuffle_check(self, cfg_sun):
        # The safety tick runs the same _run_cycle_task, so the daily
        # shuffle check (first thing inside run_cycle_command) still runs
        # on every tick.
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        with patch.object(cli_module, "run_change_command",
                          return_value=0) as change, \
             patch.object(cli_module, "check_day_passed",
                          lambda *a: True), \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            mgr._run_cycle_task()
            change.assert_called_once()
            called_args = change.call_args.args[0]
            assert called_args.config == cfg_sun
            assert called_args.theme_path is None
            assert called_args.time is None


class TestModelSwitchReload:
    """Live model switches via reload_cycle_interval (Phase 3 GUI)."""

    def test_legacy_to_sun_adds_safety_task(self, cfg_legacy):
        mgr = _make_manager(cfg_legacy, running=True)
        mgr.scheduler = MagicMock()
        # Simulate a running legacy scheduler: interval cycle job, no
        # safety job.
        mgr._tasks = {'cycle': {'interval': 60, 'type': 'interval'}}
        # Switch to sun in the config the manager was built with.
        cfg = json.loads(Path(cfg_legacy).read_text())
        cfg["scheduling"]["suntime_model"] = "sun"
        Path(cfg_legacy).write_text(json.dumps(cfg))
        with patch.object(scheduler_module, "IntervalTrigger") as it, \
             patch.object(scheduler_module, "DateTrigger"), \
             patch.object(scheduler_module, "next_change_time_for_config",
                          return_value=FIXED_NEXT):
            assert mgr.reload_cycle_interval() is True
        assert 'safety' in mgr._tasks
        assert 'cycle' in mgr._tasks  # re-armed one-shot
        assert it.call_args.kwargs.get("seconds") == 600  # safety interval

    def test_sun_to_legacy_removes_safety_task(self, cfg_sun):
        mgr = _make_manager(cfg_sun, running=True)
        mgr.scheduler = MagicMock()
        # Simulate a running sun-mode scheduler: one-shot cycle job +
        # safety job.
        mgr._tasks = {'cycle': {'next_change': FIXED_NEXT.isoformat(),
                                'type': 'date'},
                      'safety': {'interval': 600, 'type': 'interval'}}
        # Switch to legacy in the config the manager was built with.
        cfg = json.loads(Path(cfg_sun).read_text())
        cfg["scheduling"]["suntime_model"] = "legacy"
        Path(cfg_sun).write_text(json.dumps(cfg))
        with patch.object(scheduler_module, "IntervalTrigger") as it:
            assert mgr.reload_cycle_interval() is True
        assert 'safety' not in mgr._tasks
        assert 'cycle' in mgr._tasks  # interval job re-added
        assert it.call_args.kwargs.get("seconds") == 60  # cycle interval

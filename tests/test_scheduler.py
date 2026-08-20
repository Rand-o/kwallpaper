"""Tests for the scheduler.

Pins the behaviour contract:
- only the cycle task is scheduled (interval trigger); the daily shuffle
  is checked inside the cycle run (no midnight cron job)
- the cycle run performs the daily shuffle when the local date differs
  from the persisted last_change_date
- per-run results are delivered to the GUI log callback, not print
"""
import logging
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# APScheduler is a GUI/runtime dependency (bundled in the Flatpak) and is
# not installed in the bare test environment.  Stub it so the scheduler
# module imports cleanly; tests that exercise start() patch the classes
# directly.
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

from kwallpaper import scheduler as scheduler_module
from kwallpaper import cli as cli_module
from kwallpaper.scheduler import SchedulerManager


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("""{
  "location": {"latitude": 35.0, "longitude": -112.0, "timezone": "UTC"},
  "scheduling": {"cycle_interval": 1, "daily_shuffle_enabled": true, "run_cycle": true, "suntime_model": "legacy"}
}""")
    return str(p)


def _make_manager(cfg, running=True):
    mgr = SchedulerManager(config_path=cfg)
    mgr._is_running = running
    return mgr


class TestTaskScheduling:
    def test_only_cycle_task_is_scheduled(self, cfg):
        mgr = _make_manager(cfg, running=False)
        with patch.object(scheduler_module, "APScheduler_AVAILABLE", True, create=True), \
             patch.object(scheduler_module, "BackgroundScheduler") as bs:
            instance = bs.return_value
            with patch.object(scheduler_module, "IntervalTrigger") as interval:
                assert mgr.start() is True
                jobs = {c.kwargs.get("id") for c in instance.add_job.call_args_list}
                assert jobs == {"cycle_task"}
                interval.assert_called()
                assert interval.call_args.kwargs.get("seconds") == 1
        mgr.scheduler = None
        mgr._is_running = False

    def test_cycle_task_skipped_when_disabled(self, cfg):
        import json
        data = json.loads(Path(cfg).read_text())
        data["scheduling"]["run_cycle"] = False
        Path(cfg).write_text(json.dumps(data))
        mgr = _make_manager(cfg, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs:
            instance = bs.return_value
            with patch.object(scheduler_module, "IntervalTrigger"):
                assert mgr.start() is False
                instance.add_job.assert_not_called()
        mgr.scheduler = None
        mgr._is_running = False


class TestCycleDailyShuffle:
    def test_new_day_triggers_shuffle_on_cycle(self, cfg):
        """A cycle run shuffles when the local date differs from the
        persisted last_change_date (covers missed midnights, reboots,
        suspend)."""
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        with patch.object(cli_module, "run_change_command", return_value=0) as change, \
             patch.object(cli_module, "check_day_passed", return_value=True):
            assert cli_module.run_cycle_command(args) == 0
            change.assert_called_once_with(args)

    def test_same_day_does_not_shuffle(self, cfg):
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        with patch.object(cli_module, "run_change_command") as change, \
             patch.object(cli_module, "check_day_passed", return_value=False), \
             patch.object(cli_module, "run_change_command", return_value=0), \
             patch.object(cli_module, "get_current_wallpaper", return_value=None), \
             patch.object(cli_module, "change_wallpaper", return_value=True):
            # last_applied empty + no wallpaper -> cycle falls through to
            # its normal (error) path without touching the shuffler
            assert cli_module.run_cycle_command(args) == 1
            change.assert_not_called()

    def test_shuffle_disabled_skips_check(self, cfg):
        import json
        data = json.loads(Path(cfg).read_text())
        data["scheduling"]["daily_shuffle_enabled"] = False
        Path(cfg).write_text(json.dumps(data))
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        with patch.object(cli_module, "run_change_command") as change, \
             patch.object(cli_module, "check_day_passed", return_value=True), \
             patch.object(cli_module, "get_current_wallpaper", return_value=None), \
             patch.object(cli_module, "change_wallpaper", return_value=True):
            assert cli_module.run_cycle_command(args) == 1
            change.assert_not_called()

    def test_failed_shuffle_still_returns_error(self, cfg):
        args = SimpleNamespace(theme_path=None, config=cfg, time=None,
                               monitor=False)
        with patch.object(cli_module, "run_change_command", return_value=1) as change, \
             patch.object(cli_module, "check_day_passed", return_value=True):
            assert cli_module.run_cycle_command(args) == 1
            change.assert_called_once_with(args)


class TestLogCallback:
    def test_log_goes_to_callback_not_print(self, cfg, capsys):
        mgr = _make_manager(cfg)
        messages = []
        mgr.log_callback = messages.append
        mgr.log("hello")
        assert messages == ["hello"]
        out = capsys.readouterr()
        assert "hello" not in out.out

    def test_callback_exception_does_not_break(self, cfg):
        mgr = _make_manager(cfg)

        def bad_cb(msg):
            raise RuntimeError("boom")

        mgr.log_callback = bad_cb
        # Must not raise
        mgr.log("still works")

    def test_failed_cycle_task_logs_error(self, cfg):
        mgr = _make_manager(cfg)
        messages = []
        mgr.log_callback = messages.append
        with patch.object(scheduler_module, "run_cycle_command", return_value=1):
            mgr._run_cycle_task()
        assert any("failed" in m.lower() for m in messages)


def test_get_config_corrupt_config_falls_back_to_sun_model(tmp_path):
    """An unreadable config file must fall back to the same model as a
    fresh install (sun), not the pre-Phase-4 legacy default."""
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json")
    mgr = SchedulerManager(config_path=str(cfg))
    assert mgr._get_config()["suntime_model"] == "sun"

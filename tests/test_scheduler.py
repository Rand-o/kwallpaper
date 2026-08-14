"""Tests for the scheduler (phase 4).

Pins the behaviour contract:
- change task is scheduled at local midnight (CronTrigger), not every
  interval
- change task is a no-op until the local date changes
- cycle and change can never overlap (re-entrant lock)
- per-run results are delivered to the GUI log callback, not print
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kwallpaper import scheduler as scheduler_module
from kwallpaper.scheduler import SchedulerManager


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("""{
  "location": {"latitude": 35.0, "longitude": -112.0, "timezone": "UTC"},
  "interval": 1,
  "retry_attempts": 3,
  "retry_delay": 5,
  "scheduling": {"daily_shuffle_enabled": true, "run_cycle": true}
}""")
    return str(p)


def _make_manager(cfg, running=True):
    mgr = SchedulerManager(config_path=cfg)
    mgr._is_running = running
    return mgr


class TestChangeTaskScheduling:
    def test_change_task_is_cron_midnight(self, cfg):
        mgr = _make_manager(cfg, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs:
            instance = bs.return_value
            with patch.object(scheduler_module, "CronTrigger") as cron:
                assert mgr.start() is True
                jobs = {c.kwargs.get("id"): c for c in instance.add_job.call_args_list}
                assert "change_task" in jobs
                cron.assert_called()
                # Cron trigger at 00:00
                call_kwargs = cron.call_args.kwargs
                assert call_kwargs.get("hour") == 0
                assert call_kwargs.get("minute") == 0
        mgr.scheduler = None
        mgr._is_running = False

    def test_cycle_task_is_interval(self, cfg):
        mgr = _make_manager(cfg, running=False)
        with patch.object(scheduler_module, "BackgroundScheduler") as bs:
            instance = bs.return_value
            with patch.object(scheduler_module, "CronTrigger"), \
                 patch.object(scheduler_module, "IntervalTrigger") as interval:
                assert mgr.start() is True
                interval.assert_called()
                assert interval.call_args.kwargs.get("seconds") == 1
        mgr.scheduler = None
        mgr._is_running = False


class TestChangeTaskNoOp:
    def test_first_run_records_date_without_changing(self, cfg):
        mgr = _make_manager(cfg)
        with patch.object(scheduler_module, "run_change_command") as change, \
             patch.object(scheduler_module, "get_current_date", return_value="2026-02-10"):
            mgr._run_change_task()
            change.assert_not_called()
            assert mgr._last_change_date == "2026-02-10"

    def test_same_day_is_noop(self, cfg):
        mgr = _make_manager(cfg)
        mgr._last_change_date = "2026-02-10"
        with patch.object(scheduler_module, "run_change_command") as change, \
             patch.object(scheduler_module, "get_current_date", return_value="2026-02-10"):
            mgr._run_change_task()
            change.assert_not_called()

    def test_new_day_triggers_change(self, cfg):
        mgr = _make_manager(cfg)
        mgr._last_change_date = "2026-02-10"
        with patch.object(scheduler_module, "run_change_command", return_value=0) as change, \
             patch.object(scheduler_module, "get_current_date", return_value="2026-02-11"):
            mgr._run_change_task()
            change.assert_called_once()
            assert mgr._last_change_date == "2026-02-11"

    def test_failed_change_does_not_update_date(self, cfg):
        mgr = _make_manager(cfg)
        mgr._last_change_date = "2026-02-10"
        with patch.object(scheduler_module, "run_change_command", return_value=1), \
             patch.object(scheduler_module, "get_current_date", return_value="2026-02-11"):
            mgr._run_change_task()
            assert mgr._last_change_date == "2026-02-10"  # unchanged


class TestLock:
    def test_change_skipped_while_cycle_running(self, cfg):
        mgr = _make_manager(cfg)
        mgr._lock.acquire()  # simulate an in-flight cycle
        try:
            with patch.object(scheduler_module, "run_change_command") as change, \
                 patch.object(scheduler_module, "get_current_date", return_value="2026-02-11"):
                mgr._last_change_date = "2026-02-10"
                mgr._run_change_task()
                change.assert_not_called()
        finally:
            mgr._lock.release()

    def test_cycle_skipped_while_change_running(self, cfg):
        mgr = _make_manager(cfg)
        mgr._lock.acquire()
        try:
            with patch.object(scheduler_module, "run_cycle_command") as cycle:
                mgr._run_cycle_task()
                cycle.assert_not_called()
        finally:
            mgr._lock.release()


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

    def test_failed_task_logs_error(self, cfg):
        mgr = _make_manager(cfg)
        messages = []
        mgr.log_callback = messages.append
        mgr._last_change_date = "2026-02-10"
        with patch.object(scheduler_module, "run_change_command", return_value=1), \
             patch.object(scheduler_module, "get_current_date", return_value="2026-02-11"):
            mgr._run_change_task()
        assert any("failed" in m.lower() for m in messages)

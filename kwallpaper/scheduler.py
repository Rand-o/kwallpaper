#!/usr/bin/env python3
"""
Scheduler module for background task management.

Tasks:

- ``cycle_task``: interval-based (every ``scheduling.interval`` seconds).
  Re-applies the time-appropriate image of the current theme.
- ``change_task``: daily shuffle.  Scheduled at local midnight (CronTrigger)
  so it no longer hammers gdbus every ``interval`` seconds alongside
  cycle_task.  The job body is also a no-op unless the local date has
  actually changed since the last theme change, so a missed midnight
  (suspend/laptop sleep) is picked up on the next run.

A re-entrant lock guarantees cycle and change can never overlap.  Per-run
results are logged via ``logging`` and, when a callback is installed,
delivered to the GUI event log (instead of print).
"""

import io
import logging
import sys
import threading
from datetime import datetime
from typing import Optional, Callable, Any

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None
    IntervalTrigger = None

from kwallpaper.config import load_config, DEFAULT_CONFIG_PATH
from kwallpaper.cli import run_change_command, run_cycle_command
from kwallpaper.shuffle_list_manager import get_current_date

logger = logging.getLogger(__name__)


class _CaptureStream:
    """In-memory replacement for sys.stdout/sys.stderr.

    The CLI functions communicate via ``print()``.  When the scheduler runs
    them inside the GUI process, the process's real stdout/stderr are often
    closed (e.g. in the Flatpak sandbox) and every ``print`` raises
    ``BrokenPipeError`` — which surfaced as a "Cycle task error: [Errno 32]
    Broken pipe" log line on every run even though the wallpaper change
    itself succeeded.  Redirecting to an in-memory buffer avoids writing to
    the (potentially broken) pipes, and keeps the CLI's error messages so
    the scheduler can surface them in the GUI event log.

    Only ``sys.stdout`` / ``sys.stderr`` are swapped (never the underlying
    fd 1/2): the scheduler runs in a worker thread and the GUI's own
    logging may write to the real streams concurrently, so touching the
    fds would race with it.
    """

    def __init__(self):
        self.buf = io.StringIO()

    def write(self, s):
        self.buf.write(s)

    def flush(self):
        pass

    def getvalue(self):
        return self.buf.getvalue()


def _run_cli_quietly(func, args) -> tuple:
    """Run a CLI command function with stdout/stderr captured.

    Returns ``(exit_code, captured_output)`` where ``captured_output`` is
    the combined stdout+stderr text (stripped) produced by the command.
    """
    cap = _CaptureStream()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = cap, cap
    try:
        result = func(args)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return result, cap.getvalue().strip()


class SchedulerManager:
    """Manages background scheduler tasks for wallpaper changing."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.scheduler: Optional[BackgroundScheduler] = None
        self._is_running = False
        self._tasks: dict = {}
        self._lock = threading.Lock()
        self._last_change_date: Optional[str] = None
        self.log_callback: Optional[Callable[[str], None]] = None

    # ── logging ──────────────────────────────────────────────────────────
    def log(self, msg: str, level: int = logging.INFO) -> None:
        """Log a message to the logger and, if installed, to the GUI."""
        logger.log(level, msg)
        if self.log_callback is not None:
            try:
                self.log_callback(msg)
            except Exception:
                logger.debug("log_callback failed", exc_info=True)

    # ── config ───────────────────────────────────────────────────────────
    def _get_config(self) -> dict:
        try:
            config = load_config(self.config_path)
            scheduling = config.get('scheduling', {})
            location = config.get('location', {})
            return {
                'interval': config.get('interval', 60),
                'daily_shuffle_enabled': scheduling.get('daily_shuffle_enabled', True),
                'run_cycle': scheduling.get('run_cycle', True),
                'timezone': location.get('timezone', 'UTC'),
            }
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            return {
                'interval': 60,
                'daily_shuffle_enabled': True,
                'run_cycle': True,
                'timezone': 'UTC',
            }

    # ── tasks ────────────────────────────────────────────────────────────
    def _run_cycle_task(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.log("Cycle task skipped: previous run still in progress",
                     logging.DEBUG)
            return
        try:
            class MockArgs:
                theme_path = None
                config = self.config_path
                time = None
                monitor = False
            result, output = _run_cli_quietly(run_cycle_command, MockArgs())
            if result != 0:
                detail = f": {output}" if output else ""
                self.log(f"Cycle task failed with exit code {result}{detail}",
                         logging.ERROR)
            else:
                self.log("Cycle task completed", logging.DEBUG)
        except Exception as e:
            self.log(f"Cycle task error: {e}", logging.ERROR)
            logger.debug("Cycle task traceback", exc_info=True)
        finally:
            self._lock.release()

    def _run_change_task(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.log("Change task skipped: previous run still in progress",
                     logging.DEBUG)
            return
        try:
            config = self._get_config()
            today = get_current_date(config.get('timezone', 'UTC'))
            # No-op until the local date has actually changed since the last
            # theme change (midnight cron may also fire after a missed run).
            if self._last_change_date is None:
                self._last_change_date = today
                self.log("Change task: recording current date, no theme change",
                         logging.DEBUG)
                return
            if today == self._last_change_date:
                self.log("Change task: same day, no theme change",
                         logging.DEBUG)
                return

            class MockArgs:
                theme_path = None
                config = self.config_path
                time = None
                monitor = False
            result, output = _run_cli_quietly(run_change_command, MockArgs())
            if result != 0:
                detail = f": {output}" if output else ""
                self.log(f"Change task failed with exit code {result}{detail}",
                         logging.ERROR)
            else:
                self._last_change_date = today
                self.log(f"Change task completed (new day: {today})")
        except Exception as e:
            self.log(f"Change task error: {e}", logging.ERROR)
            logger.debug("Change task traceback", exc_info=True)
        finally:
            self._lock.release()

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self) -> bool:
        if not APSCHEDULER_AVAILABLE:
            logger.error("APScheduler is not installed")
            return False

        if self._is_running:
            logger.warning("Scheduler is already running")
            return True

        try:
            config = self._get_config()
            self.scheduler = BackgroundScheduler(daemon=True)

            interval = config.get('interval', 60)
            if config.get('run_cycle', True):
                self.scheduler.add_job(
                    self._run_cycle_task,
                    trigger=IntervalTrigger(seconds=interval),
                    id='cycle_task',
                    name='Cycle Wallpaper Task',
                    replace_existing=True
                )
                self._tasks['cycle'] = {'interval': interval, 'type': 'interval'}
                self.log(f"Added cycle task: runs every {interval} seconds")

            # Daily shuffle at local midnight (no-op if the day hasn't
            # changed, so a missed midnight is picked up next run).
            if config.get('daily_shuffle_enabled', True):
                self.scheduler.add_job(
                    self._run_change_task,
                    trigger=CronTrigger(hour=0, minute=0,
                                        timezone=config.get('timezone', 'UTC')),
                    id='change_task',
                    name='Daily Theme Change Task',
                    replace_existing=True
                )
                self._tasks['change'] = {
                    'interval': None,
                    'type': 'cron',
                    'schedule': 'daily at 00:00',
                }
                self.log("Added change task: daily at local midnight")

            self.scheduler.start()
            # Check if at least one task was added
            if not self._tasks:
                logger.error("Failed to start scheduler - cycle task is not enabled")
                self._is_running = False
                return False
            self._is_running = True
            self.log("Scheduler started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            self._is_running = False
            return False

    def stop(self, wait: bool = True) -> bool:
        if not self._is_running:
            logger.warning("Scheduler is not running")
            return True

        try:
            if self.scheduler is not None:
                self.scheduler.shutdown(wait=wait)
                self.scheduler = None
            self._is_running = False
            self.log("Scheduler stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
            self._is_running = False
            return False

    def add_job(self, name: str, func: Callable, trigger: Any) -> bool:
        if not self._is_running or self.scheduler is None:
            logger.error("Scheduler is not running")
            return False

        try:
            self.scheduler.add_job(func, trigger=trigger, id=name, name=name, replace_existing=True)
            self._tasks[name] = {'type': 'custom'}
            logger.info(f"Added custom job: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add job {name}: {e}", exc_info=True)
            return False

    def remove_job(self, name: str) -> bool:
        if not self._is_running or self.scheduler is None:
            logger.error("Scheduler is not running")
            return False

        try:
            self.scheduler.remove_job(name)
            if name in self._tasks:
                del self._tasks[name]
            logger.info(f"Removed job {name}")
            return True
        except Exception as e:
            return False

    def get_status(self) -> dict:
        status = {'running': self._is_running, 'tasks': self._tasks.copy()}
        if self.scheduler is not None:
            try:
                jobs = self.scheduler.get_jobs()
                status['job_count'] = len(jobs)
                status['jobs'] = [
                    {'id': job.id, 'name': job.name,
                     'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None}
                    for job in jobs
                ]
            except Exception:
                status['job_count'] = 0
                status['jobs'] = []
        return status

    def is_running(self) -> bool:
        return self._is_running


def create_scheduler(config_path: Optional[str] = None) -> SchedulerManager:
    return SchedulerManager(config_path=config_path)


if __name__ == '__main__':
    print("Testing SchedulerManager...")
    scheduler = create_scheduler()

    print("\nStarting scheduler...")
    if scheduler.start():
        print("Scheduler started successfully!")
        print(f"Status: {scheduler.get_status()}")

        import time
        print("\nRunning for 10 seconds...")
        time.sleep(10)

        print("\nStopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped!")
    else:
        print("Failed to start scheduler. APScheduler may not be installed.")
        import sys
        sys.exit(1)

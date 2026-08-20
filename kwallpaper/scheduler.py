#!/usr/bin/env python3
"""
Scheduler module for background task management.

Tasks:

- ``cycle_task``: interval-based (every ``scheduling.interval`` seconds).
  Re-applies the time-appropriate image of the current theme, and performs
  the daily shuffle when the local date differs from the persisted
  ``last_change_date`` (so a missed midnight — suspend, reboot, app not
  running at 00:00 — is picked up on the next cycle run).

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
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    DateTrigger = None
    IntervalTrigger = None

from kwallpaper.config import load_config, DEFAULT_CONFIG_PATH
from kwallpaper.core import next_change_time_for_config
from kwallpaper.cli import run_cycle_command

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

    ``sys.stdout``/``sys.stderr`` are process-global, so swapping them is a
    race if two scheduler tasks ever run concurrently.  They never do (the
    manager's re-entrant lock serialises cycle/change), but the swap is
    still guarded by a dedicated lock so a future concurrent task can't
    interleave its prints with the GUI thread's logging.
    """

    _swap_lock = threading.Lock()

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
    with _CaptureStream._swap_lock:
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
            # ``load_config`` normalizes legacy configs, so the cycle
            # interval is always ``scheduling.cycle_interval``.
            return {
                'interval': scheduling.get('cycle_interval', 60),
                'safety_interval': scheduling.get('safety_interval', 600),
                'suntime_model': scheduling.get('suntime_model', 'legacy'),
                'daily_shuffle_enabled': scheduling.get('daily_shuffle_enabled', True),
                'run_cycle': scheduling.get('run_cycle', True),
                'timezone': location.get('timezone', 'UTC'),
            }
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            return {
                'interval': 60,
                'safety_interval': 600,
                'suntime_model': 'legacy',
                'daily_shuffle_enabled': True,
                'run_cycle': True,
                'timezone': 'UTC',
            }

    # ── tasks ────────────────────────────────────────────────────────────
    def _run_cycle_task(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.log("Cycle task skipped: previous run still in progress",
                     logging.DEBUG)
            # The one-shot (if any) that triggered this run has already
            # been consumed by APScheduler; re-arm it even though the
            # actual cycle run was skipped by the lock.
            self._rearm_next_change()
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
            # Sun mode: re-arm the one-shot at the next change instant.
            # Legacy mode: no-op (the interval job keeps running).
            self._rearm_next_change()

    def _rearm_next_change(self) -> None:
        """Re-arm the one-shot cycle job at the next image boundary.

        Sun mode only (no-op for the legacy model, whose interval job
        never needs re-arming).  Called after every cycle run — one-shot
        or safety tick — and once from start().

        When the next change time cannot be computed (incomplete sun
        segments — polar day/night — or no resolvable theme), the cycle
        job falls back to the legacy-style interval trigger for the next
        run; the re-arm after that run retries the sun model, so a polar
        day self-heals once the segments are complete again.
        """
        if self.scheduler is None:
            return
        config = self._get_config()
        if config.get('suntime_model') != 'sun':
            return
        try:
            next_dt = next_change_time_for_config(self.config_path)
        except Exception as e:
            self.log(
                f"Could not compute next change time ({e}); "
                f"falling back to {config.get('interval', 60)}s interval "
                "until the next run",
                logging.WARNING)
            self.scheduler.add_job(
                self._run_cycle_task,
                trigger=IntervalTrigger(seconds=config.get('interval', 60)),
                id='cycle_task',
                name='Cycle Wallpaper Task (interval fallback)',
                replace_existing=True,
            )
            self._tasks['cycle'] = {
                'interval': config.get('interval', 60),
                'type': 'interval-fallback'}
            return
        # A generous misfire grace (1 day) makes a late one-shot — e.g.
        # after suspend/resume — fire immediately instead of being
        # dropped (APScheduler's default grace is 1 second).
        self.scheduler.add_job(
            self._run_cycle_task,
            trigger=DateTrigger(run_date=next_dt),
            id='cycle_task',
            name='Cycle Wallpaper Task (next change)',
            replace_existing=True,
            misfire_grace_time=86400,
        )
        self._tasks['cycle'] = {'next_change': next_dt.isoformat(),
                                'type': 'date'}
        self.log(f"Next wallpaper change at {next_dt.isoformat()}")

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
            # Reuse the existing scheduler instance when possible: creating
            # a fresh BackgroundScheduler on every start leaked its thread
            # pool on each start/stop cycle (the exact pattern the user
            # hammers in the GUI).  A shut-down APScheduler instance can be
            # restarted, so we only build a new one when we have none.
            if self.scheduler is None:
                self.scheduler = BackgroundScheduler(daemon=True)

            interval = config.get('interval', 60)
            if config.get('run_cycle', True):
                if config.get('suntime_model') == 'sun':
                    # Event-driven: one-shot at the exact next change
                    # (armed by _rearm_next_change, re-armed after every
                    # run) plus a coarse safety-net interval job for
                    # clock jumps, resume-from-sleep, missed runs and the
                    # daily shuffle check.
                    safety = config.get('safety_interval', 600)
                    self.scheduler.add_job(
                        self._run_cycle_task,
                        trigger=IntervalTrigger(seconds=safety),
                        id='safety_task',
                        name='Cycle Safety Net Task',
                        replace_existing=True,
                    )
                    self._tasks['safety'] = {'interval': safety,
                                             'type': 'interval'}
                    self.log(f"Added safety-net task: runs every {safety} "
                             "seconds (includes daily shuffle check)")
                    self._rearm_next_change()
                else:
                    self.scheduler.add_job(
                        self._run_cycle_task,
                        trigger=IntervalTrigger(seconds=interval),
                        id='cycle_task',
                        name='Cycle Wallpaper Task',
                        replace_existing=True
                    )
                    self._tasks['cycle'] = {'interval': interval,
                                            'type': 'interval'}
                    self.log(f"Added cycle task: runs every {interval} seconds"
                             " (includes daily shuffle check)")

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

    def stop(self, wait: bool = False) -> bool:
        """Stop the scheduler.

        ``wait`` defaults to False: the GUI calls stop() from the main
        thread, and waiting for a in-flight cycle task (which shells out to
        gdbus for several seconds per screen) would freeze the UI.  The
        task thread is a daemon and the re-entrant lock guarantees no
        overlap with the next start.
        """
        if not self._is_running:
            logger.warning("Scheduler is not running")
            return True

        try:
            if self.scheduler is not None:
                self.scheduler.shutdown(wait=wait)
            self._is_running = False
            self.log("Scheduler stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
            self._is_running = False
            return False

    def reload_cycle_interval(self) -> bool:
        """Re-read ``scheduling.cycle_interval`` from config and reschedule the
        cycle task, so interval changes made in the GUI Settings tab take
        effect without a full scheduler restart."""
        if not self._is_running or self.scheduler is None:
            return False
        try:
            config = self._get_config()
            if config.get('suntime_model') == 'sun':
                # Sun mode: re-arm the one-shot from the (possibly
                # changed) config, and make sure the safety-net job
                # exists (a live legacy→sun switch would otherwise run
                # without it).
                if 'safety' not in self._tasks:
                    safety = config.get('safety_interval', 600)
                    try:
                        self.scheduler.add_job(
                            self._run_cycle_task,
                            trigger=IntervalTrigger(seconds=safety),
                            id='safety_task',
                            name='Cycle Safety Net Task',
                            replace_existing=True,
                        )
                        self._tasks['safety'] = {'interval': safety,
                                                 'type': 'interval'}
                    except Exception as e:
                        logger.error(
                            f"Failed to add safety job on model switch: "
                            f"{e}")
                # An interval fallback armed during incomplete segments
                # picks up the new cycle_interval on the next re-arm.
                self._rearm_next_change()
                return True
            # Legacy mode: drop the sun-mode safety job (a live
            # sun→legacy switch would otherwise leave it ticking
            # forever), then re-add the interval job with the new
            # interval.
            if 'safety' in self._tasks:
                try:
                    self.scheduler.remove_job('safety_task')
                except Exception:
                    pass
                del self._tasks['safety']
            interval = config.get('interval', 60)
            if 'cycle' in self._tasks:
                self.scheduler.add_job(
                    self._run_cycle_task,
                    trigger=IntervalTrigger(seconds=interval),
                    id='cycle_task',
                    name='Cycle Wallpaper Task',
                    replace_existing=True,
                )
                self._tasks['cycle'] = {
                    'interval': interval, 'type': 'interval'}
                self.log(f"Cycle task interval updated: every {interval} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to reload cycle interval: {e}", exc_info=True)
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

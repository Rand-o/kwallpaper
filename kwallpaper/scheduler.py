#!/usr/bin/env python3
"""
Scheduler module for background task management.
"""

import sys
import logging
from datetime import datetime, time as time_class
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

from kwallpaper.wallpaper_changer import (
    load_config,
    DEFAULT_CONFIG_PATH,
    run_change_command,
    run_cycle_command
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages background scheduler tasks for wallpaper changing."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.scheduler: Optional[BackgroundScheduler] = None
        self._is_running = False
        self._tasks: dict = {}
        
    def _get_config(self) -> dict:
        try:
            config = load_config(self.config_path)
            scheduling = config.get('scheduling', {
                'interval': 60,
                'daily_shuffle_enabled': True
            })
            return {
                'interval': scheduling.get('interval', 60),
                'daily_shuffle_enabled': scheduling.get('daily_shuffle_enabled', True),
                'run_cycle': scheduling.get('run_cycle', True)
            }
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            return {
                'interval': 60,
                'daily_shuffle_enabled': True,
                'run_cycle': True
            }
    
    def _run_cycle_task(self) -> None:
        try:
            class MockArgs:
                theme_path = None
                config = self.config_path
                time = None
                monitor = False
            result = run_cycle_command(MockArgs())
            if result != 0:
                logger.error(f"Cycle task failed with exit code {result}")
        except Exception as e:
            logger.error(f"Cycle task error: {e}", exc_info=True)
    
    def _run_change_task(self) -> None:
        try:
            class MockArgs:
                theme_path = None
                config = self.config_path
                time = None
                monitor = False
            result = run_change_command(MockArgs())
            if result != 0:
                logger.error(f"Change task failed with exit code {result}")
        except Exception as e:
            logger.error(f"Change task error: {e}", exc_info=True)
    
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
                logger.info(f"Added cycle task: runs every {interval} seconds")
            
            # Add change task for daily shuffle logic if enabled
            if config.get('daily_shuffle_enabled', True):
                self.scheduler.add_job(
                    self._run_change_task,
                    trigger=IntervalTrigger(seconds=interval),
                    id='change_task',
                    name='Change Wallpaper Task',
                    replace_existing=True
                )
                self._tasks['change'] = {'interval': interval, 'type': 'interval'}
                logger.info(f"Added change task: runs every {interval} seconds")
            
            self.scheduler.start()
            # Check if at least one task was added
            if not self._tasks:
                logger.error("Failed to start scheduler - cycle task is not enabled")
                self._is_running = False
                return False
            self._is_running = True
            logger.info("Scheduler started successfully")
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
            logger.info("Scheduler stopped successfully")
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
            logger.info(f"Removed job: {name}")
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
        sys.exit(1)

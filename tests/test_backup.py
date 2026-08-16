"""Tests for the single rolling schedule backup (kwallpaper.backup)."""
import json
from datetime import datetime, timedelta

import pytest

import kwallpaper.backup as backup_mod
from kwallpaper.backup import (
    BACKUP_FILE_NAME,
    get_daily_backup_path,
    load_daily_backup_schedule,
    save_daily_backup_schedule,
)


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    d = tmp_path / "schedule-backup"
    d.mkdir()
    monkeypatch.setattr(backup_mod, "DEFAULT_SCHEDULE_BACKUP_DIR", d)
    return d


def _ts(day_offset=0):
    return (datetime.now() + timedelta(days=day_offset)).replace(
        hour=12, minute=0, second=0, microsecond=0)


class TestSingleBackupFile:
    def test_path_is_fixed_name(self, backup_dir):
        assert get_daily_backup_path() == backup_dir / BACKUP_FILE_NAME
        assert get_daily_backup_path().name == "schedule_backup.json"

    def test_save_creates_single_file(self, backup_dir):
        save_daily_backup_schedule(_ts(), _ts(), _ts(), _ts(), "day")
        files = list(backup_dir.iterdir())
        assert [f.name for f in files] == [BACKUP_FILE_NAME]

    def test_save_overwrites_instead_of_accumulating(self, backup_dir):
        for _ in range(5):
            save_daily_backup_schedule(_ts(), _ts(), _ts(), _ts(), "day")
        files = list(backup_dir.iterdir())
        assert len(files) == 1
        backup = json.loads(files[0].read_text())
        assert backup["time_of_day"] == "day"

    def test_load_roundtrip(self, backup_dir):
        save_daily_backup_schedule(_ts(), _ts(), _ts(), _ts(), "sunset")
        backup = load_daily_backup_schedule()
        assert backup is not None
        assert backup["time_of_day"] == "sunset"
        assert backup["previous_date"] == (
            datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    def test_load_missing_returns_none(self, backup_dir):
        assert load_daily_backup_schedule() is None

    def test_load_ignores_stale_backup(self, backup_dir):
        # A backup older than yesterday is useless as a fallback.
        old = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        (backup_dir / BACKUP_FILE_NAME).write_text(json.dumps({
            "date": old,
            "dawn": None, "sunrise": None, "sunset": None, "dusk": None,
            "time_of_day": "day",
            "previous_date": old,
        }))
        assert load_daily_backup_schedule() is None

    def test_load_invalid_json_returns_none(self, backup_dir):
        (backup_dir / BACKUP_FILE_NAME).write_text("{ not json")
        assert load_daily_backup_schedule() is None

    def test_load_missing_fields_returns_none(self, backup_dir):
        (backup_dir / BACKUP_FILE_NAME).write_text(json.dumps({"date": "x"}))
        assert load_daily_backup_schedule() is None

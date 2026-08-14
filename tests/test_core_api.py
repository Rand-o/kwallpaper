"""Tests for the kwallpaper.core API (phase 2)."""
import json
import zipfile
from pathlib import Path

import pytest

from kwallpaper import core
from kwallpaper.wallpaper_changer import (
    DEFAULT_SHUFFLE_LIST_PATH,
    DEFAULT_THEMES_DIR,
)


@pytest.fixture
def theme_dir(tmp_path, monkeypatch):
    """Create a fake extracted theme and point the themes dir at it."""
    themes = tmp_path / "themes"
    themes.mkdir()
    t = themes / "TestTheme"
    t.mkdir()
    (t / "theme.json").write_text(json.dumps({
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1, 2],
        "dayImageList": [3, 4],
        "sunsetImageList": [5, 6],
        "nightImageList": [7, 8],
    }))
    for i in range(1, 9):
        (t / f"test_{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", themes)
    monkeypatch.setattr(core, "discover_themes",
                        lambda: [(t.name, str(t))])
    return t


@pytest.fixture
def clean_shuffle(monkeypatch, tmp_path):
    """Point shuffle-list.json at a temp file."""
    p = tmp_path / "shuffle-list.json"
    monkeypatch.setattr(core, "load_shuffle_list",
                        lambda shuffle_path=None: {
                            "shuffle_list": [], "current_index": 0,
                            "last_used_date": "", "last_change_date": ""})
    monkeypatch.setattr(core, "save_shuffle_list",
                        lambda *a, **k: None)
    monkeypatch.setattr(core, "save_theme_change_date",
                        lambda *a, **k: None)
    monkeypatch.setattr(core, "load_theme_change_date",
                        lambda shuffle_path=None: "")
    monkeypatch.setattr(core, "check_day_passed", lambda *a, **k: False)
    return p


def test_import_theme_valid_zip(tmp_path, monkeypatch):
    src = tmp_path / "newtheme.ddw"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("theme.json", json.dumps({"displayName": "New"}))
    themes = tmp_path / "themes"
    themes.mkdir()
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", themes)
    meta = core.import_theme(str(src))
    assert meta["displayName"] == "New"
    assert (themes / "newtheme" / "theme.json").exists()


def test_import_theme_rejects_existing(tmp_path, monkeypatch):
    src = tmp_path / "dup.ddw"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("theme.json", "{}")
    themes = tmp_path / "themes"
    (themes / "dup").mkdir(parents=True)
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", themes)
    with pytest.raises(FileExistsError):
        core.import_theme(str(src))


def test_import_theme_missing_json(tmp_path, monkeypatch):
    src = tmp_path / "nojson.ddw"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("img.jpg", "x")
    themes = tmp_path / "themes"
    themes.mkdir()
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", themes)
    with pytest.raises(FileNotFoundError):
        core.import_theme(str(src))
    # partial extraction cleaned up
    assert not (themes / "nojson").exists()


def test_delete_theme(theme_dir, tmp_path, monkeypatch):
    assert core.delete_theme(str(theme_dir))
    assert not theme_dir.exists()


def test_delete_theme_refuses_outside_themes(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", tmp_path / "themes")
    with pytest.raises(ValueError):
        core.delete_theme(str(outside))


def test_apply_theme_success(theme_dir, tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "interval": 60, "retry_attempts": 3, "retry_delay": 2,
        "location": {"timezone": "America/Phoenix",
                     "latitude": 33.4, "longitude": -112.0},
        "scheduling": {"interval": 60, "run_cycle": True,
                       "daily_shuffle_enabled": False},
    }))
    monkeypatch.setattr(core, "set_wallpaper", lambda p: True)
    monkeypatch.setattr(core, "detect_time_of_day_sun",
                        lambda *a, **k: "day")
    monkeypatch.setattr(core, "select_image_for_time_cli",
                        lambda theme, cfg_path: str(theme_dir / "test_3.jpg"))
    monkeypatch.setattr(core, "load_config",
                        lambda p: json.loads(cfg.read_text()))
    monkeypatch.setattr(core, "save_config",
                        lambda p, c: cfg.write_text(json.dumps(c)))

    result = core.apply_theme(str(theme_dir), str(cfg))
    assert result.success
    assert result.theme_name == "TestTheme"
    saved = json.loads(cfg.read_text())
    assert saved["theme"]["last_applied"] == "TestTheme"


def test_apply_theme_wallpaper_failure(theme_dir, tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "interval": 60, "retry_attempts": 3, "retry_delay": 2,
        "location": {"timezone": "America/Phoenix"},
    }))
    monkeypatch.setattr(core, "set_wallpaper", lambda p: False)
    monkeypatch.setattr(core, "detect_time_of_day_sun",
                        lambda *a, **k: "day")
    monkeypatch.setattr(core, "select_image_for_time_cli",
                        lambda theme, cfg_path: str(theme_dir / "test_3.jpg"))
    monkeypatch.setattr(core, "load_config",
                        lambda p: json.loads(cfg.read_text()))

    result = core.apply_theme(str(theme_dir), str(cfg))
    assert not result.success
    assert "Failed to change wallpaper" in result.message


def test_apply_theme_unknown_theme(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "interval": 60, "retry_attempts": 3, "retry_delay": 2,
        "location": {"timezone": "America/Phoenix"},
    }))
    monkeypatch.setattr(core, "load_config",
                        lambda p: json.loads(cfg.read_text()))
    result = core.apply_theme("NoSuchTheme", str(cfg))
    assert not result.success
    assert "not found" in result.message

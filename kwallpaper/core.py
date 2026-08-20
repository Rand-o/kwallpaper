#!/usr/bin/env python3
"""
kWallpaper core API.

Clean, high-level operations shared by the CLI and the GUI:

- apply_theme():  pick the image for the current time-of-day for a theme and
  set it as the Plasma wallpaper.  Owns the config read-modify-write and the
  shuffle-list state atomically (single writer for shuffle-list.json).
- import_theme(): extract a .ddw/.zip file into the themes directory.
- delete_theme(): remove a theme from the themes directory.
- set_wallpaper(): low-level "set this image on all screens" primitive.

These functions do blocking work (JSON I/O, astral math, D-Bus calls), so
callers on a GUI thread should run them in a worker thread.
"""

import json
import logging
import random
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from kwallpaper.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_THEMES_DIR,
    load_config,
    save_config,
)
from kwallpaper.suntime import (
    detect_time_of_day_for_time,
    detect_time_of_day_sun,
)
from kwallpaper.selection import (
    select_image_for_specific_time,
    select_image_for_time_cli,
)
from kwallpaper.themes import (
    discover_themes,
    extract_theme,
    resolve_theme_path,
)
from kwallpaper.wallpaper import change_wallpaper
from kwallpaper.shuffle_list_manager import (
    check_and_reshuffle,
    check_day_passed,
    create_initial_shuffle,
    get_current_date,
    load_shuffle_list,
    load_theme_change_date,
    save_shuffle_list,
    save_theme_change_date,
)

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    """Result of an apply_theme() call."""
    success: bool
    theme_name: str = ""
    image_path: str = ""
    message: str = ""


# ============================================================================
# Low-level wallpaper primitive
# ============================================================================

def set_wallpaper(image_path: str) -> bool:
    """Set the given image as the Plasma wallpaper on all screens.

    Thin wrapper around wallpaper_changer.change_wallpaper so both the CLI
    and the GUI have a single, stable entry point.
    """
    return change_wallpaper(image_path)


# ============================================================================
# Theme import / delete
# ============================================================================

def import_theme(zip_path: str) -> dict:
    """Import a .ddw/.zip theme into the themes directory.

    Returns the extract_theme() metadata dict (extract_dir, displayName, ...).
    Raises FileNotFoundError / zipfile.BadZipFile on failure.
    """
    source_path = Path(zip_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Theme not found: {zip_path}")
    if source_path.suffix not in ('.ddw', '.zip'):
        raise ValueError(f"Not a theme archive: {zip_path}")

    extract_dir = DEFAULT_THEMES_DIR / source_path.stem
    if extract_dir.exists():
        raise FileExistsError(f"Theme already exists: {extract_dir.name}")

    DEFAULT_THEMES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(str(source_path), 'r') as zf:
            zf.extractall(str(extract_dir))
    except zipfile.BadZipFile:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise

    # Verify theme.json exists (root *.json first, then recursive theme.json)
    theme_json_path = None
    for json_file in extract_dir.glob("*.json"):
        theme_json_path = json_file
        break
    if not theme_json_path:
        for found_path in extract_dir.rglob("theme.json"):
            theme_json_path = found_path
            break
    if not theme_json_path:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise FileNotFoundError("theme.json not found in theme archive")

    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    return {
        "extract_dir": str(extract_dir),
        "displayName": theme_data.get("displayName", source_path.stem),
        "imageCredits": theme_data.get("imageCredits", "Unknown Credits"),
        "imageFilename": theme_data.get("imageFilename", "*.jpg"),
        "sunsetImageList": theme_data.get("sunsetImageList", []),
        "sunriseImageList": theme_data.get("sunriseImageList", []),
        "dayImageList": theme_data.get("dayImageList", []),
        "nightImageList": theme_data.get("nightImageList", []),
    }


def delete_theme(path: str) -> bool:
    """Delete a theme directory.

    Accepts either a full path under the themes directory or a bare theme
    folder name.  Returns True if something was removed.
    """
    theme_path = Path(path).expanduser()
    if not theme_path.is_absolute():
        theme_path = DEFAULT_THEMES_DIR / theme_path
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme not found: {path}")
    # Safety: only delete directories that live inside the themes directory
    try:
        theme_path.resolve().relative_to(DEFAULT_THEMES_DIR.resolve())
    except ValueError:
        raise ValueError(f"Refusing to delete path outside themes dir: {path}")
    shutil.rmtree(theme_path)
    return True


# ============================================================================
# Theme application
# ============================================================================

def _resolve_theme_folder(theme_path: str) -> str:
    """Resolve a theme folder name or path to an absolute theme directory."""
    p = Path(theme_path).expanduser()
    if '/' not in theme_path and '\\' not in theme_path:
        # Bare folder name: look it up in the themes directory
        themes = discover_themes()
        for name, path in themes:
            if name == theme_path:
                return path
        raise FileNotFoundError(
            f"Theme '{theme_path}' not found in themes directory")
    return resolve_theme_path(str(p))


def _pick_theme_for_shuffle(config: dict, timezone_str: str) -> str:
    """Daily shuffler: return the theme path selected for today.

    This is the single writer for shuffle-list.json: it performs the whole
    load -> maybe-reshuffle -> maybe-advance -> save sequence itself.

    The shuffle state is only persisted *after* the wallpaper has actually
    been set (see ``commit_shuffle_state`` / the callers' step 5), so a
    failed wallpaper change cannot advance the list: the next run retries
    the same theme instead of silently skipping it.
    """
    themes = discover_themes()
    if not themes:
        raise FileNotFoundError("No themes found in themes directory")

    shuffle_state = load_shuffle_list()
    shuffle_list = shuffle_state.get("shuffle_list", [])
    current_index = shuffle_state.get("current_index", 0)
    last_used_date = shuffle_state.get("last_used_date", "")

    # Reshuffle when the list is exhausted
    if check_and_reshuffle(shuffle_list, current_index, last_used_date):
        logger.info("Reshuffling themes...")
        shuffle_list = create_initial_shuffle([path for _, path in themes])
        current_index = 0

    # Advance to the next theme once per day.  The date is only persisted
    # after the wallpaper change succeeds (commit_shuffle_state), so a
    # failed run retries the same advance on the next attempt.
    last_change_date = load_theme_change_date()
    current_date = get_current_date(timezone_str)
    if check_day_passed(last_change_date, current_date):
        logger.info("New day detected - advancing to next theme")
        current_index = (current_index + 1) % len(shuffle_list) if shuffle_list else 0

    theme_path = shuffle_list[current_index]
    return theme_path


def commit_shuffle_state(config: dict, timezone_str: str) -> None:
    """Persist shuffle-list.json after a successful wallpaper change.

    Called by the shuffler-mode callers (CLI change command, apply_theme)
    once the new wallpaper is up.  A failed wallpaper change never reaches
    this point, so the list is not advanced and the next run retries the
    same theme.
    """
    shuffle_state = load_shuffle_list()
    shuffle_list = shuffle_state.get("shuffle_list", [])
    current_index = shuffle_state.get("current_index", 0)

    # Reshuffle when the list is exhausted (keeps the in-memory selection
    # and the persisted list in sync)
    if check_and_reshuffle(shuffle_list, current_index, ""):
        themes = discover_themes()
        shuffle_list = create_initial_shuffle([path for _, path in themes])
        current_index = 0

    current_date = get_current_date(timezone_str)
    # Advance to the next theme once per day (same rule as the picker)
    last_change_date = load_theme_change_date()
    if check_day_passed(last_change_date, current_date):
        current_index = (current_index + 1) % len(shuffle_list) if shuffle_list else 0
        save_theme_change_date(current_date)

    # Persist state (single writer)
    save_shuffle_list(shuffle_list, current_index, current_date)


def _reset_shuffle_to_theme(theme_path: str, timezone_str: str) -> None:
    """Rebuild the shuffle list so the applied theme is at index 0.

    Reuses shuffle_list_manager (single writer for shuffle-list.json).
    """
    themes = [str(p) for _, p in discover_themes()]
    if theme_path not in themes:
        logger.warning(f"Folder path not in themes list: {theme_path}")
        return
    other_themes = [t for t in themes if t != theme_path]
    random.shuffle(other_themes)
    save_shuffle_list([theme_path] + other_themes, 0, get_current_date(timezone_str))


def apply_theme(theme_path: str, config_path: Optional[str] = None,
                time_str: Optional[str] = None) -> ApplyResult:
    """Apply a theme: pick the image for the current time-of-day and set it.

    Owns the whole config read-modify-write:
      1. load config
      2. select the theme (manual path or daily shuffler)
      3. pick the image for the current time
      4. set the wallpaper
      5. save config (theme.last_applied) + shuffle state

    Args:
        theme_path: Theme folder name or path.  If None, the daily shuffler
            picks the theme.
        config_path: Config file path (default: DEFAULT_CONFIG_PATH).
        time_str: Optional "HH:MM" to select the image for a specific time.

    Returns:
        ApplyResult with success flag and details.
    """
    cfg_path = Path(config_path).expanduser() if config_path else Path(DEFAULT_CONFIG_PATH)
    config = load_config(str(cfg_path))
    timezone_str = config.get('location', {}).get('timezone', 'UTC')

    # 1. Pick the theme
    if theme_path:
        try:
            resolved = _resolve_theme_folder(theme_path)
        except FileNotFoundError as e:
            return ApplyResult(False, message=str(e))
        name = Path(resolved).name
        logger.info(f"Using theme: {resolved}")
    else:
        try:
            resolved = _pick_theme_for_shuffle(config, timezone_str)
        except FileNotFoundError as e:
            return ApplyResult(False, message=str(e))
        name = Path(resolved).name
        logger.info(f"Daily shuffler selected theme: {resolved}")

    # 2. Handle zip/ddw files
    expanded = Path(resolved).expanduser()
    if expanded.is_file() and expanded.suffix in ('.zip', '.ddw'):
        result = extract_theme(str(expanded), cleanup=False)
        resolved = result['extract_dir']

    # 3. Pick the image for the requested time
    if time_str:
        try:
            tod = detect_time_of_day_for_time(time_str, str(cfg_path))
            image_path = select_image_for_specific_time(time_str, resolved, str(cfg_path))
        except Exception as e:
            logger.error(f"Image selection for time {time_str} failed: {e}")
            return ApplyResult(False, name, message=f"Image selection failed: {e}")
    else:
        try:
            now = datetime.now(ZoneInfo(timezone_str))
            tod = detect_time_of_day_sun(str(cfg_path), now=now)
            image_path = select_image_for_time_cli(resolved, str(cfg_path))
        except Exception as e:
            logger.error(f"Image selection failed: {e}")
            return ApplyResult(False, name, message=f"Image selection failed: {e}")

    # 4. Set the wallpaper
    if not set_wallpaper(image_path):
        return ApplyResult(False, name, image_path, "Failed to change wallpaper")

    # 5. Persist config + shuffle state (atomic read-modify-write, done
    #    after the wallpaper is up so a crash doesn't leave stale state)
    try:
        config = load_config(str(cfg_path))
        config.setdefault('theme', {})['last_applied'] = name
        save_config(str(cfg_path), config)
        if not theme_path:
            # Shuffler mode: persist shuffle state now that the wallpaper
            # is up (a failed set_wallpaper returned before this point).
            commit_shuffle_state(config, timezone_str)
        else:
            shuffle_enabled = config.get('scheduling', {}).get(
                'daily_shuffle_enabled', False)
            if shuffle_enabled:
                _reset_shuffle_to_theme(str(Path(resolved)), timezone_str)
    except Exception as e:
        # Wallpaper is already set; state persistence failure is non-fatal.
        logger.error(f"Failed to persist config/shuffle state: {e}")

    return ApplyResult(True, name, image_path,
                       f"Applied {name} ({Path(image_path).name})")


def next_change_time_for_config(config_path: str,
                                now: Optional[datetime] = None) -> datetime:
    """Next wallpaper-change instant for the sun-position model.

    Resolves the theme the next cycle run will use (current D-Bus
    wallpaper first, then config ``theme.last_applied``), computes the
    sun segments for the configured location, and returns the next image
    boundary strictly after ``now`` (default: current time in the
    configured timezone).

    The function-level imports keep core and cli import-decoupled
    (cli already imports core inside functions; keeping the reverse
    direction function-level too avoids any import-order coupling).

    Raises:
        IncompleteSegmentsError: sun segments incomplete (polar
            day/night) — the caller (scheduler) falls back to the
            interval job.
        ValueError: no theme can be resolved, or the theme's image
            lists are inconsistent with the current time (empty
            category list).
    """
    from kwallpaper.cli import resolve_current_theme_dir
    from kwallpaper.selection import load_theme_data
    from kwallpaper.solarsegments import (
        image_at,
        next_change_time,
        segments_for_config,
    )

    config = load_config(config_path)
    tz = ZoneInfo(config.get('location', {}).get('timezone', 'UTC'))
    if now is None:
        now = datetime.now(tz)

    theme_dir = resolve_current_theme_dir(config)
    if theme_dir is None:
        raise ValueError(
            "no theme available (apply a theme first); cannot compute "
            "the next change time")
    theme_data = load_theme_data(theme_dir)
    seg = segments_for_config(config_path, now=now)
    _category, current_image = image_at(now, seg, theme_data)
    return next_change_time(now, seg, theme_data, current_image)

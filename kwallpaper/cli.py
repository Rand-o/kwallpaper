#!/usr/bin/env python3
"""
kWallpaper CLI dispatch.

Pure argparse + command handlers.  All heavy lifting lives in the
kwallpaper.core / themes / selection / wallpaper modules.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

from kwallpaper.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_THEMES_DIR,
    load_config,
    save_config,
)
from kwallpaper.shuffle_list_manager import (
    check_day_passed,
    get_current_date,
    load_theme_change_date,
)
from kwallpaper.suntime import (
    TIME_CATEGORIES,
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
from kwallpaper.wallpaper import change_wallpaper, get_current_wallpaper


def validate_time_of_day(time_of_day: str) -> bool:
    """Validate time-of-day category."""
    return time_of_day in TIME_CATEGORIES


# ============================================================================
# EXTRACT COMMAND
# ============================================================================

def run_extract_command(args) -> int:
    """Handle extract subcommand."""
    try:
        # Validate theme path exists
        theme_path = Path(args.theme_path).expanduser().resolve()
        if not theme_path.exists():
            print(f"Error: Theme path not found: {args.theme_path}", file=sys.stderr)
            return 1

        result = extract_theme(str(theme_path), args.cleanup)
        print(f"Extracted to: {result['extract_dir']}")
        print(f"Theme: {result['displayName']}")
        print(f"Image credits: {result['imageCredits']}")
        print(f"Image filename pattern: {result['imageFilename']}")
        print(f"Sunrise images: {result['sunriseImageList']}")
        print(f"Day images: {result['dayImageList']}")
        print(f"Sunset images: {result['sunsetImageList']}")
        print(f"Night images: {result['nightImageList']}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error extracting theme: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# CHANGE COMMAND
# ============================================================================

def run_change_command(args) -> int:
    """Handle change subcommand with daily shuffler support."""
    try:
        # Get timezone from config
        config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
        config = load_config(str(config_path))
        timezone_str = config.get('location', {}).get('timezone', 'UTC')

        # Check if manual theme path override is provided
        if args.theme_path:
            # Manual theme selection mode
            theme_path = args.theme_path

            # Check if theme_path is a folder name (not a path with slashes)
            if '/' not in theme_path and '\\' not in theme_path:
                try:
                    themes = discover_themes()
                    theme_dict = {Path(path).name: path for _, path in themes}
                    if theme_path in theme_dict:
                        theme_path = theme_dict[theme_path]
                        print(f"Using theme folder: {theme_path}")
                    else:
                        print(f"Error: Theme '{theme_path}' not found in themes directory", file=sys.stderr)
                        return 1
                except FileNotFoundError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    return 1
            else:
                print(f"Using manual theme selection: {theme_path}")
        else:
            # Daily shuffler mode: delegate to the shared single writer in
            # kwallpaper.core so the CLI, GUI and scheduler all advance the
            # same shuffle list consistently.
            from kwallpaper.core import _pick_theme_for_shuffle
            print("Using daily shuffler")
            try:
                theme_path = _pick_theme_for_shuffle(config, timezone_str)
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            except PermissionError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

            print(f"Selected theme: {Path(theme_path).name}")

        # Handle zip/ddw files
        expanded_path = Path(theme_path).expanduser()
        if expanded_path.is_file() and expanded_path.suffix in ['.zip', '.ddw']:
            result = extract_theme(str(theme_path), cleanup=False)
            theme_path = result['extract_dir']
        else:
            # Resolve to absolute path
            theme_path = resolve_theme_path(theme_path)

        # Get theme metadata to find where theme.json is located
        theme_json_path = Path(theme_path) / "theme.json"
        if not theme_json_path.exists():
            for item in Path(theme_path).iterdir():
                if item.is_dir() and (item / "theme.json").exists():
                    theme_json_path = item / "theme.json"
                    theme_path = str(item)
                    break
            else:
                for item in Path(theme_path).rglob("theme.json"):
                    theme_json_path = item
                    theme_path = str(item.parent)
                    break

        # Get config path (use --config if provided, otherwise default)
        if args.config:
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        # Handle --time argument for specific time selection
        if args.time:
            try:
                time_of_day = detect_time_of_day_for_time(args.time, str(config_path_obj))
                print(f"Selecting image for time: {args.time} ({time_of_day})")
                image_path = select_image_for_specific_time(args.time, theme_path, str(config_path_obj))
                print(f"Changing wallpaper to: {Path(image_path).name}")
                if change_wallpaper(image_path):
                    _persist_last_applied_image(str(config_path_obj), image_path)
                    print("Wallpaper changed successfully!")
                    return 0
                else:
                    print("Failed to change wallpaper", file=sys.stderr)
                    return 1
            except Exception as e:
                print(f"Error selecting image for specific time: {e}", file=sys.stderr)
                return 1

        # Always detect current time of day
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
        time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Monitor mode
        if args.monitor:
            print(f"Starting continuous monitoring mode...")
            print(f"Theme: {Path(theme_path).name}")
            monitor_interval = config['scheduling']['cycle_interval']
            print(f"Time-of-day check interval: {monitor_interval} seconds")
            print("Press Ctrl+C to stop")
            print("-" * 60)

            last_image_path = None
            last_time_of_day = None

            while True:
                try:
                    time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)
                    current_time_str = datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S")

                    if time_of_day != last_time_of_day:
                        print(f"\n[{current_time_str}] Time changed: {last_time_of_day} → {time_of_day}")
                        last_time_of_day = time_of_day

                        image_path = select_image_for_time_cli(theme_path, str(config_path_obj))
                        print(f"  → Changing wallpaper to: {Path(image_path).name}")

                        if change_wallpaper(image_path):
                            print(f"  ✓ Wallpaper updated successfully")
                        else:
                            print(f"  ✗ Failed to update wallpaper", file=sys.stderr)

                        last_image_path = image_path

                    else:
                        if last_image_path:
                            print(f"\r[{now}] {time_of_day} - {Path(last_image_path).name}", end="", flush=True)
                        else:
                            print(f"\r[{now}] {time_of_day} - loading...", end="", flush=True)

                    time.sleep(monitor_interval)

                except KeyboardInterrupt:
                    print("\n\nStopping monitoring mode...")
                    break
                except Exception as e:
                    print(f"\nError in monitoring loop: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
                    time.sleep(5)

            return 0

        # Single change mode - use time-based selection
        print(f"Selecting image for current time: {time_of_day}")
        now = datetime.now(ZoneInfo(timezone))
        image_path = select_image_for_time_cli(theme_path, str(config_path_obj))
        print(f"Changing wallpaper to: {image_path}")

        if change_wallpaper(image_path):
            # Persist the last-applied image now that the wallpaper is up
            # (skip-if-unchanged state; "persist after success" rule).
            _persist_last_applied_image(str(config_path_obj), image_path)
            # Persist shuffle state only now that the wallpaper is up, so a
            # failed change doesn't advance the list (the next run retries
            # the same theme instead of skipping it).
            if not args.theme_path:
                from kwallpaper.core import commit_shuffle_state
                try:
                    commit_shuffle_state(config, timezone_str)
                except Exception as e:
                    print(f"Warning: failed to persist shuffle state: {e}",
                          file=sys.stderr)
            print("Wallpaper changed successfully!")
            return 0
        else:
            print("Failed to change wallpaper", file=sys.stderr)
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"Error changing wallpaper: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# CYCLE COMMAND
# ============================================================================

def resolve_current_theme_dir(config: dict) -> Optional[Path]:
    """Resolve the theme directory the next cycle run will use.

    Prefers the theme of the current D-Bus wallpaper; falls back to the
    last-applied theme from config (covers the case where the wallpaper
    was changed outside kWallpaper, e.g. the user picked a solid colour
    or a random image in Plasma settings).  Returns None when neither
    resolves to an existing theme directory.
    """
    current_wallpaper = get_current_wallpaper()
    if current_wallpaper:
        # Extract theme name from the wallpaper path
        theme_name = Path(current_wallpaper).parent.name
        candidate = DEFAULT_THEMES_DIR / theme_name
        if candidate.exists():
            return candidate
    last_applied = config.get('theme', {}).get('last_applied', '')
    if last_applied:
        candidate = DEFAULT_THEMES_DIR / last_applied
        if candidate.exists():
            return candidate
    return None


def _same_image_path(a: str, b: str) -> bool:
    """True when both non-empty paths point at the same file (resolved)."""
    if not a or not b:
        return False
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def _persist_last_applied_image(config_path: str, image_path: str) -> None:
    """Persist ``theme.last_applied_image`` after a successful wallpaper
    change.

    Mirrors the shuffle-list "persist after success" rule: a failed
    change never updates the state, so the next run retries the same
    image.  Persistence failure is non-fatal (the wallpaper is already
    up); the worst case is one extra D-Bus call on the next run.
    """
    try:
        config = load_config(config_path)
        config.setdefault('theme', {})['last_applied_image'] = image_path
        save_config(config_path, config)
    except Exception as e:
        print(f"Warning: failed to persist last-applied image: {e}",
              file=sys.stderr)


def run_cycle_command(args) -> int:
    """Cycle to next image in current theme based on current time.

    Also performs the daily theme shuffle: if the local date differs from
    the persisted ``last_change_date``, the shuffler advances to the next
    theme and applies it.  Checking this every cycle (instead of a
    midnight cron job) means a missed midnight (suspend, reboot, app not
    running at 00:00) is picked up on the next cycle run.
    """
    try:
        # Get config path
        if args.config:
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        # Daily shuffle check: if a new day has started since the last
        # theme change, shuffle to the next theme and apply it.
        if config.get('scheduling', {}).get('daily_shuffle_enabled', True):
            timezone_str = config.get('location', {}).get('timezone', 'UTC')
            if check_day_passed(load_theme_change_date(),
                                get_current_date(timezone_str)):
                print("New day detected - shuffling to next theme")
                return run_change_command(args)

        # Resolve the theme the run will use (current D-Bus wallpaper
        # first, then the last-applied theme from config).
        theme_dir = resolve_current_theme_dir(config)

        if theme_dir is None:
            print(
                "Error: Could not determine current theme. No wallpaper found "
                "via D-Bus and no valid last-applied theme in config. "
                "Apply a theme from the GUI first.",
                file=sys.stderr,
            )
            return 1

        # Select image for current time
        image_path = select_image_for_time_cli(str(theme_dir), str(config_path_obj))
        image_path_obj = Path(image_path)

        # Skip-if-unchanged: no D-Bus call when the selected image is the
        # one we last applied (persisted in config; survives restarts).
        # The daily-shuffle path above (run_change_command) always applies.
        last_applied_image = config.get('theme', {}).get('last_applied_image', '')
        if _same_image_path(last_applied_image, str(image_path_obj)):
            print(f"No change: already showing {image_path_obj.name}")
            return 0

        if change_wallpaper(str(image_path_obj)):
            print(f"Changed wallpaper to {image_path_obj.name}")
            _persist_last_applied_image(str(config_path_obj), str(image_path_obj))
            return 0
        else:
            print(f"Failed to change wallpaper to {image_path_obj.name}", file=sys.stderr)
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error cycling wallpaper: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# SHUFFLE LIST COMMAND
# ============================================================================

def run_shuffle_list_command(args) -> int:
    """Print current shuffle list state."""
    try:
        from kwallpaper.shuffle_list_manager import load_shuffle_list, get_current_date

        # Get timezone from config
        config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
        config = load_config(str(config_path))
        timezone_str = config.get('location', {}).get('timezone', 'UTC')

        # Load shuffle list state
        shuffle_state = load_shuffle_list()

        shuffle_list = shuffle_state.get("shuffle_list", [])
        current_index = shuffle_state.get("current_index", 0)
        last_used_date = shuffle_state.get("last_used_date", "")

        # Get current wallpaper to determine which theme is actually displayed
        current_wallpaper = get_current_wallpaper()
        current_theme_name = None
        if current_wallpaper:
            current_theme_name = Path(current_wallpaper).parent.name

        # If --current flag is set, only show the current theme
        if args.current:
            if current_theme_name:
                print(current_theme_name)
            elif not shuffle_list:
                print("No themes in shuffle list.")
            elif current_index < len(shuffle_list):
                current_theme = shuffle_list[current_index]
                print(Path(current_theme).name)
            else:
                print("Shuffle list exhausted.")
            return 0

        print("Shuffle List State:")
        print(f"  Last used date: {last_used_date}")
        print(f"  Current index: {current_index}")
        print(f"  Total themes: {len(shuffle_list)}")
        print()

        if current_theme_name:
            print(f"  Current wallpaper theme: {current_theme_name}")

        if not shuffle_list:
            print("  No themes in shuffle list.")
            print("  Run 'wallpaper_cli.py change' to generate a shuffle list.")
            return 0

        print("  Current shuffle order:")
        for i, theme_path in enumerate(shuffle_list):
            theme_name = Path(theme_path).name
            marker = " >>" if i == current_index else ""
            if theme_name == current_theme_name:
                marker = " (current)"
            print(f"    {i+1}. {theme_name}{marker}")

        # Check if reshuffle is needed
        current_date = get_current_date(timezone_str)
        if last_used_date != current_date:
            print()
            print("  Note: Reshuffle needed (date changed)")

        if current_index >= len(shuffle_list):
            print()
            print("  Note: Reshuffle needed (list exhausted)")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# LIST / STATUS COMMANDS
# ============================================================================

def run_list_command(args) -> int:
    """Handle list subcommand."""
    try:
        # Resolve theme path
        theme_path = resolve_theme_path(args.theme_path)
        theme_path_obj = Path(theme_path)

        # Get config path (use --config if provided, otherwise default)
        if args.config:
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')

        if args.time_of_day:
            time_of_day = args.time_of_day
            if not validate_time_of_day(time_of_day):
                print(f"Invalid time-of-day category: {time_of_day}", file=sys.stderr)
                print("Valid categories are: sunrise, day, sunset, night", file=sys.stderr)
                return 1
        else:
            now = datetime.now(ZoneInfo(timezone))
            time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Get theme metadata to find image lists
        theme_json_path = theme_path_obj / "theme.json"
        if not theme_json_path.exists():
            for item in theme_path_obj.iterdir():
                if item.is_dir() and (item / "theme.json").exists():
                    theme_json_path = item / "theme.json"
                    theme_path = str(item)
                    break
            else:
                for item in theme_path_obj.rglob("theme.json"):
                    theme_json_path = item
                    theme_path = str(item.parent)
                    break

        with open(theme_json_path, 'r') as f:
            theme_data = json.load(f)

        image_list = theme_data.get(f"{time_of_day}ImageList", [])
        print(f"Images for {time_of_day}: {image_list}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error listing images: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_status_command(args) -> int:
    """Handle status subcommand."""
    try:
        # Get config path
        if args.config:
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        wallpaper_path = get_current_wallpaper()

        # Get time of day
        timezone = config.get('location', {}).get('timezone', 'America/Phoenix')
        now = datetime.now(ZoneInfo(timezone))
        time_of_day = detect_time_of_day_sun(str(config_path_obj), now=now)

        # Print status
        print(f"Current wallpaper:")
        if wallpaper_path and Path(wallpaper_path).exists():
            print(f"  Path: {wallpaper_path}")
            print(f"  File: {Path(wallpaper_path).name}")
        else:
            print(f"  No wallpaper currently set")
            print(f"  Tip: Run './wallpaper_cli.py change --theme-path <path>' to set a wallpaper")

        print(f"\nCurrent time-of-day: {time_of_day}")
        print(f"Image index: N/A (time-based selection now)")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error checking status: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# THEMES MANAGEMENT COMMAND
# ============================================================================

def run_themes_command(args) -> int:
    """Handle themes subcommand with subcommands (list, add, remove, reshuffle)."""
    if not args.themes_command:
        print("Error: No themes subcommand specified. Use 'list', 'add', 'remove', or 'reshuffle'.", file=sys.stderr)
        return 1

    try:
        if args.themes_command == 'list':
            return run_themes_list(args)
        elif args.themes_command == 'add':
            return run_themes_add(args)
        elif args.themes_command == 'remove':
            return run_themes_remove(args)
        elif args.themes_command == 'reshuffle':
            return run_themes_reshuffle(args)
        else:
            print(f"Error: Unknown themes subcommand: {args.themes_command}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_themes_list(args) -> int:
    """List all available themes in the themes directory."""
    try:
        themes = discover_themes()

        if not themes:
            print("No themes found in themes directory.")
            return 0

        print("Available themes:")
        for theme_name, theme_path in themes:
            print(f"  - {theme_name}: {theme_path}")

        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_themes_add(args) -> int:
    """Add a theme to the themes directory by extracting .ddw file."""
    try:
        from kwallpaper.themes import import_theme
        meta = import_theme(args.source)
        print(f"Added theme: {meta['extract_dir']}")
        print(f"  Location: {meta['extract_dir']}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error adding theme: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_themes_remove(args) -> int:
    """Remove a theme from the themes directory."""
    try:
        from kwallpaper.themes import delete_theme
        delete_theme(args.theme)
        print(f"Removed theme: {args.theme}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error removing theme: {e}", file=sys.stderr)
        return 1


def run_themes_reshuffle(args) -> int:
    """Manually reshuffle the theme list."""
    try:
        from kwallpaper.shuffle_list_manager import (
            create_initial_shuffle,
            save_shuffle_list,
            get_current_date,
        )

        # Get timezone from config
        config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
        config = load_config(str(config_path))
        timezone_str = config.get('location', {}).get('timezone', 'UTC')

        themes = discover_themes()

        if not themes:
            print("Error: No themes found in themes directory", file=sys.stderr)
            return 1

        theme_paths = [path for _, path in themes]
        shuffle_list = create_initial_shuffle(theme_paths)

        save_shuffle_list(shuffle_list, 0, get_current_date(timezone_str))

        print("Themes reshuffled successfully!")
        print(f"Total themes: {len(shuffle_list)}")

        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reshuffling themes: {e}", file=sys.stderr)
        return 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="kWallpaper - Automatically change wallpapers based on time-of-day",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
Extract theme from .ddw file
    wallpaper_cli.py extract --theme-path theme.ddw --cleanup

Change wallpaper using daily shuffler (cycles through all themes)
    wallpaper_cli.py change

Change wallpaper to specific theme (by folder name)
    wallpaper_cli.py change 24hr-Miami-1

Change wallpaper to specific theme (by path)
    wallpaper_cli.py change --theme-path theme.ddw

Change wallpaper to specific image based on current time (same theme)
    wallpaper_cli.py cycle

Print current shuffle list state
    wallpaper_cli.py shuffle-list

List all available themes
    wallpaper_cli.py themes list

Add a new theme to the themes directory
    wallpaper_cli.py themes add --source theme.ddw

List images for a time-of-day category
    wallpaper_cli.py list --theme-path extracted_theme --time-of-day day

Monitor mode (continuous wallpaper changes)
    wallpaper_cli.py change --monitor
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract theme from .ddw file')
    extract_parser.add_argument('--theme-path', required=True, help='Path to .ddw zip file')
    extract_parser.add_argument('--cleanup', action='store_true', help='Remove temp directory after extraction')

    # Change wallpaper command
    change_parser = subparsers.add_parser('change', help='Change wallpaper to next image')
    change_parser.add_argument('--theme-path', required=False, help='Theme folder name (e.g., "24hr-Miami-1") or path to .ddw/extracted theme (optional, uses daily shuffler if not provided)')
    change_parser.add_argument('--config', help='Path to config file (default: ~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/config.json)')
    change_parser.add_argument('--monitor', action='store_true', help='Run continuously, cycling wallpapers based on time-of-day')
    change_parser.add_argument('--time', help='Specific time to use for wallpaper selection (HH:MM format)')

    # Cycle command - change to next image in current theme based on current time
    cycle_parser = subparsers.add_parser('cycle', help='Cycle to next image in current theme based on current time')
    cycle_parser.add_argument('--config', help='Path to config file (default: ~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/config.json)')

    # Shuffle list command - print current shuffle list state
    shuffle_list_parser = subparsers.add_parser('shuffle-list', help='Print current shuffle list state')
    shuffle_list_parser.add_argument('--config', help='Path to config file (default: ~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/config.json)')
    shuffle_list_parser.add_argument('--current', action='store_true', help='Only show the current theme')

    # List images command
    list_parser = subparsers.add_parser('list', help='List available images in time-of-day category')
    list_parser.add_argument('--theme-path', required=True, help='Path to extracted theme directory or theme name')
    list_parser.add_argument('--time-of-day', help='Time-of-day category (day/sunset/sunrise/night)')
    list_parser.add_argument('--config', help='Path to config file (default: ~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/config.json)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check current wallpaper')
    status_parser.add_argument('--config', help='Path to config file (default: ~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/config.json)')

    # Themes management command
    themes_parser = subparsers.add_parser('themes', help='Manage themes')
    themes_subparsers = themes_parser.add_subparsers(dest='themes_command', help='Theme management commands')

    # themes list
    themes_list_parser = themes_subparsers.add_parser('list', help='List all available themes')

    # themes add
    themes_add_parser = themes_subparsers.add_parser('add', help='Add a theme to the themes directory')
    themes_add_parser.add_argument('--source', required=True, help='Path to source .ddw file')

    # themes remove
    themes_remove_parser = themes_subparsers.add_parser('remove', help='Remove a theme from the themes directory')
    themes_remove_parser.add_argument('--theme', required=True, help='Theme filename to remove')

    # themes reshuffle
    themes_reshuffle_parser = themes_subparsers.add_parser('reshuffle', help='Manually reshuffle the theme list')

    args = parser.parse_args()

    # Route to appropriate handler
    if args.command == 'extract':
        return run_extract_command(args)
    elif args.command == 'change':
        return run_change_command(args)
    elif args.command == 'list':
        return run_list_command(args)
    elif args.command == 'status':
        return run_status_command(args)
    elif args.command == 'cycle':
        return run_cycle_command(args)
    elif args.command == 'shuffle-list':
        return run_shuffle_list_command(args)
    elif args.command == 'themes':
        return run_themes_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

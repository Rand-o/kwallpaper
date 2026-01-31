#!/usr/bin/env python3
import argparse
import sys
import os
import json
from pathlib import Path
import glob
from datetime import datetime
import time

# Add config directory to path for imports
wallpaper_changer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.config', 'wallpaper-changer')
sys.path.insert(0, wallpaper_changer_dir)

from wallpaper_changer import extract_theme, select_next_image, load_config, save_config, detect_time_of_day, change_wallpaper
from typing import Optional


def validate_time_of_day(time_of_day: str) -> bool:
    """Validate time-of-day category.

    Args:
        time_of_day: Time-of-day category to validate

    Returns:
        True if valid, False otherwise
    """
    valid_categories = ['sunrise', 'day', 'sunset', 'night']
    return time_of_day in valid_categories


def resolve_theme_path(theme_path: str, theme_name: Optional[str] = None) -> str:
    """Resolve theme path to absolute path, handling zip files and extracted directories.

    Args:
        theme_path: Path to theme (zip file or directory)
        theme_name: Optional theme name for searching in cache

    Returns:
        Absolute path to theme directory

    Raises:
        FileNotFoundError: If theme cannot be resolved
    """
    expanded_path = Path(theme_path).expanduser()

    # If path exists, return it
    if expanded_path.exists():
        return str(expanded_path)

    # If path doesn't exist, try to find in cache
    if theme_name:
        cache_dir = Path.home() / ".cache" / "wallpaper-changer"
        matches = list(cache_dir.glob("theme_*"))
        for match in matches:
            try:
                if (match / theme_name).exists():
                    return str(match)
            except:
                pass

    raise FileNotFoundError(f"Theme not found: {theme_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="KDE Wallpaper Changer")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract theme')
    extract_parser.add_argument('--theme-path', required=True, help='Path to .ddw file')
    extract_parser.add_argument('--cleanup', action='store_true', help='Remove temp directory')

    # Change wallpaper command
    change_parser = subparsers.add_parser('change', help='Change wallpaper')
    change_parser.add_argument('--theme-path', required=True, help='Path to .ddw file')
    change_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')
    change_parser.add_argument('--monitor', action='store_true', help='Run continuously, cycling wallpapers based on time-of-day')

    # List images command
    list_parser = subparsers.add_parser('list', help='List images')
    list_parser.add_argument('--theme-path', required=True, help='Path to extracted theme directory or theme name')
    list_parser.add_argument('--time-of-day', help='Time-of-day category (day/sunset/sunrise/night)')
    list_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check current wallpaper')
    status_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

    # Standalone arguments (deprecated but maintained for backward compatibility)
    parser.add_argument('--theme-path', type=str, help='Path to .ddw zip file containing wallpaper theme (deprecated - use subcommands)')
    parser.add_argument('--config', type=str, help='Path to config file (deprecated)')
    parser.add_argument('--theme-name', type=str, help='Name of theme to load (deprecated)')
    parser.add_argument('--cleanup', action='store_true', help='Remove temp directory after extraction (deprecated - use extract subcommand)')

    args = parser.parse_args()

    # Handle standalone arguments (for backward compatibility)
    if not args.command and (args.theme_path or args.config):
        print("Warning: Standalone arguments are deprecated. Use subcommands instead.", file=sys.stderr)
        print("Usage: wallpaper-changer.py extract --theme-path <path>", file=sys.stderr)
        print("       wallpaper-changer.py change --theme-path <path>", file=sys.stderr)
        print("       wallpaper-changer.py list [--time-of-day day]", file=sys.stderr)
        return 1

    if args.command == 'extract':
        try:
            # Validate theme path exists
            if not Path(args.theme_path).expanduser().resolve().exists():
                print(f"Error: Theme path not found: {args.theme_path}", file=sys.stderr)
                return 1

            result = extract_theme(str(Path(args.theme_path).expanduser().resolve()), args.cleanup)
            print(f"Extracted to: {result['extract_dir']}")
            print(f"Theme: {result['displayName']}")
            print(f"Image credits: {result['imageCredits']}")
            print(f"Image filename pattern: {result['imageFilename']}")
            print(f"Sunrise images: {result['sunriseImageList']}")
            print(f"Day images: {result['dayImageList']}")
            print(f"Sunset images: {result['sunsetImageList']}")
            print(f"Night images: {result['nightImageList']}")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error extracting theme: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    elif args.command == 'change':
        try:
            # Resolve theme path (may be extracted directory or zip file)
            theme_path = args.theme_path

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
                # Look for theme.json in subdirectories
                for item in Path(theme_path).iterdir():
                    if item.is_dir() and (item / "theme.json").exists():
                        theme_json_path = item / "theme.json"
                        theme_path = str(item)
                        break
                else:
                    # If still not found, search recursively
                    for item in Path(theme_path).rglob("theme.json"):
                        theme_json_path = item
                        # Get the parent directory of theme.json
                        theme_path = str(item.parent)
                        break

            # Get config path (use --config if provided, otherwise default)
            if args.config:
                config_path = Path(args.config).expanduser().resolve()
            else:
                config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"

            config = load_config(config_path)
            time_of_day = config['current_time_of_day']

            # Monitor mode
            if args.monitor:
                print(f"Starting continuous monitoring mode...")
                print(f"Theme: {Path(theme_path).name}")
                print(f"Time-of-day intervals: {config['interval']} seconds each")
                print("Press Ctrl+C to stop")
                print("-" * 60)

                last_image_path = None
                last_time_of_day = None

                while True:
                    try:
                        # Get current time of day
                        time_of_day = detect_time_of_day()
                        current_time = datetime.now().strftime("%H:%M:%S")

                        # Check if time-of-day changed
                        if time_of_day != last_time_of_day:
                            print(f"\n[{current_time}] Time changed: {last_time_of_day} → {time_of_day}")
                            last_time_of_day = time_of_day

                            # Select new image for current time-of-day
                            image_path = select_next_image(theme_path, config_path)
                            print(f"  → Changing wallpaper to: {Path(image_path).name}")

                            if change_wallpaper(image_path):
                                print(f"  ✓ Wallpaper updated successfully")
                            else:
                                print(f"  ✗ Failed to update wallpaper", file=sys.stderr)

                            last_image_path = image_path

                        else:
                            # Just log current status
                            if last_image_path:
                                print(f"\r[{current_time}] {time_of_day} - {Path(last_image_path).name}", end="", flush=True)
                            else:
                                print(f"\r[{current_time}] {time_of_day} - loading...", end="", flush=True)

                        # Wait for next interval (check if time changed)
                        time.sleep(config['interval'])

                    except KeyboardInterrupt:
                        print("\n\nStopping monitoring mode...")
                        break
                    except Exception as e:
                        print(f"\nError in monitoring loop: {e}", file=sys.stderr)
                        import traceback
                        traceback.print_exc()
                        time.sleep(5)  # Wait before retrying

                return 0

            # Single change mode
            print(f"Selecting image for: {time_of_day}")
            image_path = select_next_image(theme_path, config_path)
            print(f"Changing wallpaper to: {image_path}")

            if change_wallpaper(image_path):
                print("Wallpaper changed successfully!")
            else:
                print("Failed to change wallpaper", file=sys.stderr)
                return 1

        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error changing wallpaper: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    elif args.command == 'list':
        try:
            # Resolve theme path
            theme_path = resolve_theme_path(args.theme_path)
            theme_path = Path(theme_path)

            # Get config path (use --config if provided, otherwise default)
            if args.config:
                config_path = Path(args.config).expanduser().resolve()
            else:
                config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"

            config = load_config(config_path)

            if args.time_of_day:
                time_of_day = args.time_of_day
                if not validate_time_of_day(time_of_day):
                    print(f"Invalid time-of-day category: {time_of_day}", file=sys.stderr)
                    print("Valid categories are: sunrise, day, sunset, night", file=sys.stderr)
                    return 1
            else:
                time_of_day = config['current_time_of_day']

            # Get theme metadata to find image lists
            theme_json_path = theme_path / "theme.json"
            if not theme_json_path.exists():
                # Look for theme.json in subdirectories
                for item in theme_path.iterdir():
                    if item.is_dir() and (item / "theme.json").exists():
                        theme_json_path = item / "theme.json"
                        theme_path = str(item)
                        break
                else:
                    # Search recursively
                    for item in theme_path.rglob("theme.json"):
                        theme_json_path = item
                        theme_path = str(item.parent)
                        break

            with open(theme_json_path, 'r') as f:
                theme_data = json.load(f)

            image_list = theme_data.get(f"{time_of_day}ImageList", [])
            print(f"Images for {time_of_day}: {image_list}")

        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error listing images: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    elif args.command == 'status':
        try:
            # Get config path
            if args.config:
                config_path = Path(args.config).expanduser().resolve()
            else:
                config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"

            config = load_config(config_path)

            # Import here to avoid issues
            from wallpaper_changer import get_current_wallpaper
            wallpaper_path = get_current_wallpaper()

            # Get time of day
            time_of_day = config.get('current_time_of_day', 'day')

            # Print status
            print(f"Current wallpaper:")
            if wallpaper_path and Path(wallpaper_path).exists():
                print(f"  Path: {wallpaper_path}")
                print(f"  File: {Path(wallpaper_path).name}")
            else:
                print(f"  No wallpaper currently set")
                print(f"  Tip: Run './wallpaper-changer.py change --theme-path <path>' to set a wallpaper")

            print(f"\nCurrent time-of-day: {time_of_day}")
            print(f"Image index: {config.get('current_image_index', 0)}")

        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error checking status: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    # If no command specified and no standalone arguments
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

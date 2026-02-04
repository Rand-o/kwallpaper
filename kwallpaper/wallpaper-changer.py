#!/usr/bin/env python3
import argparse
import sys
import os
import json
from pathlib import Path
import glob

# Add config directory to path for imports
wallpaper_changer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.config', 'wallpaper-changer')
sys.path.insert(0, wallpaper_changer_dir)

from wallpaper_changer import extract_theme, select_next_image, load_config, save_config, detect_time_of_day, change_wallpaper


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

    # List images command
    list_parser = subparsers.add_parser('list', help='List images')
    list_parser.add_argument('--theme-path', required=True, help='Path to extracted theme directory or theme name')
    list_parser.add_argument('--time-of-day', help='Time-of-day category (day/sunset/sunrise/night)')

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
            result = extract_theme(args.theme_path, args.cleanup)
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
            if not Path(theme_path).exists():
                # Try to find extracted theme directory
                matches = glob.glob(f"~/.cache/wallpaper-changer/theme_*")
                if matches:
                    # Try to find theme directory containing the theme path
                    for match in matches:
                        try:
                            if Path(match).joinpath(theme_path).exists():
                                theme_path = match
                                break
                        except:
                            pass
                    else:
                        raise FileNotFoundError(f"Theme not found: {theme_path}")
            elif Path(theme_path).is_file() and Path(theme_path).suffix == '.zip':
                # Extract zip file
                result = extract_theme(theme_path, cleanup=False)
                theme_path = result['extract_dir']

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

            # Get time-of-day from config
            config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"
            config = load_config(config_path)
            time_of_day = config['current_time_of_day']

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
            theme_path = Path(args.theme_path).expanduser().resolve()

            if not theme_path.exists():
                # Try to find extracted theme directory
                cache_dir = Path.home() / ".cache" / "wallpaper-changer"
                for item in cache_dir.glob("theme_*"):
                    try:
                        if (item / args.theme_path).exists():
                            theme_path = item
                            break
                    except:
                        pass

            config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"
            config = load_config(config_path)

            if args.time_of_day:
                time_of_day = args.time_of_day
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
        except Exception as e:
            print(f"Error listing images: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
        except Exception as e:
            print(f"Error listing images: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error listing images: {e}", file=sys.stderr)
            return 1

    # If no command specified and no standalone arguments
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

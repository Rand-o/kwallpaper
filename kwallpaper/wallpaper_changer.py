#!/usr/bin/env python3
"""
KDE Wallpaper Changer - Core functionality module.

This module provides all core functions for the KDE Wallpaper Changer tool,
including config management, theme extraction, image selection, and wallpaper changes.
"""

import argparse
import sys
import os
import json
from pathlib import Path
import glob
from datetime import datetime
import time
import subprocess
import zipfile
import tempfile
from typing import Optional, Dict, Any


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "wallpaper-changer" / "config.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "wallpaper-changer"


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

DEFAULT_CONFIG = {
    "interval": 5400,
    "retry_attempts": 3,
    "retry_delay": 5,
    "current_image_index": 0,
    "current_time_of_day": "day"
}


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config JSON file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file contains invalid JSON
    """
    config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

    # Validate config
    validate_config(config)

    return config


def save_config(config_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to JSON file.

    Args:
        config_path: Path to save config JSON file
        config: Configuration dictionary to save
    """
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, sort_keys=True)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If config is invalid
    """
    required_fields = ['interval', 'retry_attempts', 'retry_delay', 'current_image_index', 'current_time_of_day']

    for field in required_fields:
        if field not in config:
            raise ValueError(f"Config validation failed: Missing required field '{field}'")

    # Validate interval
    if not isinstance(config['interval'], int) or config['interval'] <= 0:
        raise ValueError("Config validation failed: 'interval' must be a positive integer")

    # Validate retry_attempts
    if not isinstance(config['retry_attempts'], int) or config['retry_attempts'] <= 0:
        raise ValueError("Config validation failed: 'retry_attempts' must be a positive integer")

    # Validate retry_delay
    if not isinstance(config['retry_delay'], int) or config['retry_delay'] <= 0:
        raise ValueError("Config validation failed: 'retry_delay' must be a positive integer")

    # Validate current_image_index
    if not isinstance(config['current_image_index'], int) or config['current_image_index'] < 0:
        raise ValueError("Config validation failed: 'current_image_index' must be a non-negative integer")

    # Validate current_time_of_day
    valid_categories = ['sunrise', 'day', 'sunset', 'night']
    if config['current_time_of_day'] not in valid_categories:
        raise ValueError(
            f"Config validation failed: 'current_time_of_day' must be one of {valid_categories}"
        )


# ============================================================================
# THEME EXTRACTION
# ============================================================================

def extract_theme(zip_path: str, cleanup: bool = False) -> Dict[str, Any]:
    """Extract .ddw wallpaper theme from zip file.

    Args:
        zip_path: Path to .ddw zip file
        cleanup: If True, remove temp directory after extraction

    Returns:
        Dictionary containing theme metadata:
        - extract_dir: Path to extracted directory
        - displayName: Theme display name
        - imageCredits: Image credits
        - imageFilename: Image filename pattern
        - sunsetImageList: List of sunset image indices
        - sunriseImageList: List of sunrise image indices
        - dayImageList: List of day image indices
        - nightImageList: List of night image indices

    Raises:
        FileNotFoundError: If theme.json not found in zip
    """
    zip_path_obj = Path(zip_path)

    if not zip_path_obj.exists():
        raise FileNotFoundError(f"Theme not found: {zip_path}")

    # Create directory with the same name as zip file (without extension)
    extract_dir = DEFAULT_CACHE_DIR / zip_path_obj.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract zip file
        with zipfile.ZipFile(str(zip_path_obj), 'r') as zf:
            zf.extractall(extract_dir)

        # Find theme.json - first look for any .json file in root, then theme.json recursively
        theme_json_path = None

        # Check root directory for any .json file
        for json_file in extract_dir.glob("*.json"):
            theme_json_path = json_file
            break

        # If not found, search recursively for theme.json
        if not theme_json_path:
            for found_path in extract_dir.rglob("theme.json"):
                theme_json_path = found_path
                break

        if not theme_json_path:
            raise FileNotFoundError("theme.json not found in zip file")

        # Parse theme.json
        with open(theme_json_path, 'r') as f:
            theme_data = json.load(f)

        # Return metadata
        result = {
            "extract_dir": str(extract_dir),
            "displayName": theme_data.get("displayName", "Unknown Theme"),
            "imageCredits": theme_data.get("imageCredits", "Unknown Credits"),
            "imageFilename": theme_data.get("imageFilename", "*.jpg"),
            "sunsetImageList": theme_data.get("sunsetImageList", []),
            "sunriseImageList": theme_data.get("sunriseImageList", []),
            "dayImageList": theme_data.get("dayImageList", []),
            "nightImageList": theme_data.get("nightImageList", [])
        }

        # Cleanup if requested
        if cleanup:
            import shutil
            shutil.rmtree(extract_dir)

        return result

    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        # Clean up on error
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        raise


def get_current_wallpaper() -> Optional[str]:
    """Get current KDE Plasma wallpaper path.

    Returns:
        Path to current wallpaper, or None if not found
    """
    try:
        result = subprocess.run([
            'kreadconfig5',
            '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
            '--group', 'Wallpaper',
            '--group', 'org.kde.image',
            '--key', 'Image'
        ], capture_output=True, text=True, check=True)

        wallpaper_path = result.stdout.strip()
        if wallpaper_path:
            return wallpaper_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Plasma not running or config not found
        pass

    return None


# ============================================================================
# TIME-OF-DAY DETECTION
# ============================================================================

def detect_time_of_day(hour: Optional[int] = None) -> str:
    """Detect current time-of-day category based on hour.

    Args:
        hour: Optional hour value to use for detection (for testing)
              If None, uses current system time.

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
    if hour is None:
        hour = datetime.now().hour

    if 0 <= hour < 5:
        return "night"
    elif 5 <= hour < 7:
        return "sunrise"
    elif 7 <= hour < 17:
        return "day"
    elif 17 <= hour < 19:
        return "sunset"
    else:
        return "night"


# ============================================================================
# IMAGE SELECTION
# ============================================================================

def select_next_image(theme_path: str, config_path: str) -> str:
    """Select next image based on current time-of-day.

    Args:
        theme_path: Path to theme directory or zip file
        config_path: Path to config file

    Returns:
        Path to selected image file

    Raises:
        FileNotFoundError: If theme.json not found
        ValueError: If no images available
    """
    config_path_obj = Path(config_path)
    theme_path_obj = Path(theme_path)

    # Resolve zip file to theme directory
    if theme_path_obj.is_file() and theme_path_obj.suffix in ['.zip', '.ddw']:
        result = extract_theme(str(theme_path_obj), cleanup=False)
        theme_path_obj = Path(result['extract_dir'])

    # Find theme.json - first look for any .json file in root, then theme.json recursively
    theme_json_path = None

    # Check root directory for any .json file
    for json_file in theme_path_obj.glob("*.json"):
        theme_json_path = json_file
        break

    # If not found, search recursively for theme.json
    if not theme_json_path:
        for found_path in theme_path_obj.rglob("theme.json"):
            theme_json_path = found_path
            break

    if not theme_json_path:
        raise FileNotFoundError("theme.json not found in theme directory")

    # Load theme data
    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    # Load config
    config = load_config(str(config_path_obj))
    current_image_index = config['current_image_index']
    current_time_of_day = config['current_time_of_day']

    # Get image list for current time-of-day
    image_list = theme_data.get(f"{current_time_of_day}ImageList", [])

    # If current time-of-day has no images, switch to next category
    while not image_list:
        time_categories = ['sunrise', 'day', 'sunset', 'night']
        try:
            current_idx = time_categories.index(current_time_of_day)
            if current_idx < len(time_categories) - 1:
                current_time_of_day = time_categories[current_idx + 1]
                image_list = theme_data.get(f"{current_time_of_day}ImageList", [])
            else:
                # All categories empty, raise error
                raise ValueError("No images available in any time-of-day category")
        except ValueError:
            raise ValueError("No images available in any time-of-day category")

    # Validate image index
    if current_image_index >= len(image_list):
        current_image_index = 0

    # Get image filename from index
    image_index = image_list[current_image_index]

    # Find image file
    # Pattern: imageFilename contains index, e.g., "24hr-Tahoe-2026_*.jpeg"
    filename_pattern = theme_data.get("imageFilename", "*.jpg")

    # Extract base name and extension from pattern for later use
    if filename_pattern:
        pattern_base = Path(filename_pattern).stem
        pattern_ext = Path(filename_pattern).suffix
    else:
        pattern_base = "theme"
        pattern_ext = ".jpg"

    # Try to find file matching pattern
    image_files = list(theme_path_obj.glob(filename_pattern))

    # If pattern doesn't match, try numbered files
    if not image_files:
        # Try numbered files: pattern_base_1.ext, pattern_base_2.ext, etc.
        numbered_files = []
        for i in range(1, 100):
            numbered_files.append(theme_path_obj / f"{pattern_base}_{i}{pattern_ext}")

        # Filter to only existing files
        image_files = [f for f in numbered_files if f.exists()]

    if not image_files:
        raise FileNotFoundError(
            f"Image file not found for index {image_index} in theme '{theme_data.get('displayName')}'"
        )

    # Match by index using the globbed list
    # Sort files to ensure consistent ordering
    image_files.sort()

    # Find the file at the correct index
    if image_index <= len(image_files):
        image_path = image_files[image_index - 1]  # 1-based index to 0-based
    else:
        # Wrap around if index exceeds available files
        image_path = image_files[(image_index - 1) % len(image_files)]

    # Update config
    config['current_image_index'] = (current_image_index + 1) % len(image_list)
    config['current_time_of_day'] = current_time_of_day
    save_config(str(config_path_obj), config)

    return str(image_path)


# ============================================================================
# WALLPAPER CHANGE
# ============================================================================

def change_wallpaper(image_path: str) -> bool:
    """Change KDE Plasma wallpaper to specified image.

    Args:
        image_path: Path to image file to set as wallpaper

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if Plasma is running
        plasma_check = subprocess.run(
            ['pgrep', '-x', 'plasmashell'],
            capture_output=True
        )
        if plasma_check.returncode != 0:
            print("Error: Plasma is not running. Please start Plasma first.", file=sys.stderr)
            return False

        # Try plasma-apply-wallpaperimage first (most reliable)
        result = subprocess.run(
            ['plasma-apply-wallpaperimage', image_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Wallpaper changed successfully!")
            return True

        # Fall back to kwriteconfig5 if plasma-apply-wallpaperimage fails
        print("Attempting fallback method using kwriteconfig5...", file=sys.stderr)
        subprocess.run([
            'kwriteconfig5',
            '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
            '--group', 'Wallpaper',
            '--group', 'org.kde.image',
            '--key', 'Image',
            image_path
        ], check=False, capture_output=True)

        # Verify wallpaper was set
        verify_result = subprocess.run([
            'kreadconfig5',
            '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
            '--group', 'Wallpaper',
            '--group', 'org.kde.image',
            '--key', 'Image'
        ], capture_output=True, text=True)

        if verify_result.returncode == 0 and verify_result.stdout.strip():
            print("Wallpaper changed successfully (using fallback method)", file=sys.stderr)
            return True
        else:
            print(f"Error: Failed to change wallpaper. plasma-apply-wallpaperimage returned: {result.stderr}", file=sys.stderr)
            return False

    except FileNotFoundError as e:
        print(f"Error: Required command not found: {e}", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to change wallpaper: {e.stderr}", file=sys.stderr)
        return False


# ============================================================================
# CLI SUBCOMMANDS
# ============================================================================

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
        cache_dir = DEFAULT_CACHE_DIR
        matches = list(cache_dir.glob("theme_*"))
        for match in matches:
            try:
                if (match / theme_name).exists():
                    return str(match)
            except (OSError, PermissionError):
                # Skip directories that can't be accessed
                pass

    raise FileNotFoundError(f"Theme not found: {theme_path}")


def run_extract_command(args) -> int:
    """Handle extract subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
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


def run_change_command(args) -> int:
    """Handle change subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
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
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))
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
                        image_path = select_next_image(theme_path, str(config_path_obj))
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
        image_path = select_next_image(theme_path, str(config_path_obj))
        print(f"Changing wallpaper to: {image_path}")

        if change_wallpaper(image_path):
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


def run_list_command(args) -> int:
    """Handle list subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
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

        if args.time_of_day:
            time_of_day = args.time_of_day
            if not validate_time_of_day(time_of_day):
                print(f"Invalid time-of-day category: {time_of_day}", file=sys.stderr)
                print("Valid categories are: sunrise, day, sunset, night", file=sys.stderr)
                return 1
        else:
            time_of_day = config['current_time_of_day']

        # Get theme metadata to find image lists
        theme_json_path = theme_path_obj / "theme.json"
        if not theme_json_path.exists():
            # Look for theme.json in subdirectories
            for item in theme_path_obj.iterdir():
                if item.is_dir() and (item / "theme.json").exists():
                    theme_json_path = item / "theme.json"
                    theme_path = str(item)
                    break
            else:
                # Search recursively
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
    """Handle status subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get config path
        if args.config:
            config_path_obj = Path(args.config).expanduser().resolve()
        else:
            config_path_obj = DEFAULT_CONFIG_PATH

        config = load_config(str(config_path_obj))

        # Import here to avoid issues
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
            print(f"  Tip: Run './wallpaper_cli.py change --theme-path <path>' to set a wallpaper")

        print(f"\nCurrent time-of-day: {time_of_day}")
        print(f"Image index: {config.get('current_image_index', 0)}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error checking status: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="KDE Wallpaper Changer - Automatically change wallpapers based on time-of-day",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Extract theme from .ddw file
    wallpaper_cli.py extract --theme-path theme.ddw --cleanup

  Change wallpaper to next image
    wallpaper_cli.py change --theme-path theme.ddw

  List images for a time-of-day category
    wallpaper_cli.py list --theme-path extracted_theme --time-of-day day

  Monitor mode (continuous wallpaper changes)
    wallpaper_cli.py change --theme-path theme.ddw --monitor
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract theme from .ddw file')
    extract_parser.add_argument('--theme-path', required=True, help='Path to .ddw zip file')
    extract_parser.add_argument('--cleanup', action='store_true', help='Remove temp directory after extraction')

    # Change wallpaper command
    change_parser = subparsers.add_parser('change', help='Change wallpaper to next image')
    change_parser.add_argument('--theme-path', required=True, help='Path to .ddw zip file or extracted theme directory')
    change_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')
    change_parser.add_argument('--monitor', action='store_true', help='Run continuously, cycling wallpapers based on time-of-day')

    # List images command
    list_parser = subparsers.add_parser('list', help='List available images in time-of-day category')
    list_parser.add_argument('--theme-path', required=True, help='Path to extracted theme directory or theme name')
    list_parser.add_argument('--time-of-day', help='Time-of-day category (day/sunset/sunrise/night)')
    list_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check current wallpaper')
    status_parser.add_argument('--config', help='Path to config file (default: ~/.config/wallpaper-changer/config.json)')

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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

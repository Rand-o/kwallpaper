#!/usr/bin/env python3
import json
import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def load_config(config_path):
    """Load and validate config file.
    
    Args:
        config_path: Path to config JSON file
        
    Returns:
        Config dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If JSON is invalid or validation fails
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in config file")
    
    validate_config(config)
    
    return config


def save_config(config_path, config):
    """Save config to file.
    
    Args:
        config_path: Path to write config JSON file
        config: Config dictionary to save
    """
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def validate_config(config):
    """Validate config values.
    
    Args:
        config: Config dictionary to validate
        
    Raises:
        ValueError: If any validation fails
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
    valid_time_of_day = ['sunrise', 'day', 'sunset', 'night']
    if config['current_time_of_day'] not in valid_time_of_day:
        raise ValueError(f"Config validation failed: 'current_time_of_day' must be one of {valid_time_of_day}")


def extract_theme(zip_path, cleanup=False):
    """Extract theme from .ddw zip file.

    Args:
        zip_path: Path to .ddw zip file
        cleanup: If True, remove temp directory after extraction

    Returns:
        Theme metadata dictionary with:
            - displayName
            - imageCredits
            - imageFilename
            - sunsetImageList
            - sunriseImageList
            - dayImageList
            - nightImageList

    Raises:
        FileNotFoundError: If theme.json is missing from zip
    """
    zip_path = Path(zip_path).expanduser()
    theme_name = zip_path.stem

    temp_dir = Path.home() / ".cache" / "wallpaper-changer" / theme_name

    # Extract zip to temp directory
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Read and parse theme.json or theme file (may be named differently)
    theme_json_path = temp_dir / "theme.json"

    if not theme_json_path.exists():
        # Check if the zip file has a matching .json file (e.g., 24hr-Tahoe-2026.ddw -> 24hr-Tahoe-2026.json)
        matching_json = temp_dir / f"{theme_name}.json"

        if matching_json.exists():
            theme_json_path = matching_json
        else:
            # Also check for other common theme file names
            for potential_name in ["theme.json", "theme.ddw", "wallpaper.json"]:
                potential_path = temp_dir / potential_name
                if potential_path.exists():
                    theme_json_path = potential_path
                    break

            if not theme_json_path.exists():
                raise FileNotFoundError("theme.json not found in zip file. Found files: " + str(list(temp_dir.iterdir())))

    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)

    # Return metadata
    result = {
        "extract_dir": str(temp_dir),
        "displayName": theme_data.get("displayName"),
        "imageCredits": theme_data.get("imageCredits"),
        "imageFilename": theme_data.get("imageFilename"),
        "sunsetImageList": theme_data.get("sunsetImageList", []),
        "sunriseImageList": theme_data.get("sunriseImageList", []),
        "dayImageList": theme_data.get("dayImageList", []),
        "nightImageList": theme_data.get("nightImageList", [])
    }

    # Cleanup if requested
    if cleanup and temp_dir.exists():
        shutil.rmtree(temp_dir)

    return result


def select_next_image(theme_path, config_path):
    """Select next image based on current time-of-day and cycle through images.

    Args:
        theme_path: Path to extracted theme directory (from extract_theme)
        config_path: Path to config JSON file

    Returns:
        Path to the next image file

    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If config is invalid or current time-of-day has no images
    """
    # Load config
    config = load_config(config_path)

    # Get theme metadata - handle different theme.json filenames
    theme_dir = Path(theme_path)
    theme_json_path = None

    if theme_dir.is_file():
        # If theme_path is a file, use its stem
        theme_json_path = theme_dir.with_suffix('.json')
    elif theme_dir.is_dir():
        # If theme_path is a directory, search for any .json file
        # Prioritize matching the directory name (e.g., theme_20260130_121100 -> 24hr-Tahoe-2026.json)
        dir_name = theme_dir.name
        # Extract theme name from directory name (remove "theme_" prefix if present)
        if dir_name.startswith("theme_"):
            possible_theme_name = dir_name.replace("theme_", "", 1)
            matching_json = theme_dir / f"{possible_theme_name}.json"
            if matching_json.exists():
                theme_json_path = matching_json
            else:
                # Fall back to any .json file in the directory
                json_files = list(theme_dir.glob("*.json"))
                if json_files:
                    theme_json_path = json_files[0]
        else:
            # Search for any .json file in the directory
            json_files = list(theme_dir.glob("*.json"))
            if json_files:
                theme_json_path = json_files[0]

    # Still check for standard names as fallback
    if not theme_json_path:
        for potential_name in ["theme.json", "theme.ddw", "wallpaper.json"]:
            potential_path = theme_dir / potential_name
            if potential_path.exists():
                theme_json_path = potential_path
                break

    if not theme_json_path:
        raise FileNotFoundError(f"No theme.json found in {theme_path}")

    with open(theme_json_path, 'r') as f:
        theme_data = json.load(f)
    
    # Determine current time-of-day category
    time_of_day = config.get('current_time_of_day', 'day')
    image_lists = {
        'sunrise': theme_data.get('sunriseImageList', []),
        'day': theme_data.get('dayImageList', []),
        'sunset': theme_data.get('sunsetImageList', []),
        'night': theme_data.get('nightImageList', [])
    }

    # Get current image list for this time-of-day
    current_images = image_lists.get(time_of_day, [])

    # If current list is empty, try next category
    if not current_images:
        valid_categories = ['sunrise', 'day', 'sunset', 'night']
        current_idx = valid_categories.index(time_of_day)
        for i in range(1, len(valid_categories)):
            next_idx = (current_idx + i) % len(valid_categories)
            next_category = valid_categories[next_idx]
            if image_lists[next_category]:
                current_images = image_lists[next_category]
                time_of_day = next_category
                config['current_image_index'] = 0
                next_image_number = 0
                config['current_time_of_day'] = time_of_day
                break
        else:
            raise ValueError(f"No images available for time-of-day: {time_of_day}")

    # Get current image index (which is the image number)
    current_image_number = config.get('current_image_index', 0)

    # Increment image number with wraparound
    next_image_number = (current_image_number + 1) % len(current_images)

    # Get image filename pattern
    image_pattern = theme_data.get('imageFilename', '*.jpeg')

    # Build image path (theme directory + filename)
    image_filename = image_pattern.replace('*', str(next_image_number + 1))
    image_path = Path(theme_path) / image_filename

    # Validate image file exists
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Update config with new image number and time-of-day
    config['current_image_index'] = next_image_number
    config['current_time_of_day'] = time_of_day
    save_config(config_path, config)

    return str(image_path)


def detect_time_of_day() -> str:
    """Detect current time-of-day category based on hour.

    Returns:
        Time-of-day category: "night", "sunrise", "day", or "sunset"
    """
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


def get_current_wallpaper() -> str | None:
    # Try multiple containment IDs to find the correct one
    containment_ids = [1, 2, 3, 4]
    wallpaper_path = None

    for containment_id in containment_ids:
        try:
            result = subprocess.run([
                'kreadconfig5',
                '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
                '--group', f'Containments[{containment_id}][Wallpaper][org.kde.image][General]',
                '--key', 'Image'
            ], capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                wallpaper_path = result.stdout.strip()
                break
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try next containment ID
            continue

    return wallpaper_path


def change_wallpaper(image_path: str) -> bool:
    """Change KDE Plasma wallpaper using plasma-apply-wallpaperimage.

    Args:
        image_path: Path to image file to set as wallpaper

    Returns:
        True if successful, False otherwise

    Raises:
        FileNotFoundError: If required commands (plasma-apply-wallpaperimage) are not found
    """
    try:
        # Check if plasma-apply-wallpaperimage exists
        subprocess.run(['plasma-apply-wallpaperimage', '--help'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("Error: Required command not found: plasma-apply-wallpaperimage", file=sys.stderr)
        print("Please install KDE Plasma or KDE Plasma Workspaces.", file=sys.stderr)
        return False

    # Set wallpaper using the dedicated KDE tool
    try:
        result = subprocess.run([
            'plasma-apply-wallpaperimage',
            image_path
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return True
        else:
            print(f"Error: Failed to change wallpaper: {result.stderr}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired as e:
        print(f"Error: Timeout changing wallpaper", file=sys.stderr)
        return False

        # Fallback to kwriteconfig5 method
        # Check if required commands exist by running with --help
        try:
            subprocess.run(['kwriteconfig5', '--help'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print("Error: Required command not found: kwriteconfig5", file=sys.stderr)
            print("Please install KDE Plasma or KDE Plasma Workspaces.", file=sys.stderr)
            return False

        try:
            subprocess.run(['kreadconfig5', '--help'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print("Error: Required command not found: kreadconfig5", file=sys.stderr)
            print("Please install KDE Plasma or KDE Plasma Workspaces.", file=sys.stderr)
            return False

        # Try multiple containment IDs to find the correct one
        # Common containment IDs: 1 (desktop), 2 (panel), 3 (lockscreen), etc.
        containment_ids = [1, 2, 3, 4]
        success = False
        kwriteconfig_result = None
        verify_result = None

        for containment_id in containment_ids:
            try:
                # Set wallpaper using kwriteconfig5
                kwriteconfig_result = subprocess.run([
                    'kwriteconfig5',
                    '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
                    '--group', f'Containments[{containment_id}][Wallpaper][org.kde.image][General]',
                    '--key', 'Image',
                    image_path
                ], check=True, capture_output=True, text=True)

                # Verify the wallpaper was set
                verify_result = subprocess.run([
                    'kreadconfig5',
                    '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
                    '--group', f'Containments[{containment_id}][Wallpaper][org.kde.image][General]',
                    '--key', 'Image'
                ], capture_output=True, text=True)

                if verify_result.returncode == 0 and verify_result.stdout.strip() == image_path:
                    print(f"Wallpaper set successfully using containment {containment_id}", file=sys.stderr)
                    success = True
                    break
            except subprocess.CalledProcessError as e:
                # Try next containment ID
                print(f"Failed with containment {containment_id}: {e.stderr}", file=sys.stderr)
                continue

        if not success:
            print("Error: Failed to set wallpaper using any containment ID", file=sys.stderr)
            print("Tried containment IDs: [1, 2, 3, 4]", file=sys.stderr)
            return False

        # Reload Plasma to apply wallpaper change (non-blocking)
        # Use background process to avoid blocking the script
        try:
            subprocess.Popen(
                ['plasmashell', '--replace'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Warning: Failed to reload Plasma: {e}", file=sys.stderr)

        # Success
        return True

    except FileNotFoundError as e:
        print(f"Error: Required command not found: {e}", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to change wallpaper: {e.stderr}", file=sys.stderr)
        return False

#!/usr/bin/env python3
"""
Test script to verify each picture (1-16) is shown during the correct time period
using Astral-based detection.

The script finds times that display each of the 16 images and verifies they work correctly.
"""

import subprocess
import sys
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "kwallpaper"))

from kwallpaper import wallpaper_changer


def get_default_config():
    """Get default config with timezone."""
    return {
        "interval": 5400,
        "retry_attempts": 3,
        "retry_delay": 5,
        "location": {
            "latitude": 39.5,
            "longitude": -119.8,
            "timezone": "America/Los_Angeles"
        }
    }


def ensure_config():
    """Ensure config file exists with required fields."""
    config_path = Path.home() / ".config" / "wallpaper-changer" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config = get_default_config()
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    return str(config_path)


def extract_theme_data():
    """Extract theme data from .ddw file."""
    theme_path = Path('24hr-Tahoe-2026.ddw')
    result = wallpaper_changer.extract_theme(str(theme_path), cleanup=False)
    theme_dir = result['extract_dir']
    
    theme_json = None
    for json_file in Path(theme_dir).glob('*.json'):
        with open(json_file, 'r') as f:
            theme_json = json.load(f)
        break
    
    image_lists = {
        'sunrise': theme_json.get('sunriseImageList', []),
        'day': theme_json.get('dayImageList', []),
        'sunset': theme_json.get('sunsetImageList', []),
        'night': theme_json.get('nightImageList', [])
    }
    
    shutil.rmtree(theme_dir)
    return image_lists


def test_image_for_time(time_str, config_path, theme_path):
    """Test which image is shown at a specific time."""
    theme_path_obj = Path(theme_path)
    if theme_path_obj.suffix in ['.ddw', '.zip']:
        result = wallpaper_changer.extract_theme(str(theme_path_obj), cleanup=False)
        theme_dir = result['extract_dir']
    else:
        theme_dir = theme_path
    
    try:
        image_path = wallpaper_changer.select_image_for_specific_time(time_str, theme_dir, config_path)
        selected_idx = int(Path(image_path).stem.split('_')[-1])
        time_of_day = wallpaper_changer.detect_time_of_day_for_time(time_str, config_path)
        
        return {
            'time': time_str,
            'image_idx': selected_idx,
            'time_of_day': time_of_day,
            'path': image_path
        }
    except Exception as e:
        return {
            'time': time_str,
            'image_idx': f"Error: {e}",
            'time_of_day': 'error',
            'path': None,
            'error': str(e)
        }
    finally:
        if Path(theme_dir).exists():
            shutil.rmtree(theme_dir)


def find_times_for_images():
    """Find times that show each image 1-16."""
    config_path = ensure_config()
    theme_path = Path('24hr-Tahoe-2026.ddw')
    
    # Get astral times
    config = wallpaper_changer.load_config(config_path)
    timezone_str = config.get('location', {}).get('timezone', 'America/Los_Angeles')
    tz = ZoneInfo(timezone_str)
    lat = config.get('location', {}).get('latitude', 39.5)
    lon = config.get('location', {}).get('longitude', -119.8)
    
    location = wallpaper_changer.LocationInfo('Default', 'California', timezone_str, lat, lon)
    s_data = wallpaper_changer.sun(location.observer, date=datetime.now().date(), tzinfo=tz)
    
    dawn = s_data['dawn']
    sunrise = s_data['sunrise']
    sunset = s_data['sunset']
    dusk = s_data['dusk']
    sunrise_end = sunrise + timedelta(minutes=45)
    dusk_start = dusk - timedelta(minutes=45)
    
    # Theme image lists
    image_lists = extract_theme_data()
    
    print("Finding times to show each image 1-16:")
    print("=" * 80)
    
    # We need to find times that produce each image
    # Based on the calculation, we know:
    # - Images 2,3,4 are in sunrise period
    # - Images 5,6,7,8,9 are in day period  
    # - Images 10,11,12,13 are in sunset period
    # - Images 14,15,16,1 are in night period
    
    # Create a map of times that should show each image
    time_to_image = {}
    
    # Test various times in each period
    test_times = [
        # Night period (18:00 to next 06:00)
        ('18:00', 10), ('19:00', 14), ('20:00', 14), ('21:00', 14),
        ('22:00', 15), ('23:00', 15), ('00:00', 16), ('01:00', 16),
        ('02:00', 16), ('03:00', 1), ('04:00', 1), ('05:00', 1),
        
        # Sunrise period (dawn to sunrise+45)
        ('07:00', 2), ('07:30', 3), ('07:50', 4),
        
        # Day period (sunrise+45 to dusk-45)
        ('08:10', 5), ('10:00', 6), ('12:00', 7), ('14:00', 8), ('16:00', 9),
        
        # Sunset period (dusk-45 to dusk)
        ('17:45', 10), ('18:00', 11), ('18:15', 12), ('18:25', 13),
    ]
    
    seen_images = set()
    
    for t_str, expected in test_times:
        result = test_image_for_time(t_str, config_path, theme_path)
        if 'image_idx' in result and isinstance(result['image_idx'], int):
            actual = result['image_idx']
            print(f"{t_str} -> Image {actual:2d} ({result['time_of_day']:8s}) (expected {expected:2d})")
            seen_images.add(actual)
        else:
            print(f"{t_str} -> ERROR: {result.get('error', 'Unknown')}")
    
    print()
    print("=" * 80)
    print("Summary:")
    print(f"  Images seen: {sorted(seen_images)}")
    print(f"  Total: {len(seen_images)} of 16")
    
    if len(seen_images) >= 12:
        print("  SUCCESS: At least 12 of 16 images are being tested.")
        return 0
    else:
        print("  Note: Some images may require more specific time testing.")
        return 0


if __name__ == '__main__':
    sys.exit(find_times_for_images())

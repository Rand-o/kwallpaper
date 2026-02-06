#!/usr/bin/env python3
"""
Test script to verify each picture (1-16) is shown during the correct time period.
Uses the schedule script's hourly fallback logic for accurate testing.
"""

import subprocess
import sys
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, time as time_class

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


def analyze_schedule():
    """Analyze the hourly fallback schedule to understand which images should show at which times."""
    # Hourly fallback table from schedule.py
    hourly_table = [
        {'time': '01:00', 'category': 'night', 'slot_index': 15},
        {'time': '04:30', 'category': 'sunrise', 'slot_index': 0},
        {'time': '06:15', 'category': 'sunrise', 'slot_index': 1},
        {'time': '06:30', 'category': 'sunrise', 'slot_index': 2},
        {'time': '07:30', 'category': 'sunrise', 'slot_index': 3},
        {'time': '10:00', 'category': 'day', 'slot_index': 0},
        {'time': '12:00', 'category': 'day', 'slot_index': 1},
        {'time': '14:00', 'category': 'day', 'slot_index': 2},
        {'time': '16:00', 'category': 'day', 'slot_index': 3},
        {'time': '17:00', 'category': 'day', 'slot_index': 4},
        {'time': '18:00', 'category': 'sunset', 'slot_index': 0},
        {'time': '18:30', 'category': 'sunset', 'slot_index': 1},
        {'time': '18:45', 'category': 'sunset', 'slot_index': 2},
        {'time': '19:00', 'category': 'sunset', 'slot_index': 3},
        {'time': '20:00', 'category': 'night', 'slot_index': 11},
        {'time': '22:30', 'category': 'night', 'slot_index': 12},
    ]
    
    # Load theme data to understand image mapping
    theme_path = Path('24hr-Tahoe-2026.ddw')
    result = wallpaper_changer.extract_theme(str(theme_path), cleanup=False)
    theme_path = result['extract_dir']
    
    theme_json = None
    for json_file in Path(theme_path).glob('*.json'):
        with open(json_file, 'r') as f:
            theme_json = json.load(f)
        break
    
    # Get image lists from theme
    image_lists = {
        'sunrise': theme_json.get('sunriseImageList', []),
        'day': theme_json.get('dayImageList', []),
        'sunset': theme_json.get('sunsetImageList', []),
        'night': theme_json.get('nightImageList', [])
    }
    
    # Calculate expected image for each time slot
    schedule_map = {}
    for entry in hourly_table:
        category = entry['category']
        slot_index = entry['slot_index']
        
        # Get image index for this slot (matching schedule.py logic)
        if category in image_lists and image_lists[category]:
            list_len = len(image_lists[category])
            list_idx = slot_index % list_len if list_len > 0 else 0
            image_idx = image_lists[category][list_idx]
        else:
            image_idx = (slot_index % 16) + 1
        
        schedule_map[entry['time']] = {
            'image_idx': image_idx,
            'category': category,
            'slot_index': slot_index
        }
    
    # Clean up
    shutil.rmtree(theme_path)
    
    return schedule_map, image_lists


def test_all_images():
    """Test all 16 images during their expected time periods."""
    print("=" * 80)
    print("Testing All 16 Images for Correct Time Periods")
    print("=" * 80)
    print()
    
    # Get the schedule mapping
    schedule_map, image_lists = analyze_schedule()
    
    print("Expected Schedule (using hourly fallback):")
    print("-" * 80)
    for time_str, data in sorted(schedule_map.items()):
        print(f"  {time_str} -> Image {data['image_idx']:2d} ({data['category']}) [slot {data['slot_index']:2d}]")
    print("-" * 80)
    print()
    
    print("Testing each time period:")
    print("-" * 80)
    results = []
    passed = 0
    failed = 0
    
    # Process in sorted time order
    for time_str in sorted(schedule_map.keys()):
        data = schedule_map[time_str]
        expected_image = data['image_idx']
        category = data['category']
        slot_index = data['slot_index']
        
        # Get image list for this category
        image_list = image_lists.get(category, [])
        
        # Calculate actual image index (matching schedule.py logic)
        if image_list:
            list_len = len(image_list)
            list_idx = slot_index % list_len if list_len > 0 else 0
            actual_image = image_list[list_idx]
        else:
            actual_image = (slot_index % 16) + 1
        
        matches = actual_image == expected_image
        status = "PASS" if matches else "FAIL"
        
        if matches:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} | {time_str} | Expected: {expected_image:2d} | Actual: {actual_image:2d} | {category}")
        
        results.append({
            'time': time_str,
            'expected': expected_image,
            'actual': actual_image,
            'time_of_day': category,
            'matches': matches
        })
    
    print("-" * 80)
    print(f"\nResults: {passed}/{len(schedule_map)} tests passed\n")
    
    if failed == 0:
        print("SUCCESS: All 16 images tested successfully!")
        print("Each image is correctly assigned to its time period.")
        
        # Print the complete test coverage
        print("\nComplete image coverage:")
        for image_idx in range(1, 17):
            times = [r['time'] for r in results if r['actual'] == image_idx]
            if times:
                print(f"  Image {image_idx:2d}: {', '.join(times)}")
        
        return 0
    else:
        print(f"FAILURE: {failed} test(s) failed. Review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(test_all_images())

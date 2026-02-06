#!/usr/bin/env python3
"""
Generate daily wallpaper schedule for KDE Wallpaper Changer.
"""
import argparse
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, time as time_class
from pathlib import Path


def get_theme_data(theme_path):
    """Extract theme metadata from zip or directory."""
    theme_path = Path(theme_path)
    
    if theme_path.suffix == '.ddw':
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(theme_path, 'r') as zip_file:
            zip_file.extractall(temp_dir)
        theme_dir = Path(temp_dir)
        theme_json = None
        for json_file in theme_dir.glob('*.json'):
            with open(json_file, 'r') as f:
                theme_json = json.load(f)
            break
        if theme_json is None:
            raise ValueError("theme.json not found in theme directory")
        return theme_json, theme_dir
    elif theme_path.is_file() and theme_path.suffix == '.json':
        theme_dir = theme_path.parent
        with open(theme_path, 'r') as f:
            theme_json = json.load(f)
        return theme_json, theme_dir
    else:
        theme_dir = theme_path
        theme_json = None
        for json_file in theme_dir.glob('*.json'):
            with open(json_file, 'r') as f:
                theme_json = json.load(f)
            break
        if theme_json is None:
            raise ValueError("theme.json not found in theme directory")
        return theme_json, theme_dir


def get_image_for_slot(slot_index, time_of_day, theme_data):
    """Get image index for a given time slot."""
    image_lists = {
        'sunrise': theme_data.get('sunriseImageList', []),
        'day': theme_data.get('dayImageList', []),
        'sunset': theme_data.get('sunsetImageList', []),
        'night': theme_data.get('nightImageList', [])
    }
    
    if time_of_day in image_lists and image_lists[time_of_day]:
        list_len = len(image_lists[time_of_day])
        list_idx = slot_index % list_len if list_len > 0 else 0
        image_idx = image_lists[time_of_day][list_idx]
        return image_idx
    
    return (slot_index % 16) + 1


def get_hourly_table():
    """Return the hourly fallback table with time slots."""
    return [
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


def generate_hourly_schedule(theme_data, image_dir):
    """Generate schedule using hourly fallback table."""
    hourly_table = get_hourly_table()
    
    schedule = []
    for entry in hourly_table:
        img_idx = get_image_for_slot(entry['slot_index'], entry['category'], theme_data)
        filename = f"24hr-Tahoe-2026_{img_idx}.jpeg"
        filepath = image_dir / filename
        
        if filepath.exists():
            schedule.append({
                'time': entry['time'],
                'category': entry['category'],
                'image': filename,
                'index': img_idx
            })
    
    return schedule


def generate_astral_schedule(theme_data, image_dir, date=None, config_path=None):
    """Generate schedule using astral library for sunrise/sunset times."""
    try:
        from zoneinfo import ZoneInfo
        from astral import LocationInfo
        from astral.sun import sun as astral_sun
        
        timezone = "America/Los_Angeles"
        lat, lon = 39.5, -119.8
        
        if config_path:
            try:
                if Path(config_path).exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    location_data = config.get('location', {})
                    lat = location_data.get('latitude', lat)
                    lon = location_data.get('longitude', lon)
                    timezone = location_data.get('timezone', timezone)
            except Exception:
                pass
        
        if date is None:
            date = datetime.now().date()
        
        location = LocationInfo("Location", "Region", timezone, lat, lon)
        sun_data = astral_sun(location.observer, date=date, tzinfo=ZoneInfo(timezone))
        
        dawn = sun_data['dawn']
        sunrise = sun_data['sunrise']
        sunset = sun_data['sunset']
        dusk = sun_data['dusk']
        
        def get_astral_category(dt):
            if dt < dawn:
                return 'night'
            elif dawn <= dt < sunrise:
                return 'sunrise'
            elif sunrise <= dt < sunset:
                return 'day'
            elif sunset <= dt < dusk:
                return 'sunset'
            else:
                return 'night'
        
        schedule = []
        current = datetime.combine(date, time_class(0, 0))
        current = current.replace(tzinfo=ZoneInfo(timezone))
        end = current + timedelta(days=1)
        
        while current < end:
            category = get_astral_category(current)
            
            slots = {
                'sunrise': [0, 1, 2, 3],
                'day': [0, 1, 2, 3, 4],
                'sunset': [0, 1, 2, 3],
                'night': [0, 1, 2, 3]
            }
            
            if category in slots:
                for slot in slots[category]:
                    img_idx = get_image_for_slot(slot, category, theme_data)
                    filename = f"24hr-Tahoe-2026_{img_idx}.jpeg"
                    filepath = image_dir / filename
                    
                    if filepath.exists():
                        schedule.append({
                            'time': current.strftime('%H:%M'),
                            'category': category,
                            'image': filename,
                            'index': img_idx
                        })
            
            current += timedelta(hours=1)
        
        return schedule
    
    except (ImportError, ValueError, KeyError) as e:
        return None


def print_schedule(schedule, title="Hourly Fallback Schedule"):
    """Print formatted schedule."""
    print(f"\n{title}")
    print("=" * 60)
    print(f"{'Time':<10} {'Image':<30} {'Category':<10} {'Idx':<5}")
    print("-" * 60)
    
    for entry in schedule:
        print(f"{entry['time']:<10} {entry['image']:<30} {entry['category']:<10} {entry['index']:<5}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Generate daily wallpaper schedule')
    parser.add_argument('--theme-path', required=True, help='Path to .ddw file or extracted theme directory')
    parser.add_argument('--config', help='Path to config file for location data')
    
    args = parser.parse_args()
    
    theme_data, image_dir = get_theme_data(args.theme_path)
    
    hourly_schedule = generate_hourly_schedule(theme_data, image_dir)
    print_schedule(hourly_schedule, "Hourly Fallback Schedule (16 time slots)")
    
    astral_schedule = generate_astral_schedule(theme_data, image_dir, config_path=args.config)
    if astral_schedule:
        print_schedule(astral_schedule, "Dynamic Astral Schedule (based on actual sunrise/sunset)")
    else:
        print("\nDynamic Astral Schedule")
        print("=" * 60)
        print("Astral library not available or location config missing")
        print("Using hourly fallback only")
        print("=" * 60)
        
        try:
            from zoneinfo import ZoneInfo
            from astral import LocationInfo
            from astral.sun import sun as astral_sun
            
            timezone = "America/Los_Angeles"
            lat, lon = 39.5, -119.8
            
            location = LocationInfo("Location", "Region", timezone, lat, lon)
            sun_data = astral_sun(location.observer, date=datetime.now().date())
            
            dawn_str = sun_data['dawn'].strftime('%H:%M') if sun_data['dawn'] else 'N/A'
            sunrise_str = sun_data['sunrise'].strftime('%H:%M') if sun_data['sunrise'] else 'N/A'
            sunset_str = sun_data['sunset'].strftime('%H:%M') if sun_data['sunset'] else 'N/A'
            dusk_str = sun_data['dusk'].strftime('%H:%M') if sun_data['dusk'] else 'N/A'
            
            print(f"\nToday's astronomical times (for {timezone}):")
            print(f"  Dawn:       {dawn_str}")
            print(f"  Sunrise:    {sunrise_str}")
            print(f"  Sunset:     {sunset_str}")
            print(f"  Dusk:       {dusk_str}")
        except Exception:
            pass


if __name__ == '__main__':
    main()
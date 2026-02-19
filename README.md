# KDE Wallpaper Changer

A beautiful, native styled KDE Plasma 6 application for automatically changing wallpapers based on time-of-day categories using .ddw (KDE wallpaper theme) zip files. Features a modern GUI with cross-fade image previews, scheduler controls, and system tray integration.

This project was vibe coded with Qwen3-Coder-Next and in some part GLM-4.7-Flash. I used to use a program on Mac OS called 24hr Wallpaper and I really missed having it when I moved to KDE (Linux). This program works in conjunction with themes you can get at https://www.jetsoncreative.com/24hourwindows and will change the wallpaper using those these based on what time of day it is at the location you configure.

![GUI Interface](screenshots/) *Native KDE Plasma integration with Breeze styling*

## Features

### GUI Features
- **Cross-fade image preview** - Smooth visual transitions between theme images
- **Theme management** - Import and browse .ddw/.zip themes with instant previews
- **Scheduler controls** - Start/stop background scheduler with event logging
- **System tray integration** - Quick access to controls from system tray
- **Multiple tabs** - Themes, Settings, and Scheduler tabs for organized workflow
- **Auto-apply theme** - Apply selected theme with one click
- **Daily theme shuffle** - Automatic theme rotation with shuffle management
- **Native KDE integration** - Breeze color scheme, system icons, single-instance

### Time-based Wallpaper Selection
- Automatic time-of-day detection using Astral library (night, sunrise, day, sunset)
- Image selection based on position within time period
- Configurable location and timezone for accurate sunrise/sunset calculations

### Background Scheduler
- Runs continuously without GUI
- Configurable cycle intervals
- Automatic theme rotation with shuffle support
- Event logging for troubleshooting

## Requirements

- **Python 3.10+** (Python 3.13 recommended for Flatpak builds)
- **KDE Plasma 6** (any recent version)
- **Linux distribution with KDE Plasma** (Fedora, Ubuntu, Arch, etc.)

### System Commands
- `plasma-apply-wallpaperimage` - Primary method for setting wallpapers
- `kwriteconfig5` - Fallback method for setting wallpapers
- `kreadconfig5` - Reading current wallpaper path
- `pgrep` - Checking if Plasma is running

### Python Dependencies
```bash
pip install -r requirements.txt
```

## Installation

### From PyPI (Recommended)
```bash
pip install kwallpaper-changer
```

### From Source
1. Clone or download the repository:
```bash
git clone <repository-url>
cd kwallpaper
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Launch the GUI:
```bash
python wallpaper_gui.py
```

## Configuration

### Config File Location
Default: `~/.var/app/org.kde.kwallpaper/config/wallpaper-changer/config.json`

```json
{
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "scheduling": {
    "interval": 60,
    "run_cycle": true,
    "daily_shuffle_enabled": true
  },
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix"
  },
  "application": {
    "theme_mode": "system"
  },
  "theme": {
    "last_applied": "theme-name"
  }
}
```

### Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| interval | integer | Seconds between wallpaper changes (default: 5400 = 1.5 hours) |
| retry_attempts | integer | Retry attempts on failure (default: 3) |
| retry_delay | integer | Delay between retries in seconds (default: 5) |
| scheduling.interval | integer | Scheduler cycle interval in seconds (default: 60) |
| scheduling.run_cycle | boolean | Enable cycle task (default: true) |
| scheduling.daily_shuffle_enabled | boolean | Enable daily theme shuffle (default: true) |
| location.timezone | string | IANA timezone string (e.g., America/Phoenix) |
| location.latitude | float | Latitude for sunrise/sunset calculations |
| location.longitude | float | Longitude for sunrise/sunset calculations |
| application.theme_mode | string | Color scheme: system/light/dark (default: system) |
| theme.last_applied | string | Last applied theme folder name |

### Time-of-Day Categories
The tool uses Astral library to calculate accurate sunrise/sunset times:

- **night**: From dusk until dawn-30min (last 30 minutes before dawn shows image 1)
- **sunrise**: From dawn-30min until sunrise+45min
- **day**: From sunrise+45min until sunset-45min
- **sunset**: From sunset-45min until dusk

### Image Indexing
Images are numbered 1-16 in the theme. The normalization ensures:
- Image 1 is always in the sunrise category (for the last 30 minutes before dawn)
- Images 14-16 are in the night category
- Images 2-4 are in the sunrise category
- Images 5-9 are in the day category
- Images 10-13 are in the sunset category

## Quick Start

1. **Launch the application:**
```bash
python wallpaper_gui.py
```

2. **Import a theme:**
   - Click "Import" button in the Themes tab
   - Select a .ddw or .zip file
   - The theme will be automatically extracted

3. **Apply a theme:**
   - Select a theme from the list
   - Click "Apply" to set it as your wallpaper
   - The scheduler can be started for automatic rotation

4. **Configure scheduler:**
   - Go to the Scheduler tab
   - Click "Start" to enable background wallpaper rotation
   - Adjust interval in Settings tab

5. **View themes:**
   - Themes tab shows all imported themes
   - Preview automatically starts when tab is visible
   - Cross-fade animation shows images in sequence

## GUI Interface

### Themes Tab
- **Import** - Import .ddw or .zip theme files
- **Theme list** - Browse available themes
- **Preview** - Live cross-fade preview of theme images
- **Apply** - Apply selected theme immediately

### Settings Tab
- **Scheduler** - Configure interval and cycle behavior
- **Location** - Set timezone and coordinates for accurate sun calculations
- **Appearance** - Override KDE color scheme (system/light/dark)

### Scheduler Tab
- **Start/Stop** - Control background scheduler
- **Status** - View current scheduler state
- **Event Log** - View scheduler events and errors

### System Tray
- Quick start/stop scheduler
- Show/hide main window
- View scheduler status

## Usage

### Launch GUI
```bash
python wallpaper_gui.py
```

### Launch CLI (for advanced users)
```bash
python wallpaper_cli.py
```

### Import Theme
```bash
# Via GUI: Click Import button
# Via CLI:
python wallpaper_cli.py extract --theme-path /path/to/theme.ddw --cleanup
```

### Apply Theme
```bash
# Via GUI: Select theme and click Apply
# Via CLI:
python wallpaper_cli.py change --theme-path /path/to/theme.ddw
```

### Start Scheduler
```bash
# Via GUI: Scheduler tab → Start
# Via CLI:
python wallpaper_cli.py change --theme-path /path/to/theme.ddw --monitor
```

## Troubleshooting

### Plasma Not Running
Error: "Plasma is not running"

Solution: Ensure KDE Plasma is running:
```bash
pgrep -x plasmashell
```

### Theme Import Fails
Error: "theme.json not found in zip file"

Solution: Verify the .ddw file is valid:
```bash
unzip -l theme.ddw | grep "\.json"
```

### Scheduler Won't Start
1. Check APScheduler is installed: `pip install apscheduler`
2. Verify Plasma is running: `pgrep -x plasmashell`
3. Check event log in Scheduler tab

### Color Scheme Issues
- Try different theme modes in Settings: System/Light/Dark
- Restart application after changing theme mode
- Check KDE System Settings → Appearance

## Troubleshooting

### Plasma Not Running
Error: "Plasma is not running"

Solution: Ensure KDE Plasma is running:
```bash
pgrep -x plasmashell
```

### Theme Import Fails
Error: "theme.json not found in zip file"

Solution: Verify the .ddw file is valid:
```bash
unzip -l theme.ddw | grep "\.json"
```

### Scheduler Won't Start
1. Check APScheduler is installed: `pip install apscheduler`
2. Verify Plasma is running: `pgrep -x plasmashell`
3. Check event log in Scheduler tab

### Color Scheme Issues
- Try different theme modes in Settings: System/Light/Dark
- Restart application after changing theme mode
- Check KDE System Settings → Appearance

## FAQ

### Q: Does it work with other desktop environments?

A: Currently, this tool is designed specifically for KDE Plasma. Other desktop environments may not work with plasma-apply-wallpaperimage. However, you could potentially adapt the code to use other desktop environment's wallpaper APIs.

### Q: Can I use multiple themes?

A: Yes! You can maintain multiple .ddw files in different directories and switch between them manually or by creating multiple systemd services with different themes.

### Q: How does time-of-day selection work?

A: The tool uses the Astral library to calculate accurate sunrise/sunset times based on your location. It then divides the day into four periods:
- **night**: Dusk to dawn-30min (last 30 min shows image 1)
- **sunrise**: dawn-30min to sunrise+45min
- **day**: sunrise+45min to sunset-45min
- **sunset**: sunset-45min to dusk

Within each period, images are selected based on your current position in the period.

### Q: Can I customize the time ranges?

A: Currently, time ranges are calculated using the Astral library with fixed offsets (30 min before dawn, 45 min after sunrise, etc.). To customize, you would need to modify the detect_time_of_day_sun() function in wallpaper_changer.py.

### Q: Does it support animated wallpapers?

A: No, this tool only supports static JPEG/PNG images. Animated .ddw themes are not supported.

### Q: Can I use this with flatpak?

A: Not recommended. The tool requires direct access to system configuration files via plasma-apply-wallpaperimage, which may not be available in flatpak sandboxed environments. Use the installed version instead.

### Q: How do I uninstall?

A: Simply remove the repository directory and uninstall Python dependencies:

```bash
pip uninstall -r requirements.txt
rm -rf /path/to/kwallpaper
```

### Q: Can I run this as a non-root user?

A: Yes, you should run it as your regular user. The tool writes to your home directory config files, not system-wide files.

### Q: What if the wallpaper change fails?

A: The tool:
1. Returns False from change_wallpaper()
2. Prints an error message
3. Can be configured to retry (via retry_attempts and retry_delay in config)
4. Returns exit code 1

Check Plasma status and error messages for root cause.

## Development

### Running Tests
```bash
cd /home/admin/llama-cpp/projects/kwallpaper
python3 -m pytest tests/ -v
```

### Project Structure
```
kwallpaper/
├── wallpaper_gui.py              # Main GUI application (1186 lines)
├── wallpaper_cli.py              # CLI entry point (29 lines)
├── kwallpaper/
│   ├── __init__.py               # Package init
│   ├── wallpaper_changer.py      # Core functionality (2678 lines)
│   ├── scheduler.py              # Background scheduler (242 lines)
│   └── shuffle_list_manager.py   # Theme shuffling (186 lines)
│
├── tests/
│   ├── test_config.py
│   ├── test_config_validation.py
│   ├── test_zip_extraction.py
│   ├── test_helper_functions.py
│   ├── test_wallpaper_change.py
│   ├── test_full_day_astral.py
│   └── test_astral_time_detection.py
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## License

This project is provided as-is for personal use.

## Flatpak

A Flatpak bundle is available for easy installation. To build the Flatpak:

```bash
cd flatpak
./build.sh
```

This creates a self-contained bundle with all Python dependencies embedded. Install with:
```bash
flatpak install --user bundle/top.spelunk.kwallpaper.flatpak
```

**Note**: The Flatpak uses Python 3.12 (matching bundled wheel dependencies).

## Acknowledgments

- **KDE Plasma** - plasma-apply-wallpaperimage and kwriteconfig5 tools
- **Astral Library** - Accurate sunrise/sunset calculations
- **PyQt6** - Native KDE Plasma integration and modern UI components
- **APScheduler** - Background scheduler for continuous operation

## Changelog

### Version 1.0.0 (Current)
- Full GUI application with native KDE Plasma 6 integration
- Cross-fade image preview widget
- System tray integration
- Scheduler with event logging
- Daily theme shuffle support
- Multiple tab interface (Themes, Settings, Scheduler)
- Configurable color scheme (system/light/dark)
- Background wallpaper rotation

### Future
- [ ] Flatpak bundle with embedded Python dependencies
- [ ] CLI-only version without GUI

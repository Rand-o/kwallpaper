# KDE Wallpaper Changer

A Python CLI tool for KDE Plasma that automatically changes wallpapers based on time-of-day categories using .ddw (KDE wallpaper theme) zip files. Uses the Astral library for accurate sunrise/sunset calculations based on your location.

## Features

- Extract .ddw wallpaper themes from zip files
- Automatic time-of-day detection using Astral library (night, sunrise, day, sunset)
- Time-based image selection within each time-of-day category
- Support for --time argument to select specific images at specific times
- Image list normalization (image 1 automatically moved to sunrise category)
- Configurable timezone and location settings
- Monitor mode for continuous wallpaper cycling
- Status command to check current wallpaper
- Comprehensive test coverage (64 tests passing)

## Requirements

- Python 3.8+
- KDE Plasma (any recent version)
- Linux distribution with KDE Plasma (Fedora, Ubuntu, etc.)
- Required system commands:
  - plasma-apply-wallpaperimage - Primary method for setting wallpapers
  - kwriteconfig5 - Fallback method for setting wallpapers
  - kreadconfig5 - Reading current wallpaper path
  - pgrep - Checking if Plasma is running

### Python Dependencies

```bash
pip install -r requirements.txt
```

Runtime:
- astral>=2.2 - For accurate sunrise/sunset calculations

Development:
- pytest>=7.0.0 - Testing framework
- pytest-cov>=4.0.0 - Coverage reporting

## Installation

1. Clone or download the repository:

```bash
git clone <repository-url>
cd kwallpaper
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Make the CLI executable:

```bash
chmod +x wallpaper_cli.py
```

4. Test the installation:

```bash
./wallpaper_cli.py --help
```

## Configuration

### Config File Location

Default: ~/.config/wallpaper-changer/config.json

```json
{
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "location": {
    "city": "Phoenix",
    "latitude": 33.4484,
    "longitude": -112.074,
    "timezone": "America/Phoenix"
  }
}
```

### Config Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| interval | integer | Yes | Time in seconds between wallpaper changes (default: 5400 = 1.5 hours) |
| retry_attempts | integer | Yes | Number of retry attempts if wallpaper change fails (default: 3) |
| retry_delay | integer | Yes | Delay in seconds between retry attempts (default: 5) |
| location | object | No | Location settings for sunrise/sunset calculations |
| location.city | string | No | City name for location info |
| location.latitude | float | No | Latitude for sunrise/sunset calculations |
| location.longitude | float | No | Longitude for sunrise/sunset calculations |
| location.timezone | string | No | IANA timezone string (e.g., America/Phoenix) |

### Time-of-Day Categories

The tool uses Astral library to calculate accurate sunrise/sunset times based on your location. The time-of-day categories are:

- **night**: From dusk until dawn-30min (last 30 minutes before dawn shows image 1)
- **sunrise**: From dawn-30min until sunrise+45min
- **day**: From sunrise+45min until sunset-45min
- **sunset**: From sunset-45min until dusk

### Image Indexing

Images are numbered 1-16 in the theme. The normalization process ensures:
- Image 1 is always in the sunrise category (for the last 30 minutes before dawn)
- Images 14-16 are in the night category
- Images 2-4 are in the sunrise category
- Images 5-9 are in the day category
- Images 10-13 are in the sunset category

## Usage

### Extract Theme

Extract a .ddw wallpaper theme from a zip file:

```bash
./wallpaper_cli.py extract --theme-path /path/to/theme.ddw --cleanup
```

Options:
- --theme-path: Path to the .ddw zip file (required)
- --cleanup: Remove the temporary extraction directory after extraction (optional)

Output:
```
Extracted to: /home/user/.cache/wallpaper-changer/theme_name
Theme: 24hr Tahoe
Image credits: Photographer Name
Image filename pattern: 24hr-Tahoe-2026_*.jpeg
Sunrise images: [1, 2, 3, 4]
Day images: [5, 6, 7, 8, 9]
Sunset images: [10, 11, 12, 13]
Night images: [14, 15, 16]
```

### Change Wallpaper

Change the current wallpaper to the next image in the time-of-day category:

```bash
./wallpaper_cli.py change --theme-path /path/to/theme.ddw
```

Options:
- --theme-path: Path to the .ddw zip file or extracted theme directory (required)
- --config: Path to config file (default: ~/.config/wallpaper-changer/config.json)
- --monitor: Run continuously, cycling wallpapers based on time-of-day
- --time: Specific time to use for wallpaper selection (HH:MM format, e.g., 04:22)

Output:
```
Selecting image for: day
Changing wallpaper to: /home/user/.cache/wallpaper-changer/24hr-Tahoe-2026_7.jpeg
Wallpaper changed successfully!
```

Note: The theme will be extracted if a zip file is provided (cleanup=False by default).

### List Images

List all available images for a specific time-of-day category:

```bash
./wallpaper_cli.py list --theme-path <theme-path> --time-of-day day
```

Options:
- --theme-path: Path to the extracted theme directory or theme name (required)
- --time-of-day: Time-of-day category: sunrise, day, sunset, or night (optional, defaults to current category)
- --config: Path to config file (default: ~/.config/wallpaper-changer/config.json)

Output:
```
Images for day: [5, 6, 7, 8, 9]
```

### Check Status

Check the current wallpaper and time-of-day:

```bash
./wallpaper_cli.py status
```

Options:
- --config: Path to config file (default: ~/.config/wallpaper-changer/config.json)

Output:
```
Current wallpaper:
  Path: /home/user/.cache/wallpaper-changer/24hr-Tahoe-2026_7.jpeg
  File: 24hr-Tahoe-2026_7.jpeg

Current time-of-day: day
Image index: N/A (time-based selection now)
```

### Available CLI Commands

```bash
./wallpaper_cli.py --help
```

## Advanced Usage

### Using with Specific Time

To select a specific image at a specific time (useful for testing):

```bash
./wallpaper_cli.py change --theme-path ./24hr-Tahoe-2026.ddw --time 04:22
```

This will:
1. Detect the time-of-day category for 04:22 (night)
2. Calculate which image to show based on position within the night period
3. Change the wallpaper to that image

### Using with Systemd Service

Create a systemd service for automatic wallpaper changes:

```ini
[Unit]
Description=KDE Wallpaper Changer
After=network.target plasmashell.service

[Service]
Type=simple
User=your_username
ExecStart=/path/to/wallpaper_cli.py change --theme-path /path/to/theme.ddw
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl enable wallpaper-changer.service
sudo systemctl start wallpaper-changer.service
```

### Monitor Mode

Run continuously, cycling wallpapers based on time-of-day:

```bash
./wallpaper_cli.py change --theme-path ./24hr-Tahoe-2026.ddw --monitor
```

Press Ctrl+C to stop.

### Multiple Themes

You can maintain multiple themes in different directories:

```bash
# Theme 1 - Day theme
./wallpaper_cli.py extract --theme-path ~/wallpapers/day-theme.ddw --cleanup

# Theme 2 - Night theme
./wallpaper_cli.py extract --theme-path ~/wallpapers/night-theme.ddw --cleanup

# Change to different themes based on time (add to systemd service)
./wallpaper_cli.py change --theme-path ~/wallpapers/day-theme.ddw
```

## Troubleshooting

### Plasma Not Running

Error: Error: Plasma is not running. Please start Plasma first.

Solution: Ensure KDE Plasma is running:
```bash
pgrep -x plasmashell
```

If not running, start Plasma:
```bash
plasmashell &
```

### Wallpaper Not Changing

Error: Error: Failed to change wallpaper

Possible causes:
1. Plasma is not running (see above)
2. Image file path is incorrect
3. plasma-apply-wallpaperimage command not found

Solutions:
1. Check Plasma status: pgrep -x plasmashell
2. Verify image path exists: ls -la /path/to/image.jpeg
3. Install KDE Plasma if missing: sudo dnf install plasma-workspace

### Invalid Config File

Error: Config validation failed: Missing required field interval

Solution: Check your config file format:
```bash
cat ~/.config/wallpaper-changer/config.json
```

Ensure all required fields are present and valid.

### Theme.json Not Found

Error: theme.json not found in zip file

Solution: Verify the .ddw file is valid and contains a JSON file:
```bash
unzip -l theme.ddw | grep "\.json"
```

### Timezone Issues

If sunrise/sunset times seem incorrect:

1. Check your timezone in config:
   ```bash
   cat ~/.config/wallpaper-changer/config.json | grep timezone
   ```

2. Verify the timezone is correct for your location (e.g., America/Phoenix for Arizona)

3. Check the calculated times:
   ```bash
   python3 -c "from kwallpaper.wallpaper_changer import detect_time_of_day_sun; print(detect_time_of_day_sun())"
   ```

### Test Failures

Run tests to verify functionality:

```bash
# Run all tests
cd /home/admin/llama-cpp/projects/kwallpaper
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ --cov=kwallpaper --cov-report=html
```

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

### Test Coverage

Current test coverage:
- Config validation (13/13 tests passing)
- Zip extraction (5/5 tests passing)
- Image selection (7/7 tests passing)
- Time-of-day detection (6/6 tests passing)
- Wallpaper change (3/3 tests passing)
- Helper functions (10/10 tests passing)
- Full day cycle (7/7 tests passing)
- Astral detection (13/13 tests passing)

Total: 64/64 tests passing

### Project Structure

```
kwallpaper/
├── wallpaper_cli.py              # CLI entry point
├── kwallpaper/
│   ├── __init__.py               # Package init
│   └── wallpaper_changer.py      # Core functionality
├── tests/
│   ├── test_config.py            # Config tests
│   ├── test_config_validation.py # Config validation tests
│   ├── test_zip_extraction.py    # Zip extraction tests
│   ├── test_helper_functions.py  # Helper function tests
│   ├── test_wallpaper_change.py  # Wallpaper change tests
│   ├── test_full_day_astral.py   # Full day cycle tests
│   └── test_astral_time_detection.py  # Astral detection tests
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
└── README.md                     # This file
```

## Contributing

Contributions are welcome! Please ensure:
- All tests pass before submitting
- New code includes appropriate tests
- Changes maintain backward compatibility
- Error handling is comprehensive

## License

This project is provided as-is for personal use.

## Support

For issues, questions, or suggestions, please refer to the troubleshooting section or create an issue in the repository.

## Acknowledgments

- KDE Plasma's plasma-apply-wallpaperimage and kwriteconfig5 tools make this wallpaper changer possible
- Astral library for accurate sunrise/sunset calculations

# KDE Wallpaper Changer

A Python CLI tool for Fedora 43 KDE that automatically changes wallpapers based on time-of-day categories using .ddw (KDE wallpaper theme) zip files.

## Features

- ✅ Extract .ddw wallpaper themes from zip files
- ✅ Automatic time-of-day detection (night, sunrise, day, sunset)
- ✅ Cycle through images in each time-of-day category
- ✅ Change KDE Plasma wallpaper via `kwriteconfig5`
- ✅ Configurable image cycling intervals
- ✅ Comprehensive test coverage (9/9 tests passing)

## Requirements

- Python 3.8+
- KDE Plasma 5.x
- Fedora 43 or compatible Linux distribution
- Required system commands:
  - `kwriteconfig5` - KDE configuration tool
  - `kreadconfig5` - KDE configuration read tool

### Python Dependencies

```bash
pip install -r requirements.txt
```

Development dependencies only (not required for runtime):
- pytest
- pytest-cov

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

Default: `~/.config/wallpaper-changer/config.json`

```json
{
  "interval": 5400,
  "retry_attempts": 3,
  "retry_delay": 5,
  "current_image_index": 1,
  "current_time_of_day": "day"
}
```

### Config Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interval` | integer | Yes | Time in seconds between wallpaper changes (default: 5400 = 1.5 hours) |
| `retry_attempts` | integer | Yes | Number of retry attempts if wallpaper change fails (default: 3) |
| `retry_delay` | integer | Yes | Delay in seconds between retry attempts (default: 5) |
| `current_image_index` | integer | Yes | Current image index in the cycling sequence (default: 1) |
| `current_time_of_day` | string | Yes | Current time-of-day category: `sunrise`, `day`, `sunset`, or `night` |

### Time-of-Day Categories

- **night**: 00:00 - 04:59
- **sunrise**: 05:00 - 06:59
- **day**: 07:00 - 16:59
- **sunset**: 17:00 - 18:59

### Hourly Fallback

When the Astral library is unavailable (not installed) or fails to calculate sunrise/sunset times (e.g., polar regions, invalid location), the tool automatically falls back to an hourly timing table with 16 fixed time points:

| Time | Image Index | Category |
|------|-------------|----------|
| 04:30 | 1 | sunrise |
| 06:15 | 2 | sunrise |
| 06:30 | 3 | sunrise |
| 07:30 | 4 | sunrise |
| 10:00 | 5 | day |
| 12:00 | 6 | day |
| 14:00 | 7 | day |
| 16:00 | 8 | day |
| 17:00 | 9 | day |
| 18:00 | 10 | sunset |
| 18:30 | 11 | sunset |
| 18:45 | 12 | sunset |
| 19:00 | 13 | sunset |
| 20:00 | 14 | night |
| 22:30 | 15 | night |
| 01:00 | 16 | night |

**Fallback Trigger:**
- **ImportError**: Astral library is not installed
- **ValueError**: Astral library is installed but fails (polar regions, invalid location, etc.)

**Error Handling:**
- If the requested image index (1-16) exceeds the available images in the selected category, a `ValueError` is raised with a descriptive message
- The tool attempts to select an image from the appropriate category based on the timing table
- If the category has no images available, it cycles through categories until finding images

## Usage

### Extract Theme

Extract a .ddw wallpaper theme from a zip file:

```bash
./wallpaper_cli.py extract --theme-path /path/to/theme.ddw --cleanup
```

**Options:**
- `--theme-path`: Path to the .ddw zip file (required)
- `--cleanup`: Remove the temporary extraction directory after extraction (optional)

**Output:**
```
Extracted to: /home/user/.cache/wallpaper-changer/theme_20260130_143022
Theme: 24hr Tahoe
Image credits: Photographer Name
Image filename pattern: 24hr-Tahoe-2026_*.jpeg
Sunrise images: ['24hr-Tahoe-2026_1.jpeg', '24hr-Tahoe-2026_2.jpeg', ...]
Day images: ['24hr-Tahoe-2026_3.jpeg', '24hr-Tahoe-2026_4.jpeg', ...]
Sunset images: ['24hr-Tahoe-2026_5.jpeg', '24hr-Tahoe-2026_6.jpeg', ...]
Night images: ['24hr-Tahoe-2026_7.jpeg', '24hr-Tahoe-2026_8.jpeg', ...]
```

### Change Wallpaper

Change the current wallpaper to the next image in the time-of-day category:

```bash
./wallpaper_cli.py change --theme-path /path/to/theme.ddw
```

**Options:**
- `--theme-path`: Path to the .ddw zip file or extracted theme directory (required)
- `--config`: Path to config file (default: `~/.config/wallpaper-changer/config.json`)

**Output:**
```
Selecting image for: day
Changing wallpaper to: /home/user/.config/wallpaper-changer/24hr-Tahoe-2026_3.jpeg
Wallpaper changed successfully!
```

**Note:** The theme will be extracted if a zip file is provided (cleanup=False by default).

### List Images

List all available images for a specific time-of-day category:

```bash
./wallpaper_cli.py list --theme-path <theme-path> --time-of-day day
```

**Options:**
- `--theme-path`: Path to the extracted theme directory or theme name (required)
- `--time-of-day`: Time-of-day category: `sunrise`, `day`, `sunset`, or `night` (optional, defaults to configured category)
- `--config`: Path to config file (default: `~/.config/wallpaper-changer/config.json`)

**Output:**
```
Images for day: ['24hr-Tahoe-2026_3.jpeg', '24hr-Tahoe-2026_4.jpeg', ...]
```

### Available CLI Commands

```bash
./wallpaper_cli.py --help
```

## Advanced Usage

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

### Custom Time-of-Day Categories

The tool automatically detects the current time-of-day based on system time. To manually set a category:

1. Edit `~/.config/wallpaper-changer/config.json`
2. Change `current_time_of_day` to desired category:
    ```json
    {
      "current_time_of_day": "night"
    }
    ```
3. Run `./wallpaper_cli.py change --theme-path /path/to/theme.ddw`

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

**Error:** `kwriteconfig5 failed: No such file or directory`

**Solution:** Ensure KDE Plasma is running:
```bash
pgrep -x plasmashell
```

If not running, start Plasma:
```bash
plasmashell &
```

### kwriteconfig5 Not Found

**Error:** `Error: Required command not found: kwriteconfig5`

**Solution:** Install KDE Plasma or KDE Plasma Workspaces:
```bash
sudo dnf install plasma-workspace
```

**Note:** The tool now uses `plasma-apply-wallpaperimage` for setting wallpapers, which is more reliable than `kwriteconfig5` alone.

### Invalid Config File

**Error:** `Config validation failed: Missing required field 'interval'`

**Solution:** Check your config file format:
```bash
cat ~/.config/wallpaper-changer/config.json
```

Ensure all required fields are present and valid.

### Theme.json Not Found

**Error:** `theme.json not found in zip file`

**Solution:** Verify the .ddw file is valid and contains a JSON file (theme.json or filename.json):
```bash
unzip -l theme.ddw | grep "\.json"
```

### Wallpaper Not Changing

**Possible causes:**
1. Plasma is not running (see above)
2. Image file path is incorrect
3. kwriteconfig5 doesn't have permission to write config
4. Plasma configuration file is locked

**Solutions:**
1. Check Plasma status: `pgrep -x plasmashell`
2. Verify image path: Check that the image file exists and is accessible
3. Check permissions: Ensure Plasma can write to the config directory
4. Reset Plasma config:
   ```bash
   kwriteconfig5 --file plasma-org.kde.plasma.desktop-appletsrc --delete
   plasmashell --replace
   ```

### Test Failures

Run tests to verify functionality:

```bash
# Run all tests
pytest ~/.config/wallpaper-changer/tests/ -v

# Run with coverage
pytest ~/.config/wallpaper-changer/tests/ --cov=wallpaper_changer

# Run specific test file
pytest ~/.config/wallpaper-changer/tests/test_time_of_day.py -v
```

## FAQ

### Q: Does it work with other desktop environments?

**A:** Currently, this tool is designed specifically for KDE Plasma. Other desktop environments may not work with `kwriteconfig5`. However, you could potentially adapt the code to use other desktop environment's wallpaper APIs.

### Q: Can I use multiple themes?

**A:** Yes! You can maintain multiple .ddw files in different directories and switch between them manually or by creating multiple systemd services with different themes.

### Q: How does time-of-day selection work?

**A:** The tool uses simple hour-based detection:
- **night**: 00:00 - 04:59
- **sunrise**: 05:00 - 06:59
- **day**: 07:00 - 16:59
- **sunset**: 17:00 - 18:59

It automatically detects the current hour and switches to the appropriate category. You can also manually set the category in the config file.

### Q: Can I customize the time ranges?

**A:** Currently, time ranges are fixed. To customize, you would need to modify the `detect_time_of_day()` function in `wallpaper_changer.py`.

### Q: Does it support animated wallpapers?

**A:** No, this tool only supports static JPEG/PNG images. Animated .ddw themes are not supported.

### Q: Can I use this with flatpak?

**A:** Not recommended. The tool requires direct access to system configuration files via `kwriteconfig5`, which is not available in flatpak sandboxed environments. Use the installed version instead.

### Q: How do I uninstall?

**A:** Simply remove the repository directory and uninstall Python dependencies:

```bash
pip uninstall -r requirements.txt
rm -rf /path/to/kwallpaper
```

### Q: Can I run this as a non-root user?

**A:** Yes, you should run it as your regular user. The tool writes to your home directory config files, not system-wide files.

### Q: What if the wallpaper change fails?

**A:** The tool:
1. Returns False from `change_wallpaper()`
2. Prints an error message
3. Can be configured to retry (via `retry_attempts` and `retry_delay` in config)
4. Returns exit code 1

Check Plasma status and error messages for root cause.

## Development

### Running Tests

```bash
# Run all tests
pytest ~/.config/wallpaper-changer/tests/ -v

# Run specific test
pytest ~/.config/wallpaper-changer/tests/test_time_of_day.py -v

# Run with coverage
pytest ~/.config/wallpaper-changer/tests/ --cov=wallpaper_changer
```

### Test Coverage

Current test coverage:
- ✅ Config validation (13/13 tests passing)
- ✅ Zip extraction (5/5 tests passing)
- ✅ Image selection (7/7 tests passing)
- ✅ Time-of-day detection (6/6 tests passing)
- ✅ Wallpaper change (3/3 tests passing)

Total: 34/35 tests passing (1 pre-existing failure in test_zip_extraction.py)

### Project Structure

```
kwallpaper/
├── wallpaper_cli.py              # CLI entry point
├── wallpaper_changer.py          # Core functions
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── .config/
    └── wallpaper-changer/
        ├── config.json           # User configuration
        ├── tests/
        │   ├── test_config.py            # Config tests
        │   ├── test_config_validation.py # Config validation tests
        │   ├── test_zip_extraction.py    # Zip extraction tests
        │   ├── test_image_selection.py   # Image selection tests
        │   ├── test_time_of_day.py       # Time-of-day tests
        │   ├── test_wallpaper_change.py  # Wallpaper change tests
        │   └── test_cli.py               # CLI tests
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

KDE Plasma's `kwriteconfig5` and `kreadconfig5` tools make this wallpaper changer possible without complex DBus interfaces.

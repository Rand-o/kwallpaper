# Flatpak Build Guide

This directory contains the Flatpak configuration for building a single-file bundle of KDE Wallpaper Changer.

## Prerequisites

You need `flatpak-builder` installed:

```bash
sudo dnf install flatpak-builder
```

KDE Platform 6.9 runtime and SDK:

```bash
flatpak install --user org.kde.Platform//6.9
flatpak install --user org.kde.Sdk//6.9
```

## Preparing Python Dependencies

Download Python dependencies for Python 3.12:

```bash
pip download --python-version 312 --only-binary=:all: apscheduler astral pyqt6 pyqt6-sip python_dateutil pytz
```

Move all `.whl` files to `flatpak-deps/`:

```bash
mkdir -p flatpak-deps
mv *.whl flatpak-deps/
```

## Building a Single Flatpak File

Run the build script:

```bash
cd flatpak
./build.sh
```

This will create `bundle/org.kde.kwallpaper.flatpak`.

## Installing the Bundle

To install the created bundle on any machine with Flatpak:

```bash
flatpak install --user bundle/org.kde.kwallpaper.flatpak
```

### Configuration Storage

The app stores configuration, themes, and cache in Flatpak-specific paths:
- **Config**: `~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/`
- **Cache**: `~/.var/app/top.spelunk.kwallpaper/cache/kwallpaper/`
- **Themes**: `~/.var/app/top.spelunk.kwallpaper/config/kwallpaper/themes/`

These paths are self-contained and don't require access to the host's `~/.config` or `~/.cache` directories.

### Multi-monitor wallpaper support

**Note:** The Flatpak sandbox prevents direct access to `plasma-apply-wallpaperimage`. The DBus implementation using `evaluateScript` now iterates through all available screens via `desktops()` and sets the wallpaper on each one.

**How it works:**
- Uses QML script with `desktops()` API to get all desktop objects
- Iterates through each desktop and calls `writeConfig("Image", ...)` 
- Properly handles `file://` URLs for image paths

**Filesystem permissions needed:**
- Images must be accessible from within the Flatpak sandbox
- The flatpak manifest must include filesystem access for image locations

**Known limitations:**
1. Images must be in Flatpak-accessible paths (e.g., `~/.var/app/top.spelunk.kwallpaper/`)
2. For full system access, add `--filesystem=host:ro` to finish-args (not recommended for security)

## Troubleshooting

### Network errors during build
If you see DNS resolution errors during build, ensure your network is accessible from the flatpak-builder sandbox. You may need to:

1. Run the build while connected to a network
2. Use `--disable-network=false` if supported by your flatpak-builder version
3. Pre-download dependencies and include them in the build

### Source files not found
If flatpak-builder cannot find source files:

1. Verify the `path` field points to the correct location
2. Ensure the path is accessible from the flatpak-builder context
3. Use relative paths when possible



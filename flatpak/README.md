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

After installation, the app can be launched from the application menu as "KDE Wallpaper Changer".

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



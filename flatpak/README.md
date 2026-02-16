# Flatpak Build Guide

This directory contains the Flatpak configuration for building a single-file bundle of KDE Wallpaper Changer.

## Prerequisites

You need `flatpak-builder` installed:

```bash
# Fedora/RHEL
sudo dnf install flatpak-builder

# Ubuntu/Debian
sudo apt install flatpak-builder
```

You also need the KDE Platform 6.7 runtime and SDK:

```bash
# Add Flathub repository if not already added
flatpak remote-add --_if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install KDE Platform 6.7 runtime and SDK
flatpak install org.kde.Platform//6.7
flatpak install org.kde.Sdk//6.7
```

## Building a Single Flatpak File

Run the build script:

```bash
cd flatpak
./build.sh
```

This will:
1. Build the Flatpak using `flatpak-builder`
2. Create a single `.flatpak` bundle file in the `bundles/` directory

## Installing the Bundle

To install the created bundle on any machine with Flatpak:

```bash
flatpak install --user org.kde.kwallpaper.flatpak
```

After installation, the app can be launched from the application menu as "KDE Wallpaper Changer".

## Troubleshooting

### Build fails with "Runtime not found"
Make sure the KDE runtime is installed:
```bash
flatpak list | grep org.kde.Platform
```

### Permission denied errors
Ensure your user has permissions to access the necessary directories:
```bash
ls -la ~/.local/share/flatpak
```

### Build is slow
The build downloads all Python dependencies. This only happens on the first build - subsequent builds will use cached dependencies.

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

## Using the Bundle

The `.flatpak` file is a single-file bundle that can be copied to any machine and installed with:
```bash
flatpak install --user org.kde.kwallpaper.flatpak
```

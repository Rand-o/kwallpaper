# Flatpak Build Guide

This directory contains the Flatpak configuration for building a single-file bundle of KDE Wallpaper Changer.

## Prerequisites

You need `flatpak-builder` installed:

```bash
sudo dnf install flatpak-builder
```

KDE Platform 6.9 SDK (will be installed automatically if missing):

```bash
flatpak install org.kde.Sdk//6.9
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



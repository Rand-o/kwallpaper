#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/top.spelunk.kwallpaper.json"
BUNDLE_NAME="top.spelunk.kwallpaper"

if ! command -v flatpak-builder &> /dev/null; then
    echo "Error: flatpak-builder not installed"
    exit 1
fi

if [ ! -f "$MANIFEST" ]; then
    echo "Error: Manifest not found"
    exit 1
fi

BUILD_DIR="$SCRIPT_DIR/build"
BUNDLE_DIR="$SCRIPT_DIR/bundle"
FLATPAK_REPO="$SCRIPT_DIR/flatpak-repo"

rm -rf "$BUILD_DIR" "$BUNDLE_DIR" "$FLATPAK_REPO"
mkdir -p "$BUNDLE_DIR"

flatpak-builder --user --force-clean --repo="$FLATPAK_REPO" "$BUILD_DIR" "$MANIFEST"

# Build bundle from the local repo (flatpak-repo created by flatpak-builder)
flatpak build-bundle "$FLATPAK_REPO" "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" "$BUNDLE_NAME" master 2>&1 || true

if [ -f "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" ]; then
    SIZE=$(du -h "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" | cut -f1)
    echo "Bundle: $BUNDLE_DIR/$BUNDLE_NAME.flatpak ($SIZE)"
    echo "Install: flatpak install --user $BUNDLE_DIR/$BUNDLE_NAME.flatpak"
else
    echo "Bundle creation failed"
    exit 1
fi

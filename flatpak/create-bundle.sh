#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_NAME="top.spelunk.kwallpaper"
BUNDLE_DIR="$SCRIPT_DIR/bundle"

if ! command -v flatpak build-bundle &> /dev/null; then
    echo "Error: flatpak build-bundle not available"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/repo" ] || [ ! -d "$SCRIPT_DIR/repo" ]; then
    echo "Error: Build repository not found (run build.sh first)"
    exit 1
fi

rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"

flatpak build-bundle "$SCRIPT_DIR/repo" "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" "$BUNDLE_NAME" stable

if [ -f "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" ]; then
    SIZE=$(ls -lh "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" | awk '{print $5}')
    echo "Bundle: $BUNDLE_DIR/$BUNDLE_NAME.flatpak ($SIZE)"
    echo "Install: flatpak install --user $BUNDLE_DIR/$BUNDLE_NAME.flatpak"
else
    echo "Error: Bundle creation failed"
    exit 1
fi

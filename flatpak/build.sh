#!/bin/bash

# Build kwallpaper Flatpak as a single bundle file
# Usage: ./build.sh [branch]
#        ./build.sh main     # Build from main branch
#        ./build.sh v1.0.0   # Build from a tag

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST="$SCRIPT_DIR/org.kde.kwallpaper.json"
BUNDLE_NAME="org.kde.kwallpaper"

# Check if flatpak-builder is available
if ! command -v flatpak-builder &> /dev/null; then
    echo "Error: flatpak-builder is not installed"
    echo "Install it with: sudo dnf install flatpak-builder"
    exit 1
fi

# Check if manifest exists
if [ ! -f "$MANIFEST" ]; then
    echo "Error: Manifest not found at $MANIFEST"
    exit 1
fi

BUILD_DIR="$SCRIPT_DIR/build"
BUNDLE_DIR="$SCRIPT_DIR/bundles"

# Clean previous builds
rm -rf "$BUILD_DIR"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"

echo "Building Flatpak bundle..."
echo "Manifest: $MANIFEST"
echo "Build dir: $BUILD_DIR"
echo "Bundle dir: $BUNDLE_DIR"

# Build and bundle in one step
flatpak-builder \
    --user \
    --force-clean \
    --repo="$BUNDLE_DIR/repo" \
    --default-branch=stable \
    "$BUILD_DIR" \
    "$MANIFEST"

# Export to single bundle file
if [ -d "$BUNDLE_DIR/repo" ]; then
    echo "Creating flatpak bundle..."
    flatpak build-bundle \
        "$BUNDLE_DIR/repo" \
        "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" \
        --runtime-source="$BUNDLE_DIR/repo" \
        "$BUNDLE_NAME" \
        stable
    
    if [ -f "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" ]; then
        SIZE=$(du -h "$BUNDLE_DIR/$BUNDLE_NAME.flatpak" | cut -f1)
        echo ""
        echo "Bundle created successfully!"
        echo "File: $BUNDLE_DIR/$BUNDLE_NAME.flatpak"
        echo "Size: $SIZE"
        echo ""
        echo "To install on another machine:"
        echo "  flatpak install --user $BUNDLE_DIR/$BUNDLE_NAME.flatpak"
    else
        echo "Warning: Bundle was created but could not find the .flatpak file"
    fi
else
    echo "Error: Build repository not created"
    exit 1
fi

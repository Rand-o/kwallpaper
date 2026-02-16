#!/bin/bash
# Create a single-file Flatpak bundle

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/org.kde.kwallpaper.json"

echo "=== Flatpak Bundle Creator ==="
echo ""

# Check prerequisites
if ! command -v flatpak-builder &> /dev/null; then
    echo "Error: flatpak-builder not found"
    exit 1
fi

if ! command -v flatpak build-bundle &> /dev/null; then
    echo "Error: flatpak build-bundle not available"
    exit 1
fi

BUILD_DIR="$SCRIPT_DIR/build"
REPO_DIR="$SCRIPT_DIR/repo"
BUNDLE_DIR="$SCRIPT_DIR/bundle"

# Clean up previous builds
rm -rf "$BUILD_DIR" "$REPO_DIR" "$BUNDLE_DIR"
mkdir -p "$REPO_DIR" "$BUNDLE_DIR"

echo "Step 1: Building Flatpak runtime..."
flatpak-builder --user --force-clean "$BUILD_DIR" "$MANIFEST"

echo ""
echo "Step 2: Creating repository..."
flatpak build-bundle "$REPO_DIR" "$BUNDLE_DIR/org.kde.kwallpaper.flatpak" \
    org.kde.kwallpaper \
    --runtime-source="$REPO_DIR"

echo ""
echo "Step 3: Verifying bundle..."
if [ -f "$BUNDLE_DIR/org.kde.kwallpaper.flatpak" ]; then
    SIZE=$(ls -lh "$BUNDLE_DIR/org.kde.kwallpaper.flatpak" | awk '{print $5}')
    echo "✓ Bundle created: $BUNDLE_DIR/org.kde.kwallpaper.flatpak"
    echo "  Size: $SIZE"
else
    echo "✗ Bundle creation failed"
    exit 1
fi

echo ""
echo "=== Build Complete ==="
echo ""
echo "To install on another machine:"
echo "  flatpak install --user $BUNDLE_DIR/org.kde.kwallpaper.flatpak"
echo ""

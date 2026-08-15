#!/usr/bin/env python3
"""
kWallpaper Plasma wallpaper application.

Sets the wallpaper on all screens via the org.kde.plasmashell D-Bus API.

Implementation note: the calls go through ``gdbus`` subprocesses (one
connection per call) rather than a persistent D-Bus connection.  This is
deliberate: it preserves the exact behaviour (and testability via
``subprocess.run`` mocks) of the legacy implementation, and works in the
Flatpak sandbox where a direct dbus-next/QDBusConnection setup would need
extra permissions.  A persistent-connection rewrite is a future
optimization.
"""

import logging
import re
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_PLASMA_DEST = "org.kde.plasmashell"
_PLASMA_PATH = "/PlasmaShell"


def _gdbus(method: str, *args: str, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    """Run a gdbus session-bus call against the Plasma shell."""
    return subprocess.run(
        ['gdbus', 'call', '--session', '--dest', _PLASMA_DEST,
         '--object-path', _PLASMA_PATH, '--method', method] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def change_wallpaper(image_path: str) -> bool:
    """Change KDE Plasma wallpaper to specified image using DBus.
    Sets wallpaper on all available screens using evaluateScript.
    Falls back to single-screen approach if desktops() is not available.

    Args:
        image_path: Path to image file to set as wallpaper

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if Plasma shell is running
        plasma_check = subprocess.run(
            ['gdbus', 'call', '--session', '--dest', _PLASMA_DEST,
             '--object-path', _PLASMA_PATH,
             '--method', 'org.freedesktop.DBus.Peer.Ping'],
            capture_output=True,
            text=True
        )
        if plasma_check.returncode != 0:
            print("Error: Plasma shell is not running. Please start Plasma first.", file=sys.stderr)
            return False

        # Try to get screen count using desktops().length
        screen_count_script = 'print(desktops().length);'
        screen_count_result = subprocess.run(
            ['gdbus', 'call', '--session', '--dest', _PLASMA_DEST,
             '--object-path', _PLASMA_PATH,
             '--method', 'org.kde.PlasmaShell.evaluateScript', screen_count_script],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Parse output - try to extract screen count from formats like "('1',)" or "(1,)"
        # First try: extract digit inside quotes like "('1',)"
        match = re.search(r"'(\d+)'", screen_count_result.stdout)
        if match:
            screen_count = int(match.group(1))
        else:
            # Fallback: try to get the number directly without quotes
            match = re.search(r'\((\d+),\)', screen_count_result.stdout)
            if match:
                screen_count = int(match.group(1))
            else:
                # Try just the number alone
                match = re.search(r'^(\d+)$', screen_count_result.stdout.strip())
                screen_count = int(match.group(1)) if match else 1

        # If no screens detected (headless or desktops() not available), try setting on screen 0
        if screen_count < 1:
            screen_count = 1

        screen_num = 0
        success_count = 0
        while True:
            try:
                result = subprocess.run(
                    ['gdbus', 'call', '--session', '--dest', _PLASMA_DEST,
                     '--object-path', _PLASMA_PATH,
                     '--method', 'org.kde.PlasmaShell.wallpaper', str(screen_num)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if '"Image": <' not in result.stdout and "'Image': <" not in result.stdout:
                    break
                wallpaper_param = f"{{'Image': <'file://{image_path}'>}}"
                set_result = subprocess.run(
                    ['gdbus', 'call', '--session', '--dest', _PLASMA_DEST,
                     '--object-path', _PLASMA_PATH,
                     '--method', 'org.kde.PlasmaShell.setWallpaper', 'org.kde.image',
                     wallpaper_param, str(screen_num)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if set_result.returncode == 0:
                    success_count += 1
                screen_num += 1
            except Exception:
                break

        if success_count > 0:
            print(f"Wallpaper changed successfully on {success_count} screen(s)!", file=sys.stderr)
            return True
        else:
            print("Error: Failed to change wallpaper on any screen", file=sys.stderr)
            return False

    except FileNotFoundError as e:
        print(f"Error: gdbus command not found: {e}", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to change wallpaper: {e.stderr}", file=sys.stderr)
        return False


def get_current_wallpaper() -> Optional[str]:
    """Get current KDE Plasma wallpaper path.

    Tries the D-Bus ``wallpaper`` method first (works in Flatpak where
    ``kreadconfig5`` is absent), then falls back to ``kreadconfig6`` / ``kreadconfig5``.

    Returns:
        Path to current wallpaper, or None if not found
    """
    # Primary: D-Bus wallpaper method (screen 0)
    try:
        result = _gdbus('org.kde.PlasmaShell.wallpaper', '0', timeout=5)
        if result.returncode == 0:
            # Output looks like: ({'Image': <'file:///path/to/img.jpg'>, ...},)
            match = re.search(r"'Image':\s*<'(file://[^']+)'>", result.stdout)
            if not match:
                match = re.search(r'"Image":\s*<(file://[^>]+)>', result.stdout)
            if match:
                uri = match.group(1)
                if uri.startswith('file://'):
                    return uri[len('file://'):]
                return uri
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback: kreadconfig6 / kreadconfig5
    for tool in ('kreadconfig6', 'kreadconfig5'):
        try:
            result = subprocess.run([
                tool,
                '--file', 'plasma-org.kde.plasma.desktop-appletsrc',
                '--group', 'Wallpaper',
                '--group', 'org.kde.image',
                '--key', 'Image'
            ], capture_output=True, text=True, check=True, timeout=5)
            wallpaper_path = result.stdout.strip()
            if wallpaper_path:
                return wallpaper_path
        except (subprocess.CalledProcessError, FileNotFoundError,
                subprocess.TimeoutExpired, OSError):
            continue

    return None

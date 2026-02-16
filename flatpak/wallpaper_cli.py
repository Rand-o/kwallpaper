#!/usr/bin/env python3
"""
KDE Wallpaper Changer - CLI entry point.

This script provides a command-line interface for the KDE Wallpaper Changer tool.
"""

import sys
import os

# Get project root directory
project_root = os.path.dirname(os.path.abspath(__file__))

# Add project root to path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add kwallpaper directory to path
kwallpaper_dir = os.path.join(project_root, 'kwallpaper')
if kwallpaper_dir not in sys.path:
    sys.path.insert(0, kwallpaper_dir)

# Import main function from consolidated module
from kwallpaper.wallpaper_changer import main


if __name__ == '__main__':
    sys.exit(main())

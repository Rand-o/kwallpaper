#!/usr/bin/env python3
"""
KDE Wallpaper Changer - Setup Script

A Python CLI tool for Fedora 43 KDE that automatically changes wallpapers
based on time-of-day categories using .ddw (KDE wallpaper theme) zip files.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="kde-wallpaper-changer",
    version="1.0.0",
    description="Automatically change KDE Plasma wallpapers based on time-of-day",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/kwallpaper",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Desktop Environment :: KDE",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=[
        # Runtime dependencies
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "wallpaper-changer=kwallpaper.wallpaper_changer:main",
        ],
    },
    keywords="kde plasma wallpaper changer time-of-day",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/kwallpaper/issues",
        "Source": "https://github.com/yourusername/kwallpaper",
    },
)

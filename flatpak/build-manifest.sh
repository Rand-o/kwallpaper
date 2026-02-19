#!/bin/bash

# Create the Flatpak manifest for kwallpaper

cat > /home/admin/llama-cpp/projects/kwallpaper/flatpak/org.kde.kwallpaper.json << EOF
{
    "id": "org.kde.kwallpaper",
    "runtime": "org.kde.Platform",
    "runtime-version": "6.7",
    "sdk": "org.kde.Sdk",
    "command": "wallpaper-gui",
    "finish-args": [
        "--share=ipc",
        "--share=network",
        "--socket=fallback-x11",
        "--socket=wayland",
        "--socket=session_bus",
        "--filesystem=xdg-config/kdeglobals:ro",
        "--filesystem=xdg-cache/wallpaper-changer:rw",
        "--filesystem=xdg-config/wallpaper-changer:rw"
    ],
    "modules": [
        {
            "name": "python-dependencies",
            "buildsystem": "simple",
            "build-commands": [
                "pip3 install --no-build-isolation astral>=2.2",
                "pip3 install --no-build-isolation apscheduler>=3.10.0",
                "pip3 install --no-build-isolation PyQt6>=6.6.0"
            ]
        },
        {
            "name": "kwallpaper",
            "buildsystem": "simple",
            "build-commands": [
                "pip3 install --no-build-isolation .",
                "install -Dm644 org.kde.kwallpaper.desktop /app/share/applications/org.kde.kwallpaper.desktop",
                "install -Dm644 org.kde.kwallpaper.metainfo.xml /app/share/metainfo/org.kde.kwallpaper.metainfo.xml"
            ],
            "sources": [
                {
                    "type": "dir",
                    "path": ".."
                }
            ]
        }
    ]
}
EOF


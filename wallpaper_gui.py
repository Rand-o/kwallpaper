#!/usr/bin/env python3
"""
KDE Wallpaper Changer - GUI Application with Scheduling

A PyQt6 GUI application that uses APScheduler to automatically run
wallpaper-changing tasks at specified intervals.
"""

import sys
import logging
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QTextEdit, QGroupBox, QFormLayout, QTabWidget,
        QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QFileDialog, QGridLayout,
        QFrame, QScrollArea
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
    from PyQt6.QtGui import QFont, QPixmap, QImage, QColor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from kwallpaper.scheduler import SchedulerManager, create_scheduler
from kwallpaper.wallpaper_changer import (
    load_config, save_config, DEFAULT_CONFIG_PATH,
    discover_themes, extract_theme
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LogEmitter(QObject):
    """Emits log messages as Qt signals for thread-safe GUI updates."""
    log_signal = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.log_signal.connect(self._on_log)
        self._messages = []
        
    def _on_log(self, level: str, message: str):
        self._messages.append((level, message))


class ThemePreviewThread(QThread):
    """Thread to handle theme preview slideshow."""
    preview_changed = pyqtSignal(str)
    
    def __init__(self, theme_path: str, parent=None):
        super().__init__(parent)
        self.theme_path = theme_path
        self._running = False
        
    def run(self):
        self._running = True
        try:
            theme_json = None
            for f in Path(self.theme_path).rglob("*.json"):
                theme_json = f
                break
                
            if not theme_json:
                return
                
            with open(theme_json, 'r') as f:
                theme_data = json.load(f)
            
            images = []
            for category in ['sunrise', 'day', 'sunset', 'night']:
                img_list = theme_data.get(f'{category}ImageList', [])
                if img_list:
                    images.append(img_list[0])
            
            if not images:
                return
            
            while self._running:
                for img_idx in images:
                    if not self._running:
                        break
                    img_file = self._find_image_file(self.theme_path, img_idx)
                    if img_file:
                        self.preview_changed.emit(img_file)
                    self.msleep(2000)
                    
        except Exception as e:
            logger.error(f"Preview error: {e}")
            
    def _find_image_file(self, theme_path: str, index: int) -> Optional[str]:
        theme_path = Path(theme_path)
        for f in theme_path.glob("*.jpeg"):
            if str(index) in f.stem:
                return str(f)
        for f in theme_path.glob("*.jpg"):
            if str(index) in f.stem:
                return str(f)
        return None
        
    def stop(self):
        self._running = False
        self.wait()


class ModernCard(QFrame):
    """Modern card widget with KDE styling."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 15px;
            }
            QFrame:hover {
                border: 2px solid #0088cc;
            }
        """)


class SettingsTab(QWidget):
    """Settings tab for scheduler configuration."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        self.setLayout(layout)
        
        scheduler_card = ModernCard()
        scheduler_layout = QVBoxLayout()
        scheduler_card.setLayout(scheduler_layout)
        
        title = QLabel("Scheduler Settings")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        scheduler_layout.addWidget(title)
        
        scheduler_form = QFormLayout()
        scheduler_form.setSpacing(10)
        scheduler_layout.addLayout(scheduler_form)
        
        self.cycle_interval = QSpinBox()
        self.cycle_interval.setRange(1, 3600)
        self.cycle_interval.setValue(60)
        self.cycle_interval.setSuffix(" seconds")
        self.cycle_interval.setStyleSheet("""
            QSpinBox {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """)
        scheduler_form.addRow("Cycle Interval:", self.cycle_interval)
        
        self.daily_change_time = QLineEdit("00:00")
        self.daily_change_time.setPlaceholderText("HH:MM")
        self.daily_change_time.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """)
        scheduler_form.addRow("Daily Change Time:", self.daily_change_time)
        
        self.run_cycle = QCheckBox("Enable cycle task (runs every interval)")
        self.run_cycle.setChecked(True)
        self.run_cycle.setStyleSheet("QCheckBox { padding: 5px; }")
        scheduler_form.addRow("", self.run_cycle)
        
        self.run_daily = QCheckBox("Enable daily change task (runs at specified time)")
        self.run_daily.setChecked(True)
        self.run_daily.setStyleSheet("QCheckBox { padding: 5px; }")
        scheduler_form.addRow("", self.run_daily)
        
        layout.addWidget(scheduler_card)
        
        location_card = ModernCard()
        location_layout = QVBoxLayout()
        location_card.setLayout(location_layout)
        
        title = QLabel("Location Settings")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        location_layout.addWidget(title)
        
        location_form = QFormLayout()
        location_form.setSpacing(10)
        location_layout.addLayout(location_form)
        
        self.timezone = QLineEdit("America/Phoenix")
        self.timezone.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """)
        location_form.addRow("Timezone:", self.timezone)
        
        self.latitude = QDoubleSpinBox()
        self.latitude.setRange(-90, 90)
        self.latitude.setValue(33.4484)
        self.latitude.setDecimals(4)
        self.latitude.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """)
        location_form.addRow("Latitude:", self.latitude)
        
        self.longitude = QDoubleSpinBox()
        self.longitude.setRange(-180, 180)
        self.longitude.setValue(-112.074)
        self.longitude.setDecimals(4)
        self.longitude.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: #f9f9f9;
            }
        """)
        location_form.addRow("Longitude:", self.longitude)
        
        layout.addWidget(location_card)
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self._save_settings)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #0088cc;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #006699;
            }
            QPushButton:pressed {
                background-color: #005577;
            }
        """)
        layout.addWidget(self.save_button)
        
        layout.addStretch()
        self._load_config()
        
    def _load_config(self):
        try:
            config = load_config(self.config_path)
            scheduling = config.get('scheduling', {})
            self.cycle_interval.setValue(scheduling.get('interval', 60))
            self.daily_change_time.setText(scheduling.get('daily_change_time', '00:00'))
            self.run_cycle.setChecked(scheduling.get('run_cycle', True))
            self.run_daily.setChecked(scheduling.get('run_daily_change', True))
            
            location = config.get('location', {})
            self.timezone.setText(location.get('timezone', 'America/Phoenix'))
            self.latitude.setValue(location.get('latitude', 33.4484))
            self.longitude.setValue(location.get('longitude', -112.074))
            
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            
    def _save_settings(self):
        try:
            config = load_config(self.config_path)
            
            config['scheduling'] = {
                'interval': self.cycle_interval.value(),
                'daily_change_time': self.daily_change_time.text(),
                'run_cycle': self.run_cycle.isChecked(),
                'run_daily_change': self.run_daily.isChecked()
            }
            
            config['location'] = {
                'timezone': self.timezone.text(),
                'latitude': self.latitude.value(),
                'longitude': self.longitude.value()
            }
            
            save_config(self.config_path, config)
            logger.info("Settings saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")


class ThemePreviewWidget(QWidget):
    """Widget to display theme preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_thread = None
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        self.setLayout(layout)
        
        self.preview_label = QLabel("Hover over theme to preview slideshow")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(250)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                color: #00ff00;
                border: 2px dashed #555;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        layout.addWidget(self.preview_label)
        
    def start_preview(self, theme_path: str):
        if self.preview_thread:
            self.preview_thread.stop()
            
        self.preview_thread = ThemePreviewThread(theme_path)
        self.preview_thread.preview_changed.connect(self._update_preview)
        self.preview_thread.start()
        
    def stop_preview(self):
        if self.preview_thread:
            self.preview_thread.stop()
            self.preview_thread = None
        self.preview_label.setText("Hover over theme to preview slideshow")
        
    def _update_preview(self, image_path: str):
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.preview_label.setText(f"Could not load: {Path(image_path).name}")
        else:
            scaled = pixmap.scaled(self.preview_label.size(), 
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled)


class ThemeCard(QFrame):
    """Card widget for displaying a theme."""
    
    def __init__(self, name: str, path: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self._init_ui()
        
    def _init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 10px;
            }
            QFrame:hover {
                border: 2px solid #0088cc;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        self.setLayout(layout)
        
        name_label = QLabel(self.name)
        name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: #333;")
        layout.addWidget(name_label)
        
        self.preview_label = QLabel("Preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(180, 120)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.preview_label)
        
        self._load_preview()
        
    def _load_preview(self):
        try:
            theme_json = None
            # Look for any JSON file in the theme directory
            for f in Path(self.path).glob("*.json"):
                theme_json = f
                break
                
            if not theme_json:
                return
                
            with open(theme_json, 'r') as f:
                theme_data = json.load(f)
                
            # Get first image from each category
            for category in ['sunrise', 'day', 'sunset', 'night']:
                img_list = theme_data.get(f'{category}ImageList', [])
                if img_list:
                    img_idx = img_list[0]
                    img_file = self._find_image_file(self.path, img_idx)
                    if img_file:
                        pixmap = QPixmap(img_file)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(180, 120,
                                                   Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
                            self.preview_label.setPixmap(scaled)
                    break
        except Exception as e:
            logger.warning(f"Could not load preview for {self.name}: {e}")
            
    def _find_image_file(self, theme_path: str, index: int) -> Optional[str]:
        theme_path = Path(theme_path)
        all_images = list(theme_path.glob("*.jpeg")) + list(theme_path.glob("*.jpg"))
        
        def get_index(f):
            try:
                stem = f.stem
                if '_' in stem:
                    num_part = stem.split('_')[-1]
                    return int(num_part)
            except (ValueError, IndexError):
                pass
            return 0
            
        all_images.sort(key=get_index)
        
        for f in all_images:
            try:
                stem = f.stem
                if '_' in stem:
                    num_part = stem.split('_')[-1]
                    if int(num_part) == index:
                        return str(f)
            except (ValueError, IndexError):
                pass
                
        return None


class ThemesTab(QWidget):
    """Themes tab showing all imported themes."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.themes = []
        self.preview_widget = ThemePreviewWidget()
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        self.setLayout(layout)
        
        current_card = ModernCard()
        current_layout = QVBoxLayout()
        current_card.setLayout(current_layout)
        
        title = QLabel("Current Theme")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        current_layout.addWidget(title)
        
        self.current_theme_label = QLabel("Not set")
        self.current_theme_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_theme_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #0088cc;
                padding: 10px;
                background-color: #e8f4fc;
                border-radius: 6px;
            }
        """)
        current_layout.addWidget(self.current_theme_label)
        
        layout.addWidget(current_card)
        
        themes_card = ModernCard()
        themes_layout = QVBoxLayout()
        themes_card.setLayout(themes_layout)
        
        title = QLabel("Available Themes")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        themes_layout.addWidget(title)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.themes_container = QWidget()
        self.themes_grid = QGridLayout()
        self.themes_grid.setSpacing(15)
        self.themes_container.setLayout(self.themes_grid)
        
        scroll_area.setWidget(self.themes_container)
        themes_layout.addWidget(scroll_area)
        
        layout.addWidget(themes_card)
        
        layout.addWidget(self.preview_widget)
        
        self.refresh_button = QPushButton("Refresh Themes")
        self.refresh_button.clicked.connect(self._load_themes)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #0088cc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #006699;
            }
        """)
        layout.addWidget(self.refresh_button)
        
        layout.addStretch()
        self._load_themes()
        
    def _load_themes(self):
        while self.themes_grid.count():
            child = self.themes_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self.themes = []
        
        try:
            self.themes = discover_themes()
            self.themes.sort(key=lambda x: x[0].lower())
            
            row = 0
            col = 0
            for theme_name, theme_path in self.themes:
                theme_widget = ThemeCard(theme_name, theme_path)
                self.themes_grid.addWidget(theme_widget, row, col)
                
                col += 1
                if col > 3:
                    col = 0
                    row += 1
                    
            logger.info(f"Loaded {len(self.themes)} themes")
            
        except Exception as e:
            logger.error(f"Failed to load themes: {e}")
            
    def start_preview(self, theme_path: str):
        self.preview_widget.start_preview(theme_path)
        
    def stop_preview(self):
        self.preview_widget.stop_preview()


class WallpaperGUI(QMainWindow):
    """Main GUI window for KDE Wallpaper Changer."""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.scheduler: Optional[SchedulerManager] = None
        self.log_emitter = LogEmitter()
        
        self._init_ui()
        self._setup_scheduler()
        
    def _init_ui(self):
        self.setWindowTitle("KDE Wallpaper Changer")
        self.setGeometry(100, 100, 900, 700)
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        central.setLayout(main_layout)
        
        title = QLabel("KDE Wallpaper Changer")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #0088cc;
                padding: 15px;
            }
        """)
        main_layout.addWidget(title)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                background: #f9f9f9;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #333;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0088cc;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #006699;
                color: white;
            }
        """)
        main_layout.addWidget(self.tabs)
        
        self.settings_tab = SettingsTab(self.config_path)
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        self.themes_tab = ThemesTab(self.config_path)
        self.tabs.addTab(self.themes_tab, "🎨 Themes")
        
        scheduler_tab = QWidget()
        scheduler_layout = QVBoxLayout()
        scheduler_layout.setSpacing(15)
        scheduler_tab.setLayout(scheduler_layout)
        
        status_card = ModernCard()
        status_layout = QVBoxLayout()
        status_card.setLayout(status_layout)
        
        status_title = QLabel("Scheduler Status")
        status_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        status_layout.addWidget(status_title)
        
        self.status_label = QLabel("Scheduler: Stopped")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #e8f4fc;
                border-radius: 6px;
                color: #0088cc;
            }
        """)
        status_layout.addWidget(self.status_label)
        
        scheduler_layout.addWidget(status_card)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.start_button = QPushButton("▶ Start Scheduler")
        self.start_button.clicked.connect(self._start_scheduler)
        self.start_button.setFont(QFont("Arial", 11))
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹ Stop Scheduler")
        self.stop_button.clicked.connect(self._stop_scheduler)
        self.stop_button.setFont(QFont("Arial", 11))
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.stop_button)
        
        scheduler_layout.addLayout(button_layout)
        
        log_card = ModernCard()
        log_layout = QVBoxLayout()
        log_card.setLayout(log_layout)
        
        log_title = QLabel("Event Log")
        log_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        log_layout.addWidget(log_title)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Courier", 9))
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 10px;
                min-height: 150px;
            }
        """)
        log_layout.addWidget(self.log_area)
        
        scheduler_layout.addWidget(log_card)
        
        self.tabs.addTab(scheduler_tab, "⏱ Scheduler")
        
    def _setup_scheduler(self):
        try:
            self.scheduler = create_scheduler(self.config_path)
            logger.info("Scheduler manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            self.status_label.setText(f"Error: {e}")
            
    def _start_scheduler(self):
        if self.scheduler is None:
            self.log_area.append("Error: Scheduler not initialized")
            return
            
        if self.scheduler.is_running():
            self.log_area.append("Scheduler is already running")
            return
            
        if self.scheduler.start():
            self.status_label.setText("Scheduler: Running")
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 15px;
                    background-color: #d4edda;
                    border-radius: 6px;
                    color: #155724;
                }
            """)
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.log_area.append("Scheduler started successfully")
            self.log_area.append("Cycle task: Every 60 seconds")
            self.log_area.append("Daily change task: At 00:00")
        else:
            self.log_area.append("Failed to start scheduler")
            
    def _stop_scheduler(self):
        if self.scheduler is None:
            return
            
        if not self.scheduler.is_running():
            self.log_area.append("Scheduler is not running")
            return
            
        if self.scheduler.stop():
            self.status_label.setText("Scheduler: Stopped")
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 15px;
                    background-color: #e8f4fc;
                    border-radius: 6px;
                    color: #0088cc;
                }
            """)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.log_area.append("Scheduler stopped successfully")
        else:
            self.log_area.append("Failed to stop scheduler")
            
    def log_message(self, level: str, message: str):
        timestamp = self._get_timestamp()
        self.log_area.append(f"[{timestamp}] [{level}] {message}")
        
    def _get_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def closeEvent(self, event):
        if self.scheduler is not None and self.scheduler.is_running():
            self.log_area.append("Shutting down scheduler...")
            self.scheduler.stop(wait=True)
            self.log_area.append("Scheduler shutdown complete")
        if hasattr(self.themes_tab, 'preview_widget'):
            self.themes_tab.stop_preview()
        event.accept()


def main():
    """Main entry point for the GUI application."""
    if not PYQT6_AVAILABLE:
        print("Error: PyQt6 is not installed.")
        print("Please install it with: pip install PyQt6")
        sys.exit(1)
        
    import argparse
    parser = argparse.ArgumentParser(description="KDE Wallpaper Changer GUI")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: ~/.config/wallpaper-changer/config.json)"
    )
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor("#f0f0f0"))
    palette.setColor(palette.ColorRole.WindowText, QColor("#333333"))
    palette.setColor(palette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(palette.ColorRole.AlternateBase, QColor("#f5f5f5"))
    palette.setColor(palette.ColorRole.ToolTipBase, QColor("#0088cc"))
    palette.setColor(palette.ColorRole.ToolTipText, QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Text, QColor("#333333"))
    palette.setColor(palette.ColorRole.Button, QColor("#0088cc"))
    palette.setColor(palette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(palette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Link, QColor("#0088cc"))
    palette.setColor(palette.ColorRole.Highlight, QColor("#0088cc"))
    palette.setColor(palette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    
    window = WallpaperGUI(config_path=args.config)
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
KDE Wallpaper Changer - GUI Application with Scheduling
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
        QPushButton, QLabel, QTextEdit, QFormLayout, QTabWidget,
        QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QGridLayout,
        QFrame, QScrollArea, QFileDialog
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QColor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from kwallpaper.scheduler import SchedulerManager, create_scheduler
from kwallpaper.wallpaper_changer import (
    load_config, save_config, DEFAULT_CONFIG_PATH,
    discover_themes, extract_theme
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
        self.preview_label.setMinimumSize(200, 150)
        self.preview_label.setMaximumSize(200, 150)
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
            for f in Path(self.path).glob("*.json"):
                theme_json = f
                break
                
            if not theme_json:
                return
                
            with open(theme_json, 'r') as f:
                theme_data = json.load(f)
                
            for category in ['sunrise', 'day', 'sunset', 'night']:
                img_list = theme_data.get(f'{category}ImageList', [])
                if img_list:
                    img_idx = img_list[0]
                    img_file = self._find_image_file(self.path, img_idx)
                    if img_file:
                        pixmap = QPixmap(img_file)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(200, 150,
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
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        self.setLayout(layout)
        
        # Theme header section
        header_card = ModernCard()
        header_layout = QVBoxLayout()
        header_card.setLayout(header_layout)
        
        header_title = QLabel("Themes")
        header_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_title.setStyleSheet("color: #0088cc; margin: 10px;")
        header_layout.addWidget(header_title)
        
        header_desc = QLabel("Select a theme to apply to your desktop")
        header_desc.setFont(QFont("Arial", 10))
        header_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_desc.setStyleSheet("color: #666; margin-bottom: 15px;")
        header_layout.addWidget(header_desc)
        
        layout.addWidget(header_card)
        
        # Current theme display
        current_card = ModernCard()
        current_layout = QVBoxLayout()
        current_card.setLayout(current_layout)
        
        current_title = QLabel("Current Theme")
        current_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        current_layout.addWidget(current_title)
        
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
        
        # Themes grid
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
        
        # Import button at bottom left
        import_layout = QHBoxLayout()
        import_layout.addStretch()
        
        self.import_button = QPushButton("Import Theme File")
        self.import_button.clicked.connect(self._import_theme)
        self.import_button.setStyleSheet("""
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
        import_layout.addWidget(self.import_button)
        
        layout.addLayout(import_layout)
        
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
            
    def _import_theme(self):
        """Import a theme file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Theme File",
            "",
            "Theme Files (*.ddw *.zip);;All Files (*)"
        )
        
        if file_path:
            try:
                result = extract_theme(file_path, cleanup=False)
                logger.info(f"Theme imported: {result['extract_dir']}")
                self._load_themes()
            except Exception as e:
                logger.error(f"Failed to import theme: {e}")


class SchedulerTab(QWidget):
    """Scheduler tab with start/stop controls and event log."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.scheduler: Optional[SchedulerManager] = None
        self._init_ui()
        self._setup_scheduler()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        self.setLayout(layout)
        
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
        
        layout.addWidget(status_card)
        
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
        
        layout.addLayout(button_layout)
        
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
        
        layout.addWidget(log_card)
        
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


class WallpaperGUI(QMainWindow):
    """Main GUI window for KDE Wallpaper Changer."""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self._init_ui()
        
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
        
        # Tab order: Themes, Settings, Scheduler
        self.themes_tab = ThemesTab(self.config_path)
        self.tabs.addTab(self.themes_tab, "🎨 Themes")
        
        self.settings_tab = SettingsTab(self.config_path)
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        self.scheduler_tab = SchedulerTab(self.config_path)
        self.tabs.addTab(self.scheduler_tab, "⏱ Scheduler")
        
    def closeEvent(self, event):
        if hasattr(self.scheduler_tab, 'scheduler') and self.scheduler_tab.scheduler is not None:
            if self.scheduler_tab.scheduler.is_running():
                self.scheduler_tab.log_area.append("Shutting down scheduler...")
                self.scheduler_tab.scheduler.stop(wait=True)
                self.scheduler_tab.log_area.append("Scheduler shutdown complete")
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

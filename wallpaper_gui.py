#!/usr/bin/env python3
"""
KDE Wallpaper Changer - GUI Application with Scheduling

A PyQt6 GUI application that uses APScheduler to automatically run
wallpaper-changing tasks at specified intervals.
"""

import sys
import logging
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QTextEdit, QGroupBox, QFormLayout
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QFont
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from kwallpaper.scheduler import SchedulerManager, create_scheduler

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


class WallpaperGUI(QMainWindow):
    """Main GUI window for KDE Wallpaper Changer."""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.scheduler: Optional[SchedulerManager] = None
        self.log_emitter = LogEmitter()
        
        self._init_ui()
        self._setup_scheduler()
        
    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("KDE Wallpaper Changer")
        self.setGeometry(100, 100, 600, 500)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        
        # Title
        title = QLabel("KDE Wallpaper Changer")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Status section
        status_group = QGroupBox("Scheduler Status")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        
        self.status_label = QLabel("Scheduler: Stopped")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        main_layout.addWidget(status_group)
        
        # Schedule info section
        schedule_group = QGroupBox("Scheduled Tasks")
        schedule_layout = QFormLayout()
        schedule_group.setLayout(schedule_layout)
        
        self.cycle_label = QLabel("Every 60 seconds")
        self.change_label = QLabel("Daily at 00:00")
        
        schedule_layout.addRow("Cycle Task:", self.cycle_label)
        schedule_layout.addRow("Daily Change:", self.change_label)
        
        main_layout.addWidget(schedule_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Scheduler")
        self.start_button.clicked.connect(self._start_scheduler)
        self.start_button.setFont(QFont("Arial", 10))
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop Scheduler")
        self.stop_button.clicked.connect(self._stop_scheduler)
        self.stop_button.setEnabled(False)
        self.stop_button.setFont(QFont("Arial", 10))
        button_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(button_layout)
        
        # Log area
        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_area)
        
        main_layout.addWidget(log_group)
        
        # Apply styles
        self._apply_styles()
        
    def _apply_styles(self):
        """Apply CSS styling to the GUI."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#startButton {
                background-color: #28a745;
            }
            QPushButton#startButton:hover {
                background-color: #218838;
            }
            QPushButton#stopButton {
                background-color: #dc3545;
            }
            QPushButton#stopButton:hover {
                background-color: #c82333;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QLabel {
                color: #333;
            }
        """)
        
    def _setup_scheduler(self):
        """Initialize the scheduler manager."""
        try:
            self.scheduler = create_scheduler(self.config_path)
            logger.info("Scheduler manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            self.status_label.setText(f"Error: {e}")
            
    def _start_scheduler(self):
        """Start the scheduler."""
        if self.scheduler is None:
            self.log_area.append("Error: Scheduler not initialized")
            return
            
        if self.scheduler.is_running():
            self.log_area.append("Scheduler is already running")
            return
            
        if self.scheduler.start():
            self.status_label.setText("Scheduler: Running")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.log_area.append("Scheduler started successfully")
            self.log_area.append("Cycle task: Every 60 seconds")
            self.log_area.append("Daily change task: At 00:00")
        else:
            self.log_area.append("Failed to start scheduler")
            
    def _stop_scheduler(self):
        """Stop the scheduler."""
        if self.scheduler is None:
            return
            
        if not self.scheduler.is_running():
            self.log_area.append("Scheduler is not running")
            return
            
        if self.scheduler.stop():
            self.status_label.setText("Scheduler: Stopped")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.log_area.append("Scheduler stopped successfully")
        else:
            self.log_area.append("Failed to stop scheduler")
            
    def log_message(self, level: str, message: str):
        """Add a message to the log area."""
        timestamp = self._get_timestamp()
        self.log_area.append(f"[{timestamp}] [{level}] {message}")
        
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def closeEvent(self, event):
        """Handle window close event."""
        if self.scheduler is not None and self.scheduler.is_running():
            self.log_area.append("Shutting down scheduler...")
            self.scheduler.stop(wait=True)
            self.log_area.append("Scheduler shutdown complete")
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
    
    window = WallpaperGUI(config_path=args.config)
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

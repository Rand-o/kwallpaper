#!/usr/bin/env python3
"""
KDE Wallpaper Changer - GUI Application with Scheduling
"""

import sys
import logging
import json
import socket
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QTextEdit, QFormLayout, QTabWidget,
        QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QFrame,
        QScrollArea, QFileDialog, QListWidget, QListWidgetItem,
        QSystemTrayIcon, QMenu
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
    from PyQt6.QtGui import QFont, QPixmap, QColor, QPainter, QPen, QIcon, QAction
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from kwallpaper.scheduler import SchedulerManager, create_scheduler
from kwallpaper.wallpaper_changer import (
    load_config, save_config, DEFAULT_CONFIG_PATH,
    discover_themes, extract_theme
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global reference to the main window for single instance
_main_window = None

# Single instance lock - uses socket to prevent multiple instances
_instance_lock = None


def _acquire_single_instance_lock():
    """Acquire a lock to prevent multiple instances. Returns True if lock acquired."""
    global _instance_lock
    try:
        # Create a socket and bind to a local port
        _instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _instance_lock.bind(('127.0.0.1', 28765))  # Random port for single instance
        _instance_lock.listen(1)
        return True
    except OSError:
        # Port is already in use, another instance is running
        return False


def _show_existing_instance():
    """Show the existing window instance by sending a signal via socket."""
    global _main_window
    
    # First try to show the local window reference
    if _main_window is not None:
        _main_window.show()
        _main_window.raise_()
        _main_window.activateWindow()
        return True
    
    # If no local reference, try to send signal to existing instance
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('127.0.0.1', 28765))
        client_socket.send(b'SHOW_WINDOW')
        client_socket.close()
        return True
    except Exception:
        return False


# KDE 6 Plasma Design System
KDE_COLORS = {
    'background': '#eff0f1',
    'panel': '#ffffff',
    'text_primary': '#31363b',
    'text_secondary': '#636d76',
    'accent': '#0082FC',
    'accent_hover': '#0072e6',
    'accent_active': '#005db3',
    'border': '#d3d6d9',
    'border_hover': '#0082FC',
}

KDE_STYLES = {
    'card': """
        QFrame {
            background-color: #ffffff;
            border: 1px solid #d3d6d9;
            border-radius: 8px;
            padding: 16px;
        }
        QFrame:hover {
            border: 1px solid #0082FC;
        }
    """,
    'button_primary': """
        QPushButton {
            background-color: #0082FC;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #0072e6;
        }
        QPushButton:pressed {
            background-color: #005db3;
        }
    """,
    'button_secondary': """
        QPushButton {
            background-color: #eff0f1;
            color: #31363b;
            border: 1px solid #d3d6d9;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #e0e3e6;
            border: 1px solid #0082FC;
        }
    """,
    'input': """
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            border: 1px solid #d3d6d9;
            border-radius: 4px;
            padding: 6px 10px;
            color: #31363b;
            min-height: 28px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #0082FC;
            padding: 5px 9px;
        }
    """,
    'checkbox': """
        QCheckBox {
            spacing: 8px;
            padding: 4px;
            color: #31363b;
        }
        QCheckBox::indicator {
            width: 20px;
            height: 20px;
            border: 2px solid #d3d6d9;
            border-radius: 4px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:hover {
            border: 2px solid #0082FC;
        }
        QCheckBox::indicator:checked {
            background-color: #0082FC;
            border: 2px solid #0082FC;
        }
    """,
    'tab_widget': """
        QTabWidget::pane {
            border: 1px solid #d3d6d9;
            border-radius: 8px;
            background-color: #eff0f1;
        }
        QTabBar::tab {
            background-color: #eff0f1;
            color: #31363b;
            padding: 8px 16px;
            border: 1px solid #d3d6d9;
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }
        QTabBar::tab:hover {
            background-color: #e0e3e6;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            color: #0082FC;
            border-bottom: 2px solid #0082FC;
        }
    """,
    'scroll_area': """
        QScrollArea {
            border: none;
            background-color: #eff0f1;
        }
        QScrollArea > QWidget > QWidget {
            background-color: #eff0f1;
        }
    """,
    'label_title': """
        QLabel {
            color: #31363b;
            font-weight: 600;
            font-size: 14px;
        }
    """,
    'label_subtitle': """
        QLabel {
            color: #636d76;
            font-size: 12px;
        }
    """,
}

logger = logging.getLogger(__name__)


class ModernCard(QFrame):
    """Modern card widget with KDE 6 Plasma styling."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet(KDE_STYLES['card'])


class SystemTrayIcon(QSystemTrayIcon):
    """System tray icon with scheduler controls."""
    
    def __init__(self, scheduler_tab, parent=None):
        super().__init__(parent)
        self.scheduler_tab = scheduler_tab
        self.setIcon(self._create_icon())
        self.setVisible(True)
        self.activated.connect(self._on_activated)
        
    def _create_icon(self) -> QIcon:
        """Create a window icon with 4 panes for the system tray."""
        # Create a window icon with 4 panes - rectangular shape
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 48" fill="#31363b">
            <rect x="2" y="4" width="28" height="40" rx="2" fill="#ffffff" stroke="#d3d6d9" stroke-width="1"/>
            <line x1="2" y1="20" x2="30" y2="20" stroke="#d3d6d9" stroke-width="1"/>
            <line x1="16" y1="4" x2="16" y2="20" stroke="#d3d6d9" stroke-width="1"/>
            <line x1="16" y1="24" x2="16" y2="44" stroke="#d3d6d9" stroke-width="1"/>
        </svg>'''
        pixmap = QPixmap()
        pixmap.loadFromData(svg.encode('utf-8'))
        return QIcon(pixmap)
        
    def _on_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_app()
        
    def update_menu(self):
        """Update tray menu based on scheduler status."""
        menu = QMenu()
        
        # Scheduler status
        status = "Running" if self.scheduler_tab.scheduler.is_running() else "Stopped"
        status_action = menu.addAction(f"Status: {status}")
        status_action.setEnabled(False)
        
        menu.addSeparator()
        
        # Start scheduler
        if not self.scheduler_tab.scheduler.is_running():
            start_action = menu.addAction("Start Scheduler")
            start_action.triggered.connect(self.scheduler_tab._start_scheduler)
        
        # Stop scheduler
        if self.scheduler_tab.scheduler.is_running():
            stop_action = menu.addAction("Stop Scheduler")
            stop_action.triggered.connect(self.scheduler_tab._stop_scheduler)
        
        menu.addSeparator()
        
        # Open app window
        open_action = menu.addAction("Open App")
        open_action.triggered.connect(self._open_app)
        
        # Quit
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        
        self.setContextMenu(menu)
        
    def _open_app(self):
        """Open the main application window."""
        # Find the main window by traversing up the parent hierarchy
        parent = self.parent()
        while parent and not hasattr(parent, 'show'):
            parent = parent.parent()
        if parent and hasattr(parent, 'show'):
            parent.show()
            parent.raise_()
            parent.activateWindow()


class SettingsTab(QWidget):
    """Settings tab for scheduler configuration - KDE 6 Plasma design."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self._init_ui()
        
    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)
        
        # Left column - all settings (350px fixed width)
        left_column = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(16)
        left_column.setLayout(left_layout)
        
        # Scheduler Section
        scheduler_card = ModernCard()
        scheduler_inner_layout = QVBoxLayout()
        scheduler_inner_layout.setSpacing(12)
        scheduler_card.setLayout(scheduler_inner_layout)
        
        title = QLabel("Scheduler")
        title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet(KDE_STYLES['label_title'])
        scheduler_inner_layout.addWidget(title)
        
        scheduler_form = QFormLayout()
        scheduler_form.setSpacing(8)
        scheduler_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        scheduler_inner_layout.addLayout(scheduler_form)
        
        self.cycle_interval = QSpinBox()
        self.cycle_interval.setRange(1, 3600)
        self.cycle_interval.setValue(60)
        self.cycle_interval.setSuffix(" seconds")
        self.cycle_interval.setStyleSheet(KDE_STYLES['input'])
        scheduler_form.addRow("Cycle Interval:", self.cycle_interval)
        
        self.daily_shuffle_enabled = QCheckBox("Enable daily theme shuffle")
        self.daily_shuffle_enabled.setChecked(True)
        self.daily_shuffle_enabled.setStyleSheet(KDE_STYLES['checkbox'])
        scheduler_inner_layout.addWidget(self.daily_shuffle_enabled)
        
        self.run_cycle = QCheckBox("Enable cycle task (runs every interval)")
        self.run_cycle.setChecked(True)
        self.run_cycle.setStyleSheet(KDE_STYLES['checkbox'])
        scheduler_inner_layout.addWidget(self.run_cycle)
        
        left_layout.addWidget(scheduler_card)
        
        # Location Section
        location_card = ModernCard()
        location_inner_layout = QVBoxLayout()
        location_inner_layout.setSpacing(12)
        location_card.setLayout(location_inner_layout)
        
        title = QLabel("Location")
        title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet(KDE_STYLES['label_title'])
        location_inner_layout.addWidget(title)
        
        location_form = QFormLayout()
        location_form.setSpacing(8)
        location_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        location_inner_layout.addLayout(location_form)
        
        self.timezone = QLineEdit("America/Phoenix")
        self.timezone.setStyleSheet(KDE_STYLES['input'])
        location_form.addRow("Timezone:", self.timezone)
        
        self.latitude = QDoubleSpinBox()
        self.latitude.setRange(-90, 90)
        self.latitude.setValue(33.4484)
        self.latitude.setDecimals(4)
        self.latitude.setStyleSheet(KDE_STYLES['input'])
        location_form.addRow("Latitude:", self.latitude)
        
        self.longitude = QDoubleSpinBox()
        self.longitude.setRange(-180, 180)
        self.longitude.setValue(-112.074)
        self.longitude.setDecimals(4)
        self.longitude.setStyleSheet(KDE_STYLES['input'])
        location_form.addRow("Longitude:", self.longitude)
        
        left_layout.addWidget(location_card)
        
        left_column.setFixedWidth(350)
        main_layout.addWidget(left_column)
        
        # Right column - blank for future settings
        right_column = QWidget()
        right_column.setStyleSheet("background-color: #eff0f1;")
        right_column.setMinimumWidth(300)
        main_layout.addWidget(right_column)
        
        # Save Button
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self._save_settings)
        self.save_button.setStyleSheet(KDE_STYLES['button_primary'])
        main_layout.addWidget(self.save_button)
        
        main_layout.addStretch()
        self._load_config()
        
    def _load_config(self):
        try:
            config = load_config(self.config_path)
            scheduling = config.get('scheduling', {})
            self.cycle_interval.setValue(scheduling.get('interval', 60))
            self.daily_shuffle_enabled.setChecked(scheduling.get('daily_shuffle_enabled', True))
            self.run_cycle.setChecked(scheduling.get('run_cycle', True))
            
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
                'daily_shuffle_enabled': self.daily_shuffle_enabled.isChecked(),
                'run_cycle': self.run_cycle.isChecked()
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


class ThemeListWidget(QListWidget):
    """List widget for displaying themes."""
    
    theme_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:hover {
                background-color: #e8f4fc;
            }
            QListWidget::item:selected {
                background-color: #0088cc;
                color: white;
            }
        """)
        
    def load_themes(self):
        """Load all themes into the list."""
        self.clear()
        
        try:
            themes = discover_themes()
            themes.sort(key=lambda x: x[0].lower())
            
            for theme_name, theme_path in themes:
                item = QListWidgetItem(theme_name)
                item.setData(Qt.ItemDataRole.UserRole, theme_path)
                self.addItem(item)
                
            logger.info(f"Loaded {len(themes)} themes")
            
        except Exception as e:
            logger.error(f"Failed to load themes: {e}")


class ThemePreviewWidget(QWidget):
    """Widget to display theme preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)
        
        # Small title at top
        title = QLabel("Theme Preview")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #0088cc; margin: 5px;")
        layout.addWidget(title)
        
        # Large preview area - takes most vertical space
        self.preview_label = QLabel("Select a theme to preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(400)
        from PyQt6.QtWidgets import QSizePolicy
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        layout.addWidget(self.preview_label)
        
    def load_preview(self, theme_path: str):
        """Load preview for given theme."""
        try:
            theme_json = None
            for f in Path(theme_path).glob("*.json"):
                theme_json = f
                break
                
            if not theme_json:
                self.preview_label.setText("No theme.json found")
                return
                
            with open(theme_json, 'r') as f:
                theme_data = json.load(f)
                
            # Get first image from each category
            images = []
            for category in ['sunrise', 'day', 'sunset', 'night']:
                img_list = theme_data.get(f'{category}ImageList', [])
                if img_list:
                    img_file = self._find_image_file(theme_path, img_list[0])
                    if img_file:
                        images.append(img_file)
                    break
                    
            if not images:
                self.preview_label.setText("No images found in theme")
                return
                
            # Show first image
            pixmap = QPixmap(images[0])
            if pixmap.isNull():
                self.preview_label.setText("Could not load preview image")
            else:
                # Scale to fit while maintaining aspect ratio
                scaled = pixmap.scaled(self.preview_label.size(),
                                       Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                self.preview_label.setPixmap(scaled)
                
        except Exception as e:
            logger.error(f"Failed to load preview: {e}")
            self.preview_label.setText(f"Error loading preview: {e}")
            
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



class ImageCrossFadeWidget(QWidget):
    """Widget that smoothly cross-fades between multiple images."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: list[str] = []
        self._blend_value = 0.0
        self._current_image_index = 0
        self._pixmap_cache: dict[int, QPixmap] = {}
        
        # Title label
        self.title_label = QLabel("Theme Preview")
        self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #0088cc;
                padding: 15px;
                background-color: #f5f5f5;
                border-radius: 8px;
                margin: 5px;
            }
        """)
        
        # Animation for cross-fade
        self._animation = QPropertyAnimation(self, b'blend')
        self._animation.setDuration(800)  # 0.8 seconds fade
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.finished.connect(self._on_animation_finished)
        
        # Auto-advance timer - will be controlled by tab visibility
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_image)
        self._timer.setSingleShot(False)
        
        self.setMinimumSize(800, 450)
        
        # Store parent tab widget for visibility tracking
        self._parent_tab = None
        self._is_visible = False  # Start as not visible
        
    @pyqtProperty(float)
    def blend(self) -> float:
        """Get current blend value (0.0 to 1.0)."""
        return self._blend_value
        
    @blend.setter
    def blend(self, value: float):
        """Set current blend value and trigger repaint."""
        self._blend_value = value
        self.update()
        
    def set_images(self, image_paths: list[str]):
        """Set the list of images to cross-fade between."""
        self._images = image_paths
        self._current_image_index = 0
        self._pixmap_cache.clear()
        
        # Pre-cache first two images
        if len(self._images) >= 1:
            self._load_pixmap(0)
        if len(self._images) >= 2:
            self._load_pixmap(1)
            
        self._blend_value = 0.0
        self.update()
        
    def _load_pixmap(self, index: int):
        """Load and cache a pixmap for a given index."""
        if index < 0 or index >= len(self._images):
            return
            
        if index in self._pixmap_cache:
            return
            
        # Clear old cache entries to limit memory usage
        # Only keep current and next image in cache
        current_index = self._current_image_index
        next_index = (current_index + 1) % len(self._images)
        
        # Clear all entries except current and next
        keys_to_keep = {current_index, next_index}
        keys_to_remove = [k for k in self._pixmap_cache if k not in keys_to_keep]
        for k in keys_to_remove:
            del self._pixmap_cache[k]
            
        image_path = self._images[index]
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self._pixmap_cache[index] = pixmap
            
    def _advance_image(self):
        """Advance to next image in the sequence."""
        if len(self._images) < 2:
            return
            
        # Start animation to fade out current image
        self._animation.stop()
        self._animation.setStartValue(self._blend_value)
        self._animation.setEndValue(1.0)
        self._animation.start()
        
    def _on_animation_finished(self):
        """Handle animation completion - switch to next image."""
        self._current_image_index = (self._current_image_index + 1) % len(self._images)
        self._blend_value = 0.0
        
        # Pre-cache next image
        next_index = (self._current_image_index + 1) % len(self._images)
        self._load_pixmap(next_index)
        
        self.update()
        
    def paintEvent(self, event):
        """Paint event for cross-fading images."""
        if not self._images:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget size
        widget_size = self.size()
        
        # Get current and next image pixmaps
        current_pixmap = self._pixmap_cache.get(self._current_image_index)
        next_index = (self._current_image_index + 1) % len(self._images)
        next_pixmap = self._pixmap_cache.get(next_index)
        
        if current_pixmap is None:
            return
            
        # Scale images to fit widget while maintaining aspect ratio
        scaled_current = self._scale_pixmap(current_pixmap, widget_size)
        
        if next_pixmap is not None:
            scaled_next = self._scale_pixmap(next_pixmap, widget_size)
        else:
            scaled_next = scaled_current
            
        # Calculate position to center the image
        x = (widget_size.width() - scaled_current.width()) // 2
        y = (widget_size.height() - scaled_current.height()) // 2
        
        # Draw title above the image
        title_height = 50  # Height of title area
        title_y = 10
        title_width = widget_size.width()
        title_rect = QRectF(0, title_y, title_width, title_height)
        painter.setOpacity(1.0)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title_label.text())
        
        # Draw separator line below title
        painter.setOpacity(1.0)
        painter.setPen(QPen(QColor("#d0d0d0"), 1))
        separator_y = title_y + title_height - 5
        painter.drawLine(0, separator_y, widget_size.width(), separator_y)
        
        # Draw current image below title (fades out as blend goes from 0 to 1)
        image_y = separator_y + 10
        painter.setOpacity(1.0 - self._blend_value)
        painter.drawPixmap(x, image_y + y, scaled_current)
        
        # Draw next image (fades in as blend goes from 0 to 1)
        painter.setOpacity(self._blend_value)
        if next_pixmap is not None:
            painter.drawPixmap(x, image_y + y, scaled_next)
            
    def _scale_pixmap(self, pixmap: QPixmap, target_size: tuple[int, int]) -> QPixmap:
        """Scale pixmap to fit target size while maintaining aspect ratio."""
        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
    def set_visible(self, visible: bool):
        """Control timer based on visibility."""
        if visible:
            self._timer.start(3000)
            self._is_visible = True
        else:
            self._timer.stop()
            self._is_visible = False
            # Clear pixmap cache when not visible to free memory
            self._pixmap_cache.clear()


class ThemesTab(QWidget):
    """Themes tab showing all imported themes - KDE 6 Plasma design."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(layout)
        
        # Left column - theme list (30% width)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Header
        header = QLabel("Themes")
        header.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        header.setStyleSheet(KDE_STYLES['label_title'])
        left_layout.addWidget(header)
        
        header_desc = QLabel("Select a theme to preview")
        header_desc.setFont(QFont("Noto Sans", 11))
        header_desc.setStyleSheet(KDE_STYLES['label_subtitle'])
        left_layout.addWidget(header_desc)
        
        self.theme_list = ThemeListWidget()
        self.theme_list.theme_selected.connect(self._on_theme_selected)
        self.theme_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.theme_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d3d6d9;
                border-radius: 6px;
                padding: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #e0e3e6;
            }
            QListWidget::item:selected {
                background-color: #0082FC;
                color: white;
            }
        """)
        left_layout.addWidget(self.theme_list)
        
        # Import button
        self.import_button = QPushButton("Import Theme File")
        self.import_button.clicked.connect(self._import_theme)
        self.import_button.setStyleSheet(KDE_STYLES['button_secondary'])
        left_layout.addWidget(self.import_button)
        
        left_panel.setFixedWidth(300)
        layout.addWidget(left_panel)
        
        # Right panel - preview (70% width)
        self.preview_widget = ImageCrossFadeWidget()
        self.preview_widget.setStyleSheet("background-color: #eff0f1;")
        layout.addWidget(self.preview_widget)
        
        # Track tab visibility to control preview timer
        # Store reference to check later when tab widget is fully set up
        self._pending_tab_check = True
        
    def _check_initial_tab_visibility(self):
        """Check if this tab is visible and start timer if so."""
        if not self._pending_tab_check:
            return
        self._pending_tab_check = False
        
        parent_tab_widget = self.parentWidget()
        if parent_tab_widget and hasattr(parent_tab_widget, 'currentChanged'):
            parent_tab_widget.currentChanged.connect(self._on_tab_changed)
            # Check if this tab is initially visible
            current_index = parent_tab_widget.currentIndex()
            for i in range(parent_tab_widget.count()):
                if parent_tab_widget.widget(i) is self:
                    self.preview_widget.set_visible(i == current_index)
                    break
        
        # Load themes
        self.theme_list.load_themes()
        
        # Select first theme if available
        if self.theme_list.count() > 0:
            self.theme_list.setCurrentRow(0)
            # Trigger preview update
            current_item = self.theme_list.currentItem()
            if current_item:
                theme_path = current_item.data(Qt.ItemDataRole.UserRole)
                images = self._load_theme_images(theme_path)
                self.preview_widget.set_images(images)
        
    def _on_tab_changed(self, index: int):
        """Handle tab change to control preview timer based on visibility."""
        parent_tab_widget = self.parentWidget()
        if not parent_tab_widget or not hasattr(parent_tab_widget, 'currentIndex'):
            return
        
        current_index = parent_tab_widget.currentIndex()
        # Find which tab index this ThemesTab is at
        if hasattr(parent_tab_widget, 'count'):
            for i in range(parent_tab_widget.count()):
                if parent_tab_widget.widget(i) is self:
                    # This is the ThemesTab
                    is_visible = i == current_index
                    self.preview_widget.set_visible(is_visible)
                    # If tab became visible, refresh the preview for current selection
                    if is_visible:
                        current_item = self.theme_list.currentItem()
                        if current_item:
                            theme_path = current_item.data(Qt.ItemDataRole.UserRole)
                            images = self._load_theme_images(theme_path)
                            self.preview_widget.set_images(images)
                    break
        
    def _on_selection_changed(self):
        """Handle theme selection change."""
        current_item = self.theme_list.currentItem()
        if current_item:
            theme_path = current_item.data(Qt.ItemDataRole.UserRole)
            images = self._load_theme_images(theme_path)
            self.preview_widget.set_images(images)
            
    def _on_theme_selected(self, theme_path: str):
        """Handle theme selected signal."""
        images = self._load_theme_images(theme_path)
        self.preview_widget.set_images(images)
        
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
                self.theme_list.load_themes()
            except Exception as e:
                logger.error(f"Failed to import theme: {e}")



    def _load_theme_images(self, theme_path: str) -> list[str]:
        """Extract images from theme for cross-fade preview (images 1-16, sorted)."""
        images = []
        try:
            theme_json = None
            for f in Path(theme_path).glob("*.json"):
                theme_json = f
                break
                
            if not theme_json:
                return images
                
            with open(theme_json, 'r') as f:
                theme_data = json.load(f)
                
            # Get images 1-16 from all categories, sorted by index
            all_image_indices = []
            for category in ['sunrise', 'day', 'sunset', 'night']:
                img_list = theme_data.get(f'{category}ImageList', [])
                for img_index in img_list:
                    # Only include images 1-16
                    if 1 <= img_index <= 16:
                        all_image_indices.append(img_index)
            
            # Sort indices and get unique values
            all_image_indices = sorted(set(all_image_indices))
            
            # Get image files in sorted order
            for img_index in all_image_indices:
                img_file = self._find_image_file(theme_path, img_index)
                if img_file and img_file not in images:
                    images.append(img_file)
                        
        except Exception as e:
            logger.error(f"Failed to load theme images: {e}")
            
        # Debug: log the images being loaded
        logger.info(f"Loaded {len(images)} images for preview: {all_image_indices}")
            
        return images

    def _find_image_file(self, theme_path: str, index: int) -> Optional[str]:
        """Find image file by index in theme directory."""
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

class SchedulerTab(QWidget):
    """Scheduler tab with start/stop controls and event log - KDE 6 Plasma design."""
    
    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        self.scheduler: Optional[SchedulerManager] = None
        self._init_ui()
        self._setup_scheduler()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(layout)
        
        # Status Card
        status_card = ModernCard()
        status_layout = QVBoxLayout()
        status_layout.setSpacing(12)
        status_card.setLayout(status_layout)
        
        status_title = QLabel("Scheduler Status")
        status_title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        status_title.setStyleSheet(KDE_STYLES['label_title'])
        status_layout.addWidget(status_title)
        
        self.status_label = QLabel("Scheduler: Stopped")
        self.status_label.setFont(QFont("Noto Sans", 12))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 20px;
                background-color: #e8f4fc;
                border-radius: 6px;
                color: #0082FC;
            }
        """)
        status_layout.addWidget(self.status_label)
        
        layout.addWidget(status_card)
        
        # Button Layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        
        self.start_button = QPushButton("▶ Start Scheduler")
        self.start_button.clicked.connect(self._start_scheduler)
        self.start_button.setFont(QFont("Noto Sans", 11))
        self.start_button.setStyleSheet(KDE_STYLES['button_primary'])
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹ Stop Scheduler")
        self.stop_button.clicked.connect(self._stop_scheduler)
        self.stop_button.setFont(QFont("Noto Sans", 11))
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet(KDE_STYLES['button_secondary'])
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        # Log Card
        log_card = ModernCard()
        log_layout = QVBoxLayout()
        log_layout.setSpacing(12)
        log_card.setLayout(log_layout)
        
        log_title = QLabel("Event Log")
        log_title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        log_title.setStyleSheet(KDE_STYLES['label_title'])
        log_layout.addWidget(log_title)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Noto Sans Mono", 10))
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #eff0f1;
                color: #31363b;
                border: 1px solid #d3d6d9;
                border-radius: 6px;
                padding: 12px;
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
            self.log_area.append("Daily shuffle: Enabled")
            # Update tray menu by finding main window
            parent = self.parentWidget()
            while parent and not hasattr(parent, 'tray_icon'):
                parent = parent.parentWidget()
            if parent and hasattr(parent, 'tray_icon'):
                parent.tray_icon.update_menu()
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
            # Update tray menu by finding main window
            parent = self.parentWidget()
            while parent and not hasattr(parent, 'tray_icon'):
                parent = parent.parentWidget()
            if parent and hasattr(parent, 'tray_icon'):
                parent.tray_icon.update_menu()
        else:
            self.log_area.append("Failed to stop scheduler")


class WallpaperGUI(QMainWindow):
    """Main GUI window for KDE Wallpaper Changer - KDE 6 Plasma design."""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path or str(DEFAULT_CONFIG_PATH)
        # Set global reference for single instance
        global _main_window
        _main_window = self
        self._init_ui()
        
    def _init_ui(self):
        self.setWindowTitle("KDE Wallpaper Changer")
        # Set initial size to 16:9 aspect ratio (matching wallpaper resolution 5120x2880)
        self.setGeometry(100, 100, 1600, 900)
        # Maintain 16:9 aspect ratio
        self.setMinimumSize(800, 450)
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        central.setLayout(main_layout)
        
        title = QLabel("KDE Wallpaper Changer")
        title.setFont(QFont("Noto Sans", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(KDE_STYLES['label_title'])
        main_layout.addWidget(title)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(KDE_STYLES['tab_widget'])
        main_layout.addWidget(self.tabs)
        
        # Tab order: Themes, Settings, Scheduler
        self.themes_tab = ThemesTab(self.config_path)
        self.tabs.addTab(self.themes_tab, "🎨 Themes")
        # Check initial tab visibility after adding to tab widget
        self.themes_tab._check_initial_tab_visibility()
        
        self.settings_tab = SettingsTab(self.config_path)
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        self.scheduler_tab = SchedulerTab(self.config_path)
        self.tabs.addTab(self.scheduler_tab, "⏱ Scheduler")
        
        # Auto-start scheduler when application opens
        if self.scheduler_tab.scheduler is not None and not self.scheduler_tab.scheduler.is_running():
            self.scheduler_tab._start_scheduler()
        
        # Initialize system tray icon
        self.tray_icon = SystemTrayIcon(self.scheduler_tab, self)
        self.tray_icon.update_menu()
        
        # Set up socket listener for single instance communication
        self._socket_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket_listener.setblocking(False)
        self._socket_listener.listen(1)
        self._socket_timer = QTimer(self)
        self._socket_timer.timeout.connect(self._handle_socket_connection)
        self._socket_timer.start(100)  # Check every 100ms
        
    def _handle_socket_connection(self):
        """Handle incoming socket connections to show the window."""
        try:
            self._socket_listener.setblocking(False)
            conn, addr = self._socket_listener.accept()
            data = conn.recv(1024)
            if data == b'SHOW_WINDOW':
                self.show()
                self.raise_()
                self.activateWindow()
            conn.close()
        except BlockingIOError:
            # No connection pending
            pass
        except Exception:
            pass
        
    def closeEvent(self, event):
        """Handle window close event - hide to tray instead of quitting."""
        # Only hide if system tray is available
        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            # No system tray - shutdown scheduler and quit
            if hasattr(self.scheduler_tab, 'scheduler') and self.scheduler_tab.scheduler is not None:
                if self.scheduler_tab.scheduler.is_running():
                    self.scheduler_tab.log_area.append("Shutting down scheduler...")
                    self.scheduler_tab.scheduler.stop(wait=True)
                    self.scheduler_tab.log_area.append("Scheduler shutdown complete")
            event.accept()
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
    # Prevent app from quitting when window is closed (tray icon should keep it running)
    app.setQuitOnLastWindowClosed(False)
    
    # Try to acquire single instance lock
    if not _acquire_single_instance_lock():
        # Another instance is running - show it and exit
        _show_existing_instance()
        # Give time for the signal to be processed
        import time
        time.sleep(0.1)
        sys.exit(0)
    
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
    
    # Check if a window already exists (single instance)
    global _main_window
    if _main_window is not None:
        # Window exists - show it instead of creating a new one
        _main_window.show()
        _main_window.raise_()
        _main_window.activateWindow()
    else:
        # Create new window
        window = WallpaperGUI(config_path=args.config)
        window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
kWallpaper — Native KDE Plasma 6 Application

Integrates with the KDE desktop by:
  • Using system Breeze styling and icons via QPalette / QIcon.fromTheme()
  • Providing a QSystemTrayIcon with scheduler controls
  • Persisting window state with QSettings
  • Enforcing single-instance via local socket

Color scheme can be overridden in Settings → Appearance,
or follows the system KDE theme by default.
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
        QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox,
        QGroupBox, QSplitter, QFileDialog, QListWidget, QListWidgetItem,
        QSystemTrayIcon, QMenu, QSizePolicy, QMessageBox, QFrame,
        QScrollArea,
    )
    from PyQt6.QtCore import (
        Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve,
        pyqtProperty, QSettings, QEvent, QThreadPool, QRunnable,
        QObject,
    )
    from PyQt6.QtGui import (
        QPixmap, QColor, QPainter, QPen, QIcon, QPalette, QFontDatabase,
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from kwallpaper.scheduler import SchedulerManager, create_scheduler
from kwallpaper.wallpaper_changer import (
    load_config, save_config, DEFAULT_CONFIG_PATH,
    discover_themes, extract_theme,
)

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

APP_NAME    = "kWallpaper"
APP_VERSION = "1.0.0"
ORG_NAME    = "kwallpaper"
SOCKET_PORT = 28765

_main_window:    Optional["WallpaperChangerWindow"] = None
_instance_lock:  Optional[socket.socket]            = None
_system_palette: Optional["QPalette"]               = None   # snapshot at startup


# ── Single-instance helpers ──────────────────────────────────────────────────

def _acquire_lock() -> bool:
    """Bind a local TCP socket to act as an instance lock."""
    global _instance_lock
    try:
        _instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _instance_lock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _instance_lock.bind(("127.0.0.1", SOCKET_PORT))
        _instance_lock.listen(1)
        _instance_lock.setblocking(False)
        return True
    except OSError:
        return False


def _signal_running_instance() -> bool:
    """Tell the already-running instance to raise its window."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", SOCKET_PORT))
        s.sendall(b"SHOW")
        s.close()
        return True
    except Exception:
        return False


# ── Breeze-matching QPalettes for manual scheme override ─────────────────────

def _breeze_light() -> QPalette:
    """QPalette that mirrors KDE Breeze Light colour scheme."""
    p = QPalette()
    _s = p.setColor
    for role, c in (
        (QPalette.ColorRole.Window,          "#eff0f1"),
        (QPalette.ColorRole.WindowText,      "#31363b"),
        (QPalette.ColorRole.Base,            "#fcfcfc"),
        (QPalette.ColorRole.AlternateBase,   "#eff0f1"),
        (QPalette.ColorRole.Text,            "#31363b"),
        (QPalette.ColorRole.Button,          "#eff0f1"),
        (QPalette.ColorRole.ButtonText,      "#31363b"),
        (QPalette.ColorRole.Highlight,       "#3daee9"),
        (QPalette.ColorRole.HighlightedText, "#fcfcfc"),
        (QPalette.ColorRole.ToolTipBase,     "#eff0f1"),
        (QPalette.ColorRole.ToolTipText,     "#31363b"),
        (QPalette.ColorRole.Link,            "#2980b9"),
        (QPalette.ColorRole.Mid,             "#c8cbce"),
        (QPalette.ColorRole.PlaceholderText, "#8e9297"),
    ):
        _s(role, QColor(c))
    d = QPalette.ColorGroup.Disabled
    for role in (QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        _s(d, role, QColor("#a0a1a3"))
    return p


def _breeze_dark() -> QPalette:
    """QPalette that mirrors KDE Breeze Dark colour scheme."""
    p = QPalette()
    _s = p.setColor
    for role, c in (
        (QPalette.ColorRole.Window,          "#31363b"),
        (QPalette.ColorRole.WindowText,      "#eff0f1"),
        (QPalette.ColorRole.Base,            "#232629"),
        (QPalette.ColorRole.AlternateBase,   "#31363b"),
        (QPalette.ColorRole.Text,            "#eff0f1"),
        (QPalette.ColorRole.Button,          "#31363b"),
        (QPalette.ColorRole.ButtonText,      "#eff0f1"),
        (QPalette.ColorRole.Highlight,       "#3daee9"),
        (QPalette.ColorRole.HighlightedText, "#eff0f1"),
        (QPalette.ColorRole.ToolTipBase,     "#31363b"),
        (QPalette.ColorRole.ToolTipText,     "#eff0f1"),
        (QPalette.ColorRole.Link,            "#2980b9"),
        (QPalette.ColorRole.Mid,             "#464b50"),
        (QPalette.ColorRole.PlaceholderText, "#7f8487"),
    ):
        _s(role, QColor(c))
    d = QPalette.ColorGroup.Disabled
    for role in (QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        _s(d, role, QColor("#6e7174"))
    return p


def apply_color_scheme(name: str):
    """Apply a colour scheme by name: 'system', 'light', or 'dark'."""
    app = QApplication.instance()
    if name == "dark":
        app.setPalette(_breeze_dark())
    elif name == "light":
        app.setPalette(_breeze_light())
    else:
        if _system_palette is not None:
            app.setPalette(QPalette(_system_palette))



# ── Icon management for theme-aware icons ────────────────────────────────────────────


def get_icon_for_theme(theme_mode: str) -> QIcon:
    """Get appropriate icon based on theme mode: "system", "light", or "dark"."""
    icons_dir = Path(__file__).parent / "icons"
    
    # Map theme modes to icon filenames
    icon_map = {
        "light": "kWallpaper-light.png",
        "dark": "kWallpaper-dark.png",
        "system": "kWallpaper-light.png",  # Default to light for system mode
    }
    
    icon_filename = icon_map.get(theme_mode, "kwallpaper.png")
    icon_path = icons_dir / icon_filename
    
    if icon_path.exists():
        return QIcon(str(icon_path))
    else:
        # Fallback to theme icon
        return QIcon.fromTheme("preferences-desktop-wallpaper", QIcon.fromTheme("image-x-generic"))

# ═════════════════════════════════════════════════════════════════════════════
#  Widgets
# ═════════════════════════════════════════════════════════════════════════════

class _PixmapLoader(QRunnable):
    """Loads a QPixmap off the GUI thread and emits it when ready."""

    def __init__(self, path: str, sig: QObject):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._sig = sig

    def run(self):
        pm = QPixmap(self._path)
        if pm.isNull():
            pm = QPixmap()
        self._sig.pixmap_loaded.emit(self._path, pm)


class _ThumbnailWorker(QRunnable):
    """Generates a small JPEG thumbnail off the GUI thread."""

    def __init__(self, path: str, sig: QObject):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._sig = sig

    def run(self):
        from kwallpaper.wallpaper_changer import ensure_thumbnail
        self._sig.thumb_ready.emit(self._path, ensure_thumbnail(self._path))


class _LoadSignals(QObject):
    """Signal emitter shared by background workers (lives on the GUI thread)."""

    pixmap_loaded = pyqtSignal(str, QPixmap)
    thumb_ready = pyqtSignal(str, str)  # (source path, thumbnail path)
    op_finished = pyqtSignal(str, bool, str)  # (op name, success, message)


class _OpWorker(QRunnable):
    """Runs a blocking core operation off the GUI thread.

    The callable must return (success: bool, message: str).
    """

    def __init__(self, op: str, fn, sig: QObject):
        super().__init__()
        self.setAutoDelete(True)
        self._op = op
        self._fn = fn
        self._sig = sig

    def run(self):
        try:
            success, message = self._fn()
        except Exception as e:
            import traceback
            logger.error(f"{self._op} failed: {e}")
            logger.error(traceback.format_exc())
            success, message = False, str(e)
        self._sig.op_finished.emit(self._op, success, message)


class ImageCrossFadeWidget(QWidget):
    """Cross-fade preview widget.

    All image decoding and scaling happens in background worker threads.
    The widget only ever renders ~512px thumbnails (never full-res files),
    pre-scaled once to widget size, and paintEvent is pure drawPixmap.
    """

    _MAX_CACHE = 32   # LRU cap for raw (thumbnail) pixmaps

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: list[str] = []
        self._blend: float = 0.0
        self._idx: int = 0
        self._thumb_paths: dict[int, str] = {}   # image idx -> thumb path
        self._raw_cache: dict[str, QPixmap] = {} # thumb path -> pixmap (LRU)
        self._scaled: dict[int, QPixmap] = {}    # image idx -> scaled pixmap
        self._loading: set[str] = set()          # thumb paths in flight

        self._pool = QThreadPool(self)
        self._signals = _LoadSignals(self)
        self._signals.pixmap_loaded.connect(self._on_pixmap_loaded)
        self._signals.thumb_ready.connect(self._on_thumb_ready)

        self.setAutoFillBackground(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 200)

        # Cross-fade animation
        self._anim = QPropertyAnimation(self, b"blendValue")
        self._anim.setDuration(1200)    # 1.2 s cross-fade for cinematic smoothness
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.finished.connect(self._on_fade_done)

        # Auto-advance timer
        self._timer = QTimer(self)
        self._timer.setInterval(2700)   # 1.5 s hold + 1.2 s fade = 2.7 s per frame
        self._timer.timeout.connect(self._advance)

    # -- animated property -----------------------------------------------------
    @pyqtProperty(float)
    def blendValue(self) -> float:
        return self._blend

    @blendValue.setter
    def blendValue(self, v: float):
        self._blend = v
        self.update()

    # -- public API ------------------------------------------------------------
    def set_images(self, paths: list[str]):
        """Switch to a new image list. Cheap: stores the list and kicks off
        background thumbnail + pixmap loading; the first frame appears as
        soon as the first background load finishes."""
        self._timer.stop()
        self._anim.stop()
        self._images = list(paths)
        self._idx = 0
        self._blend = 0.0
        self._thumb_paths = {}
        self._scaled = {}
        self._loading = set()
        for i, p in enumerate(self._images):
            self._request(i)
        self.update()

    def start(self):
        if len(self._images) > 1:
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self._anim.stop()

    # -- background loading ----------------------------------------------------
    def _request(self, idx: int):
        """Kick off the thumbnail + pixmap pipeline for one image."""
        if not (0 <= idx < len(self._images)):
            return
        path = self._images[idx]
        if idx in self._thumb_paths or idx in self._scaled:
            return
        self._pool.start(_ThumbnailWorker(path, self._signals))

    def _on_thumb_ready(self, src: str, thumb: str):
        idx = self._images.index(src) if src in self._images else None
        if idx is None:
            return
        self._thumb_paths[idx] = thumb
        if thumb in self._raw_cache:
            self._on_pixmap_loaded(thumb, self._raw_cache[thumb])
            return
        if thumb in self._loading:
            return
        self._loading.add(thumb)
        self._pool.start(_PixmapLoader(thumb, self._signals))

    def _on_pixmap_loaded(self, thumb: str, pm: QPixmap):
        self._loading.discard(thumb)
        if pm.isNull():
            return
        # LRU insert: move to end, evict oldest beyond the cap
        self._raw_cache.pop(thumb, None)
        self._raw_cache[thumb] = pm
        while len(self._raw_cache) > self._MAX_CACHE:
            self._raw_cache.pop(next(iter(self._raw_cache)))
        # Scale once to current widget size for every image using this thumb
        for idx, t in self._thumb_paths.items():
            if t == thumb and idx not in self._scaled:
                self._scaled[idx] = self._scale_to_widget(pm)
        self.update()

    def _scale_to_widget(self, pm: QPixmap) -> QPixmap:
        sz = self.size()
        if sz.width() <= 0 or sz.height() <= 0:
            return pm
        return pm.scaled(sz, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

    # -- internals -------------------------------------------------------------
    def _advance(self):
        if len(self._images) < 2:
            return
        nxt = (self._idx + 1) % len(self._images)
        self._request(nxt)
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _on_fade_done(self):
        self._idx = (self._idx + 1) % len(self._images)
        self._blend = 0.0
        self.update()

    def resizeEvent(self, event):
        # Widget size changed: re-scale cached pixmaps once, not per-paint.
        self._scaled = {}
        for idx, t in self._thumb_paths.items():
            pm = self._raw_cache.get(t)
            if pm is not None:
                self._scaled[idx] = self._scale_to_widget(pm)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        pal = self.palette()
        sz = self.size()

        if not self._images:
            # Draw dashed placeholder
            pen = QPen(pal.color(QPalette.ColorRole.Mid))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRoundedRect(
                self.rect().adjusted(8, 8, -8, -8), 8, 8)
            painter.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Select a theme to preview")
            painter.end()
            return

        cur = self._scaled.get(self._idx)
        if cur is None:
            # Fast placeholder until the first background load arrives
            painter.fillRect(self.rect(),
                             pal.color(QPalette.ColorRole.AlternateBase))
            painter.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Loading preview…")
            painter.end()
            return

        cx = (sz.width()  - cur.width())  // 2
        cy = (sz.height() - cur.height()) // 2
        painter.setOpacity(1.0 - self._blend)
        painter.drawPixmap(cx, cy, cur)

        if self._blend > 0.001:
            nxt = self._scaled.get((self._idx + 1) % len(self._images))
            if nxt is not None:
                nx = (sz.width()  - nxt.width())  // 2
                ny = (sz.height() - nxt.height()) // 2
                painter.setOpacity(self._blend)
                painter.drawPixmap(nx, ny, nxt)

        painter.end()


# ═════════════════════════════════════════════════════════════════════════════
#  Pages (tabs)
# ═════════════════════════════════════════════════════════════════════════════

class ThemesPage(QWidget):
    """Browse, preview, import, and apply wallpaper themes."""

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self._cfg = config_path
        # Ensure config directories exist before any operations
        from kwallpaper.wallpaper_changer import ensure_config_dirs
        ensure_config_dirs()
        # Cache for image paths per theme (path -> list[str])
        self._image_cache: dict[str, list[str]] = {}
        # Shared worker pool + signals for background Apply/Import/Delete
        self._pool = QThreadPool(self)
        self._signals = _LoadSignals(self)
        self._signals.op_finished.connect(self._on_op_finished)
        self._build()

    # ── construction ----------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split)

        # Left: theme list + buttons
        # Left: theme list + buttons
        left = QWidget()
        left.setMinimumWidth(200)  # Smaller initial width for themes list
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        self.theme_list = QListWidget()
        self.theme_list.setAlternatingRowColors(True)
        self.theme_list.currentItemChanged.connect(self._on_select)
        lv.addWidget(self.theme_list)

        brow = QHBoxLayout()
        brow.setSpacing(6)
        self.import_btn = QPushButton(
            QIcon.fromTheme("document-import"), "Import…")
        self.import_btn.setToolTip("Import a .ddw or .zip theme file")
        self.import_btn.clicked.connect(self._import)
        brow.addWidget(self.import_btn)

        self.apply_btn = QPushButton(
            QIcon.fromTheme("dialog-ok-apply"), "Apply")
        self.apply_btn.setToolTip(
            "Set the selected theme as your wallpaper")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        brow.addWidget(self.apply_btn)

        self.delete_btn = QPushButton(
            QIcon.fromTheme("user-trash"), "Delete")
        self.delete_btn.setToolTip("Delete the selected theme")
        self.delete_btn.clicked.connect(self._delete_theme)
        brow.addWidget(self.delete_btn)
        # Make buttons smaller
        btn_size = 75
        self.import_btn.setMaximumWidth(btn_size)
        self.apply_btn.setMaximumWidth(btn_size)
        self.delete_btn.setMaximumWidth(btn_size)
        # Delete warning goes under buttons (separate row)
        self.delete_warning = QLabel(
            "Scheduler must be stopped to delete themes")
        self.delete_warning.setStyleSheet("color: red;")
        self.delete_warning.setVisible(False)
        lv.addLayout(brow)

        lv.addWidget(self.delete_warning)



        split.addWidget(left)

        # Right: cross-fade preview
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(4)

        self.preview = ImageCrossFadeWidget()
        rv.addWidget(self.preview, 1)

        # Image count info goes after preview on the right side
        self.preview_info = QLabel()
        self.preview_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rv.addWidget(self.preview_info)

        split.addWidget(right)
        # Set initial splitter sizes: left=150, right=850 (total 1000)
        split.setSizes([150, 850])
    def load_themes(self):
        self.theme_list.clear()
        try:
            for name, path in sorted(discover_themes(),
                                     key=lambda t: t[0].lower()):
                it = QListWidgetItem(name)
                it.setData(Qt.ItemDataRole.UserRole, path)
                self.theme_list.addItem(it)
            if self.theme_list.count():
                self.theme_list.setCurrentRow(0)
        except Exception as e:
            logger.error(f"Theme discovery failed: {e}")

    def set_tab_visible(self, vis: bool):
        """Start/stop the preview slideshow based on tab visibility."""
        if vis:
            cur = self.theme_list.currentItem()
            if cur:
                self.preview.set_images(
                    self._images_for(
                        cur.data(Qt.ItemDataRole.UserRole)))
            self.preview.start()
        else:
            self.preview.stop()

    # ── slots -----------------------------------------------------------------
    def _on_select(self, cur, _prev):
        if cur is None:
            self.apply_btn.setEnabled(False)
            self.preview.set_images([])
            self.preview_info.clear()
            return
        self.apply_btn.setEnabled(True)
        imgs = self._images_for(cur.data(Qt.ItemDataRole.UserRole))
        self.preview.set_images(imgs)
        self.preview.start()
        if imgs:
            self.preview_info.setText(f"{len(imgs)} images")
        else:
            self.preview_info.clear()
    def _import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Theme", "",
            "Theme Files (*.ddw *.zip);;All Files (*)")
        if not paths:
            return
        self._set_busy(self.import_btn, True)
        self._pool.start(_OpWorker(
            "import", lambda: self._import_worker(paths), self._signals))

    def _import_worker(self, paths: list[str]):
        """Blocking import of one or more theme archives (worker thread)."""
        from kwallpaper.core import import_theme
        imported = 0
        failed = 0
        errors = []
        for path in paths:
            try:
                import_theme(path)
                imported += 1
            except Exception as e:
                logger.error(f"Import failed for {path}: {e}")
                failed += 1
                errors.append(f"{Path(path).name}: {e}")
        msg = f"{imported} theme(s) imported successfully"
        if failed:
            msg += f"; {failed} failed"
            errors.append("See log for details")
        detail = "\n".join(errors) if failed else ""
        return (failed == 0, msg, detail)

    def _on_op_finished(self, op: str, success: bool, message: str):
        """Slot: a background Apply/Import/Delete operation completed."""
        if op == "import":
            self._set_busy(self.import_btn, False)
            self.load_themes()
            self._status(message)
            if not success:
                QMessageBox.warning(self, "Import Failed", message)
        elif op == "apply":
            self._set_busy(self.apply_btn, False)
            self._status(message)
            if not success:
                QMessageBox.warning(self, "Apply Failed", message)
        elif op == "delete":
            self._set_busy(self.delete_btn, False)
            self.load_themes()
            self._status(message)
            if not success:
                QMessageBox.warning(self, "Delete Failed", message)

    def _set_busy(self, btn: QPushButton, busy: bool):
        btn.setEnabled(not busy)
        if busy:
            btn.setText("Working…")
        else:
            btn.setText("Apply" if btn is self.apply_btn
                        else "Import…" if btn is self.import_btn
                        else "Delete")

    def _delete_theme(self):
        cur = self.theme_list.currentItem()
        if not cur:
            return

        name = cur.text()
        theme_path = cur.data(Qt.ItemDataRole.UserRole)

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Theme",
            f"Delete theme '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # Delete theme folder from disk in a background worker
        self._set_busy(self.delete_btn, True)
        self._pool.start(_OpWorker(
            "delete",
            lambda: self._delete_worker(theme_path, name),
            self._signals))

    def _delete_worker(self, theme_path: str, name: str):
        """Blocking theme deletion (worker thread)."""
        from kwallpaper.core import delete_theme
        try:
            delete_theme(theme_path)
        except Exception as e:
            logger.error(f"Delete failed for {theme_path}: {e}")
            return (False, f"Delete failed: {e}", "")
        return (True, f"Theme '{name}' deleted successfully", "")
    def _apply(self):
        cur = self.theme_list.currentItem()
        if not cur:
            return
        name   = cur.text()
        folder_path = cur.data(Qt.ItemDataRole.UserRole)
        folder = Path(folder_path).name
        
        # Load config to check shuffle setting
        config = load_config(self._cfg)
        shuffle_enabled = config.get('scheduling', {}).get('daily_shuffle_enabled', False)
        
        # If shuffle is enabled, ask user for confirmation
        if shuffle_enabled:
            reply = QMessageBox.question(
                self,
                "Confirm Theme Apply",
                f"Daily shuffle is enabled. If you apply this theme, a new shuffle list will be created. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return  # Cancel the apply operation
        
        logger.info(f"Applying theme: {name}, folder_path: {folder_path}, folder: {folder}")
        # Run the whole apply (astral math, D-Bus, config + shuffle writes)
        # in a background worker so the GUI never freezes.
        self._set_busy(self.apply_btn, True)
        self._pool.start(_OpWorker(
            "apply",
            lambda: self._apply_worker(folder_path),
            self._signals))

    def _apply_worker(self, folder_path: str):
        """Blocking theme apply (worker thread)."""
        from kwallpaper.core import apply_theme
        result = apply_theme(folder_path, self._cfg)
        if result.success:
            return (True, f"Applied: {result.theme_name}", "")
        return (False, f"Failed to apply: {result.message}", "")

    # ── helpers ---------------------------------------------------------------
    def _update_delete_button_state(self, running: bool):
        """Update delete button state based on scheduler running status."""
        if running:
            self.delete_btn.setEnabled(False)
            self.delete_warning.setVisible(True)
        else:
            self.delete_btn.setEnabled(True)
            self.delete_warning.setVisible(False)

    def _status(self, msg: str, ms: int = 5000):
        w = self.window()
        if isinstance(w, QMainWindow):
            w.statusBar().showMessage(msg, ms)
    def _discover_images(self, theme_path: str) -> list[str]:
        """Discover all image files in theme directory in one glob call."""
        images = []
        try:
            # Single glob to get all JPEG/PNG files - much faster than 3 globs
            for f in Path(theme_path).glob("*.jpeg"):
                images.append((f.stem, str(f)))
            for f in Path(theme_path).glob("*.jpg"):
                images.append((f.stem, str(f)))
            for f in Path(theme_path).glob("*.png"):
                images.append((f.stem, str(f)))

            # Filter for index pattern and sort by index
            result: list[str] = []
            for name, path in sorted(images, key=lambda x: int(x[0].rsplit("_", 1)[-1])):
                try:
                    if "_" in name:
                        idx = int(name.rsplit("_", 1)[-1])
                        if 1 <= idx <= 16:
                            result.append(path)
                except (ValueError, IndexError):
                    continue
            return result
        except Exception as e:
            logger.error(f"Image discovery error: {e}")
            return []

    def _images_for(self, theme_path: str) -> list[str]:
        """Return sorted image file paths (indices 1-16) for a theme."""
        # Check cache first - eliminates 48+ glob() calls on repeated selection
        if theme_path in self._image_cache:
            return self._image_cache[theme_path]

        result: list[str] = []
        try:
            jf = next(Path(theme_path).glob("*.json"), None)
            if not jf:
                return result
            with open(jf) as fh:
                data = json.load(fh)
            # Discover images in one pass instead of 48 individual calls
            images = self._discover_images(theme_path)
            # Filter to indices 1-16
            for path in images:
                stem = Path(path).stem
                try:
                    if "_" in stem:
                        idx = int(stem.rsplit("_", 1)[-1])
                        if 1 <= idx <= 16:
                            result.append(path)
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            logger.error(f"Image list error: {e}")
        # Cache the result for future theme selections
        if result:
            self._image_cache[theme_path] = result
        return result


# ─────────────────────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    """Scheduler, location, and appearance configuration."""

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self._cfg = config_path
        # Ensure config directories exist before any operations
        from kwallpaper.wallpaper_changer import ensure_config_dirs
        ensure_config_dirs()
        self._build()
        self._load()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        body = QWidget()
        col  = QVBoxLayout(body)
        col.setSpacing(16)

        # ── Scheduler ──
        sg = QGroupBox("Scheduler")
        col.addWidget(sg)
        sf = QFormLayout(sg)
        self.interval = QSpinBox()
        self.interval.setRange(1, 3600)
        self.interval.setSuffix(" s")
        sf.addRow("Cycle interval:", self.interval)
        self.run_cycle = QCheckBox(
            "Enable cycle task (runs every interval)")
        sf.addRow(self.run_cycle)
        self.daily_shuffle = QCheckBox("Enable daily theme shuffle")
        sf.addRow(self.daily_shuffle)
        self.auto_start_scheduler = QCheckBox("Start scheduler on app launch")
        sf.addRow(self.auto_start_scheduler)

        # ── Location ──
        lg = QGroupBox("Location")
        lf = QFormLayout(lg)
        self.timezone = QLineEdit()
        lf.addRow("Timezone:", self.timezone)
        
        # Lat/lon row with auto-detect button
        lat_lon_row = QHBoxLayout()
        self.lat = QDoubleSpinBox()
        self.lat.setRange(-90.0, 90.0)
        self.lat.setDecimals(4)
        lat_lon_row.addWidget(self.lat)
        lat_lon_row.addWidget(QLabel("Latitude"))
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180.0, 180.0)
        self.lon.setDecimals(4)
        lat_lon_row.addWidget(self.lon)
        lat_lon_row.addWidget(QLabel("Longitude"))
        self.auto_detect_btn = QPushButton(
            QIcon.fromTheme("view-refresh"), "Auto-detect")
        self.auto_detect_btn.setToolTip("Detect current location from KDE system settings")
        self.auto_detect_btn.clicked.connect(self._on_auto_detect_location)
        lat_lon_row.addWidget(self.auto_detect_btn)
        lf.addRow(lat_lon_row)
        col.addWidget(lg)

        # ── Appearance ──
        ag = QGroupBox("Appearance")
        af = QFormLayout(ag)
        self.scheme = QComboBox()
        self.scheme.addItems(["System", "Breeze Light", "Breeze Dark"])
        self.scheme.setToolTip(
            "Override the colour scheme or follow the system KDE theme")
        self.scheme.currentIndexChanged.connect(self._on_scheme)
        
        # Autostart at login
        self.autostart = QCheckBox("Start automatically at login")
        self.autostart.toggled.connect(self._on_autostart)
        af.addRow(self.autostart)
        af.addRow("Color scheme:", self.scheme)
        col.addWidget(ag)

        col.addStretch()
        scroll.setWidget(body)

        # ── Save ──
        row = QHBoxLayout()
        row.addStretch()
        self.save_btn = QPushButton(
            QIcon.fromTheme("document-save"), "Save Settings")
        self.save_btn.setShortcut("Ctrl+S")
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.save_btn)
        outer.addLayout(row)

    # ── config I/O ------------------------------------------------------------
    def _load(self):
        try:
            c   = load_config(self._cfg)
            s   = c.get("scheduling", {})
            loc = c.get("location", {})
            self.interval.setValue(s.get("interval", 60))
            self.run_cycle.setChecked(s.get("run_cycle", True))
            self.daily_shuffle.setChecked(
                s.get("daily_shuffle_enabled", True))
            self.auto_start_scheduler.setChecked(
                s.get("auto_start_on_launch", False))
            self.timezone.setText(loc.get("timezone", "America/Phoenix"))
            self.lat.setValue(loc.get("latitude",  33.4484))
            self.lon.setValue(loc.get("longitude", -112.074))
            mode = c.get("application", {}).get("theme_mode", "system")
            idx  = {"system": 0, "light": 1, "dark": 2}.get(mode, 0)
            self.scheme.blockSignals(True)
            self.scheme.setCurrentIndex(idx)
            self.scheme.blockSignals(False)
            autostart = c.get("application", {}).get("autostart", False)
            self.autostart.setChecked(autostart)
        except Exception as e:
            logger.warning(f"Config load: {e}")

    def _save(self):
        try:
            c = load_config(self._cfg)
            c["scheduling"] = {
                "interval":              self.interval.value(),
                "run_cycle":             self.run_cycle.isChecked(),
                "daily_shuffle_enabled": self.daily_shuffle.isChecked(),
                "auto_start_on_launch":  self.auto_start_scheduler.isChecked(),
            }
            c["location"] = {
                "timezone":  self.timezone.text(),
                "latitude":  self.lat.value(),
                "longitude": self.lon.value(),
            }
            scheme_map = {0: "system", 1: "light", 2: "dark"}
            c.setdefault("application", {})["theme_mode"] = \
                scheme_map.get(self.scheme.currentIndex(), "system")
            c["application"].setdefault("autostart", self.autostart.isChecked())
            save_config(self._cfg, c)
            
            autostart_dir = Path.home() / ".config" / "autostart"
            autostart_file = autostart_dir / "org.kde.kwallpaper.desktop"
            if self.autostart.isChecked():
                autostart_dir.mkdir(parents=True, exist_ok=True)
                source_file = Path(__file__).parent / "autostart.desktop"
                if source_file.exists():
                    import shutil
                    shutil.copy2(str(source_file), str(autostart_file))
            else:
                if autostart_file.exists():
                    autostart_file.unlink()
            
            w = self.window()
            if isinstance(w, QMainWindow):
                w.statusBar().showMessage("Settings saved", 4000)
        except Exception as e:
            logger.error(f"Save failed: {e}")
            QMessageBox.warning(
                self, "Error", f"Could not save settings:\n{e}")

    def _on_scheme(self, idx: int):
        name = {0: "system", 1: "light", 2: "dark"}.get(idx, "system")
        apply_color_scheme(name)
        # Persist the preference immediately
        try:
            c = load_config(self._cfg)
            c.setdefault("application", {})["theme_mode"] = name
            save_config(self._cfg, c)
            # Refresh window and tray icons based on theme
            self.setWindowIcon(self._get_current_icon())
            self.tray.setIcon(self._get_current_icon())
        except Exception:
            pass

    def _on_autostart(self, enabled: bool):
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "org.kde.kwallpaper.desktop"
        
        if enabled:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            source_file = Path(__file__).parent / "autostart.desktop"
            if source_file.exists():
                import shutil
                shutil.copy2(str(source_file), str(autostart_file))
                logger.info("Autostart enabled")
        else:
            if autostart_file.exists():
                autostart_file.unlink()
                logger.info("Autostart disabled")

    def _on_auto_detect_location(self):
        """Auto-detect location from KDE system settings."""
        try:
            lat, lon, tz = self._get_system_location()
            self.lat.setValue(lat)
            self.lon.setValue(lon)
            self.timezone.setText(tz)
            w = self.window()
            if isinstance(w, QMainWindow):
                w.statusBar().showMessage(
                    f"Location detected: {lat:.4f}, {lon:.4f} ({tz})", 4000)
            logger.info(
                f"Auto-detected location: {lat:.4f}, {lon:.4f} ({tz})")
        except Exception as e:
            logger.warning(f"Auto-detect failed: {e}")
            QMessageBox.warning(
                self, "Auto-detect Failed",
                f"Could not detect location from KDE system settings:\n{e}")

    def _get_system_location(self):
        """
        Get current location from KDE system settings.
        Returns (latitude, longitude, timezone) tuple.
        Fallback: returns default Phoenix coordinates if not available.
        """
        # Try to read from KDE system config (localstorage.kcfg)
        # This is where Plasma stores location settings
        import subprocess
        import configparser
        
        # Check if plasma-apply-wallpaperimage is available (KDE indicator)
        try:
            result = subprocess.run(
                ["kreadconfig5", "--file", "plasma-org.kde.plasma.desktop-appletsrc",
                 "--group", "DataEngines", "--key", "geoclue2Enabled"],
                capture_output=True, text=True, timeout=5
            )
            geoclue_enabled = result.stdout.strip() == "true"
        except Exception:
            geoclue_enabled = False
        
        if not geoclue_enabled:
            # Fallback to default Phoenix coordinates
            return (33.4484, -112.074, "America/Phoenix")
        
        # Try to get location from Geoclue2 D-Bus
        try:
            import dbus
            bus = dbus.SessionBus()
            geoclue = bus.get_object(
                "org.freedesktop.Geoclue2",
                "/org/freedesktop/Geoclue2/Agents/org.kde.plasma.workspace"
            )
            current = geoclue.Get("org.freedesktop.Geoclue2.Agent", "Current",
                                   dbus_interface="org.freedesktop.DBus.Properties")
            # Current returns Dict{string,Variant}
            if isinstance(current, dict):
                lat = current.get("latitude", 33.4484)
                lon = current.get("longitude", -112.074)
                tz = current.get("timezone", "America/Phoenix")
                return (float(lat), float(lon), str(tz))
        except Exception:
            pass
        
        # If D-Bus fails, try to read from system config
        try:
            # KDE stores location in plasma-org.kde.plasma.desktop-appletsrc
            config = configparser.ConfigParser()
            config.read("~/.config/plasma-org.kde.plasma.desktop-appletsrc")
            if "DataEngines" in config and "geoclue2" in config["DataEngines"]:
                geoclue_cfg = config["DataEngines"]["geoclue2"]
                lat = float(geoclue_cfg.get("latitude", 33.4484))
                lon = float(geoclue_cfg.get("longitude", -112.074))
                tz = geoclue_cfg.get("timezone", "America/Phoenix")
                return (lat, lon, tz)
        except Exception:
            pass
        
        # Ultimate fallback: Phoenix coordinates
        return (33.4484, -112.074, "America/Phoenix")


# ─────────────────────────────────────────────────────────────────────────────

class SchedulerPage(QWidget):
    """Start / stop the background scheduler and view its event log."""

    state_changed = pyqtSignal(bool)        # True = running

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self._cfg = config_path
        # Ensure config directories exist before any operations
        from kwallpaper.wallpaper_changer import ensure_config_dirs
        ensure_config_dirs()
        self.scheduler: Optional[SchedulerManager] = None
        self._build()
        self._init_scheduler()

    def _build(self):
        col = QVBoxLayout(self)
        col.setSpacing(12)

        # ── Status ──
        sg = QGroupBox("Status")
        sv = QVBoxLayout(sg)
        self.status_lbl = QLabel("Stopped")
        f = self.status_lbl.font()
        f.setPointSize(f.pointSize() + 2)
        # Status text should not be bold
        self.status_lbl.setFont(f)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sv.addWidget(self.status_lbl)
        col.addWidget(sg)

        # ── Controls ──
        row = QHBoxLayout()
        self.start_btn = QPushButton(
            QIcon.fromTheme("media-playback-start"), "Start")
        self.start_btn.clicked.connect(self.start)
        row.addWidget(self.start_btn)
        self.stop_btn = QPushButton(
            QIcon.fromTheme("media-playback-stop"), "Stop")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        row.addWidget(self.stop_btn)
        row.addStretch()
        col.addLayout(row)

        # ── Event Log ──
        lg = QGroupBox("Event Log")
        lv = QVBoxLayout(lg)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        mono = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(max(mono.pointSize(), 9))
        self.log.setFont(mono)
        self.log.setMinimumHeight(180)
        lv.addWidget(self.log)
        col.addWidget(lg, 1)

    def _init_scheduler(self):
        try:
            self.scheduler = create_scheduler(self._cfg)
            # Wire scheduler task results into the GUI event log
            self.scheduler.log_callback = self._append
        except Exception as e:
            logger.error(f"Scheduler init: {e}")
            self._append(f"Init error: {e}")

    # ── helpers ---------------------------------------------------------------
    def _append(self, msg: str):
        ts = datetime.now().strftime("%I:%M:%S %p")
        self.log.append(f"[{ts}]  {msg}")

    def is_running(self) -> bool:
        return (self.scheduler is not None
                and self.scheduler.is_running())

    # ── public slots ----------------------------------------------------------
    def start(self):
        if self.scheduler is None:
            self._append("Scheduler not initialised")
            return
        if self.is_running():
            self._append("Already running")
            return
        if self.scheduler.start():
            self.status_lbl.setText("Running")
            p = self.status_lbl.palette()
            p.setColor(
                QPalette.ColorRole.WindowText,
                self.palette().color(QPalette.ColorRole.Highlight))
            self.status_lbl.setPalette(p)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            interval = self.scheduler.get_status().get(
                "tasks", {}).get("cycle", {}).get("interval", 60)
            self._append(f"Started  (cycle every {interval}s)")
            self.state_changed.emit(True)
        else:
            self._append("Start failed")

    def stop(self):
        if not self.is_running():
            self._append("Not running")
            return
        if self.scheduler.stop():
            self.status_lbl.setText("Stopped")
            # Reset label palette to default
            self.status_lbl.setPalette(self.palette())
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self._append("Stopped")
            self.state_changed.emit(False)
        else:
            self._append("Stop failed")


# ═════════════════════════════════════════════════════════════════════════════
#  Main Window
# ═════════════════════════════════════════════════════════════════════════════

class WallpaperChangerWindow(QMainWindow):
    """Top-level window with native KDE Plasma integration."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        global _main_window
        _main_window = self
        self._cfg = config_path or str(DEFAULT_CONFIG_PATH)
        self._qs  = QSettings(ORG_NAME, APP_NAME)
        
        # Ensure config directories exist before any operations
        from kwallpaper.wallpaper_changer import ensure_config_dirs
        ensure_config_dirs()

        self._build_ui()
        self._build_tray()
        self._start_ipc()
        self._restore_state()
        self._apply_saved_scheme()
        self._maybe_start_scheduler()

    # ── UI construction -------------------------------------------------------

    def _get_current_icon(self) -> QIcon:
        """Get the icon corresponding to the current theme mode."""
        try:
            c = load_config(self._cfg)
            mode = c.get("application", {}).get("theme_mode", "system")
            return get_icon_for_theme(mode)
        except Exception:
            return get_icon_for_theme("system")
    
    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(get_icon_for_theme("system"))
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)

        # Menu bar
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        act = fm.addAction(
            QIcon.fromTheme("document-import"), "&Import Theme…")
        act.setShortcut("Ctrl+I")
        act.triggered.connect(lambda: self.themes._import())
        fm.addSeparator()
        act = fm.addAction(
            QIcon.fromTheme("application-exit"), "&Quit")
        act.setShortcut("Ctrl+Q")
        act.triggered.connect(self._quit)

        sm = mb.addMenu("&Scheduler")
        self._act_start = sm.addAction(
            QIcon.fromTheme("media-playback-start"), "&Start")
        self._act_start.triggered.connect(
            lambda: self.sched.start())
        self._act_stop = sm.addAction(
            QIcon.fromTheme("media-playback-stop"), "S&top")
        self._act_stop.setEnabled(False)
        self._act_stop.triggered.connect(
            lambda: self.sched.stop())

        hm = mb.addMenu("&Help")
        hm.addAction(
            QIcon.fromTheme("help-about"), "&About…"
        ).triggered.connect(self._about)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.themes = ThemesPage(self._cfg)
        self.tabs.addTab(
            self.themes,
            QIcon.fromTheme("preferences-desktop-wallpaper"),
            "Themes")

        self.settings = SettingsPage(self._cfg)
        self.tabs.addTab(
            self.settings,
            QIcon.fromTheme("configure"),
            "Settings")

        self.sched = SchedulerPage(self._cfg)
        self.tabs.addTab(
            self.sched,
            QIcon.fromTheme("chronometer"),
            "Scheduler")

        self.tabs.currentChanged.connect(self._on_tab)
        self.sched.state_changed.connect(self._on_sched_state)
        self.sched.state_changed.connect(self.themes._update_delete_button_state)

        # Initial data load
        self.themes.load_themes()
        if self.tabs.currentWidget() is self.themes:
            self.themes.set_tab_visible(True)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self._get_current_icon(), self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self._on_tray)
        self._refresh_tray()
        self.tray.setVisible(True)

    def _refresh_tray(self):
        m = QMenu()
        running = self.sched.is_running()
        st = m.addAction(
            f"Scheduler: {'Running' if running else 'Stopped'}")
        st.setEnabled(False)
        m.addSeparator()
        if running:
            m.addAction(
                QIcon.fromTheme("media-playback-stop"),
                "Stop Scheduler"
            ).triggered.connect(self.sched.stop)
        else:
            m.addAction(
                QIcon.fromTheme("media-playback-start"),
                "Start Scheduler"
            ).triggered.connect(self.sched.start)
        m.addSeparator()
        m.addAction(
            QIcon.fromTheme("window-new"), "Show"
        ).triggered.connect(self._raise)
        m.addAction(
            QIcon.fromTheme("application-exit"), "Quit"
        ).triggered.connect(self._quit)
        self.tray.setContextMenu(m)

    # ── slots -----------------------------------------------------------------

    def _on_tab(self, idx):
        self.themes.set_tab_visible(
            self.tabs.widget(idx) is self.themes)

    def _on_sched_state(self, running: bool):
        self._act_start.setEnabled(not running)
        self._act_stop.setEnabled(running)
        self._refresh_tray()
        self.tray.setToolTip(
            f"{APP_NAME} — "
            f"{'Running' if running else 'Stopped'}")

    def _on_tray(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.hide() if self.isVisible() else self._raise()

    def _raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>Dynamic wallpaper manager for KDE Plasma.<br>"
            f"Changes wallpapers based on time of day using "
            f"sunrise / sunset calculations.</p>")

    # ── single-instance IPC ---------------------------------------------------

    def _start_ipc(self):
        self._ipc_timer = QTimer(self)
        self._ipc_timer.timeout.connect(self._poll_ipc)
        self._ipc_timer.start(250)

    def _poll_ipc(self):
        if _instance_lock is None:
            return
        try:
            conn, _ = _instance_lock.accept()
            if conn.recv(64) == b"SHOW":
                self._raise()
            conn.close()
        except BlockingIOError:
            pass
        except Exception:
            pass

    # ── window state persistence ----------------------------------------------

    def _restore_state(self):
        g = self._qs.value("geometry")
        if g:
            self.restoreGeometry(g)
        s = self._qs.value("windowState")
        if s:
            self.restoreState(s)

    def _persist_state(self):
        self._qs.setValue("geometry",    self.saveGeometry())
        self._qs.setValue("windowState", self.saveState())

    def _apply_saved_scheme(self):
        """Read the saved colour scheme from config and apply it."""
        try:
            c    = load_config(self._cfg)
            mode = c.get("application", {}).get(
                "theme_mode", "system")
            apply_color_scheme(mode)
            idx = {"system": 0, "light": 1, "dark": 2}.get(mode, 0)
            self.settings.scheme.blockSignals(True)
            self.settings.scheme.setCurrentIndex(idx)
            self.settings.scheme.blockSignals(False)
            # Refresh window and tray icons based on theme
            self.setWindowIcon(self._get_current_icon())
            self.tray.setIcon(self._get_current_icon())
        except Exception:
            pass

    # ── lifecycle -------------------------------------------------------------

    def closeEvent(self, event):
        self._persist_state()
        if self.tray.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self._cleanup()
            event.accept()

    def showEvent(self, event):
        """Start preview when window is shown."""
        super().showEvent(event)
        if self.tabs.currentWidget() is self.themes:
            self.themes.preview.start()

    def hideEvent(self, event):
        """Stop preview when window is hidden."""
        super().hideEvent(event)
        if self.tabs.currentWidget() is self.themes:
            self.themes.preview.stop()

    def _quit(self):
        self._persist_state()
        self._cleanup()
        QApplication.quit()

    def _cleanup(self):
        if self.sched.is_running():
            self.sched.scheduler.stop(wait=True)

    def _maybe_start_scheduler(self):
        """Auto-start scheduler if enabled in config."""
        try:
            config = load_config(self._cfg)
            auto_start = config.get('scheduling', {}).get(
                'auto_start_on_launch', False)
            run_cycle = config.get('scheduling', {}).get('run_cycle', True)
            if auto_start and run_cycle:
                logger.info("Auto-starting scheduler on launch")
                # Small delay to ensure UI is fully loaded
                QTimer.singleShot(1000, self.sched.start)
        except Exception as e:
            logger.warning(f"Auto-start check failed: {e}")

    def windowEvent(self, event):
        """Handle window state changes to stop preview when minimized."""
        if event.type() == QEvent.Type.WindowStateChange:
            if event.newState() & Qt.WindowState.WindowMinimized:
                if self.tabs.currentWidget() is self.themes:
                    self.themes.preview.stop()
            else:
                if self.tabs.currentWidget() is self.themes:
                    self.themes.preview.start()
        return super().windowEvent(event)


# ═════════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    if not PYQT6_AVAILABLE:
        print("Error: PyQt6 is required.  pip install PyQt6")
        sys.exit(1)

    import argparse
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--config", default=None,
                    help="Path to config file")
    args = ap.parse_args()

    global _system_palette

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setDesktopFileName("org.kde.kwallpaper")
    app.setWindowIcon(
        QIcon.fromTheme("preferences-desktop-wallpaper"))
    app.setQuitOnLastWindowClosed(False)

    # Snapshot the system palette before any overrides
    _system_palette = QPalette(app.palette())

    if not _acquire_lock():
        _signal_running_instance()
        sys.exit(0)

    win = WallpaperChangerWindow(config_path=args.config)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

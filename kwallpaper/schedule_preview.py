#!/usr/bin/env python3
"""
kWallpaper schedule preview widget (Phase 3).

A 24-hour timeline bar showing which image of the selected theme
displays when (sun-position model), with a current-time marker.

All computation runs off the GUI thread via QThreadPool workers,
matching the main window's existing worker pattern (QRunnable worker +
QObject signal emitter + version-token cancellation).  Thumbnails reuse
the shared adaptive thumbnail cache (ensure_thumbnail) at a small size,
so a theme already previewed in the cross-fade widget costs no decode.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import (
    QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from kwallpaper.image_schedule import ThemeSchedule, schedule_for_config
from kwallpaper.themes import ensure_thumbnail

logger = logging.getLogger(__name__)

BAR_HEIGHT = 56
THUMB_PX = 26
TICK_MS = 60_000      # marker refresh + date-change check
POOL_THREADS = 4

# Segment band colours (translucent — visible on light and dark themes).
BAND_COLORS = {
    "night":   QColor(0x55, 0x66, 0x88, 0x66),
    "sunrise": QColor(0xF5, 0xC2, 0x6B, 0x66),
    "day":     QColor(0x7E, 0xC8, 0xF0, 0x55),
    "sunset":  QColor(0xF0, 0x95, 0x5A, 0x66),
}


class _PreviewToken:
    """Monotonic generation counter used to cancel superseded loads
    (same pattern as wallpaper_gui._LoadToken)."""

    __slots__ = ("version",)

    def __init__(self):
        self.version = 0


class _ScheduleSignals(QObject):
    """Signal bridge for the schedule workers (lives on the GUI thread).

    Every signal carries the token version captured when the worker
    started, so the slot can drop superseded results.
    """
    schedule_ready = pyqtSignal(object, int)   # (ThemeSchedule, version)
    schedule_failed = pyqtSignal(str, int)     # (message, version)
    thumbs_ready = pyqtSignal(dict, int)       # ({src: thumb}, version)


class ScheduleComputeWorker(QRunnable):
    """Compute a theme's day schedule off the GUI thread."""

    def __init__(self, config_path: str, theme_dir: str,
                 sig: _ScheduleSignals, token: _PreviewToken):
        super().__init__()
        self.setAutoDelete(True)
        self._config_path = config_path
        self._theme_dir = theme_dir
        self._sig = sig
        self._token = token

    def run(self):
        v = self._token.version
        try:
            sch = schedule_for_config(self._config_path,
                                      Path(self._theme_dir))
        except Exception as e:
            logger.warning(f"Schedule compute failed: {e}")
            if self._token.version == v:
                self._sig.schedule_failed.emit(str(e), v)
            return
        if self._token.version == v:
            self._sig.schedule_ready.emit(sch, v)


class _ThumbsWorker(QRunnable):
    """Generate small thumbnails for all schedule entries off the GUI
    thread (one worker, sequential — at most 16 small decodes, and the
    shared cache makes them cheap when the cross-fade preview already
    ran)."""

    def __init__(self, paths: List[str], sig: _ScheduleSignals,
                 token: _PreviewToken):
        super().__init__()
        self.setAutoDelete(True)
        self._paths = list(dict.fromkeys(paths))  # dedup, keep order
        self._sig = sig
        self._token = token

    def run(self):
        v = self._token.version
        out = {}
        for p in self._paths:
            if self._token.version != v:
                return  # superseded; drop the whole batch
            try:
                out[p] = ensure_thumbnail(p, thumb_size=96,
                                          token=self._token)
            except Exception as e:
                logger.debug(f"Thumbnail failed for {p}: {e}")
        if self._token.version == v:
            self._sig.thumbs_ready.emit(out, v)


class _BarArea(QWidget):
    """The painted 24-hour timeline (bands, ticks, thumbnails, marker)."""

    def __init__(self, owner: "SchedulePreviewWidget"):
        super().__init__(owner)
        self._owner = owner

    def _x_for(self, dt: datetime) -> int:
        """Pixel x for an aware datetime within the schedule day.

        Uses the actual wall-clock span of the day (23/25 h on DST
        days), so positions stay correct across DST transitions.
        """
        sch = self._owner._schedule
        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        span = (day_start + timedelta(days=1) - day_start).total_seconds()
        return int((dt - day_start).total_seconds() / span * self.width())

    def mouseMoveEvent(self, event):
        self._owner._show_entry_at(event.position().x())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._owner._reset_title()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))

        state = self._owner._state
        if state in ("empty", "loading", "legacy", "error"):
            msg = {
                "empty": "Select a theme to see its schedule",
                "loading": "Computing schedule…",
                "legacy": ("Schedule preview is available in the "
                           "Sun-position model (Settings → Time model)"),
                "error": "Schedule unavailable",
            }[state]
            p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
            f = p.font()
            f.setPointSize(max(f.pointSize(), 8))
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            p.end()
            return

        sch = self._owner._schedule
        if sch is None:
            p.end()
            return

        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        day_end = day_start + timedelta(days=1)

        # Segment bands (from today's segments)
        seg = sch.segments
        if seg is not None and seg.complete:
            def band(s, e, color):
                x1, x2 = self._x_for(s), self._x_for(e)
                if x2 > x1:
                    p.fillRect(x1, 0, x2 - x1, h, color)
            band(day_start, seg.dawn, BAND_COLORS["night"])
            band(seg.dawn, seg.golden_hour_end, BAND_COLORS["sunrise"])
            band(seg.golden_hour_end, seg.golden_hour, BAND_COLORS["day"])
            band(seg.golden_hour, seg.dusk, BAND_COLORS["sunset"])
            band(seg.dusk, day_end, BAND_COLORS["night"])

        # Hour ticks + labels (every 3 h)
        p.setPen(QPen(pal.color(QPalette.ColorRole.Mid), 1))
        f = QFont()
        f.setPointSize(max(f.pointSize(), 7))
        p.setFont(f)
        for hour in range(0, 25, 3):
            x = self._x_for(day_start + timedelta(hours=hour))
            p.drawLine(x, h - 8, x, h)
            if hour < 24:
                p.drawText(x + 2, h - 2, f"{hour:02d}")

        # Thumbnails at each entry's start
        for e in sch.entries:
            x = self._x_for(e.start)
            y = (h - THUMB_PX) // 2
            pm = self._owner._pixmaps.get(e.path)
            if pm is not None:
                scaled = pm.scaled(
                    THUMB_PX, THUMB_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(x - THUMB_PX // 2, y, scaled)
            else:
                p.setPen(QPen(pal.color(QPalette.ColorRole.Mid), 1))
                p.drawRect(x - THUMB_PX // 2, y, THUMB_PX, THUMB_PX)

        # Current-time marker
        if self._owner._now is not None:
            mx = self._x_for(self._owner._now)
            p.setPen(QPen(pal.color(QPalette.ColorRole.Highlight), 2))
            p.drawLine(mx, 0, mx, h)
            p.setPen(pal.color(QPalette.ColorRole.Highlight))
            label = self._owner._now.strftime("%H:%M")
            lx = mx + 3 if mx < w - 44 else mx - 41
            p.drawText(lx, 12, label)
        p.end()


class SchedulePreviewWidget(QWidget):
    """24-hour schedule timeline for the selected theme (sun model).

    States: "empty" (no theme), "loading", "ready" (timeline),
    "legacy" (model notice), "error".  ``refresh()`` recomputes in a
    worker; ``refresh_now()`` only moves the marker.  A 60 s timer
    refreshes the marker and recomputes when the calendar date changes
    in the configured timezone.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(POOL_THREADS)
        self._sig = _ScheduleSignals(self)
        self._sig.schedule_ready.connect(self._on_schedule_ready)
        self._sig.schedule_failed.connect(self._on_schedule_failed)
        self._sig.thumbs_ready.connect(self._on_thumbs_ready)

        self._token = _PreviewToken()
        self._state = "empty"
        self._schedule: Optional[ThemeSchedule] = None
        self._now: Optional[datetime] = None
        self._pixmaps: Dict[str, QPixmap] = {}
        self._config_path: Optional[str] = None
        self._theme_dir: Optional[str] = None

        self.setFixedHeight(BAR_HEIGHT + 22)
        self.setMinimumWidth(400)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._title = QLabel("Schedule preview")
        f = self._title.font()
        f.setPointSize(max(f.pointSize(), 9))
        self._title.setFont(f)
        lay.addWidget(self._title)
        self._bar = _BarArea(self)
        self._bar.setFixedHeight(BAR_HEIGHT)
        lay.addWidget(self._bar)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    # ── public API ────────────────────────────────────────────────────────
    def refresh(self, config_path: str, theme_dir: str):
        """(Re)compute the schedule for this theme in a worker."""
        self._config_path = config_path
        self._theme_dir = theme_dir
        self._bump()
        self._state = "loading"
        self._schedule = None
        self._now = None
        self._pixmaps.clear()
        self._reset_title()
        self._bar.update()
        self._pool.start(ScheduleComputeWorker(
            config_path, theme_dir, self._sig, self._token))

    def refresh_now(self):
        """Move the current-time marker (no recompute)."""
        if self._schedule is None:
            return
        self._now = datetime.now(self._schedule.tz)
        self._bar.update()

    def clear(self):
        """No theme selected."""
        self._bump()
        self._state = "empty"
        self._schedule = None
        self._now = None
        self._pixmaps.clear()
        self._config_path = None
        self._theme_dir = None
        self._bar.update()

    # ── internals ─────────────────────────────────────────────────────────
    def _bump(self):
        self._token.version += 1

    def _on_tick(self):
        sch = self._schedule
        if sch is None:
            return
        now = datetime.now(sch.tz)
        if now.date() != sch.date:
            # Calendar date changed (midnight, or DST day): recompute.
            if self._config_path and self._theme_dir:
                self.refresh(self._config_path, self._theme_dir)
            return
        self._now = now
        self._bar.update()

    def _on_schedule_ready(self, sch: ThemeSchedule, v: int):
        if v != self._token.version:
            return  # superseded
        self._schedule = sch
        self._now = sch.now
        if sch.model != "sun":
            self._state = "legacy"
            self._bar.update()
            return
        self._state = "ready"
        paths = [e.path for e in sch.entries if e.path]
        if paths:
            self._pool.start(_ThumbsWorker(paths, self._sig, self._token))
        self._bar.update()

    def _on_schedule_failed(self, msg: str, v: int):
        if v != self._token.version:
            return
        self._state = "error"
        self._schedule = None
        self._bar.setToolTip(msg)
        self._bar.update()

    def _on_thumbs_ready(self, thumbs: dict, v: int):
        if v != self._token.version:
            return
        for src, thumb in thumbs.items():
            pm = QPixmap(thumb)
            if not pm.isNull():
                self._pixmaps[src] = pm
        self._bar.update()

    def _show_entry_at(self, x: int):
        """Hover feedback: show the entry under the cursor in the title."""
        sch = self._schedule
        if sch is None or self._state != "ready":
            return
        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        span = (day_start + timedelta(days=1) - day_start).total_seconds()
        t = day_start + timedelta(
            seconds=x / max(self._bar.width(), 1) * span)
        for e in sch.entries:
            if e.start <= t < e.end:
                self._title.setText(
                    f"{e.start:%H:%M}–{e.end:%H:%M}  ·  image {e.image}"
                    + (f"  ·  {Path(e.path).name}" if e.path else ""))
                return

    def _reset_title(self):
        if self._state == "ready":
            self._title.setText("Schedule preview")

    def _cleanup(self):
        """Drain the pool (called from the main window on exit)."""
        self._bump()
        self._timer.stop()
        self._pool.clear()
        self._pool.waitForDone(1000)

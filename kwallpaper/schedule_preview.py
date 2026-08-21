#!/usr/bin/env python3
"""
kWallpaper schedule preview widget (Phase 3, Breeze-timeline restyle).

A 24-hour timeline showing which image of the selected theme displays
when (sun-position model).  Styled to blend with the application's
current KDE palette — no hardcoded theme colours except the four
semantic segment tints (night/sunrise/day/sunset), which are subtle
low-alpha fills that read on both light and dark Base:

  ┌──────────────────────────────────────────────────────────┐
  │ Schedule                     ■ Night ■ Sunrise ■ Day ■ S │
  │  00    03    06    09    12    15    18    21            │
  │  ┌───────┐ ┌────────────────────┐ ┌─────┐   ║ 14:03     │
  │  │▣ 00:00│ │▣ 06:27–08:52       │ │ ▣   │   ║           │
  │  └───────┘ └────────────────────┘ └─────┘   ║           │
  │ Now: 16:09–18:35 · image 9 · 24hr-Miami-1_9.jpeg         │
  └──────────────────────────────────────────────────────────┘

Header (title + segment legend), hour ruler (minor ticks hourly,
major every 3 h), image-window segments (rounded, tinted, with
thumbnail + time range), a slider-handle current-time marker
(line + dot + time chip), and a footer line showing the current
(or hovered) window.

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
    QObject, QRunnable, QRectF, Qt, QThreadPool, QTimer, QPointF,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from kwallpaper.image_schedule import ThemeSchedule, schedule_for_config
from kwallpaper.themes import ensure_thumbnail

logger = logging.getLogger(__name__)

# Geometry (px)
HEAD_H = 22
RULER_H = 16
RULER_GAP = 4
STRIP_H = 40
BAR_H = RULER_H + RULER_GAP + STRIP_H      # 60
FOOT_H = 20
MARGIN_X = 8
MARGIN_Y = 6
SPACING = 3
WIDGET_H = MARGIN_Y * 2 + HEAD_H + SPACING + BAR_H + SPACING + FOOT_H  # 120

THUMB_PX = 28
TICK_MS = 60_000      # marker refresh + date-change check
POOL_THREADS = 4

SEG_NAMES = ("night", "sunrise", "day", "sunset")
SEG_LABELS = {"night": "Night", "sunrise": "Sunrise",
              "day": "Day", "sunset": "Sunset"}
# (fill, border) — subtle tints that read on both light and dark Base.
SEG_COLORS = {
    "night":   (QColor(0x55, 0x66, 0x88, 0x22),
                QColor(0x55, 0x66, 0x88, 0x59)),
    "sunrise": (QColor(0xF5, 0xC2, 0x6B, 0x2B),
                QColor(0xF5, 0xC2, 0x6B, 0x66)),
    "day":     (QColor(0x7E, 0xC8, 0xF0, 0x22),
                QColor(0x7E, 0xC8, 0xF0, 0x59)),
    "sunset":  (QColor(0xF0, 0x95, 0x5A, 0x2B),
                QColor(0xF0, 0x95, 0x5A, 0x66)),
}


def segment_type_for(start: datetime, seg) -> str:
    """Map a schedule entry's start time to its segment type.

    "night" outside [dawn, dusk), "sunrise" in the morning golden
    window, "day" between the golden windows, "sunset" in the evening
    golden window.  Returns "day" (neutral) when segments are
    unavailable.
    """
    if seg is None or not seg.complete:
        return "day"
    if start < seg.dawn or start >= seg.dusk:
        return "night"
    if start < seg.golden_hour_end:
        return "sunrise"
    if start < seg.golden_hour:
        return "day"
    return "sunset"


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


class _LegendArea(QWidget):
    """Right-aligned segment legend (swatch + label × 4)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(HEAD_H)
        self.setFixedWidth(236)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        f = QFont()
        f.setPointSize(max(f.pointSize(), 8))
        p.setFont(f)
        fm = QFontMetrics(f)
        items = [(SEG_COLORS[s][0], SEG_COLORS[s][1], SEG_LABELS[s])
                 for s in SEG_NAMES]
        sw, gap, pad = 10, 5, 12
        widths = [sw + gap + fm.horizontalAdvance(label) for _, _, label
                  in items]
        total = sum(widths) + pad * (len(items) - 1)
        x = self.width() - total
        y = (self.height() - sw) // 2
        for (fill, border, _label), wdt in zip(items, widths):
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, sw, sw), 2, 2)
            p.fillPath(path, fill)
            p.setPen(QPen(border, 1))
            p.drawPath(path)
            x += sw + gap
            p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
            p.drawText(int(x), y + sw - 2, _label)
            x += wdt - sw - gap + pad
        p.end()


class _BarArea(QWidget):
    """The painted 24-hour timeline: hour ruler, image-window segments,
    and the current-time marker."""

    def __init__(self, owner: "SchedulePreviewWidget"):
        super().__init__(owner)
        self._owner = owner
        self.setFixedHeight(BAR_H)
        self.setAutoFillBackground(False)

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

    def _entry_at(self, x: int):
        """The schedule entry whose window contains pixel x (or None)."""
        sch = self._owner._schedule
        if sch is None:
            return None
        day_start = datetime(sch.date.year, sch.date.month, sch.date.day,
                             tzinfo=sch.tz)
        span = (day_start + timedelta(days=1) - day_start).total_seconds()
        t = day_start + timedelta(seconds=x / max(self.width(), 1) * span)
        for e in sch.entries:
            if e.start <= t < e.end:
                return e
        return None

    def mouseMoveEvent(self, event):
        self._owner._show_entry_at(event.position().x())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._owner._reset_footer()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pal = self.palette()
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
            f.setPointSize(max(f.pointSize(), 9))
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

        mid_light = pal.color(QPalette.ColorRole.Midlight)
        mid = pal.color(QPalette.ColorRole.Mid)

        # ── hour ruler ──────────────────────────────────────────────────
        p.setPen(QPen(mid_light, 1))
        p.drawLine(0, RULER_H - 1, w, RULER_H - 1)
        f = QFont()
        f.setPointSize(max(f.pointSize(), 8))
        p.setFont(f)
        for hour in range(0, 25):
            x = self._x_for(day_start + timedelta(hours=hour))
            major = hour % 3 == 0
            p.setPen(QPen(mid if major else mid_light, 1))
            p.drawLine(x, RULER_H - 1 - (7 if major else 4), x, RULER_H - 1)
            if major and hour < 24:
                p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
                p.drawText(x + 3, RULER_H - 2, f"{hour:02d}")

        # ── image-window segments ───────────────────────────────────────
        strip_y = RULER_H + RULER_GAP
        seg = sch.segments
        for e in sch.entries:
            x1 = self._x_for(e.start)
            x2 = self._x_for(e.end)
            if x2 - x1 < 3:
                continue
            r = QRectF(x1 + 1, strip_y, x2 - x1 - 3, STRIP_H)
            t = segment_type_for(e.start, seg)
            fill, border = SEG_COLORS[t]
            path = QPainterPath()
            path.addRoundedRect(r, 3, 3)
            if seg is not None and seg.complete:
                p.fillPath(path, fill)
            p.setPen(QPen(border, 1))
            p.drawPath(path)

            tx = x1 + 1 + 5
            ty = strip_y + (STRIP_H - THUMB_PX) // 2
            if r.width() > THUMB_PX + 12:
                pm = self._owner._pixmaps.get(e.path)
                if pm is not None:
                    scaled = pm.scaled(
                        THUMB_PX, THUMB_PX,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    tp = QPainterPath()
                    tp.addRoundedRect(QRectF(tx, ty, THUMB_PX, THUMB_PX),
                                      3, 3)
                    p.save()
                    p.setClipPath(tp)
                    p.drawPixmap(tx, ty, scaled)
                    p.restore()
                    p.setPen(QPen(QColor(0, 0, 0, 64), 1))
                    p.drawPath(tp)
                else:
                    p.setPen(QPen(mid, 1))
                    p.drawRoundedRect(QRectF(tx, ty, THUMB_PX, THUMB_PX),
                                      3, 3)
                # time range (only when there is room)
                if r.width() > THUMB_PX + 12 + 64:
                    p.setPen(pal.color(QPalette.ColorRole.WindowText))
                    tf = QFont()
                    tf.setPointSize(max(tf.pointSize(), 9))
                    p.setFont(tf)
                    text_r = QRectF(tx + THUMB_PX + 6, strip_y,
                                    r.width() - (tx - r.x()) - THUMB_PX - 12,
                                    STRIP_H)
                    p.drawText(text_r,
                               Qt.AlignmentFlag.AlignVCenter
                               | Qt.AlignmentFlag.AlignLeft,
                               f"{e.start:%H:%M}–{e.end:%H:%M}")

        # ── current-time marker (slider-handle style) ───────────────────
        if self._owner._now is not None:
            mx = self._x_for(self._owner._now)
            hl = pal.color(QPalette.ColorRole.Highlight)
            p.setPen(QPen(hl, 2))
            p.drawLine(mx, 0, mx, h)
            p.setPen(QPen(pal.color(QPalette.ColorRole.Base), 2))
            p.setBrush(hl)
            p.drawEllipse(QPointF(mx, 6), 4, 4)
            label = self._owner._now.strftime("%H:%M")
            cf = QFont()
            cf.setPointSize(max(cf.pointSize(), 8))
            cf.setBold(True)
            p.setFont(cf)
            tw = QFontMetrics(cf).horizontalAdvance(label) + 10
            cx = mx + 7 if mx + 7 + tw < w else mx - 7 - tw
            chip = QRectF(cx, 1, tw, 15)
            cp = QPainterPath()
            cp.addRoundedRect(chip, 3, 3)
            p.fillPath(cp, hl)
            p.setPen(pal.color(QPalette.ColorRole.HighlightedText))
            p.drawText(chip, Qt.AlignmentFlag.AlignCenter, label)
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

        self.setFixedHeight(WIDGET_H)
        self.setMinimumWidth(400)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(MARGIN_X, MARGIN_Y, MARGIN_X, MARGIN_Y)
        lay.setSpacing(SPACING)

        # Header: title + legend
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._title = QLabel("Schedule")
        f = self._title.font()
        f.setPointSize(max(f.pointSize(), 9))
        f.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(f)
        head.addWidget(self._title)
        head.addStretch(1)
        self._legend = _LegendArea(self)
        head.addWidget(self._legend)
        lay.addLayout(head)

        self._bar = _BarArea(self)
        lay.addWidget(self._bar)

        # Footer: current / hovered window
        self._foot = QLabel("")
        ff = self._foot.font()
        ff.setPointSize(max(ff.pointSize(), 8))
        self._foot.setFont(ff)
        fpal = self._foot.palette()
        fpal.setColor(QPalette.ColorRole.WindowText,
                      fpal.color(QPalette.ColorRole.PlaceholderText))
        self._foot.setPalette(fpal)
        lay.addWidget(self._foot)

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
        self._foot.setText("")
        self._bar.update()
        self._pool.start(ScheduleComputeWorker(
            config_path, theme_dir, self._sig, self._token))

    def refresh_now(self):
        """Move the current-time marker (no recompute)."""
        if self._schedule is None:
            return
        self._now = datetime.now(self._schedule.tz)
        self._update_footer()
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
        self._foot.setText("")
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
        self._update_footer()
        self._bar.update()

    def _on_schedule_ready(self, sch: ThemeSchedule, v: int):
        if v != self._token.version:
            return  # superseded
        self._schedule = sch
        self._now = sch.now
        if sch.model != "sun":
            self._state = "legacy"
            self._foot.setText("")
            self._bar.update()
            return
        self._state = "ready"
        paths = [e.path for e in sch.entries if e.path]
        if paths:
            self._pool.start(_ThumbsWorker(paths, self._sig, self._token))
        self._update_footer()
        self._bar.update()

    def _on_schedule_failed(self, msg: str, v: int):
        if v != self._token.version:
            return  # superseded
        self._state = "error"
        self._schedule = None
        self._foot.setText("")
        self._bar.setToolTip(msg)
        self._bar.update()

    def _on_thumbs_ready(self, thumbs: dict, v: int):
        if v != self._token.version:
            return  # superseded
        # Scale down before caching: the shared thumbnail cache may hold
        # multi-megapixel entries (the crossfade preview writes up to 4K),
        # but this widget only draws THUMB_PX squares.  Caching the full
        # decode would pin ~20MB per image for a 28px display.
        cache_px = THUMB_PX * 4  # 4x headroom for HiDPI + smooth downscale
        for src, thumb in thumbs.items():
            pm = QPixmap(thumb)
            if pm.isNull():
                continue
            if max(pm.width(), pm.height()) > cache_px:
                pm = pm.scaled(cache_px, cache_px,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            self._pixmaps[src] = pm
        self._bar.update()

    def _entry_text(self, e) -> str:
        return (f"{e.start:%H:%M}–{e.end:%H:%M}  ·  image {e.image}"
                + (f"  ·  {Path(e.path).name}" if e.path else ""))

    def _update_footer(self):
        """Footer shows the window containing the current time."""
        if self._state != "ready" or self._schedule is None:
            self._foot.setText("")
            return
        e = self._bar._entry_at(self._bar._x_for(self._now)) \
            if self._now is not None else None
        if e is not None:
            self._foot.setText(f"Now: {self._entry_text(e)}")
        else:
            self._foot.setText("")

    def _show_entry_at(self, x: int):
        """Hover feedback: show the entry under the cursor."""
        if self._state != "ready":
            return
        e = self._bar._entry_at(x)
        if e is not None:
            self._foot.setText(self._entry_text(e))
            self._bar.setToolTip(self._entry_text(e))
        else:
            self._reset_footer()

    def _reset_footer(self):
        self._bar.setToolTip("")
        self._update_footer()

    def _cleanup(self):
        """Drain the pool (called from the main window on exit)."""
        self._bump()
        self._timer.stop()
        self._pool.clear()
        self._pool.waitForDone(1000)

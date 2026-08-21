"""Memory-footprint tests for ImageCrossFadeWidget.

Pins the four trims that keep the preview's decoded-pixmap use small:

1. ``_scaled`` holds only the keep set (current + fade target), not one
   widget-sized pixmap per image.
2. The raw-pixmap byte budget is 48MB — eviction is safe because
   ``_scaled_for`` re-requests evicted images and the slideshow requests
   each image 2.7s ahead of display (a decode takes ~100ms).
3. Hiding the widget frees both pixmap caches (and pauses the timer);
   showing it re-populates them from the fast disk thumbnail cache.
4. No oversampling headroom: thumb long-edge == physical widget
   long-edge (960px floor), so decoded pixmaps are as small as the
   display needs.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

import wallpaper_gui


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_jpeg(path, w: int, h: int, color: int):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(color)
    assert img.save(str(path), "JPG", 80)


def _spin(qapp, seconds: float):
    loop = QEventLoop()
    QTimer.singleShot(max(1, int(seconds * 1000)), loop.quit)
    loop.exec()


def _wait_until(qapp, cond, timeout: float = 30.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        _spin(qapp, 0.2)
    return cond()


def _current_shown(w) -> bool:
    with w._state_lock:
        n = len(w._images)
        idx = w._idx if n else 0
        return w._scaled.get(idx) is not None


@pytest.fixture()
def widget(qapp, tmp_path, monkeypatch):
    """Crossfade preview with 16 synthetic 2000x1125 images, shown and
    fully loaded (all 16 raw pixmaps cached — they are small enough to
    fit the 48MB budget)."""
    from kwallpaper import themes
    monkeypatch.setattr(themes, "DEFAULT_CACHE_DIR", tmp_path / "cache")
    tdir = tmp_path / "Theme"
    tdir.mkdir()
    paths = []
    for i in range(16):
        p = tdir / f"img_{i:02d}.jpg"
        _make_jpeg(p, 2000, 1125, 0x10 * (i + 1) * 0x010101)
        paths.append(str(p))

    w = wallpaper_gui.ImageCrossFadeWidget()
    w.resize(800, 600)
    w.show()
    _spin(qapp, 0.1)
    w.set_images(paths)          # requests 0, 1, 2
    for idx in range(3, 16):
        w._request(idx)

    ok = _wait_until(
        qapp,
        lambda: len(w._raw_cache) >= 16,
        timeout=60,
    )
    assert ok, f"warm-up incomplete: raw={len(w._raw_cache)}"
    return w


class TestScaledKeepSet:
    def test_scaled_limited_to_keep_set(self, widget, qapp):
        """_scaled must hold at most the current image and the fade
        target — not one widget-sized pixmap per loaded image."""
        # Advance the slideshow by simulating fade completions.
        for _ in range(5):
            widget._on_fade_done()
        widget.update()
        _spin(qapp, 0.3)
        with widget._state_lock:
            idx = widget._idx
            keys = set(widget._scaled.keys())
        assert keys <= {idx, (idx + 1) % 16}, \
            f"_scaled holds {sorted(keys)} — expected only {idx}, {idx + 1}"
        # The current image must still render (re-scaled on demand).
        assert _wait_until(qapp, lambda: _current_shown(widget), timeout=10)


class TestRawBudget:
    def test_budget_is_48mb(self):
        assert wallpaper_gui.ImageCrossFadeWidget._MAX_CACHE_BYTES \
            == 48 * 1024 * 1024

    def test_eviction_under_budget_pressure_still_shows(self, qapp, tmp_path,
                                                        monkeypatch):
        """With big images the 48MB budget evicts; the preview must stay
        showing (self-healing re-request)."""
        from kwallpaper import themes
        monkeypatch.setattr(themes, "DEFAULT_CACHE_DIR", tmp_path / "cache")
        tdir = tmp_path / "BigTheme"
        tdir.mkdir()
        paths = []
        for i in range(16):
            p = tdir / f"big_{i:02d}.jpg"
            _make_jpeg(p, 4000, 2250, 0x10 * (i + 1) * 0x010101)
            paths.append(str(p))

        w = wallpaper_gui.ImageCrossFadeWidget()
        w.resize(1600, 900)      # -> 1600px thumbs, ~5.8MB each
        w.show()
        _spin(qapp, 0.1)
        w.set_images(paths)
        for idx in range(3, 16):
            w._request(idx)

        # Wait for the pipeline to drain (no loads in flight)...
        assert _wait_until(
            qapp,
            lambda: (w._loading == set()
                     and len(w._raw_cache) >= 4),
            timeout=90,
        )
        _spin(qapp, 1.0)
        with w._state_lock:
            n_raw = len(w._raw_cache)
            raw_bytes = w._raw_bytes
        # ...which must have evicted under the 48MB budget...
        assert n_raw < 16, f"no eviction: {n_raw} raw entries"
        assert raw_bytes <= 48 * 1024 * 1024 + 8 * 1024 * 1024
        # ...yet the current image still shows (self-healing).
        assert _wait_until(qapp, lambda: _current_shown(w), timeout=30), \
            "preview stuck under budget pressure"


class TestHideShow:
    def test_hide_frees_caches_show_repopulates(self, widget, qapp):
        w = widget
        assert len(w._raw_cache) >= 10
        w.hide()
        _spin(qapp, 0.3)
        with w._state_lock:
            assert w._raw_cache == {}
            assert w._raw_bytes == 0
            assert w._scaled == {}
            assert w._thumb_paths == {}
            assert w._loading == set()
        assert not w._timer.isActive(), "timer must pause while hidden"

        w.show()
        # Re-populates from the disk thumbnail cache (fast).
        assert _wait_until(qapp, lambda: _current_shown(w), timeout=30), \
            "preview did not recover after show"
        with w._state_lock:
            assert len(w._raw_cache) >= 1

    def test_timer_paused_while_hidden(self, widget, qapp):
        w = widget
        w.start()
        assert w._timer.isActive()
        w.hide()
        _spin(qapp, 0.3)
        assert not w._timer.isActive()
        w.show()
        _spin(qapp, 0.3)
        assert w._timer.isActive(), "timer must resume after show"


class TestThumbSize:
    def test_no_oversample(self, qapp, tmp_path, monkeypatch):
        from kwallpaper import themes
        monkeypatch.setattr(themes, "DEFAULT_CACHE_DIR", tmp_path / "cache")
        w = wallpaper_gui.ImageCrossFadeWidget()
        w.show()
        w.resize(1000, 600)
        _spin(qapp, 0.1)
        # 1.0x the physical long-edge, above the 960 floor.
        assert w._desired_thumb_size() == 1000
        w.resize(800, 600)
        _spin(qapp, 0.1)
        # Below the floor -> the floor applies.
        assert w._desired_thumb_size() == 960

    def test_constants(self):
        assert wallpaper_gui.ImageCrossFadeWidget._THUMB_OVERSAMPLE == 1.0
        assert wallpaper_gui.ImageCrossFadeWidget._THUMB_MIN == 960

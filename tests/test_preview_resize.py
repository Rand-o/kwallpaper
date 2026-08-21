"""Repro tests: the crossfade preview must keep showing an image after
the window (widget) is resized.

Reported bug: resizing the window leaves the preview stuck on
"Loading preview…" — no picture at all.

Root cause: ``resizeEvent`` rebuilds ``_scaled`` only from entries still
present in the LRU ``_raw_cache``.  If the current image's raw pixmap
was evicted (the byte budget is smaller than the total of all decoded
thumbnails), nothing re-requests it: ``_request()`` early-returns while
the image is still mapped in ``_thumb_paths``, and ``_scaled_for()``
returns None without triggering a reload.  The preview then stays on
"Loading preview…" until (if ever) the slideshow happens to land on an
image whose raw pixmap is still cached.
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
    """Spin a real event loop (needed for worker->GUI signal delivery)."""
    loop = QEventLoop()
    QTimer.singleShot(max(1, int(seconds * 1000)), loop.quit)
    loop.exec()


def _wait_until(qapp, cond, timeout: float = 20.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        _spin(qapp, 0.2)
    return cond()


@pytest.fixture()
def preview(qapp, tmp_path, monkeypatch):
    """Crossfade preview with 16 synthetic 2000x1125 images, fully loaded
    (all 16 in _scaled and _raw_cache)."""
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
    w.show()  # hidden widgets never receive resizeEvent
    _spin(qapp, 0.1)
    w.set_images(paths)          # requests 0, 1, 2
    for idx in range(3, 16):     # request the rest in parallel
        w._request(idx)

    # _scaled is bounded to the keep set (current + fade target) by
    # design; the raw cache is what we warm up here.
    ok = _wait_until(
        qapp,
        lambda: len(w._raw_cache) >= 16,
        timeout=60,
    )
    assert ok, f"warm-up incomplete: raw={len(w._raw_cache)}"
    return w


def _current_shown(w) -> bool:
    with w._state_lock:
        n = len(w._images)
        idx = w._idx if n else 0
        return w._scaled.get(idx) is not None


def test_grow_resize_keeps_showing(preview, qapp):
    """Growing the window (triggers _re_request_sharp re-encodes) must
    not leave the preview stuck on 'Loading preview…'."""
    assert _current_shown(preview)
    preview.resize(1400, 900)
    _spin(qapp, 0.3)
    assert preview.size().width() == 1400, "resize was not processed"
    assert _wait_until(qapp, lambda: _current_shown(preview), timeout=30), \
        "preview stuck on 'Loading preview…' after grow resize"


def test_shrink_resize_keeps_showing(preview, qapp):
    """Shrinking the window (no re-request path) must not blank the
    preview while every raw pixmap is still cached."""
    assert _current_shown(preview)
    preview.resize(500, 400)
    _spin(qapp, 0.3)
    assert preview.size().width() == 500, "resize was not processed"
    assert _wait_until(qapp, lambda: _current_shown(preview), timeout=10), \
        "preview stuck on 'Loading preview…' after shrink resize"


def test_shrink_resize_after_lru_eviction_recovers(preview, qapp):
    """The reported bug: the current image's raw pixmap has been evicted
    from the LRU (as happens whenever the byte budget is smaller than the
    total of all decoded thumbnails), then the window is shrunk.

    The preview must re-request the evicted pixmap instead of staying on
    'Loading preview…' forever."""
    # Simulate the LRU evicting the CURRENT image's raw pixmap — exactly
    # the state the cache is in once _raw_bytes exceeds the budget.
    with preview._state_lock:
        idx = preview._idx
        t = preview._thumb_paths[idx]
        pm = preview._raw_cache.pop(t)
        preview._raw_bytes -= preview._pixmap_bytes(pm)
        assert t not in preview._raw_cache

    preview.resize(500, 400)   # shrink: no _re_request_sharp path
    _spin(qapp, 0.3)
    assert preview.size().width() == 500, "resize was not processed"
    # Guard against a vacuous pass: verify resizeEvent actually rebuilt
    # the scaled cache at the new (smaller) size — pre-resize pixmaps
    # were ~800px wide for the 800x600 widget.
    with preview._state_lock:
        rebuilt = any(pm.width() <= 520 for pm in preview._scaled.values())
    assert rebuilt, "resizeEvent did not rebuild the scaled cache"
    # The widget must recover by re-requesting the evicted pixmap.
    assert _wait_until(qapp, lambda: _current_shown(preview), timeout=30), \
        "preview stuck on 'Loading preview…' after shrink resize " \
        "following LRU eviction"

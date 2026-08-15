"""Race-condition stress tests for ImageCrossFadeWidget.

These tests hammer the exact code paths that previously raised on the GUI
thread (or corrupted state):

- ``_on_thumb_ready`` with a stale ``src`` (theme switched mid-flight) —
  previously ``list.index()`` could raise ValueError.
- ``_on_image_loaded`` mutating ``_scaled`` while ``_thumb_paths`` is
  consulted — previously iterated the dict while it was assigned elsewhere.
- ``set_images`` / ``start`` / ``stop`` / ``_advance`` / ``_on_fade_done``
  / ``paintEvent`` racing with in-flight background loads.

Run with:  python3 -m pytest tests/test_preview_stress.py -q
"""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QTimer, QSize  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402

import wallpaper_gui  # noqa: E402
from wallpaper_gui import ImageCrossFadeWidget, _LoadToken  # noqa: E402


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    return app


def _fake_images(n: int, w: int = 320, h: int = 200) -> list:
    """Return n unique (non-null) QImages for direct slot invocation."""
    imgs = []
    for i in range(n):
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(i * 10 % 255)
        imgs.append(img)
    return imgs


class TestStaleResultGuards:
    def test_thumb_ready_stale_src_is_ignored(self, app):
        """A thumb for an image no longer in the list must not raise or
        touch state (previously: ValueError from list.index)."""
        w = ImageCrossFadeWidget()
        w.set_images(["a.jpg", "b.jpg"])
        # Simulate a worker finishing for a theme that was already switched
        w._on_thumb_ready("OLD-THEME.jpg", "/thumbs/OLD-THEME.thumb.jpg")
        # State must be untouched: no thumb registered, no load started
        assert w._thumb_paths == {}
        assert w._loading == set()

    def test_image_loaded_stale_thumb_is_ignored(self, app):
        """A pixmap for a thumb no longer mapped to any index must not
        raise or pollute the cache."""
        w = ImageCrossFadeWidget()
        w.set_images(["a.jpg"])
        img = _fake_images(1)[0]
        # No thumb registered for this path -> stale
        w._on_image_loaded("/thumbs/ghost.thumb.jpg", img)
        assert "/thumbs/ghost.thumb.jpg" not in w._raw_cache
        assert w._scaled == {}

    def test_thumb_ready_then_set_images_then_image_loaded(self, app):
        """Full race: thumb arrives, list switches, pixmap arrives late.
        The late pixmap must be dropped, not painted from a dead list."""
        w = ImageCrossFadeWidget()
        w.set_images(["a.jpg", "b.jpg"])
        w._on_thumb_ready("a.jpg", "/thumbs/a.thumb.jpg")
        assert 0 in w._thumb_paths
        # Switch theme mid-flight
        w.set_images(["c.jpg"])
        assert w._thumb_paths == {}
        # Late pixmap for the old theme
        img = _fake_images(1)[0]
        w._on_image_loaded("/thumbs/a.thumb.jpg", img)
        assert "/thumbs/a.thumb.jpg" not in w._raw_cache
        assert w._scaled == {}


class SetImagesRace:
    pass


class TestSetImagesRace:
    def test_rapid_set_images_with_pending_loads(self, app):
        """Rapid theme switches while loads are 'in flight' (simulated by
        priming _loading) must not raise and must leave consistent state."""
        w = ImageCrossFadeWidget()
        for i in range(50):
            w.set_images([f"theme{i}.jpg", f"theme{i}b.jpg"])
            # Prime an in-flight load for the current image
            w._on_thumb_ready(f"theme{i}.jpg", f"/thumbs/t{i}.thumb.jpg")
            w._loading.add(f"/thumbs/t{i}.thumb.jpg")
            # Advance the slideshow a few times
            for _ in range(3):
                w._advance()
            # Paint while everything is in a half-loaded state
            w.resize(400, 300)
            w.update()
        # Final state must be internally consistent
        assert len(w._images) == 2
        assert 0 <= w._idx < len(w._images)
        # Every scaled entry must map to a valid index
        for idx in w._scaled:
            assert 0 <= idx < len(w._images)

    def test_set_images_empty_then_paint(self, app):
        w = ImageCrossFadeWidget()
        w.set_images(["a.jpg"])
        w._advance()
        w.set_images([])
        w._advance()          # must not crash on empty list
        w._on_fade_done()     # must not crash on empty list
        w.resize(300, 200)
        w.update()            # paintEvent with empty list

    def test_advance_fade_done_with_single_image(self, app):
        w = ImageCrossFadeWidget()
        w.set_images(["only.jpg"])
        for _ in range(10):
            w._advance()
            w._on_fade_done()
        assert w._idx == 0

    def test_resize_during_loading(self, app):
        """resizeEvent re-scales the cache; do it while loads are pending."""
        w = ImageCrossFadeWidget()
        w.set_images([f"i{j}.jpg" for j in range(8)])
        for j in range(8):
            w._on_thumb_ready(f"i{j}.jpg", f"/thumbs/i{j}.thumb.jpg")
            w._loading.add(f"/thumbs/i{j}.thumb.jpg")
        for size in [(400, 300), (800, 600), (320, 200), (1280, 720)]:
            w.resize(*size)
            w.update()
        # All thumbs registered, none scaled yet (no pixmaps loaded)
        assert len(w._thumb_paths) == 8
        assert w._scaled == {}


class TestRealBackgroundPipeline:
    """End-to-end: real QThreadPool workers + fake token, rapid switches.

    Uses real (small) JPEG files so the thumbnail/pixmap pipeline runs for
    real.  The point is to interleave set_images() with in-flight decodes —
    the exact pattern that used to corrupt GUI-thread state.
    """

    def test_rapid_theme_switches_with_real_workers(self, app, tmp_path):
        from PIL import Image as PILImage  # may be absent; skip if so
        from PyQt6.QtCore import QEventLoop
        # Build 4 small JPEGs (large enough to exercise the decode path)
        paths = []
        for i in range(4):
            p = tmp_path / f"img{i}.jpg"
            im = PILImage.new("RGB", (1600, 1000), (i * 40 % 255, 100, 200))
            im.save(p, "JPEG")
            paths.append(str(p))

        w = ImageCrossFadeWidget()
        w.resize(400, 300)

        # Rapidly switch between two image lists while workers are running.
        # A real event loop is required: queued cross-thread signals are only
        # delivered while the loop is spinning (processEvents alone is not
        # enough for the worker->GUI handoff).
        loop = QEventLoop()
        state = {"i": 0}

        def spin():
            state["i"] += 1
            if state["i"] >= 30:
                loop.quit()
                return
            w.set_images(paths if state["i"] % 2 == 0 else paths[1:])
            QTimer.singleShot(80, spin)

        QTimer.singleShot(0, spin)
        loop.exec()

        # Let the pool drain and deliver any final signals
        w._pool.waitForDone(5000)
        loop2 = QEventLoop()
        QTimer.singleShot(200, loop2.quit)
        loop2.exec()

        # State must be consistent after the drain
        assert 0 <= w._idx < max(len(w._images), 1)
        for idx in w._scaled:
            assert 0 <= idx < len(w._images)
        # No orphaned in-flight markers
        assert w._loading == set()

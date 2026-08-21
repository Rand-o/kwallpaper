"""Memory-footprint tests for the thumbnail pipeline.

The shared thumbnail cache (themes.ensure_thumbnail) is keyed per image,
and different consumers request very different sizes: the schedule
preview wants ~96px squares while the crossfade preview wants up to 4K.
Without a sane reuse rule, a 96px request happily reuses a 3076px cache
file and decodes ~21MB of pixels to draw a 28px square.  These tests pin
the reuse rule (re-encode when the cached thumb is much larger than the
request) and the schedule preview's pixmap cache size.
"""
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage, QImageReader
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_jpeg(path: Path, w: int, h: int):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(0x3060C0)
    assert img.save(str(path), "JPG", 85)


def _setup(tmp_path, monkeypatch, src_size=(400, 200)):
    from kwallpaper import themes
    monkeypatch.setattr(themes, "DEFAULT_CACHE_DIR", tmp_path / "cache")
    src_dir = tmp_path / "MyTheme"
    src_dir.mkdir()
    src = src_dir / "img_1.jpeg"
    _make_jpeg(src, *src_size)
    thumb = tmp_path / "cache" / "thumbs" / "MyTheme" / "img_1.thumb.jpg"
    thumb.parent.mkdir(parents=True)
    return themes, src, thumb


def test_reuse_when_cache_close_to_request(qapp, tmp_path, monkeypatch):
    """A cached thumb within 2x the requested size is reused as-is."""
    themes, src, thumb = _setup(tmp_path, monkeypatch)
    _make_jpeg(thumb, 400, 200)      # cached long edge 400
    thumb.touch()                    # newer than the source
    out = themes.ensure_thumbnail(str(src), thumb_size=200)
    assert out == str(thumb)
    r = QImageReader(str(thumb))
    assert max(r.size().width(), r.size().height()) == 400  # untouched


def test_reencode_when_cache_much_larger_than_request(qapp, tmp_path,
                                                     monkeypatch):
    """A cached thumb >2x the requested size is re-encoded smaller, so a
    96px request never decodes a multi-megapixel cache file."""
    themes, src, thumb = _setup(tmp_path, monkeypatch)
    _make_jpeg(thumb, 400, 200)      # cached long edge 400
    thumb.touch()
    out = themes.ensure_thumbnail(str(src), thumb_size=100)
    assert out == str(thumb)
    r = QImageReader(str(thumb))
    assert max(r.size().width(), r.size().height()) <= 100


def test_schedule_preview_stores_small_pixmaps(qapp, tmp_path):
    """The schedule preview draws THUMB_PX squares; it must not pin a
    full-size cache decode (~21MB at 3076px) per image in memory."""
    from kwallpaper.schedule_preview import THUMB_PX, SchedulePreviewWidget
    w = SchedulePreviewWidget()
    src = tmp_path / "MyTheme" / "img_1.jpeg"
    src.parent.mkdir(parents=True)
    thumb = tmp_path / "MyTheme" / "img_1.thumb.jpg"
    _make_jpeg(thumb, 300, 300)
    w._on_thumbs_ready({str(src): str(thumb)}, w._token.version)
    pm = w._pixmaps[str(src)]
    assert max(pm.width(), pm.height()) <= THUMB_PX * 4
    assert max(pm.width(), pm.height()) < 300  # actually downscaled

"""Phase 4: strict theme import validation (missing referenced images)."""
import json
import zipfile

import pytest

from kwallpaper import core
from kwallpaper import themes as themes_module


def _make_theme_zip(path, theme_data, image_names):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("theme.json", json.dumps(theme_data))
        for name in image_names:
            zf.writestr(name, b"\xff\xd8\xff\xe0fake")


def _base_theme_data(**overrides):
    data = {
        "displayName": "Test Theme",
        "imageFilename": "test_*.jpg",
        "sunriseImageList": [1],
        "dayImageList": [2, 3],
        "sunsetImageList": [4],
        "nightImageList": [5, 6],
    }
    data.update(overrides)
    return data


@pytest.fixture
def themes_dir(tmp_path, monkeypatch):
    themes = tmp_path / "themes"
    themes.mkdir()
    monkeypatch.setattr(core, "DEFAULT_THEMES_DIR", themes)
    monkeypatch.setattr(themes_module, "DEFAULT_THEMES_DIR", themes)
    return themes


def test_import_rejects_missing_day_image(themes_dir, tmp_path):
    src = tmp_path / "broken.ddw"
    # only dayImageList references images; it asks for the 3rd file but
    # only one exists -> exactly "day image 3" is missing
    _make_theme_zip(
        src,
        _base_theme_data(sunriseImageList=[], sunsetImageList=[],
                         nightImageList=[], dayImageList=[3]),
        ["test_3.jpg"],
    )
    with pytest.raises(ValueError) as excinfo:
        core.import_theme(str(src))
    msg = str(excinfo.value)
    assert "Test Theme" in msg
    assert "day image 3" in msg
    assert "sunrise image" not in msg
    assert "sunset image" not in msg
    assert "night image" not in msg
    assert not (themes_dir / "broken").exists()  # no partial import


def test_import_lists_every_missing_image(themes_dir, tmp_path):
    src = tmp_path / "gaps.ddw"
    # 3 files exist; sunset 4, night 5 and night 6 are all missing
    _make_theme_zip(src, _base_theme_data(),
                    ["test_1.jpg", "test_2.jpg", "test_3.jpg"])
    with pytest.raises(ValueError) as excinfo:
        core.import_theme(str(src))
    msg = str(excinfo.value)
    for expected in ("sunset image 4", "night image 5", "night image 6"):
        assert expected in msg
    # present images must not be reported
    assert "sunrise image" not in msg
    assert "day image" not in msg
    assert not (themes_dir / "gaps").exists()


def test_import_accepts_complete_theme(themes_dir, tmp_path):
    src = tmp_path / "good.ddw"
    _make_theme_zip(src, _base_theme_data(),
                    [f"test_{i}.jpg" for i in range(1, 7)])
    meta = core.import_theme(str(src))
    assert meta["displayName"] == "Test Theme"
    assert (themes_dir / "good" / "theme.json").exists()


def test_import_rejects_theme_with_no_images(themes_dir, tmp_path):
    src = tmp_path / "noimg.ddw"
    _make_theme_zip(src, _base_theme_data(), [])
    with pytest.raises(ValueError) as excinfo:
        core.import_theme(str(src))
    msg = str(excinfo.value)
    for expected in ("sunrise image 1", "day image 2", "day image 3",
                     "sunset image 4", "night image 5", "night image 6"):
        assert expected in msg
    assert "0 image file(s)" in msg
    assert not (themes_dir / "noimg").exists()


def test_themes_import_theme_rejects_missing_image(themes_dir, tmp_path):
    """The CLI path (themes.import_theme) enforces the same validation."""
    src = tmp_path / "cli-broken.ddw"
    _make_theme_zip(src, _base_theme_data(nightImageList=[99]),
                    [f"test_{i}.jpg" for i in range(1, 7)])
    with pytest.raises(ValueError) as excinfo:
        themes_module.import_theme(str(src))
    assert "night image 99" in str(excinfo.value)
    assert not (themes_dir / "cli-broken").exists()


def test_import_not_stricter_than_selection(themes_dir, tmp_path):
    """Validation uses the same positional mapping as selection: a value
    N is satisfied by the Nth file, and 0 (which selection maps to the
    last file) is never reported missing."""
    src = tmp_path / "quirky.ddw"
    # 3 files exist; day list references 0, 2 and 150.  2 is satisfied,
    # 150 is missing, 0 is not reported.
    _make_theme_zip(
        src,
        _base_theme_data(sunriseImageList=[1], dayImageList=[0, 2, 150],
                         sunsetImageList=[], nightImageList=[]),
        ["test_1.jpg", "test_2.jpg", "test_3.jpg"],
    )
    with pytest.raises(ValueError) as excinfo:
        core.import_theme(src)
    msg = str(excinfo.value)
    assert "day image 150" in msg
    assert "day image 0" not in msg
    assert "day image 2" not in msg


def test_image_files_for_numeric_sort(tmp_path):
    """10 must sort after 2 (numeric, not lexicographic)."""
    theme = {"imageFilename": "test_*.jpg"}
    for name in ("test_10.jpg", "test_2.jpg", "test_1.jpg"):
        (tmp_path / name).touch()
    files = themes_module.image_files_for(tmp_path, theme)
    assert [f.name for f in files] == ["test_1.jpg", "test_2.jpg", "test_10.jpg"]


def test_image_files_for_numbered_fallback(tmp_path):
    """When the glob pattern matches nothing, fall back to numbered files
    {pattern_base}_{1..99}{pattern_ext} — mirrors pre-Phase-4 selection."""
    theme = {
        "imageFilename": "sun_{0}.jpg",
        "sunriseImageList": [1], "dayImageList": [2],
        "sunsetImageList": [3], "nightImageList": [4],
    }
    for i in range(1, 5):
        (tmp_path / f"sun_{{0}}_{i}.jpg").touch()
    files = themes_module.image_files_for(tmp_path, theme)
    assert [f.name for f in files] == [f"sun_{{0}}_{i}.jpg" for i in range(1, 5)]

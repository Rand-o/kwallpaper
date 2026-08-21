# WDD Time Model — Phase 4: Default Flip, Import Validation & Docs

**For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the WDD-style time model work: make the sun-position model the default (`scheduling.suntime_model: "sun"`), reject theme imports whose `theme.json` references missing image files, and document everything in the README/changelog. This is the **final required phase** of the roadmap — only the optional Phase 5 extras remain afterwards.

**Architecture:** Three small, independent changes on top of the Phase 1–3 state: (1) the config default flip is a one-line change in `_default_config()` — `normalize_config` fills *absent* keys with defaults via `setdefault`, so existing configs that explicitly set `suntime_model` (including `"legacy"`) are untouched, while every config without the field (i.e. all pre-Phase-2 configs) picks up `"sun"` at load time with no migration script; (2) a shared image-discovery helper (`themes.image_files_for`) extracted from `selection._match_image_file` so import validation uses the *exact same* positional mapping as selection, wired into both import entry points (`themes.import_theme` for the CLI, `core.import_theme` for the GUI) to run **at import time, before the theme is committed** to the themes directory; (3) README/changelog/version updates describing the new default, the visible behavior change (transition images shift by up to ~30–75 minutes), and the escape hatch.

**Tech Stack:** Python 3.11+, existing `kwallpaper` package modules (`config.py`, `themes.py`, `selection.py`, `core.py`, `scheduler.py`, `image_schedule.py`), `wallpaper_gui.py`, `pytest`. No new dependencies.

## Roadmap

From `docs/superpowers/roadmaps/2026-08-17-wdd-time-model-roadmap.md`:

1. **Phase 1** — Sun-position period model (`kwallpaper/solarsegments.py`) — ✅ done
2. **Phase 2** — Event-driven scheduling + selection routing — ✅ done
3. **Phase 3** — GUI model toggle + schedule preview — ✅ done
4. **Phase 4** — Default flip, import validation, docs — **this plan (final required phase)**
5. **Phase 5 (optional)** — Extras only: legacy model removal, theme editor, per-theme model override, more schedule preview features. Nothing in Phase 5 is required.

## Phase

Phase 4 of 5. **This is the last required phase.** When Tasks 1–4 are done and verified, the roadmap's required scope is complete; Task 5 below is an optional, user-gated legacy-removal sub-step and the Phase 5 items are optional extras.

## Context

**Baseline (post-Phase 3):** `python3 -m pytest tests/ -q` → **321 passed, 0 failed**.

**Key mechanism — why the default flip needs no migration code.** `config.normalize_config` (config.py) walks `_default_config()` and fills missing keys with `setdefault` semantics: it only writes a value when the key is *absent*. Therefore:

- Config with **no** `scheduling.suntime_model` (all configs created before Phase 2) → gets the new default `"sun"` at load time. This is the intended migration.
- Config with an **explicit** `"suntime_model": "legacy"` → preserved verbatim. The user's choice is never overwritten.
- Config with an **explicit** `"suntime_model": "sun"` → unchanged.

The flip takes effect in memory at the next `load_config()`; the config file on disk is only rewritten on the next `save_config()` (GUI save, location change, etc.). No data migration, no versioned migration step.

**Key decision — where import validation runs.** Validation runs **at import time** in the two import entry points, **before** the extracted theme is moved into `~/.config/kwallpaper/themes/`:

- `themes.import_theme()` — used by the CLI `wallpaper_cli.py themes add` (cli.py `run_themes_add`, which already catches `ValueError` and prints `Error: {e}` to stderr, exit 1).
- `core.import_theme()` — used by the GUI import worker (`wallpaper_gui.py `_import_worker`, which catches `Exception`, counts the theme as failed, and surfaces the message in the event log).

Deliberately **out of scope**:

- `themes.extract_theme()` (used by the CLI `extract` command, the CLI `change` command on zip files, and `core.apply_theme` on zip files) is an *apply/extract* path, not an import path — it stays permissive, and the existing selection-time wraparound behavior covers it. The existing test `tests/test_zip_extraction.py::test_extract_theme_valid_zip` (which imports a deliberately broken theme through `extract_theme`) must keep passing unchanged.
- **Already-installed themes are not re-validated.** There is no data migration of on-disk themes; a broken pre-existing theme behaves exactly as it does today (selection wraps around via `files[(value-1) % len(files)]`). Only *newly imported* themes are validated.

**Key decision — why `selection.py` routing needs no change for the flip.** Both routed selectors read `suntime_model` from a config loaded via `load_config()`, which always returns a normalized config where `scheduling.suntime_model` is present. The only path where the key could be absent is the `except` fallback (`config = {}` on unreadable config), where the sun branch could not run anyway (`segments_for_config` would fail on the same unreadable config and fall back to legacy — identical outcome). So the routing checks in `selection.py` stay as-is.

**Key decision — validation must see normalized lists.** `normalize_image_lists` drops out-of-range values (keeps 1–99 only). Selection normalizes via `load_theme_data`, so validation must run on the normalized lists too — otherwise a theme with `dayImageList: [0, 150]` would be rejected for images selection never requests. `themes.import_theme` already normalizes; `core.import_theme` currently does **not** — Task 2 adds the call so both entry points return identical (normalized) metadata.

**Files:**

- Modify: `kwallpaper/config.py` (1 line), `kwallpaper/scheduler.py` (2 lines), `kwallpaper/image_schedule.py` (1 line), `wallpaper_gui.py` (1 line)
- Modify: `kwallpaper/themes.py` (2 new functions + restructured `import_theme`), `kwallpaper/selection.py` (`_match_image_file` refactor), `kwallpaper/core.py` (restructured `import_theme`)
- Modify: `README.md`, `setup.py`
- Create: `tests/test_theme_import_validation.py`
- Modify: `tests/test_config.py`, `tests/test_scheduler.py` (new tests appended)

---

### Task 1: Flip the default `suntime_model` to `"sun"` (TDD)

**Files:**
- Modify: `kwallpaper/config.py` — `_default_config()`
- Modify: `kwallpaper/scheduler.py` — `_get_config()` (success-path default + error fallback dict)
- Modify: `kwallpaper/image_schedule.py` — `schedule_for_config()` (fallback literal only)
- Modify: `wallpaper_gui.py` — `SettingsPage._load()` (fallback literal only)
- Test: `tests/test_config.py` (4 new tests), `tests/test_scheduler.py` (1 new test)

**Why the extra one-line changes:** `scheduler._get_config()` has a hardcoded fallback dict used when the config file is unreadable (corrupt JSON) — it must match the fresh-install default, or a user with a corrupt config file would silently get the legacy model while a fresh install gets sun. The `image_schedule.py` and `wallpaper_gui.py` changes update fallback literals that are dead code after normalization (the key is always present in a loaded config) but must not advertise the old default.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py` (add `_default_config` to the existing `kwallpaper.config` import line if not already imported):

```python
def test_default_config_suntime_model_is_sun():
    """Phase 4: the canonical default is the sun-position model."""
    assert _default_config()["scheduling"]["suntime_model"] == "sun"


def test_load_config_absent_suntime_model_defaults_to_sun(tmp_path):
    """A config without the field (all pre-Phase-2 configs) picks up the
    new default at load time — this is the whole migration."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "location": {"timezone": "UTC", "latitude": 0.0, "longitude": 0.0},
        "scheduling": {"cycle_interval": 60},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "sun"


def test_load_config_explicit_legacy_preserved(tmp_path):
    """A user who explicitly chose the legacy model keeps it — the default
    flip must never overwrite an existing value."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "scheduling": {"suntime_model": "legacy"},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "legacy"


def test_load_config_explicit_sun_preserved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "scheduling": {"suntime_model": "sun"},
    }))
    config = load_config(str(path))
    assert config["scheduling"]["suntime_model"] == "sun"
```

Append to `tests/test_scheduler.py`:

```python
def test_get_config_corrupt_config_falls_back_to_sun_model(tmp_path):
    """An unreadable config file must fall back to the same model as a
    fresh install (sun), not the pre-Phase-4 legacy default."""
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json")
    mgr = SchedulerManager(config_path=str(cfg))
    assert mgr._get_config()["suntime_model"] == "sun"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_config.py::test_default_config_suntime_model_is_sun \
  tests/test_config.py::test_load_config_absent_suntime_model_defaults_to_sun \
  tests/test_config.py::test_load_config_explicit_legacy_preserved \
  tests/test_config.py::test_load_config_explicit_sun_preserved \
  tests/test_scheduler.py::test_get_config_corrupt_config_falls_back_to_sun_model -q
```

Expected: `test_default_config_suntime_model_is_sun`, `test_load_config_absent_suntime_model_defaults_to_sun` (an absent field currently picks up the old `"legacy"` default), and `test_get_config_corrupt_config_falls_back_to_sun_model` FAIL; the two explicit-value tests (`..._explicit_legacy_preserved`, `..._explicit_sun_preserved`) already pass because `setdefault` never overwrites existing values. After the fix all five must pass.

- [ ] **Step 3: Flip the default in `kwallpaper/config.py`**

In `_default_config()`, change the `scheduling` block from:

```python
        "scheduling": {
            "cycle_interval": 60,
            "safety_interval": 600,
            "suntime_model": "legacy",
            "run_cycle": True,
            "daily_shuffle_enabled": True,
        },
```

to:

```python
        "scheduling": {
            "cycle_interval": 60,
            "safety_interval": 600,
            "suntime_model": "sun",
            "run_cycle": True,
            "daily_shuffle_enabled": True,
        },
```

- [ ] **Step 4: Align the scheduler fallbacks in `kwallpaper/scheduler.py`**

In `_get_config()`, change the success-path read from:

```python
                'suntime_model': scheduling.get('suntime_model', 'legacy'),
```

to:

```python
                'suntime_model': scheduling.get('suntime_model', 'sun'),
```

and in the `except` fallback dict, change:

```python
                'suntime_model': 'legacy',
```

to:

```python
                'suntime_model': 'sun',
```

- [ ] **Step 5: Align the dead-code fallback literals**

In `kwallpaper/image_schedule.py`, in `schedule_for_config()`, change:

```python
    model = config.get("scheduling", {}).get("suntime_model", "legacy")
```

to:

```python
    model = config.get("scheduling", {}).get("suntime_model", "sun")
```

In `wallpaper_gui.py`, in `SettingsPage._load()`, change:

```python
        self.model_combo.setCurrentIndex(
            0 if s.get("suntime_model", "legacy") == "sun" else 1)
```

to:

```python
        self.model_combo.setCurrentIndex(
            0 if s.get("suntime_model", "sun") == "sun" else 1)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_config.py tests/test_scheduler.py -q
```

Expected: all pass.

- [ ] **Step 7: Run the full suite (no regressions)**

```bash
python3 -m pytest tests/ -q
```

Expected: 326 passed (321 + 5 new), 0 failed. If any Phase 2/3 test asserted the old `"legacy"` default (e.g. a test that builds a config without `suntime_model` and expects legacy routing), update that test to set `"suntime_model": "legacy"` explicitly — the test's intent is to pin the *legacy path*, and after the flip that requires an explicit value.

- [ ] **Step 8: Commit**

```bash
git add kwallpaper/config.py kwallpaper/scheduler.py kwallpaper/image_schedule.py wallpaper_gui.py tests/test_config.py tests/test_scheduler.py
git commit -m "config: default suntime_model to sun (explicit legacy values preserved)"
```

---

### Task 2: Strict theme import validation (TDD)

**Files:**
- Modify: `kwallpaper/themes.py` — new `image_files_for()`, new `validate_theme_images()`, restructured `import_theme()`
- Modify: `kwallpaper/selection.py` — `_match_image_file()` refactored onto `image_files_for()` (behavior unchanged)
- Modify: `kwallpaper/core.py` — restructured `import_theme()` (validate before commit; normalize like `themes.import_theme`)
- Test: Create `tests/test_theme_import_validation.py`

**Semantics:** every value in all four image lists (`sunriseImageList`, `dayImageList`, `sunsetImageList`, `nightImageList`) must satisfy `value <= len(image_files_for(...))` — the same positional mapping selection uses (value N selects the Nth numerically-sorted file; today, a larger value silently wraps around to the wrong image). All missing (category, image number) pairs are collected and reported in a single `ValueError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_theme_import_validation.py`:

```python
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


def test_import_validates_normalized_lists(themes_dir, tmp_path):
    """Values that normalize_image_lists drops (0, >99) must not be
    reported missing: validation runs on the normalized lists, exactly
    what selection will see. The returned metadata is normalized too."""
    src = tmp_path / "quirky.ddw"
    _make_theme_zip(src, _base_theme_data(dayImageList=[0, 2, 150]),
                    ["test_2.jpg"])
    meta = core.import_theme(str(src))
    assert meta["dayImageList"] == [2]


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_import_validation.py -q
```

Expected: 7 fail — the five import tests raise no `ValueError` (broken themes import fine today), and the two `image_files_for` tests fail with `AttributeError: module 'kwallpaper.themes' has no attribute 'image_files_for'`. `test_import_accepts_complete_theme` already passes (complete themes import fine today) and serves as the regression guard for the happy path.

- [ ] **Step 3: Add `image_files_for()` and `validate_theme_images()` to `kwallpaper/themes.py`**

Add `List` to the typing import (`from typing import Any, Dict, List`), then add after `normalize_image_lists()`:

```python
def image_files_for(theme_path_obj: Path, theme_data: Dict[str, Any]) -> List[Path]:
    """Ordered image file list for a theme directory.

    Single source of truth for image discovery, shared by selection
    (``selection._match_image_file``) and import validation
    (``validate_theme_images``): glob the ``imageFilename`` pattern; when
    the glob matches nothing, fall back to numbered files
    ``{pattern_base}_{1..99}{pattern_ext}``; sort numerically by the
    trailing ``_N`` in the stem (non-numeric stems sort first).
    """
    filename_pattern = theme_data.get("imageFilename", "*.jpg")
    pattern_base = Path(filename_pattern).stem if filename_pattern else "theme"
    pattern_ext = Path(filename_pattern).suffix if filename_pattern else ".jpg"

    image_files = list(theme_path_obj.glob(filename_pattern))
    if not image_files:
        numbered = [theme_path_obj / f"{pattern_base}_{i}{pattern_ext}"
                    for i in range(1, 100)]
        image_files = [f for f in numbered if f.exists()]

    def get_img_idx(f):
        try:
            return int(f.stem.split('_')[-1])
        except Exception:
            return 0
    image_files.sort(key=get_img_idx)
    return image_files


def validate_theme_images(theme_dir: Path, theme_data: Dict[str, Any]) -> None:
    """Verify that every image referenced by ``theme_data`` exists on disk.

    ``theme_data`` must be normalized (call :func:`normalize_image_lists`
    first).  Every value in all four image lists must map to an existing
    file under the ``imageFilename`` pattern using the same positional
    mapping as selection (a value N selects the Nth file from
    :func:`image_files_for`).

    Raises:
        ValueError: if any referenced image is missing.  The message lists
            every missing (category, image number) pair plus how many
            files the pattern matched, so the user can fix the theme.
    """
    files = image_files_for(theme_dir, theme_data)
    count = len(files)
    missing = [
        (category, value)
        for category in ("sunrise", "day", "sunset", "night")
        for value in theme_data.get(f"{category}ImageList", [])
        if value > count
    ]
    if missing:
        lines = "\n".join(f"  - {category} image {value}"
                          for category, value in missing)
        pattern = theme_data.get("imageFilename", "*.jpg")
        name = theme_data.get("displayName") or "unknown theme"
        raise ValueError(
            f"Theme '{name}' references image file(s) that do not exist:\n"
            f"{lines}\n"
            f"Only {count} image file(s) match '{pattern}'. "
            "Add the missing files or lower the image numbers in "
            "theme.json, then import again."
        )
```

- [ ] **Step 4: Refactor `selection._match_image_file()` onto the shared helper**

In `kwallpaper/selection.py`, change the themes import from:

```python
from kwallpaper.themes import extract_theme, normalize_image_lists
```

to:

```python
from kwallpaper.themes import extract_theme, image_files_for, normalize_image_lists
```

and replace the body of `_match_image_file()` (keeping its signature and docstring) with:

```python
    image_files = image_files_for(theme_path_obj, theme_data)
    if not image_files:
        raise FileNotFoundError(
            f"Image file not found for index {image_index} in theme '{theme_data.get('displayName')}'"
        )

    # Find the file at the correct index
    if image_index <= len(image_files):
        image_path = image_files[image_index - 1]  # 1-based to 0-based
    else:
        # Wrap around if index exceeds available files
        image_path = image_files[(image_index - 1) % len(image_files)]

    return str(image_path)
```

This is a behavior-preserving refactor: the discovery logic (glob → numbered fallback → numeric sort) is moved verbatim into `themes.image_files_for`.

- [ ] **Step 5: Restructure `themes.import_theme()` to validate before commit**

Replace the body of `import_theme()` in `kwallpaper/themes.py` (from the `with tempfile.TemporaryDirectory() as tmpdir:` block through the final `return`) with:

```python
    # Extract to a temporary location
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_theme(str(source), cleanup=False)
        extract_dir = Path(result['extract_dir'])

        # Determine target name (strip extension)
        target_name = source.stem
        target_dir = DEFAULT_THEMES_DIR / target_name

        if target_dir.exists():
            raise FileExistsError(f"Theme already exists: {target_name}")

        # Read + validate before committing to the themes directory, so a
        # rejected import leaves no partial theme behind (the temp dir is
        # cleaned up by the context manager).
        theme_json_path = extract_dir / "theme.json"
        if not theme_json_path.exists():
            for json_file in extract_dir.glob("*.json"):
                theme_json_path = json_file
                break
            else:
                raise FileNotFoundError("theme.json not found in extracted theme")
        with open(theme_json_path, 'r') as f:
            theme_data = json.load(f)
        theme_data = normalize_image_lists(theme_data)
        validate_theme_images(extract_dir, theme_data)

        # Move to themes directory
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extract_dir), str(target_dir))

    return {
        'extract_dir': str(target_dir),
        'displayName': theme_data.get('displayName', target_name),
        'imageCredits': theme_data.get('imageCredits', ''),
        'imageFilename': theme_data.get('imageFilename', ''),
        'sunriseImageList': theme_data.get('sunriseImageList', []),
        'dayImageList': theme_data.get('dayImageList', []),
        'sunsetImageList': theme_data.get('sunsetImageList', []),
        'nightImageList': theme_data.get('nightImageList', []),
    }
```

Also update the docstring's first line to: `"""Import a theme from a .zip/.ddw file to the themes directory."""` plus a second line: `Validates that every image referenced by theme.json exists; a rejected import leaves no partial theme behind.`

Note: the old code re-read `theme.json` from the final location after the move; the restructured version reads it from the temp extraction dir before the move — same file, and it is what makes "no partial import on rejection" possible.

- [ ] **Step 6: Restructure `core.import_theme()` the same way**

In `kwallpaper/core.py`, change the themes import from:

```python
from kwallpaper.themes import DEFAULT_THEMES_DIR, extract_theme
```

to:

```python
from kwallpaper.themes import (
    DEFAULT_THEMES_DIR,
    extract_theme,
    normalize_image_lists,
    validate_theme_images,
)
```

and replace the body of `import_theme()` (from the `with tempfile.TemporaryDirectory() as tmpdir:` block through the final `return`) with:

```python
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_theme(str(source), cleanup=False)
        extract_dir = Path(result['extract_dir'])

        target_name = source.stem
        target_dir = DEFAULT_THEMES_DIR / target_name
        if target_dir.exists():
            raise FileExistsError(f"Theme already exists: {target_name}")

        # Read + validate before committing, so a rejected import leaves
        # no partial theme behind (temp dir cleaned up automatically).
        theme_json_path = extract_dir / "theme.json"
        if not theme_json_path.exists():
            for json_file in extract_dir.glob("*.json"):
                theme_json_path = json_file
                break
            else:
                raise FileNotFoundError("theme.json not found in extracted theme")
        with open(theme_json_path) as f:
            theme_data = json.load(f)
        theme_data = normalize_image_lists(theme_data)
        validate_theme_images(extract_dir, theme_data)

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extract_dir), str(target_dir))

    return {
        'extract_dir': str(target_dir),
        'displayName': theme_data.get('displayName', target_name),
        'imageCredits': theme_data.get('imageCredits', ''),
        'imageFilename': theme_data.get('imageFilename', ''),
        'sunriseImageList': theme_data.get('sunriseImageList', []),
        'dayImageList': theme_data.get('dayImageList', []),
        'sunsetImageList': theme_data.get('sunsetImageList', []),
        'nightImageList': theme_data.get('nightImageList', []),
    }
```

`core.import_theme` now normalizes like `themes.import_theme` did already, so both entry points return identical metadata and validate exactly what selection will see.

- [ ] **Step 7: Run the new tests**

```bash
python3 -m pytest tests/test_theme_import_validation.py -q
```

Expected: 8 passed.

- [ ] **Step 8: Run the full suite (no regressions)**

```bash
python3 -m pytest tests/ -q
```

Expected: 334 passed (326 + 8), 0 failed. In particular `tests/test_zip_extraction.py::test_extract_theme_valid_zip` (broken theme through `extract_theme`) and `tests/test_core_api.py` import tests must still pass — `extract_theme` is deliberately not validated, and the existing `core.import_theme` tests use complete or metadata-only zips. If `test_import_theme_valid_zip` (a zip containing only `theme.json`, no images, no image lists) now fails, it fails only if the empty `theme.json` (`{"displayName": "New"}`) produced missing-image errors — it will not, because all four lists are absent (empty), and `validate_theme_images` only reports values that are present. Confirm it passes unchanged.

- [ ] **Step 9: Commit**

```bash
git add kwallpaper/themes.py kwallpaper/selection.py kwallpaper/core.py tests/test_theme_import_validation.py
git commit -m "themes: reject imports whose theme.json references missing images"
```

---

### Task 3: README + changelog + version

**Files:**
- Modify: `README.md` (configuration table, Time-of-Day Categories, Background scheduler, FAQ, Running Tests, Changelog)
- Modify: `setup.py` (version bump)

No tests for this task; verification is the diff review plus the full suite in Task 4.

- [ ] **Step 1: Update the `suntime_model` row in the Configuration Fields table**

Phase 3 added a row for `suntime_model` to the Configuration Fields table (it says the default is `"legacy"` until Phase 4). Update that row so it reads:

```markdown
| `suntime_model` | Sun-position model (`"sun"`, default) or legacy fixed slots (`"legacy"`) — see Time-of-Day Categories |
```

- [ ] **Step 2: Rewrite the Time-of-Day Categories section to cover both models**

Replace the current `## Time-of-Day Categories` section (the one describing only the `astral`-based categories) with:

```markdown
## Time-of-Day Categories

Wallpaper selection is driven by one of two time models
(`scheduling.suntime_model` in the config, or Settings → Time Model in the
GUI):

### Sun-position model (default)

Images are positioned by where the sun actually is, not by fixed clock
slots:

- **Sunrise**: images run from sunrise to sunset, position 0.0 → 1.0
- **Day**: images run from sunrise to sunset, position 0.0 → 1.0
- **Sunset**: images run from sunset to the next sunrise, position 0.0 → 1.0
- **Night**: images run from sunset to the next sunrise, position 0.0 → 1.0

Because the real sunrise/sunset times shift through the year, transition
images change at different clock times than the legacy fixed slots —
typically 30–75 minutes earlier or later, depending on season and
location.

### Legacy fixed slots

The pre-1.2 behavior, available with `suntime_model: "legacy"`:

- **Sunrise**: 06:30–09:30 local time (images start at dawn)
- **Day**: 09:30–16:30 local time
- **Sunset**: 16:30–19:30 local time (images end at dusk)
- **Night**: 19:30–06:30 local time

Both models use the `astral` library and your configured timezone and
location.
```

- [ ] **Step 3: Update the Background scheduler section**

Replace the "Cycle task" bullet in `## Background scheduler` with two model-specific bullets:

```markdown
- **Event-driven (sun model, default)**: arms a one-shot job at the exact time the next image change is due (computed from the current theme's image lists and the sun position) and re-arms after every change — no polling. A safety-interval job (default 600 s, `scheduling.safety_interval`) catches astral failures and config edits
- **Interval (legacy model)**: runs every `scheduling.cycle_interval` seconds (default 60), re-applying the time-appropriate image and performing the daily shuffle when the local date changes
```

- [ ] **Step 4: Update the two time-related FAQ answers**

Replace the answer to **Q: How does time-of-day selection work?** with:

```markdown
A: The app uses the `astral` Python library to calculate accurate sunrise/sunset times for your location. By default (the sun-position model, `suntime_model: "sun"`) it positions images by where the sun actually is — sunrise/day images run sunrise→sunset, sunset/night images run sunset→sunrise. With `suntime_model: "legacy"` it uses the old fixed clock slots instead (see Time-of-Day Categories).
```

Replace the answer to **Q: Can I customize the time ranges?** with:

```markdown
A: In the default sun-position model the ranges follow your location's real sunrise/sunset times and adjust seasonally — there are no fixed times to edit; change your location in the GUI to update them. In the legacy model (`suntime_model: "legacy"`) the slots are fixed clock times (06:30 / 09:30 / 16:30 / 19:30).
```

- [ ] **Step 5: Update the Running Tests count**

In `## Development → Running Tests`, update the stale test-count sentence ("134 tests cover ...") to:

```markdown
334 tests cover config, time detection, scheduling, theme import validation, and wallpaper changes.
```

- [ ] **Step 6: Add the changelog entry**

In `## Changelog`, insert a new section above `### Version 1.1.0` and drop "(Current)" from the 1.1.0 heading:

```markdown
### Version 1.2.0 (Current)
- **Sun-position time model is now the default** (`scheduling.suntime_model: "sun"`). **Visible behavior change:** transition images now change at times derived from the actual sun position — up to ~30–75 minutes earlier or later than the old fixed slots, varying with season and location. Configs that explicitly set `suntime_model` are untouched; to keep the old behavior set `scheduling.suntime_model: "legacy"` in `~/.config/kwallpaper/config.json` (or Settings → Time Model in the GUI)
- **Event-driven scheduling** — the scheduler arms a one-shot job at the exact next image-change time instead of polling every 60 s; a safety-interval job (default 600 s, `scheduling.safety_interval`) covers astral failures and config edits
- **Strict theme import validation** — importing a theme whose `theme.json` references missing image files is now rejected at import time with a message listing every missing image (previously this was only discovered at wallpaper-change time, when the selection wrapped around to a wrong image)
- **GUI** — Time Model toggle (Settings) and Schedule Preview table (Scheduler tab) showing the next 12 image changes
- **Shared image discovery** — selection and import validation now use one file-mapping implementation (`themes.image_files_for`), so a theme that passes import always selects the image its `theme.json` says it should

### Version 1.1.0
```

- [ ] **Step 7: Bump the version in `setup.py`**

Change:

```python
    version="1.0.3",
```

to:

```python
    version="1.2.0",
```

(The metainfo and flatpak manifest carry no version field — nothing to change there.)

- [ ] **Step 8: Commit**

```bash
git add README.md setup.py
git commit -m "docs: document sun-model default, import validation; changelog 1.2.0"
```

---

### Task 4: Full-suite verification + fresh-install end-to-end check

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

```bash
python3 -m pytest tests/ -q
```

Expected: **334 passed, 0 failed** (321 Phase-3 baseline + 5 Task-1 tests + 8 Task-2 tests).

- [ ] **Step 2: Fresh-install default check (clean HOME)**

```bash
export HOME=$(mktemp -d)
python3 -c "from kwallpaper.config import load_config, DEFAULT_CONFIG_PATH; print(load_config(str(DEFAULT_CONFIG_PATH))['scheduling']['suntime_model'])"
```

Expected output: `sun` — a fresh install (no config file) gets the sun model, and the auto-created config file contains `"suntime_model": "sun"`.

- [ ] **Step 3: Explicit-legacy escape hatch check**

```bash
python3 - <<'EOF'
import json, os
p = os.path.join(os.environ["HOME"], ".config/kwallpaper/config.json")
cfg = json.load(open(p))
cfg["scheduling"]["suntime_model"] = "legacy"
json.dump(cfg, open(p, "w"), indent=2)
from kwallpaper.config import load_config
print(load_config(p)["scheduling"]["suntime_model"])
EOF
```

Expected output: `legacy` — an explicit value survives a load cycle.

- [ ] **Step 4: Import validation end-to-end (CLI)**

Using one complete and one deliberately broken theme archive (a broken one is any theme whose `theme.json` references an image number with no matching file, e.g. `dayImageList: [7]` with only 5 images):

```bash
python3 wallpaper_cli.py themes add /path/to/complete-theme.ddw
# expect: "Added theme: ..." and exit 0
python3 wallpaper_cli.py themes add /path/to/broken-theme.ddw
echo "exit code: $?"
```

Expected for the broken theme: exit code `1` and stderr beginning `Error: Theme '<name>' references image file(s) that do not exist:` followed by one `  - <category> image <n>` line per missing image. Also confirm no partial theme directory was created: `ls ~/.config/kwallpaper/themes/` shows no entry for the broken theme.

- [ ] **Step 5: Sun-model selection end-to-end**

```bash
python3 -c "
from kwallpaper.selection import select_image_for_time_cli
print(select_image_for_time_cli('/path/to/installed-theme-dir', None))"
```

Expected: a real image path from the theme, chosen via the sun-position model (the config from Step 2/3 has `suntime_model` set; with `"sun"`, the routed sun branch in `select_image_for_time_cli` is taken). Cross-check with the schedule preview: `python3 -c "from kwallpaper.image_schedule import schedule_for_config; [print(r) for r in schedule_for_config(None, start=None)[:3]]"` — the first entry's change time should be consistent with the selected image's position.

- [ ] **Step 6: Commit (only if any fixes were needed during verification)**

```bash
git add -A
git commit -m "phase 4: verification fixes"
```

If no fixes were needed, skip this step.

---

### Task 5 (OPTIONAL — requires explicit user confirmation): Remove the legacy time model

> **STOP — this task is gated.** It is **not** required for Phase 4 completion. Do not start it unless the user explicitly confirms. Before touching any code, ask:
>
> > "Phase 4 is complete and the sun model is the default. Do you want me to also remove the legacy time model entirely? This deletes the fixed-slot code paths and their tests and removes the `suntime_model` config option — users would no longer be able to opt out of the sun model."
>
> If the user does not explicitly say yes, **skip this task**, note that in the phase summary, and stop at Task 4.

**Scope** (re-verify each reference against the actual post-Phase-4 tree at execution time; delete a symbol only when it has zero remaining references; this mirrors the roadmap's Phase 5 "remove legacy model paths once sun is proven in the field"):

- [ ] **Step 1 (only after explicit user confirmation): Confirm the gate with the user** — record the user's explicit yes before any code change.

- [ ] **Step 2: Remove legacy-only code paths**

  - `kwallpaper/suntime.py` — remove legacy-only functions, e.g. `detect_time_of_day_for_time`, `detect_time_of_day_for_date`, `detect_time_of_day_with_backup`, `detect_time_of_day`, `_detect_time_of_day`, `time_of_day_for`, `image_index_for`, and `image_period` / `_night_now_for_pos` **only if** `kwallpaper/solarsegments.py` does not use them (check first).
  - `kwallpaper/selection.py` — make the sun path unconditional in `select_image_for_time_cli` (drop the `suntime_model` routing and the legacy branch); rewrite `select_image_for_specific_time` on top of `solarsegments.image_at` for the requested HH:MM (it is currently legacy-only); remove `_pick_image_list` and the legacy-only `select_image_for_time` test wrapper if unreferenced.
  - `kwallpaper/scheduler.py` — drop the legacy interval branch in `start()` (the sun wiring becomes unconditional; keep the safety-interval job) and remove the `suntime_model` key from `_get_config`.
  - `kwallpaper/config.py` — remove `suntime_model` from `_default_config()`.
  - `kwallpaper/image_schedule.py` — drop the model branch in `schedule_for_config` (sun path only).
  - `wallpaper_gui.py` — remove the Time Model toggle from `SettingsPage` and the `suntime_model` read in `_load()`.

- [ ] **Step 3: Remove the legacy tests**

  Delete the legacy-model tests: the legacy quirk tests in `tests/test_suntime.py`, the legacy routing tests in `tests/test_selection_routing.py`, the legacy interval tests in `tests/test_scheduler.py`, and `test_load_config_explicit_legacy_preserved` in `tests/test_config.py`. Update any remaining test that sets `suntime_model` explicitly.

- [ ] **Step 4: Docs**

  README: remove the "Legacy fixed slots" subsection and legacy wording from the FAQ/scheduler sections; add a changelog line under 1.2.0: "Legacy time model removed (`suntime_model` option no longer exists)".

- [ ] **Step 5: Verify**

```bash
grep -rn "suntime_model\|detect_time_of_day_for_time\|image_index_for" kwallpaper/ wallpaper_gui.py tests/ | grep -v __pycache__
# expect: no hits
python3 -m pytest tests/ -q
# expect: all pass
python3 wallpaper_cli.py --help
# expect: CLI imports cleanly
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "remove legacy time model (user-confirmed)"
```

---

## Verification

Run after all required tasks (1–4) are complete:

1. **Full test suite**: `python3 -m pytest tests/ -q` → **334 passed, 0 failed** (321 Phase-3 baseline + 5 Task-1 tests + 8 Task-2 tests).
2. **Fresh install uses sun**: in a clean `HOME`, `load_config` returns `scheduling.suntime_model == "sun"` (Task 4, Step 2).
3. **Explicit legacy preserved**: a config with `"suntime_model": "legacy"` still loads as `"legacy"` (Task 1 tests; Task 4, Step 3).
4. **Broken theme rejected at import**: `wallpaper_cli.py themes add broken.ddw` exits 1, prints every missing image, and leaves no partial theme directory (Task 4, Step 4).
5. **Complete theme accepted**: import succeeds and `select_image_for_time_cli` returns a real image via the sun model (Task 4, Step 5).
6. **Docs**: README documents the new default, the ~30–75 minute visible behavior change, and the `suntime_model: "legacy"` escape hatch; changelog has a 1.2.0 entry; `setup.py` is at 1.2.0.
7. **Roadmap status**: Phase 4 (final required phase) complete. Remaining roadmap items are optional only: Task 5 (legacy removal, user-gated) and the Phase 5 extras (theme editor, per-theme model override, more schedule preview features).

## Phase boundary health note

After Phase 4, the app is feature-complete against the roadmap's required scope: the sun-position model is the default and end-to-end (config → scheduler → selection → GUI), the legacy model remains a fully supported explicit opt-out, broken themes are rejected at import time with an actionable message, and the docs/changelog describe the visible behavior change. The codebase should be at **334 passing tests** (321 + 13 new), with the only remaining work being the optional, user-gated legacy removal (Task 5) and the optional Phase 5 extras. Do not start Task 5 or any Phase 5 item without explicit user confirmation.

#!/usr/bin/env python3
"""
kWallpaper theme discovery, extraction, import/delete, and thumbnails.
"""

import json
import logging
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from kwallpaper.config import DEFAULT_CACHE_DIR, DEFAULT_THEMES_DIR


# ============================================================================
# THEME DISCOVERY
# ============================================================================

_discover_cache: Optional[Tuple[float, List[Tuple[str, str]]]] = None
_DISCOVER_CACHE_TIMEOUT = 2.0


def discover_themes() -> list:
    """List (name, path) tuples for all themes in the themes directory."""
    global _discover_cache

    themes_dir = DEFAULT_THEMES_DIR

    if not themes_dir.exists():
        raise FileNotFoundError(f"Themes directory not found: {themes_dir}")

    if not themes_dir.is_dir():
        raise PermissionError(f"Themes path is not a directory: {themes_dir}")

    if _discover_cache is not None:
        cache_time, cached_themes = _discover_cache
        if (time.time() - cache_time) < _DISCOVER_CACHE_TIMEOUT:
            return cached_themes

    themes = []

    try:
        for theme_dir in themes_dir.iterdir():
            if not theme_dir.is_dir() or theme_dir.name.startswith('.'):
                continue
            json_files = list(theme_dir.glob("*.json"))
            if json_files:
                themes.append((theme_dir.name, str(theme_dir)))
    except (OSError, PermissionError):
        pass

    themes.sort(key=lambda t: t[0].lower())
    _discover_cache = (time.time(), themes)

    return themes


def resolve_theme_path(theme_path: str, theme_name: Optional[str] = None) -> str:
    """Resolve theme path to absolute path, handling zip files and extracted
    directories.

    Args:
        theme_path: Path to theme (zip file or directory)
        theme_name: Optional theme name for searching in cache

    Returns:
        Absolute path to theme directory

    Raises:
        FileNotFoundError: If theme cannot be resolved
    """
    expanded_path = Path(theme_path).expanduser()

    # If path exists, return it
    if expanded_path.exists():
        return str(expanded_path)

    # If path doesn't exist, try to find in cache
    if theme_name:
        cache_dir = DEFAULT_CACHE_DIR
        matches = list(cache_dir.glob("theme_*"))
        for match in matches:
            try:
                if (match / theme_name).exists():
                    return str(match)
            except (OSError, PermissionError):
                # Skip directories that can't be accessed
                pass

    raise FileNotFoundError(f"Theme not found: {theme_path}")


# ============================================================================
# IMAGE LIST NORMALIZATION
# ============================================================================

def normalize_image_lists(theme_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize image lists to ensure image 1 is in sunrise, not night.

    This handles themes where image 1 is incorrectly placed in nightImageList.
    The script moves image 1 from nightImageList to sunriseImageList if:
    - Image 1 is in nightImageList
    - Image 1 is not already in sunriseImageList
    - NightImageList contains 14, 15, 16 (indicating it's the 24hr Tahoe theme)
    - The night list only contains 14, 15, 16 (and optionally 1)

    Args:
        theme_data: Theme data dictionary with image lists

    Returns:
        Normalized theme data dictionary
    """
    # Make a copy to avoid modifying original
    normalized = dict(theme_data)

    # Get image lists (default to empty lists)
    night_list = list(normalized.get('nightImageList', []))
    sunrise_list = list(normalized.get('sunriseImageList', []))

    # Check if we need to normalize
    has_image_1_in_night = 1 in night_list
    has_image_1_in_sunrise = 1 in sunrise_list
    has_14_15_16_in_night = all(x in night_list for x in [14, 15, 16])

    # Tahoe pattern: night list should only contain 14, 15, 16 (and optionally 1)
    # This prevents normalizing themes with all 16 images in nightImageList
    night_images_only_tahoe_pattern = set(night_list).issubset({14, 15, 16, 1})

    if has_image_1_in_night and not has_image_1_in_sunrise and has_14_15_16_in_night and night_images_only_tahoe_pattern:
        # Remove image 1 from night list
        night_list = [img for img in night_list if img != 1]

        # Add image 1 to sunrise list (in sorted order)
        sunrise_list = sorted(sunrise_list + [1])

        # Update the normalized dictionary
        normalized['nightImageList'] = night_list
        normalized['sunriseImageList'] = sunrise_list

    return normalized


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


# ============================================================================
# THEME EXTRACTION
# ============================================================================

def extract_theme(zip_path: str, cleanup: bool = False,
                  extract_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Extract .ddw wallpaper theme from zip file.

    Args:
        zip_path: Path to .ddw zip file
        cleanup: If True, remove temp directory after extraction
        extract_dir: Optional custom directory to extract to (default: DEFAULT_THEMES_DIR)

    Returns:
        Dictionary containing theme metadata:
        - extract_dir: Path to extracted directory
        - displayName: Theme display name
        - imageCredits: Image credits
        - imageFilename: Image filename pattern
        - sunsetImageList: List of sunset image indices
        - sunriseImageList: List of sunrise image indices
        - dayImageList: List of day image indices
        - nightImageList: List of night image indices

    Raises:
        FileNotFoundError: If theme.json not found in zip
    """
    zip_path_obj = Path(zip_path)

    if not zip_path_obj.exists():
        raise FileNotFoundError(f"Theme not found: {zip_path}")

    # Use custom extract_dir if provided, otherwise use DEFAULT_THEMES_DIR
    target_extract_dir = extract_dir if extract_dir else DEFAULT_THEMES_DIR

    # Create directory with the same name as zip file (without extension)
    extract_dir = target_extract_dir / zip_path_obj.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract zip file
        with zipfile.ZipFile(str(zip_path_obj), 'r') as zf:
            zf.extractall(extract_dir)

        # Find theme.json - first look for any .json file in root, then theme.json recursively
        theme_json_path = None

        # Check root directory for any .json file
        for json_file in extract_dir.glob("*.json"):
            theme_json_path = json_file
            break

        # If not found, search recursively for theme.json
        if not theme_json_path:
            for found_path in extract_dir.rglob("theme.json"):
                theme_json_path = found_path
                break

        if not theme_json_path:
            raise FileNotFoundError("theme.json not found in zip file")

        # Parse theme.json
        with open(theme_json_path, 'r') as f:
            theme_data = json.load(f)

        # Normalize image lists to ensure image 1 is in sunrise, not night
        theme_data = normalize_image_lists(theme_data)
        # Return metadata
        result = {
            "extract_dir": str(extract_dir),
            "displayName": theme_data.get("displayName", "Unknown Theme"),
            "imageCredits": theme_data.get("imageCredits", "Unknown Credits"),
            "imageFilename": theme_data.get("imageFilename", "*.jpg"),
            "sunsetImageList": theme_data.get("sunsetImageList", []),
            "sunriseImageList": theme_data.get("sunriseImageList", []),
            "dayImageList": theme_data.get("dayImageList", []),
            "nightImageList": theme_data.get("nightImageList", [])
        }

        # Cleanup if requested
        if cleanup:
            shutil.rmtree(extract_dir)

        return result

    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        # Clean up on error
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        raise


def import_theme(zip_path: str) -> Dict[str, Any]:
    """Import a theme from a .zip/.ddw file to the themes directory.

    Validates that every image referenced by theme.json exists; a
    rejected import leaves no partial theme behind.  Returns the theme
    metadata dict.  Raises FileNotFoundError, FileExistsError, ValueError,
    or zipfile.BadZipFile on failure.
    """
    source = Path(zip_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Theme not found: {zip_path}")
    if source.suffix not in ('.ddw', '.zip'):
        raise ValueError(f"Not a theme archive: {zip_path}")

    # Extract to a temporary location
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_theme(str(source), cleanup=False,
                               extract_dir=Path(tmpdir))
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
                found = list(extract_dir.rglob("theme.json"))
                if not found:
                    raise FileNotFoundError(
                        "theme.json not found in extracted theme")
                theme_json_path = found[0]
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


def delete_theme(path: str) -> bool:
    """Delete a theme directory.

    Accepts either a full path under the themes directory or a bare theme
    folder name.  Returns True if something was removed.
    """
    theme_path = Path(path).expanduser()
    if not theme_path.is_absolute():
        theme_path = DEFAULT_THEMES_DIR / theme_path
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme not found: {path}")
    # Safety: only delete directories that live inside the themes directory
    try:
        theme_path.resolve().relative_to(DEFAULT_THEMES_DIR.resolve())
    except ValueError:
        raise ValueError(f"Refusing to delete path outside themes dir: {path}")
    shutil.rmtree(theme_path)
    return True


# ============================================================================
# THUMBNAILS
# ============================================================================

def ensure_thumbnail(image_path: str, thumb_size: int = 1080,
                     token=None) -> str:
    """Generate (or reuse) a JPEG preview thumbnail for an image.

    Thumbnails are cached under DEFAULT_CACHE_DIR / "thumbs" / <theme folder
    name> / as <original stem>.thumb.jpg.  A cached thumbnail is reused only
    while it is at least as new as the source image AND at least as large as
    the requested size (so bumping the preview resolution invalidates old
    low-res caches).

    Decoding uses QImageReader.setDecodedSize(): the JPEG decoder downscales
    during the inverse transform (full-resolution sampling quality at a
    fraction of the RAM/decode cost of full-res decode + CPU rescale).

    The heavy decode happens here, so callers should run this in a background
    thread.  Returns the thumbnail path, or the original path if thumbnailing
    fails (the caller can then fall back to loading the original).

    ``token`` is an optional object with a ``version`` attribute (see the
    GUI's ``_LoadToken``).  When provided, the decode and the JPEG write are
    aborted if ``token.version`` changes mid-flight (the user switched
    themes), so abandoned workers stop wasting CPU and disk.
    """
    def _cancelled() -> bool:
        return token is not None and token.version != _start_version

    _start_version = token.version if token is not None else 0
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QImage, QImageReader
        src = Path(image_path)
        thumb_dir = DEFAULT_CACHE_DIR / "thumbs" / src.parent.name
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / (src.stem + ".thumb.jpg")

        if _cancelled():
            return str(src)
        # Reuse a cached thumbnail while it is at least as new as the source
        # AND at least as large as the requested size.  Check the size from
        # the file header (cheap) rather than decoding the whole JPEG just to
        # test isNull() — decoding a 1080p thumbnail on the hot path is the
        # kind of waste this function exists to avoid, and a failed decode
        # must fall through to a re-encode, not silently return the original
        # full-res path (which would make the preview load full-res files).
        if thumb_path.exists() and thumb_path.stat().st_mtime >= src.stat().st_mtime:
            # Check the size from the file header (cheap) rather than
            # decoding the whole JPEG.  QImageReader.size() returns 0x0 for
            # an unreadable file, so a corrupt/empty cache entry falls
            # through to a re-encode.  (QImageReader has no isNull() in
            # PyQt6 — calling it raised AttributeError, which the outer
            # except swallowed, making every cache lookup fail.)
            reader = QImageReader(str(thumb_path))
            sz = reader.size()
            if (sz.width() > 0 and sz.height() > 0
                    and max(sz.width(), sz.height()) >= thumb_size):
                return str(thumb_path)

        reader = QImageReader(str(src))
        if not reader.canRead():
            return str(src)
        src_size = reader.size()
        if src_size.width() <= 0 or src_size.height() <= 0:
            return str(src)
        # Decode directly at target size: full-res sampling quality, no
        # full-res buffer ever materializes (libjpeg IDCT downscaling).
        if src_size.width() > thumb_size or src_size.height() > thumb_size:
            reader.setScaledSize(
                src_size.scaled(thumb_size, thumb_size,
                                Qt.AspectRatioMode.KeepAspectRatio))
        img = reader.read()
        if img.isNull():
            return str(src)
        if _cancelled():
            # Theme switched mid-decode: drop the buffer, don't write.
            return str(src)
        tmp_path = thumb_dir / (src.stem + ".thumb.jpg.tmp")
        if img.save(str(tmp_path), "JPG", 85):
            if _cancelled():
                # Switched while saving: remove the orphaned tmp file.
                tmp_path.unlink(missing_ok=True)
                return str(src)
            tmp_path.replace(thumb_path)
        else:
            if tmp_path.exists():
                tmp_path.unlink()
            return str(src)
        return str(thumb_path)
    except Exception as e:
        logger.debug(f"Thumbnail generation failed for {image_path}: {e}")
        return str(image_path)

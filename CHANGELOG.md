# Changelog

All notable changes to kWallpaper are documented in this file.

## [1.0.4] — WDD sun-position time model (Phases 2–4)

### Added
- **Sun-position time model** (`scheduling.suntime_model: "sun"`) — WDD-style
  segment boundaries (dawn → +6° → −6° → dusk) drive both the scheduler and
  image selection. Now the **default** for new configs; existing configs
  without the field pick it up automatically at load time.
- **Event-driven scheduling** in sun mode: a one-shot `DateTrigger` fires
  exactly at the next segment boundary (re-armed after every cycle), with a
  configurable safety-net interval (default 600 s; the GUI applies changes
  live without a restart) as a fallback.
- **`next_change_time()`** in `solarsegments` and
  `core.next_change_time_for_config()` — the next moment the selected image
  changes, for any config.
- **Skip-if-unchanged wallpaper apply**: the scheduler no longer calls
  `org.kde.plasmawallpaper` when the selected image is unchanged (last
  applied image is persisted in `theme.last_applied_image`).
- **GUI**: Settings → Time model selector (legacy / sun-position) with hot
  reload of a running scheduler, and a 24-hour schedule preview widget in
  the Themes tab (image windows, thumbnails, current-time marker).
- **Strict theme import validation**: imports whose `theme.json` references
  missing image files are rejected with an error listing every missing
  image; rejected imports leave no partial theme behind.
- `themes.image_files_for()` — single source of truth for image discovery,
  shared by selection and import validation.

### Changed
- Default `scheduling.suntime_model` flipped from `"legacy"` to `"sun"`.
  Explicit `"legacy"` values in existing configs are preserved.
- Theme import (GUI and CLI) now validates referenced images before
  committing to the themes directory.

### Performance
- **Preview memory cut from ~925MB to ~200MB**: shared disk thumbnail
  cache no longer reuses much-larger cached thumbnails (2× reuse rule),
  schedule-preview thumbnails are downscaled to display size, and the
  crossfade preview uses a 48MB decoded-pixmap budget with a bounded
  widget-pixmap cache, no oversampling headroom, and cache release while
  the Themes tab is hidden.
- **Seamless slideshow under the small budget**: the eager path
  re-requests images whose decoded pixmap was LRU-evicted, one step
  before display, so the preview never flashes "Loading preview…"
  between images.
- **Resize recovery**: if a raw pixmap is evicted while the preview is
  shown, the current image re-loads in under a second instead of staying
  stuck on "Loading preview…".
- Schedule-preview thumbnails use a cover crop so they fill their
  squares instead of letterboxing.

### Notes
- The legacy fixed-offset model remains fully supported; select it in
  Settings → Time model.

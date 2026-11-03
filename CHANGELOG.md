# Changelog

All notable changes to KOMPRESS-OR.CLI are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-03

### Added

- **Interactive Rich main menu** with nine working options: Compress Image,
  Batch Compress, Target Size, Convert Format, Resize Image, Image Analyzer,
  Photography Mode, Settings, Exit. No placeholders; every option performs
  real work and returns to the menu.
- **Single-image compression** (`engine/compression.py`): presets
  (fast/balanced/small/max), custom quality 1–100, JPEG quality, PNG
  optimize + compress level 9, WebP quality/method, AVIF quality when the
  encoder exists; before/after sizes, reduction percentage and duration.
- **Batch compression** (`engine/batch.py`): sequential processing,
  Rich progress bar, per-file failure isolation, duplicate-filename safety,
  totals (original/output/saved/overall %), UTF-8 CSV report with unique
  output naming.
- **Target-size search** (`engine/target_size.py`): bounded binary search
  over quality (min..95, ≤8 iterations), honest achieved/not-reached
  reporting, explicit refusal for formats without quality-to-size control
  (PNG/BMP/TIFF) with an explanation of the limitation.
- **Format conversion** (`engine/conversion.py`): JPEG, PNG, WebP, TIFF, BMP
  and conditional AVIF with encoder availability probing, transparency
  flattening onto a configurable background (default `#FFFFFF`), metadata
  preservation preference.
- **Resize engine** (`engine/resize.py`): width / height / fit-box /
  percentage / exact dimensions, aspect-ratio lock, six resampling methods,
  validation against zero, negative and absurd dimensions.
- **Image analyzer** (`engine/analyzer.py`): filename, path, size,
  dimensions, aspect ratio, format, color mode, bit depth, EXIF/ICC,
  transparency, animation, plus a *measured* in-memory re-encode probe for
  the optimization estimate (nothing is invented).
- **Photography mode** (`engine/photography.py`): high-quality JPEG,
  balanced photography, web photography (WebP) and archive TIFF presets with
  honest quality statements.
- **Persistent settings** (`config/settings.py`): JSON config in the
  platform config directory, defaults for output dir/format/quality/preset/
  background/metadata/interface, validation, reset-to-default, atomic saves
  and safe recovery from missing/corrupt/mistyped files (quarantined to
  `settings.json.corrupt`).
- **File picker abstraction** (`utils/file_picker.py`): Zenity on Linux,
  Tkinter on Windows/macOS, multi-selection, correct cancellation handling,
  validation of picked paths (spaces and non-ASCII supported), automatic
  fallback to manual comma-separated path input, `KOMPRESS_NO_PICKER=1`
  opt-out, picker disabled when stdin is not an interactive TTY.
- **Safety layer** (`utils/filesystem.py`, `utils/metadata.py`): EXIF
  orientation applied to pixels, ICC/EXIF forwarding with encoder-rejection
  fallback, temporary files + atomic rename, output integrity checks,
  source-overwrite protection, unique output naming, pathlib everywhere.
- **Runtime format detection** (`utils/format_support.py`): encoders are
  probed by performing a real encode; unavailable formats are never
  advertised and produce actionable error messages with alternatives.
- **CLI entry points**: `kompressor` and `kompress-or` scripts plus
  `python -m kompressor`; `--version` and `--check` flags; root-level
  `./kompressor` and `./run-tests` launcher scripts that use the project
  virtual environment automatically (no activation required).
- **Test suite** (79 tests): compression, PNG optimization, WebP/AVIF
  detection, conversion, transparency, resizing, target-size, batch,
  duplicate names, invalid/unsupported input, missing encoders (mocked),
  metadata and EXIF orientation, settings load/corruption/reset, output
  integrity, source protection, file-picker cancellation and fallback
  (mocked system commands), analyzer and photography presets.
- **Documentation**: README, INSTALLATION (CachyOS/Linux + Windows),
  USAGE (all menu options), CONTRIBUTING, this changelog.

### Security & privacy

- No telemetry, no network access, no cloud processing, no automatic
  downloads, no background services.
- Source images are never modified; output never overwrites existing files.

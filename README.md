<<<<<<< HEAD
# kompress-or.cli
=======
# KOMPRESS-OR.CLI

**Offline-first image compression and optimization toolkit for the terminal.**

KOMPRESS-OR.CLI is a Python CLI application that compresses, converts, resizes
and analyzes images using Pillow, with a polished Rich-based interactive menu.
It works completely offline: no telemetry, no cloud processing, no external
APIs, no automatic downloads, no background services. Your images never leave
your machine, and the originals are never modified.

- **Python:** 3.14+
- **Engines:** Pillow (image), Rich (interface)
- **Platforms:** CachyOS / other Linux distributions, Windows 10, Windows 11
- **License:** MIT

## Features

| # | Menu item | What it does |
|---|-----------|--------------|
| 1 | Compress Image | Single-image compression with presets (fast / balanced / small / max) or custom quality; before/after sizes, reduction %, duration |
| 2 | Batch Compress | Sequential multi-file compression with progress bar, per-file failure isolation, duplicate-name safety, totals and CSV report |
| 3 | Target Size | Bounded binary search over quality to hit a KB/MB target — reports honestly whether the target was reached |
| 4 | Convert Format | JPEG / PNG / WebP / AVIF* / TIFF / BMP conversion with transparency flattening and metadata handling |
| 5 | Resize Image | Width, height, exact box, percentage; aspect-ratio lock; six resampling methods |
| 6 | Image Analyzer | Dimensions, aspect ratio, format, color mode, bit depth, EXIF/ICC/transparency, and a *measured* optimization probe |
| 7 | Photography Mode | Quality-first presets: high-quality JPEG, balanced photography, web photography, archive TIFF |
| 8 | Settings | Persistent per-user configuration (output dir, default format/quality/preset, background color, metadata preference) with safe corruption recovery |
| 9 | Exit | Clean shutdown |

\* AVIF is offered only when the running Pillow build actually ships an AVIF
encoder — availability is probed at runtime by performing a real encode.

## Supported formats

**Input:** JPEG/JPG, PNG, WebP, BMP, TIFF
**Output:** JPEG, PNG, WebP, TIFF, BMP, and AVIF (encoder availability detected at runtime)

Handled color modes: RGB, RGBA, grayscale (L/LA), palette (P), CMYK where the
encoder supports it, plus transparency and EXIF-orientation-aware inputs.

## Installation

```bash
git clone <repository-url> kompressor && cd kompressor   # folder name may vary
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"            # or: pip install -r requirements.txt
```

Full platform instructions: [INSTALLATION.md](INSTALLATION.md).

## Quick start

```bash
./kompressor               # launch the interactive menu (no activation needed)
./kompressor --check       # show which encoders are available on this machine
./kompressor --version
./run-tests                # run the test suite
```

Equivalent with an activated virtual environment:

```bash
source .venv/bin/activate
kompressor                 # or: python -m kompressor
kompressor --check
pytest
```

Then pick option `1`, choose a file (graphical picker on Linux/Windows, or
type a path), pick a preset and a format — the result appears with before/
after sizes. Output files are written next to the source (or to your
configured output directory) with a unique name; **the original file is never
overwritten**.

## Example session

```
╭──────────────────────────────────────────────╮
│ KOMPRESS-OR.CLI v1.0.0                       │
│ Offline image compression toolkit            │
╰──────────────────────────────────────────────╯
  1    Compress Image
  ...
Choose an option (1-9): 1
Enter image path (or 'p' to pick graphically, 'c' to cancel): photo.png
Compression preset (2, 'b' to go back):
Output format (1, 'b' to go back):
OK photo.png -> photo.jpg: 75.28 KiB -> 18.08 KiB (76.0% smaller) in 0.01s
```

## Testing

```bash
pytest
```

The suite builds all test images programmatically (no personal files), and
covers compression, conversion, transparency, resizing, target-size search,
batch/duplicate handling, invalid input, encoder detection, metadata and
EXIF orientation, settings corruption recovery, output integrity, source
protection and file-picker fallback (with mocked system commands).

## Documentation

- [INSTALLATION.md](INSTALLATION.md) — platform setup and troubleshooting
- [USAGE.md](USAGE.md) — every menu option with practical examples
- [CHANGELOG.md](CHANGELOG.md) — actual changes
- [CONTRIBUTING.md](CONTRIBUTING.md) — development workflow and standards

## Limitations (honest list)

- **Target size** works for JPEG, WebP and AVIF (quality-driven encoders).
  PNG/BMP/TIFF have no reliable quality-to-size control, so those formats are
  refused with an explanation instead of a fake result. Targets smaller than
  what the minimum quality can produce are reported as *not reached*.
- **AVIF** depends on your Pillow build; when the encoder is missing the app
  says so and offers the formats that do work.
- **Animated images** (GIF/WebP/APNG): only the first frame is processed;
  animations are not preserved.
- **Metadata:** EXIF orientation is always baked into the pixels. EXIF/ICC
  payloads are forwarded to encoders that accept them; when an encoder
  rejects a metadata payload the limitation is reported, not hidden.
- **JPEG output** cannot store transparency; transparent pixels are
  flattened onto a configurable background color (default white).
- File picking uses Zenity on Linux and Tkinter on Windows when available;
  manual path input always works, even with no graphical environment
  (`KOMPRESS_NO_PICKER=1` disables graphical pickers).

## Principles

Offline-first · no telemetry · no cloud · no automatic downloads · originals
never modified · sequential, low-memory processing suitable for low-end
hardware (e.g. Intel Celeron N4020 / 8 GB RAM) · no fake or dummy
functionality — every menu item does real work.
>>>>>>> 547105f (Initial commit: KOMPRESS-OR.CLI v1.0.0)

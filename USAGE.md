# Usage

Launch the application:

```bash
kompressor
# or
python -m kompressor
```

You are greeted by the main menu:

```
  1    Compress Image
  2    Batch Compress
  3    Target Size
  4    Convert Format
  5    Resize Image
  6    Image Analyzer
  7    Photography Mode
  8    Settings
  9    Exit
```

**Input conventions**

- Enter the number of a menu item and press Enter.
- At file prompts you can:
  - type one path, or several paths separated by commas;
  - type `p` to open the graphical picker (Zenity on Linux, Tkinter on
    Windows) when a display is available;
  - type `c` to cancel and return to the menu.
- At option prompts press Enter to accept the displayed default, or type a
  number. Type `b` at any prompt to go back.
- Press `Ctrl+C` to cancel the current flow; `Ctrl+D` exits.

**Output safety rules (all features)**

- The source image is never modified or overwritten.
- Output files get a unique name (`photo.jpg`, `photo_1.jpg`, `photo_2.jpg`,
  …) so existing files are never silently replaced.
- Output is written via a temporary file + atomic rename; a failed run never
  leaves a half-written image behind.

---

## 1. Compress Image

Compresses a single image.

```
Choose an option (1-9): 1
Enter image path (or 'p' to pick graphically, 'c' to cancel): ~/Pictures/holiday.png
Compression preset (2, 'b' to go back):
  1. fast - Fast, larger files (quality 70)
  2. balanced - Good balance (default) (quality 85) (default)
  3. small - Smaller files, visible loss possible (quality 65)
  4. max - Near-transparent quality, large files (quality 95)
  5. Custom quality
Output format (1, 'b' to go back): 1
Current output directory: same folder as the source image
Press Enter to keep ... :
OK holiday.png -> holiday.jpg: 4.10 MiB -> 780.12 KiB (81.4% smaller) in 0.62s
```

- **Presets** set JPEG/WebP quality; choose `Custom quality` to type any
  value from 1–100.
- **Output format** lists only formats whose encoder is verified on your
  machine. If AVIF is missing you get an explanation instead of a crash.
- **Output directory**: Enter keeps the default (Settings → default output
  directory, empty = next to the source image), type a path to change it,
  `p` to pick a folder graphically, `s` to force "next to the source".
- The summary shows before/after size, saved bytes, percentage and duration,
  plus what happened to EXIF/ICC metadata.

## 2. Batch Compress

Compresses many images sequentially (one at a time — this keeps memory low
on weak hardware).

```
Choose an option (1-9): 2
Enter image paths separated by commas ... : a.png,b.png,c.png
Output format (1, 'b' to go back): 1
Quality (1-100) (default 85 ...): 75
Process 3 file(s) now? (Y/n):
  Compressing c.png ━━━━━━━━━━━━━━━━━ 100%
  Processed: 3 file(s)
  Succeeded: 3   Failed: 0
  Total original size: 6.20 MiB
  Total output size:  1.11 MiB
  Total space saved:  5.09 MiB (82.1%)
Write a CSV report? (Y/n): y
CSV path (output/batch_report.csv): output/batch_report.csv
```

- Files may come from different directories.
- **Failures are isolated**: a corrupt file is reported and skipped; the
  rest of the batch still runs.
- **Duplicate names** from different folders never collide
  (`photo.png` in two folders → `photo.jpg` and `photo_1.jpg`).
- The CSV report has one row per file: source, status, error, sizes, saved
  bytes, reduction %, output path. A second report with the same name gets a
  new number instead of overwriting.

## 3. Target Size

Ask for a target file size; the app searches for the highest JPEG/WebP/AVIF
quality whose output fits.

```
Choose an option (1-9): 3
Enter image path ... : photo.jpg
Target size: 300
Unit: 1 (KB)
Output format: 1 (JPEG)
Minimum acceptable quality: 30
Target reached
  Target: 300.00 KiB   Actual: 268.41 KiB   Quality: 74   Iterations: 5
  Output: /home/me/photo_1.jpg
```

- The search is **bounded**: quality is bracketed between the minimum and
  95, at most 8 iterations — no endless loops.
- If even the minimum quality cannot fit the target, you get
  **"Target NOT reached"** plus the closest achievable file and an
  explanation — success is never faked.
- PNG/BMP/TIFF are refused with an explanation: their encoders have no
  reliable quality knob, so a size target cannot be guaranteed.

## 4. Convert Format

```
Choose an option (1-9): 4
Enter image path ... : logo.png
Output format (1, 'b' to go back): 1        # JPEG
Current output directory: ...
Change the background color? (y/N): y       # only for JPEG/BMP targets
Hex color (e.g. #FFFFFF): #000000
Preserve metadata (EXIF/ICC) ...? (Y/n):
OK logo.png (PNG) -> logo.jpg (JPEG): 12044 -> 9120 bytes
  Note: EXIF orientation applied to pixels; EXIF preserved.
  Note: Transparency (if any) was flattened onto the chosen background.
```

- Input selection, output format, output directory, transparency handling
  and metadata handling are all explicit.
- Transparent → JPEG/BMP flattens alpha onto the chosen background
  (default from Settings, white).
- Transparent → PNG/WebP/AVIF keeps the alpha channel.

## 5. Resize Image

```
Choose an option (1-9): 5
Enter image path ... : photo.png
Resize mode:
  1. Set width (aspect ratio kept)
  2. Set height (aspect ratio kept)
  3. Set width x height (fit inside box)
  4. Percentage of original size        <- default
  5. Exact width x height (aspect ratio may change)
Percent of original (default 50): 60
Resampling method: 1 (lanczos - high quality)
Output format: 1
OK photo.png: 160x160 -> 96x96 (75.28 KiB -> 5.60 KiB) in 0.01s
```

- Zero, negative, non-numeric and absurd dimensions are rejected with a
  clear message; images can never be resized to 0×0.
- Methods: `lanczos` (default, best quality), `bicubic`, `bilinear`,
  `nearest`, `box`, `hamming`.

## 6. Image Analyzer

```
Choose an option (1-9): 6
Enter image path ... : photo.jpg
┌─ Analysis: photo.jpg ─────────────────┐
│ File size   1.10 MiB                  │
│ Dimensions  4032 x 3024 px            │
│ Aspect ratio 4:3                      │
│ Format      JPEG                      │
│ Color mode  RGB                       │
│ Bit depth   8 bits per channel (24-bit)│
│ EXIF        yes                       │
│ ICC profile yes                       │
│ Transparency no                       │
└───────────────────────────────────────┘
Optimization potential: Probe: re-encoding at JPEG quality 80 would give ...
```

Everything shown is read from the file. The "optimization potential" is a
**measured probe**: the image is re-encoded in memory with a standard
setting and the real byte count is reported — no invented percentages. If no
meaningful probe exists for a format, the app says so.

## 7. Photography Mode

Quality-first presets for photographic images:

| Preset | Output | Quality | Intent |
|---|---|---|---|
| High-quality JPEG | JPEG | 96, 4:4:4 chroma, progressive | prints, further editing |
| Balanced photography | JPEG | 88, 4:2:0, progressive | everyday sharing |
| Web photography | WebP | 82, effort 6 | websites, small but sharp |
| Archive-oriented output | TIFF (deflate) | lossless-ish | long-term storage |

```
Choose an option (1-9): 7
Enter image path ... : DSC_0042.jpg
Photography preset (2, 'b' to go back): 2
OK DSC_0042.jpg -> DSC_0042.jpg: ...
```

EXIF and ICC profiles are kept where the encoder supports them. The app
states plainly that presets *optimize for* photographic content — they cannot
guarantee identical visual quality on every image.

## 8. Settings

```
Choose an option (1-9): 8
┌─ Settings (~/.config/kompressor/settings.json) ─┐
│ Default output directory        (same as source)│
│ Default format                  JPEG            │
│ Default JPEG quality            85              │
│ Default preset                  balanced        │
│ Transparent->JPEG background    #FFFFFF         │
│ Preserve metadata               yes             │
│ Confirm before batch            yes             │
└─────────────────────────────────────────────────┘
What to change (9, 'b' to go back):
```

- Settings are stored as JSON in the platform config directory:
  - Linux: `~/.config/kompressor/settings.json` (honors `XDG_CONFIG_HOME`)
  - Windows: `%APPDATA%\kompressor\settings.json`
  - macOS: `~/Library/Application Support/kompressor/settings.json`
- Invalid or corrupted settings files are quarantined as
  `settings.json.corrupt` and replaced with safe defaults — the app never
  crashes over a bad config.
- Option 7 resets everything to defaults.

## 9. Exit

Saves nothing extra, closes cleanly (`Ctrl+D` or `Ctrl+C` at the menu also
works).

---

## Headless / scripted use

- Graphical pickers only activate on an interactive terminal; with piped
  input the app goes straight to manual path entry.
- Set `KOMPRESS_NO_PICKER=1` to disable graphical pickers everywhere.
- `kompressor --check` prints encoder availability without starting the UI.

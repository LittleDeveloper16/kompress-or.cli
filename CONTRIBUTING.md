# Contributing

Thanks for helping improve KOMPRESS-OR.CLI. This project values
correctness, honesty (no fake features), offline operation and a gentle
dependency footprint.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
./run-tests                        # must pass before you push (or: pytest)
```

Run the app during development:

```bash
./kompressor                       # uses .venv automatically
# or, with the venv activated:
python -m kompressor
kompressor --check                 # encoder availability
```

## Project layout

```
src/kompressor/
├── main.py            # entry point, --version / --check
├── cli/
│   ├── menu.py        # main menu + all feature flows
│   └── display.py     # Rich console helpers
├── engine/
│   ├── compression.py # single-image core (shared by other engines)
│   ├── batch.py       # sequential batch + CSV report
│   ├── target_size.py # bounded quality search
│   ├── conversion.py  # format conversion
│   ├── resize.py      # resizing + validation
│   ├── analyzer.py    # inspection + measured probe
│   └── photography.py # quality presets
├── utils/
│   ├── file_picker.py # Zenity / Tkinter / manual fallback
│   ├── filesystem.py  # unique naming, atomic save, size formatting
│   ├── metadata.py    # EXIF orientation, EXIF/ICC handling
│   └── format_support.py  # runtime encoder detection
└── config/settings.py # persistent JSON settings
tests/                 # pytest suite (programmatic images only)
```

## Coding standards

- **Python 3.14+**, type hints on public functions, `from __future__ import
  annotations` in modules using modern syntax.
- **pathlib** for filesystem work; never string-concatenate paths.
- **No network access, no telemetry, no new heavy dependencies.** Core
  dependencies are Pillow and Rich only; a new dependency needs a clear
  technical justification in the PR description.
- **Never modify source images.** Output must go through
  `atomic_save()` (temp file + `os.replace`) and use `unique_path()` so
  existing files are not overwritten.
- **Honest reporting.** Never claim a target was reached unless it was
  measured; never advertise an encoder that was not probed; document
  limitations instead of hiding them.
- **Error handling:** engines return result objects with `ok=False` and a
  human-readable `error`; the menu loop catches unexpected exceptions so
  the app never dies mid-session.
- **Sequential by default.** No multiprocessing; close image resources
  (context managers / `img.close()`); do not hold decoded images longer
  than needed — the app must stay comfortable on a Celeron N4020 with 8 GB
  RAM.
- Keep Rich output readable on ~100-column terminals; avoid decorative
  clutter.

## Testing

- Put tests in `tests/`, one file per area; use the fixtures in
  `conftest.py` (`make_image`, `noisy_jpeg`, `transparent_png`,
  `exif_jpeg`) — **never** commit personal images.
- Mock external commands (`zenity`, `subprocess.run`) for picker tests.
- Run the whole suite: `pytest`. Do not skip or weaken tests to make a
  change pass; fix the code instead.
- New behavior needs a test: bug fixes get a regression test.

## Commit and pull requests

- Do not force-push or rewrite history; do not commit `.venv/`,
  `output/` artifacts, or personal files.
- Update `CHANGELOG.md` with a short entry describing your change.
- Update README/USAGE when user-visible behavior changes.
- Keep pull requests focused: one feature or fix per PR.

## Reporting bugs

Include: OS and Python version, output of `kompressor --check`, the exact
menu steps, the full error message, and whether the file can be shared (or
describe its properties: format, size, color mode). Never attach private
photos without permission.

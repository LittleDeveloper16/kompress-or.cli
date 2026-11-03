# Architecture

## Layering

```
main.py                entry point: argparse (--version/--check), launches the menu
  └── cli/menu.py      interactive flows (prompt -> engine -> Rich result)
        └── cli/display.py        rendering only (panels, tables, prompts)
        └── engine/*             pure logic, no terminal I/O, returns result dataclasses
              └── utils/*        filesystem safety, metadata, format probing, picking
              └── config/*       persistent settings (JSON, corruption-safe)
```

Rules:

1. **Engines never print.** Every engine returns a result object
   (`CompressionResult`, `BatchReport`, `TargetSizeResult`, …) carrying
   `ok`, `error`, sizes and notes. This keeps them unit-testable and lets
   the CLI stay thin.
2. **The menu never crashes.** `run_menu()` wraps every flow in
   try/except; unexpected errors become an error panel and return to the
   menu.
3. **Safety lives in `utils/filesystem.py`**: `validate_source()`,
   `unique_path()`, `output_path_for()`, `atomic_save()` (temp file +
   `os.replace` + integrity check + cleanup on failure) and
   `is_protected_pair()` (source-overwrite guard). Engines must go through
   these helpers.
4. **Encoder availability is probed, not assumed**
   (`utils/format_support.py`): a tiny real encode is performed per format
   and cached; `require_output_format()` raises `FormatError` with the
   available alternatives when a format is missing.
5. **Metadata policy** (`utils/metadata.py`): EXIF orientation is baked
   into pixels (tag reset to 1); EXIF/ICC bytes are forwarded to encoders
   that accept them; encoder rejection is caught and reported in the
   result's `notes` rather than silently ignored.
6. **Settings** are merged over `DEFAULTS` on load, so unknown keys, wrong
   types and corruption can never break the app; corrupt files are
   quarantined to `settings.json.corrupt`.

## Processing model

Sequential, single-image-at-a-time processing (batch = loop). No worker
pools, no resident decoded images: each image is opened, processed, saved
and closed before the next one starts — deliberate for low-end hardware
(Celeron N4020, 8 GB RAM) and for deterministic memory use.

## Data flow (compression as an example)

```
menu: pick file + preset + format + output dir
  -> compression.compress_image()
       validate_source -> require_output_format -> prepare_image
         (decode, EXIF orientation, extract EXIF/ICC)
       -> convert_mode_for(target format, background)
       -> output_path_for (unique, never existing)
       -> build_save_kwargs -> _save_with_metadata_fallback
            -> atomic_save (tmp + fsync-less rename + integrity check)
  <- CompressionResult {sizes, elapsed, metadata state, notes}
menu: render sizes / percentage / metadata summary
```

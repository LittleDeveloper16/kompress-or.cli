"""Cross-platform file picking with graceful fallback to manual input.

Resolution order:
  Linux  : Zenity (if installed) -> manual terminal input
  Windows: Tkinter file dialog (if importable) -> manual terminal input

Every path is validated after selection.  Cancellation returns an empty
list instead of raising, and the caller may fall back to manual input.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from kompressor.utils.filesystem import validate_source

ZENITY_TIMEOUT = 600  # seconds; guards against a hung dialog on headless hosts


class PickerUnavailable(Exception):
    """The platform picker could not be used at all."""


def picker_enabled() -> bool:
    """Graphical pickers are only appropriate on an interactive terminal.

    Set KOMPRESS_NO_PICKER=1 to disable them explicitly (useful on headless
    machines); the manual path input always remains available.
    """
    if os.environ.get("KOMPRESS_NO_PICKER", "").strip() not in ("", "0", "false", "no"):
        return False
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _run_zenity(args: list[str]) -> list[Path] | None:
    zenity = shutil.which("zenity")
    if not zenity:
        raise PickerUnavailable("zenity not found")
    cmd = [zenity, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=ZENITY_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PickerUnavailable(f"zenity failed to run: {exc}") from exc
    if proc.returncode != 0:
        # Exit code 1 = user cancelled; anything else = dialog error.
        return None
    paths = [line for line in proc.stdout.splitlines() if line.strip()]
    return [Path(p) for p in paths]


def _run_tkinter(multiple: bool) -> list[Path] | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # noqa: BLE001 - tkinter may be missing or broken
        raise PickerUnavailable(f"tkinter unavailable: {exc}") from exc
    try:
        root = tk.Tk()
        root.withdraw()
        root.update()
    except Exception as exc:  # noqa: BLE001 - no display, broken lib
        raise PickerUnavailable(f"tkinter display unavailable: {exc}") from exc
    try:
        if multiple:
            selection = filedialog.askopenfilenames(title="Select images")
        else:
            selection = filedialog.askopenfilename(title="Select image")
    finally:
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass
    if not selection:
        return None
    if isinstance(selection, (list, tuple)):
        return [Path(p) for p in selection]
    return [Path(selection)]


def pick_files(multiple: bool = True) -> list[Path] | None:
    """Open a graphical picker.  Returns list of paths, [] on cancel,
    or raises PickerUnavailable when no picker can run."""
    if sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
        return _run_zenity(
            ["--file-selection", "--multiple", "--separator=\n",
             "--title=Select image files"]
            if multiple
            else ["--file-selection", "--title=Select an image file"]
        )
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return _run_tkinter(multiple)
    # Unknown platform: try zenity, then tkinter.
    try:
        return _run_zenity(["--file-selection", "--multiple", "--separator=\n"])
    except PickerUnavailable:
        return _run_tkinter(multiple)


def pick_directory() -> Path | None:
    """Pick a directory graphically; None means cancelled/unavailable."""
    if sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
        try:
            result = _run_zenity(["--file-selection", "--directory", "--title=Select output folder"])
        except PickerUnavailable:
            return None
        return result[0] if result else None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:  # noqa: BLE001
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        choice = filedialog.askdirectory(title="Select output folder")
        root.destroy()
    except Exception:  # noqa: BLE001
        return None
    return Path(choice) if choice else None


def _validate_all(paths: list[Path]) -> tuple[list[Path], list[str]]:
    valid: list[Path] = []
    errors: list[str] = []
    for p in paths:
        try:
            valid.append(validate_source(p))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    return valid, errors


def choose_files(
    prompt_text: str = "Enter path(s), comma-separated (or 'p' to pick graphically, 'c' to cancel):",
    manual_reader=input,
    allow_picker: bool = True,
) -> tuple[list[Path], list[str]]:
    """Interactive file selection with picker and manual fallback.

    Returns (valid_paths, warnings).  Empty list means the user cancelled.
    """
    if allow_picker:
        try:
            picked = pick_files(multiple=True)
        except PickerUnavailable:
            picked = None
        if picked is not None:
            if not picked:  # user cancelled the dialog
                # Fall through to manual input (documented fallback).
                pass
            else:
                valid, errors = _validate_all(picked)
                if valid:
                    return valid, errors
                # Picked files were bad -> fall back to manual input.

    while True:
        raw = manual_reader(prompt_text).strip()
        if raw.lower() in {"c", "cancel", "q", "quit", ""}:
            return [], []
        parts = [seg.strip().strip('"').strip("'") for seg in raw.split(",")]
        parts = [seg for seg in parts if seg]
        if not parts:
            continue
        paths = [Path(seg).expanduser() for seg in parts]
        valid, errors = _validate_all(paths)
        if valid:
            return valid, errors
        if errors:
            print("All provided paths were rejected:")
            for e in errors:
                print(f"  - {e}")


def choose_single_file(
    prompt_text: str = "Enter image path (or 'p' to pick graphically, 'c' to cancel):",
    manual_reader=input,
    allow_picker: bool = True,
) -> Path | None:
    files, _errors = choose_files(prompt_text, manual_reader, allow_picker)
    return files[0] if files else None

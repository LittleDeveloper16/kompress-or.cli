"""Persistent application settings.

Stored as JSON in the platform configuration directory:
  Linux   : $XDG_CONFIG_HOME/kompressor/settings.json  (default ~/.config)
  Windows : %APPDATA%\\kompressor\\settings.json
  macOS   : ~/Library/Application Support/kompressor/settings.json

Missing, invalid or corrupted files are handled safely: a corrupted file is
renamed to ``settings.json.corrupt`` and replaced with defaults.
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

SETTINGS_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "version": SETTINGS_VERSION,
    # Empty string means "next to the source image".
    "output_dir": "",
    "default_format": "JPEG",
    "jpeg_quality": 85,
    "default_preset": "balanced",
    # Background used when a transparent image is written to JPEG/BMP.
    "jpeg_background": "#FFFFFF",
    "preserve_metadata": True,
    "interface": {
        "show_sizes": True,
        "confirm_before_batch": True,
    },
}

VALID_FORMATS = ("JPEG", "PNG", "WebP", "AVIF", "TIFF", "BMP")
VALID_PRESETS = ("fast", "balanced", "small", "max")
VALID_BACKGROUNDS = ("#FFFFFF", "#000000", "#F5F5F5", "#008080")


class SettingsError(Exception):
    """Raised when settings cannot be saved."""


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "kompressor"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "kompressor"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "kompressor"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _merge(defaults: dict, loaded: dict) -> dict:
    """Merge loaded values over defaults, keeping only known keys/types."""
    out = deepcopy(defaults)
    for key, value in loaded.items():
        if key not in defaults:
            continue
        expected = type(defaults[key])
        if key == "interface" and isinstance(value, dict):
            for sub, sub_val in value.items():
                if sub in defaults["interface"] and type(sub_val) is type(defaults["interface"][sub]):
                    out["interface"][sub] = sub_val
            continue
        if expected is int and isinstance(value, bool):
            continue
        if type(value) is expected or (expected is int and isinstance(value, int)):
            out[key] = value
    return out


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Load settings; never raises for missing/corrupt files."""
    p = path or settings_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        return _merge(DEFAULTS, data)
    except (json.JSONDecodeError, ValueError, OSError, UnicodeDecodeError):
        # Corrupt file: quarantine it so the user can inspect it, then reset.
        try:
            backup = p.with_suffix(p.suffix + ".corrupt")
            counter = 1
            while backup.exists():
                backup = p.with_suffix(p.suffix + f".corrupt.{counter}")
                counter += 1
            p.replace(backup)
        except OSError:
            pass
        return deepcopy(DEFAULTS)


def save_settings(settings: dict[str, Any], path: Path | None = None) -> Path:
    """Persist settings atomically.  Raises SettingsError on failure."""
    p = path or settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(_merge(DEFAULTS, settings), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, p)
    except OSError as exc:
        raise SettingsError(f"Could not save settings to {p}: {exc}") from exc
    return p


def reset_settings(path: Path | None = None) -> dict[str, Any]:
    p = path or settings_path()
    if p.exists():
        try:
            p.unlink()
        except OSError as exc:
            raise SettingsError(f"Could not remove old settings: {exc}") from exc
    return deepcopy(DEFAULTS)


def validate_settings(settings: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems (empty = valid)."""
    problems: list[str] = []
    if settings.get("default_format") not in VALID_FORMATS:
        problems.append(f"default_format must be one of {VALID_FORMATS}")
    q = settings.get("jpeg_quality")
    if not isinstance(q, int) or not (1 <= q <= 100):
        problems.append("jpeg_quality must be an integer between 1 and 100")
    if settings.get("default_preset") not in VALID_PRESETS:
        problems.append(f"default_preset must be one of {VALID_PRESETS}")
    bg = settings.get("jpeg_background", "")
    if not (isinstance(bg, str) and bg.startswith("#") and len(bg) in (4, 7)):
        problems.append("jpeg_background must be a hex color like #FFFFFF")
    od = settings.get("output_dir", "")
    if not isinstance(od, str):
        problems.append("output_dir must be a string")
    return problems

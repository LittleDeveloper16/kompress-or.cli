"""Runtime detection of supported input/output image formats and encoders.

Pillow is probed at runtime by actually attempting a tiny encode.  A format is
only ever advertised when the encoder demonstrably works on this machine.
"""

from __future__ import annotations

import io
from functools import lru_cache

from PIL import Image

# Input formats we accept (per specification).
SUPPORTED_INPUT_FORMATS: tuple[str, ...] = ("JPEG", "PNG", "WEBP", "BMP", "TIFF")

# Pillow format id -> canonical display name.
PIL_FORMAT_NAMES: dict[str, str] = {
    "JPEG": "JPEG",
    "JPG": "JPEG",
    "PNG": "PNG",
    "WEBP": "WebP",
    "AVIF": "AVIF",
    "TIFF": "TIFF",
    "BMP": "BMP",
}

# Canonical display name -> Pillow format id.
CANONICAL_TO_PIL: dict[str, str] = {v: k for k, v in PIL_FORMAT_NAMES.items() if k != "JPG"}

# Formats whose encoders ship with Pillow on all platforms (probed anyway).
_ALWAYS_CANDIDATES: tuple[str, ...] = ("JPEG", "PNG", "WEBP", "TIFF", "BMP")
# Formats that may require external codec support.
_OPTIONAL_CANDIDATES: tuple[str, ...] = ("AVIF",)

# Formats that can store an alpha channel in output.
TRANSPARENT_OUTPUT_FORMATS: frozenset[str] = frozenset({"PNG", "WEBP", "AVIF", "TIFF"})

# Human-readable explanation used when an encoder is unavailable.
ENCODER_REASONS: dict[str, str] = {
    "AVIF": "Pillow was built without AVIF support (missing libavif/AOM encoder).",
}

_ALIASES = {"JPG": "JPEG", "WEBP": "WEBP", "WEBP ": "WEBP"}


class FormatError(Exception):
    """Raised when a requested format cannot be used."""


def normalize_format(name: str) -> str:
    """Return the canonical display name (e.g. 'jpg' -> 'JPEG', 'webp' -> 'WebP')."""
    key = _ALIASES.get(name.strip().upper(), name.strip().upper())
    for pil_id, display in PIL_FORMAT_NAMES.items():
        if pil_id == key or pil_id.upper() == key:
            return display
    raise FormatError(
        f"Unknown image format: {name!r}. "
        f"Supported: {', '.join(sorted(CANONICAL_TO_PIL))}."
    )


def pil_format_of(display_name: str) -> str:
    return CANONICAL_TO_PIL[normalize_format(display_name)]


def _probe_encoder(pil_fmt: str) -> bool:
    """Actually try to encode a 2x2 image in memory with this Pillow build."""
    mode = "RGBA" if pil_fmt in TRANSPARENT_OUTPUT_FORMATS else "RGB"
    img = Image.new(mode, (2, 2), (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
    buf = io.BytesIO()
    kwargs: dict = {}
    try:
        if pil_fmt == "JPEG":
            kwargs["quality"] = 50
        elif pil_fmt == "WEBP":
            kwargs["quality"] = 50
        elif pil_fmt == "AVIF":
            kwargs["quality"] = 50
        img.save(buf, format=pil_fmt, **kwargs)
    except (OSError, ValueError, KeyError, NotImplementedError):
        return False
    return buf.getbuffer().nbytes > 0


@lru_cache(maxsize=1)
def encoder_availability() -> dict[str, bool]:
    """Map of candidate format display name -> encoder works right now."""
    result: dict[str, bool] = {}
    for pil_fmt in _ALWAYS_CANDIDATES + _OPTIONAL_CANDIDATES:
        display = PIL_FORMAT_NAMES[pil_fmt]
        result[display] = _probe_encoder(pil_fmt)
    return result


def available_output_formats() -> list[str]:
    """Display names of formats we can actually write with this build."""
    return [name for name, ok in encoder_availability().items() if ok]


def encoder_available(display_name: str) -> bool:
    return encoder_availability().get(normalize_format(display_name), False)


def require_output_format(display_name: str) -> str:
    """Return the normalized display name or raise a helpful FormatError."""
    display = normalize_format(display_name)
    if not encoder_available(display):
        reason = ENCODER_REASONS.get(display, "The encoder is not available in this Pillow build.")
        alternatives = ", ".join(available_output_formats())
        raise FormatError(
            f"{display} output is not available: {reason} "
            f"Supported output formats here: {alternatives}."
        )
    return display


def supports_input(display_name: str) -> bool:
    try:
        display = normalize_format(display_name)
    except FormatError:
        return False
    return display in {PIL_FORMAT_NAMES[f] for f in SUPPORTED_INPUT_FORMATS}


def input_format_hint(actual: str | None) -> str:
    if actual:
        return f"Detected format: {actual}."
    return ""

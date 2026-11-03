"""Single-image compression engine.

Guarantees:
  * the source image is never modified or overwritten;
  * output goes through a temporary file + atomic rename;
  * EXIF orientation is applied to pixels, EXIF/ICC are forwarded to the
    encoder when it accepts them (otherwise the limitation is reported);
  * encoder availability is checked before any work starts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from kompressor.utils.filesystem import (
    FilesystemError,
    format_size,
    is_protected_pair,
    output_path_for,
    percent_reduction,
    validate_source,
)
from kompressor.utils.format_support import (
    FormatError,
    pil_format_of,
    require_output_format,
)
from kompressor.utils.metadata import (
    MetadataState,
    apply_orientation,
    has_transparency,
    read_metadata,
)

# Refuse absurd decompression bombs early.
Image.MAX_IMAGE_PIXELS = 200_000_000

# Compression presets: quality presets for the Compress Image menu.
PRESETS: dict[str, dict] = {
    "fast": {"quality": 70, "description": "Fast, larger files"},
    "balanced": {"quality": 85, "description": "Good balance (default)"},
    "small": {"quality": 65, "description": "Smaller files, visible loss possible"},
    "max": {"quality": 95, "description": "Near-transparent quality, large files"},
}

# JPEG background colors offered when flattening transparency.
BACKGROUND_CHOICES: tuple[str, ...] = ("#FFFFFF", "#000000", "#F5F5F5", "#008080")


class CompressionError(Exception):
    """Raised for invalid input or unavailable encoders."""


@dataclass
class CompressionResult:
    source: Path
    output: Path | None
    ok: bool
    error: str | None = None
    original_size: int = 0
    output_size: int = 0
    fmt: str = ""
    quality: int | None = None
    elapsed: float = 0.0
    metadata: MetadataState | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def saved_bytes(self) -> int:
        return self.original_size - self.output_size

    @property
    def reduction_percent(self) -> float:
        return percent_reduction(self.original_size, self.output_size)

    def summary(self) -> str:
        if not self.ok:
            return f"FAILED: {self.source.name}: {self.error}"
        direction = "smaller" if self.saved_bytes >= 0 else "larger"
        return (
            f"{self.source.name} -> {self.output.name}: "
            f"{format_size(self.original_size)} -> {format_size(self.output_size)} "
            f"({abs(self.reduction_percent):.1f}% {direction}) in {self.elapsed:.2f}s"
        )


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise CompressionError(f"Invalid hex color: {color!r} (expected #RRGGBB)")
    try:
        return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise CompressionError(f"Invalid hex color: {color!r}") from exc


def flatten_transparency(image: Image.Image, background: str) -> Image.Image:
    """Composite a transparent image onto an opaque background color."""
    rgb_bg = hex_to_rgb(background)
    rgba = image.convert("RGBA")
    base = Image.new("RGB", rgba.size, rgb_bg)
    base.paste(rgba, mask=rgba.getchannel("A"))
    return base


def prepare_image(path: Path) -> tuple[Image.Image, bytes | None, bytes | None, MetadataState]:
    """Open, decode, apply EXIF orientation and extract metadata."""
    try:
        img = Image.open(path)
        img.load()
    except FileNotFoundError as exc:
        raise CompressionError(f"File not found: {path}") from exc
    except OSError as exc:
        raise CompressionError(f"Cannot read image {path.name}: {exc}") from exc

    exif_bytes, icc_bytes, state = read_metadata(img)
    img, applied = apply_orientation(img)
    state.orientation_applied = applied
    if applied:
        exif_bytes = _orientation_cleared_exif(img, exif_bytes)
    return img, exif_bytes, icc_bytes, state


def _orientation_cleared_exif(img: Image.Image, exif_bytes: bytes | None) -> bytes | None:
    """Re-serialize EXIF with Orientation=1 after the pixels were rotated."""
    try:
        exif = img.getexif()
        if not exif:
            return None
        exif[274] = 1
        return exif.tobytes()
    except Exception:  # noqa: BLE001
        return None


def convert_mode_for(image: Image.Image, pil_fmt: str, background: str) -> Image.Image:
    """Adapt the image mode to what the target encoder supports."""
    mode = image.mode
    if pil_fmt == "JPEG":
        if mode in ("RGBA", "LA", "PA", "P", "A") or has_transparency(image):
            return flatten_transparency(image, background)
        if mode in ("L", "RGB", "CMYK"):
            return image
        if mode == "1":
            return image.convert("L")
        return image.convert("RGB")
    if pil_fmt == "PNG":
        if mode in ("CMYK", "YCbCr", "I", "F"):
            return image.convert("RGB")
        return image
    if pil_fmt == "WEBP":
        if mode in ("RGBA", "LA", "P", "A"):
            if has_transparency(image):
                return image.convert("RGBA")
            return image.convert("RGB")
        if mode in ("L", "RGB"):
            return image
        return image.convert("RGB")
    if pil_fmt == "AVIF":
        if has_transparency(image) or mode in ("RGBA", "LA", "P", "A"):
            return image.convert("RGBA")
        if mode in ("L", "1"):
            return image
        return image.convert("RGB")
    if pil_fmt == "BMP":
        if mode in ("CMYK", "YCbCr") or (mode == "P"):
            if has_transparency(image):
                return image.convert("RGBA")
            return image.convert("RGB")
        return image
    if pil_fmt == "TIFF":
        return image
    return image


def build_save_kwargs(
    pil_fmt: str,
    quality: int | None,
    exif_bytes: bytes | None,
    icc_bytes: bytes | None,
    preserve_metadata: bool,
    extra: dict | None = None,
) -> dict:
    kwargs: dict = {}
    if pil_fmt == "JPEG":
        kwargs["quality"] = quality if quality is not None else 85
        kwargs["optimize"] = True
        kwargs["progressive"] = True
    elif pil_fmt == "PNG":
        kwargs["optimize"] = True
        kwargs["compress_level"] = 9
    elif pil_fmt == "WEBP":
        kwargs["quality"] = quality if quality is not None else 85
        kwargs["method"] = 6
    elif pil_fmt == "AVIF":
        kwargs["quality"] = quality if quality is not None else 85
    elif pil_fmt == "TIFF":
        kwargs["compression"] = "tiff_deflate"
    if preserve_metadata:
        if exif_bytes and pil_fmt in {"JPEG", "WEBP", "AVIF", "TIFF", "PNG"}:
            kwargs["exif"] = exif_bytes
        if icc_bytes:
            kwargs["icc_profile"] = icc_bytes
    if extra:
        kwargs.update(extra)
    return kwargs


def _save_with_metadata_fallback(image, destination, pil_fmt, kwargs, state):
    """Save; if the encoder rejects exif/icc kwargs, retry without them."""
    from kompressor.utils.filesystem import atomic_save

    had_exif = "exif" in kwargs
    had_icc = "icc_profile" in kwargs
    try:
        atomic_save(image, destination, pil_fmt, **kwargs)
        state.exif_preserved = had_exif
        state.icc_preserved = had_icc
        return
    except TypeError as exc:
        msg = str(exc).lower()
        retry = dict(kwargs)
        dropped: list[str] = []
        if "exif" in msg and "exif" in retry:
            retry.pop("exif", None)
            dropped.append("EXIF")
        if "icc" in msg and "icc_profile" in retry:
            retry.pop("icc_profile", None)
            dropped.append("ICC profile")
        if not dropped:
            raise
        state.notes.append(
            f"{pil_fmt} encoder rejected {' and '.join(dropped)} metadata; not preserved."
        )
        atomic_save(image, destination, pil_fmt, **retry)
        state.exif_preserved = "exif" in retry
        state.icc_preserved = "icc_profile" in retry


def compress_image(
    source: str | Path,
    output_dir: str | Path | None = None,
    fmt: str = "JPEG",
    quality: int = 85,
    background: str = "#FFFFFF",
    preserve_metadata: bool = True,
    extra_save_kwargs: dict | None = None,
) -> CompressionResult:
    """Compress one image.  Never touches the source file."""
    started = time.perf_counter()
    try:
        src = validate_source(source)
    except FilesystemError as exc:
        return CompressionResult(
            source=Path(source), output=None, ok=False, error=str(exc)
        )

    try:
        display_fmt = require_output_format(fmt)
        pil_fmt = pil_format_of(display_fmt)
    except FormatError as exc:
        return CompressionResult(
            source=src, output=None, ok=False, error=str(exc), fmt=str(fmt)
        )

    if not isinstance(quality, int) or not (1 <= quality <= 100):
        return CompressionResult(
            source=src, output=None, ok=False,
            error=f"Quality must be an integer between 1 and 100 (got {quality!r}).",
            fmt=display_fmt,
        )

    original_size = src.stat().st_size
    try:
        img, exif_bytes, icc_bytes, state = prepare_image(src)
        img = convert_mode_for(img, pil_fmt, background)
        destination = output_path_for(src, output_dir, display_fmt)
        if is_protected_pair(src, destination):
            raise FilesystemError("Refusing to overwrite the source image")
        kwargs = build_save_kwargs(
            pil_fmt, quality, exif_bytes, icc_bytes, preserve_metadata, extra_save_kwargs
        )
        _save_with_metadata_fallback(img, destination, pil_fmt, kwargs, state)
        img.close()
    except (CompressionError, FilesystemError, FormatError, OSError, ValueError) as exc:
        return CompressionResult(
            source=src, output=None, ok=False, error=str(exc),
            original_size=original_size, fmt=display_fmt,
            elapsed=time.perf_counter() - started,
        )

    output_size = destination.stat().st_size
    return CompressionResult(
        source=src,
        output=destination,
        ok=True,
        original_size=original_size,
        output_size=output_size,
        fmt=display_fmt,
        quality=quality,
        elapsed=time.perf_counter() - started,
        metadata=state,
        notes=state.notes,
    )

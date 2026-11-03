"""Image resizing engine with validation and aspect-ratio handling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from kompressor.engine.compression import prepare_image, convert_mode_for
from kompressor.utils.filesystem import (
    MAX_REASONABLE_DIMENSION,
    MAX_REASONABLE_PIXELS,
    FilesystemError,
    format_size,
    is_protected_pair,
    output_path_for,
    validate_source,
)
from kompressor.utils.format_support import (
    FormatError,
    pil_format_of,
    require_output_format,
)


class ResizeError(Exception):
    pass


RESAMPLE_METHODS: dict[str, Image.Resampling] = {
    "lanczos": Image.Resampling.LANCZOS,      # best for downscaling, default
    "bicubic": Image.Resampling.BICUBIC,
    "bilinear": Image.Resampling.BILINEAR,
    "nearest": Image.Resampling.NEAREST,
    "box": Image.Resampling.BOX,
    "hamming": Image.Resampling.HAMMING,
}


@dataclass
class ResizeResult:
    source: Path
    output: Path | None
    ok: bool
    error: str | None = None
    original_size: tuple[int, int] = (0, 0)
    new_size: tuple[int, int] = (0, 0)
    file_size_before: int = 0
    file_size_after: int = 0
    elapsed: float = 0.0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return f"FAILED: {self.source.name}: {self.error}"
        return (
            f"{self.source.name}: {self.original_size[0]}x{self.original_size[1]} -> "
            f"{self.new_size[0]}x{self.new_size[1]} "
            f"({format_size(self.file_size_before)} -> {format_size(self.file_size_after)}) "
            f"in {self.elapsed:.2f}s"
        )


def _validate_dimension(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ResizeError(f"{name} must be an integer (got {value!r})")
    if value <= 0:
        raise ResizeError(f"{name} must be greater than 0 (got {value})")
    if value > MAX_REASONABLE_DIMENSION:
        raise ResizeError(
            f"{name}={value} exceeds the safety limit of {MAX_REASONABLE_DIMENSION} pixels"
        )
    return value


def compute_dimensions(
    original: tuple[int, int],
    width: int | None,
    height: int | None,
    percent: float | None,
    keep_ratio: bool,
) -> tuple[int, int]:
    """Compute the target size, validating all inputs.

    Raises ResizeError for zero/negative/absurd dimensions.
    """
    ow, oh = original
    if ow <= 0 or oh <= 0:
        raise ResizeError("Source image has invalid dimensions")

    if percent is not None:
        if not isinstance(percent, (int, float)) or isinstance(percent, bool):
            raise ResizeError(f"Percent must be a number (got {percent!r})")
        if not (0 < percent <= 4000):
            raise ResizeError(f"Percent must be between 0 and 4000 (got {percent})")
        nw = max(1, round(ow * percent / 100))
        nh = max(1, round(oh * percent / 100))
        return _check(nw, nh)

    if width is None and height is None:
        raise ResizeError("Provide width, height or percent")

    if keep_ratio:
        if width is not None and height is not None:
            # Fit inside the requested box, preserving aspect ratio.
            _validate_dimension("width", width)
            _validate_dimension("height", height)
            scale = min(width / ow, height / oh)
            return _check(max(1, round(ow * scale)), max(1, round(oh * scale)))
        if width is not None:
            _validate_dimension("width", width)
            nh = max(1, round(oh * (width / ow)))
            return _check(width, nh)
        _validate_dimension("height", height)  # type: ignore[arg-type]
        nw = max(1, round(ow * (height / oh)))  # type: ignore[operator]
        return _check(nw, height)  # type: ignore[arg-type]

    nw = width if width is not None else ow
    nh = height if height is not None else oh
    if width is not None:
        _validate_dimension("width", width)
    if height is not None:
        _validate_dimension("height", height)
    return _check(nw, nh)


def _check(nw: int, nh: int) -> tuple[int, int]:
    nw = _validate_dimension("width", nw)
    nh = _validate_dimension("height", nh)
    if nw * nh > MAX_REASONABLE_PIXELS:
        raise ResizeError(
            f"Resulting image ({nw}x{nh}) exceeds the pixel safety limit"
        )
    return nw, nh


def resize_image(
    source: str | Path,
    width: int | None = None,
    height: int | None = None,
    percent: float | None = None,
    keep_ratio: bool = True,
    resample: str = "lanczos",
    output_dir: str | Path | None = None,
    fmt: str | None = None,
    background: str = "#FFFFFF",
    preserve_metadata: bool = True,
) -> ResizeResult:
    started = time.perf_counter()
    try:
        src = validate_source(source)
    except FilesystemError as exc:
        return ResizeResult(source=Path(source), output=None, ok=False, error=str(exc))

    method_key = (resample or "lanczos").lower()
    if method_key not in RESAMPLE_METHODS:
        return ResizeResult(
            source=src, output=None, ok=False,
            error=f"Unknown resampling method {resample!r}. "
                  f"Choose one of: {', '.join(RESAMPLE_METHODS)}.",
        )

    try:
        display_fmt = require_output_format(fmt or "PNG")
        pil_fmt = pil_format_of(display_fmt)
    except FormatError as exc:
        return ResizeResult(source=src, output=None, ok=False, error=str(exc))

    original_size_bytes = src.stat().st_size
    try:
        img, exif_bytes, icc_bytes, state = prepare_image(src)
        original_dims = img.size
        try:
            new_dims = compute_dimensions(original_dims, width, height, percent, keep_ratio)
        except ResizeError as exc:
            img.close()
            return ResizeResult(
                source=src, output=None, ok=False, error=str(exc),
                original_size=original_dims,
            )
        resized = img.resize(new_dims, RESAMPLE_METHODS[method_key])
        img.close()
        resized = convert_mode_for(resized, pil_fmt, background)
        destination = output_path_for(src, output_dir, display_fmt)
        if is_protected_pair(src, destination):
            raise FilesystemError("Refusing to overwrite the source image")

        from kompressor.engine.compression import build_save_kwargs, _save_with_metadata_fallback

        kwargs = build_save_kwargs(
            pil_fmt,
            quality=95 if pil_fmt in {"JPEG", "WEBP", "AVIF"} else None,
            exif_bytes=exif_bytes,
            icc_bytes=icc_bytes,
            preserve_metadata=preserve_metadata,
        )
        _save_with_metadata_fallback(resized, destination, pil_fmt, kwargs, state)
        resized.close()
    except Exception as exc:  # noqa: BLE001 - report any failure, never crash
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return ResizeResult(
            source=src, output=None, ok=False, error=str(exc),
            original_size=(0, 0), file_size_before=original_size_bytes,
            elapsed=time.perf_counter() - started,
        )

    return ResizeResult(
        source=src,
        output=destination,
        ok=True,
        original_size=original_dims,
        new_size=new_dims,
        file_size_before=original_size_bytes,
        file_size_after=destination.stat().st_size,
        elapsed=time.perf_counter() - started,
        notes=state.notes,
    )

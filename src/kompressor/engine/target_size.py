"""Target-size compression with a bounded binary search over quality.

Honesty rules implemented here:
  * the search is bounded (max iterations, min quality);
  * if the image cannot reach the target even at the minimum quality, the
    result reports ``achieved=False`` with an explanation - we never claim
    success we did not measure;
  * formats without reliable quality-based size control (PNG, BMP, TIFF)
    return an explicit limitation message instead of a fake result.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from kompressor.engine.compression import (
    build_save_kwargs,
    convert_mode_for,
    prepare_image,
)
from kompressor.utils.filesystem import (
    FilesystemError,
    format_size,
    is_protected_pair,
    output_path_for,
    validate_source,
)
from kompressor.utils.format_support import FormatError, pil_format_of, require_output_format


class TargetSizeError(Exception):
    pass


@dataclass
class TargetSizeResult:
    source: Path
    output: Path | None
    ok: bool
    achieved: bool
    error: str | None = None
    target_bytes: int = 0
    actual_bytes: int = 0
    quality: int | None = None
    iterations: int = 0
    fmt: str = ""
    elapsed: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def difference(self) -> int:
        return self.actual_bytes - self.target_bytes

    def summary(self) -> str:
        if not self.ok:
            return f"FAILED: {self.source.name}: {self.error}"
        if self.achieved:
            return (
                f"Target reached: {format_size(self.actual_bytes)} <= "
                f"{format_size(self.target_bytes)} at quality {self.quality} "
                f"({self.iterations} iterations, {self.elapsed:.2f}s)"
            )
        return (
            f"Target NOT reached: {format_size(self.actual_bytes)} vs "
            f"{format_size(self.target_bytes)} at quality {self.quality} "
            f"({self.iterations} iterations, {self.elapsed:.2f}s)"
        )


# Formats where adjusting quality predictably controls output size.
SIZE_CONTROLLABLE_FORMATS = frozenset({"JPEG", "WebP", "AVIF"})


def _encode_size(
    img: Image.Image, pil_fmt: str, quality: int, kwargs: dict
) -> int:
    """Encode to memory and return the byte size (no disk writes)."""
    buf = io.BytesIO()
    encode_kwargs = dict(kwargs)
    encode_kwargs.pop("exif", None)  # measured size focuses on pixel data
    encode_kwargs.pop("icc_profile", None)
    if pil_fmt in {"JPEG", "WEBP", "AVIF"}:
        encode_kwargs["quality"] = quality
    img.save(buf, format=pil_fmt, **encode_kwargs)
    return buf.getbuffer().nbytes


def target_size(
    source: str | Path,
    target_bytes: int,
    fmt: str = "JPEG",
    min_quality: int = 30,
    max_quality: int = 95,
    max_iterations: int = 8,
    output_dir: str | Path | None = None,
    background: str = "#FFFFFF",
    preserve_metadata: bool = True,
) -> TargetSizeResult:
    """Find the highest quality whose output is <= target_bytes (bounded)."""
    started = time.perf_counter()
    try:
        src = validate_source(source)
    except FilesystemError as exc:
        return TargetSizeResult(
            source=Path(source), output=None, ok=False, achieved=False, error=str(exc)
        )

    if not isinstance(target_bytes, int) or target_bytes <= 0:
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            error="Target size must be a positive number of bytes.",
        )

    try:
        display_fmt = require_output_format(fmt)
    except FormatError as exc:
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False, error=str(exc)
        )

    pil_fmt = pil_format_of(display_fmt)
    if display_fmt not in SIZE_CONTROLLABLE_FORMATS:
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            fmt=display_fmt, target_bytes=target_bytes,
            error=(
                f"Target-size control is not supported for {display_fmt}: its encoder "
                "has no reliable quality knob that maps to output size. "
                f"Use one of: {', '.join(sorted(SIZE_CONTROLLABLE_FORMATS))}."
            ),
        )

    if not (1 <= min_quality < max_quality <= 100):
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            error=f"Invalid quality range {min_quality}..{max_quality}.",
        )

    original_size = src.stat().st_size
    try:
        img, exif_bytes, icc_bytes, state = prepare_image(src)
        img = convert_mode_for(img, pil_fmt, background)
    except Exception as exc:  # noqa: BLE001
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            error=f"Cannot read image: {exc}",
        )

    base_kwargs = build_save_kwargs(
        pil_fmt, min_quality, exif_bytes, icc_bytes, preserve_metadata
    )

    lo, hi = min_quality, max_quality
    best_quality = min_quality
    best_size = 0
    iterations = 0
    found = False

    try:
        # Probe the extremes first to know whether the target is reachable.
        size_at_max = _encode_size(img, pil_fmt, hi, base_kwargs)
        iterations += 1
        if size_at_max <= target_bytes:
            best_quality, best_size, found = hi, size_at_max, True
        else:
            size_at_min = _encode_size(img, pil_fmt, lo, base_kwargs)
            iterations += 1
            best_quality, best_size = lo, size_at_min
            if size_at_min > target_bytes:
                found = False  # even the lowest quality is too big
            else:
                while lo <= hi and iterations < max_iterations:
                    mid = (lo + hi) // 2
                    if mid == best_quality:
                        break
                    size_mid = _encode_size(img, pil_fmt, mid, base_kwargs)
                    iterations += 1
                    if size_mid <= target_bytes:
                        best_quality, best_size, found = mid, size_mid, True
                        lo = mid + 1
                    else:
                        hi = mid - 1
    except Exception as exc:  # noqa: BLE001
        img.close()
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            error=f"Encoding failed: {exc}", target_bytes=target_bytes,
            fmt=display_fmt,
        )

    destination = output_path_for(src, output_dir, display_fmt)
    notes: list[str] = []
    save_error: Exception | None = None
    try:
        if is_protected_pair(src, destination):
            raise FilesystemError("Refusing to overwrite the source image")
        final_kwargs = build_save_kwargs(
            pil_fmt, best_quality, exif_bytes, icc_bytes, preserve_metadata
        )
        from kompressor.engine.compression import _save_with_metadata_fallback

        _save_with_metadata_fallback(img, destination, pil_fmt, final_kwargs, state)
    except Exception as exc:  # noqa: BLE001
        save_error = exc
    img.close()

    if save_error is not None:
        return TargetSizeResult(
            source=src, output=None, ok=False, achieved=False,
            error=f"Could not write output: {save_error}", target_bytes=target_bytes,
            quality=best_quality, iterations=iterations, fmt=display_fmt,
            elapsed=time.perf_counter() - started,
        )

    actual = destination.stat().st_size
    achieved = actual <= target_bytes
    if not achieved:
        notes.append(
            f"The smallest reliable output ({format_size(actual)}) is larger than the "
            f"requested {format_size(target_bytes)}. The target is unrealistic for this "
            "image at the configured minimum quality."
        )
    elif best_quality == min_quality and iterations >= 2:
        notes.append("Target met, but at the minimum allowed quality.")

    return TargetSizeResult(
        source=src,
        output=destination,
        ok=True,
        achieved=achieved,
        target_bytes=target_bytes,
        actual_bytes=actual,
        quality=best_quality,
        iterations=iterations,
        fmt=display_fmt,
        elapsed=time.perf_counter() - started,
        notes=notes,
    )

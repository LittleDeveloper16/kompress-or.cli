"""Format conversion engine (transparency + metadata aware)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kompressor.engine.compression import (
    CompressionResult,
    compress_image,
)
from kompressor.utils.filesystem import validate_source, FilesystemError
from kompressor.utils.format_support import FormatError, require_output_format


class ConversionError(Exception):
    pass


@dataclass
class ConversionResult:
    source: Path
    output: Path | None
    ok: bool
    error: str | None = None
    original_format: str = ""
    target_format: str = ""
    original_size: int = 0
    output_size: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return f"FAILED: {self.source.name}: {self.error}"
        return (
            f"{self.source.name} ({self.original_format}) -> {self.output.name} "
            f"({self.target_format}): {self.original_size} -> {self.output_size} bytes"
        )


def convert_image(
    source: str | Path,
    fmt: str,
    output_dir: str | Path | None = None,
    background: str = "#FFFFFF",
    preserve_metadata: bool = True,
    quality: int = 92,
) -> ConversionResult:
    """Convert *source* to format *fmt* without touching the original."""
    try:
        src = validate_source(source)
    except FilesystemError as exc:
        return ConversionResult(source=Path(source), output=None, ok=False, error=str(exc))

    try:
        display_fmt = require_output_format(fmt)
    except FormatError as exc:
        return ConversionResult(
            source=src, output=None, ok=False, error=str(exc), target_format=str(fmt)
        )

    original_size = src.stat().st_size
    # Determine original format from Pillow.
    try:
        from PIL import Image

        with Image.open(src) as probe:
            original_format = probe.format or "unknown"
    except OSError as exc:
        return ConversionResult(
            source=src, output=None, ok=False,
            error=f"Cannot read image: {exc}",
            target_format=display_fmt,
        )

    result: CompressionResult = compress_image(
        src,
        output_dir=output_dir,
        fmt=display_fmt,
        quality=quality,
        background=background,
        preserve_metadata=preserve_metadata,
    )

    notes: list[str] = []
    if result.ok and result.metadata is not None:
        from kompressor.utils.metadata import describe_metadata

        notes.append(describe_metadata(result.metadata))
        notes.extend(result.notes)
        if display_fmt == "JPEG":
            notes.append("Transparency (if any) was flattened onto the chosen background.")

    return ConversionResult(
        source=src,
        output=result.output,
        ok=result.ok,
        error=result.error,
        original_format=original_format,
        target_format=display_fmt,
        original_size=original_size,
        output_size=result.output_size,
        notes=notes,
    )

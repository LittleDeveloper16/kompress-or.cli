"""Filesystem helpers: safe naming, atomic writes, size formatting."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from kompressor.utils.format_support import CANONICAL_TO_PIL, normalize_format

MAX_REASONABLE_DIMENSION = 100_000
MAX_REASONABLE_PIXELS = 200_000_000


class FilesystemError(Exception):
    """Raised for unsafe or impossible filesystem operations."""


def format_size(num_bytes: int | float) -> str:
    """Human readable file size (binary units)."""
    size = float(num_bytes)
    if size < 1024:
        return f"{int(size)} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        size /= 1024.0
        if size < 1024:
            return f"{size:.2f} {unit}"
    return f"{size:.2f} PiB"


def percent_reduction(original: int, new: int) -> float:
    if original <= 0:
        return 0.0
    return (original - new) / original * 100.0


def validate_source(path: str | Path) -> Path:
    """Validate a source path exists, is a file and is readable."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FilesystemError(f"Path does not exist: {p}")
    if not p.is_file():
        raise FilesystemError(f"Not a file: {p}")
    if not os.access(p, os.R_OK):
        raise FilesystemError(f"File is not readable: {p}")
    return p.resolve()


def ensure_output_dir(directory: str | Path | None) -> Path | None:
    """Create the output directory if needed; None means 'same as source'."""
    if directory is None or str(directory).strip() == "":
        return None
    d = Path(directory).expanduser()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FilesystemError(f"Cannot create output directory {d}: {exc}") from exc
    return d.resolve()


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """Return a path that does not exist yet: name, name_1, name_2, ...

    Never returns an existing path, so existing outputs are never overwritten.
    """
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
        if counter > 10_000:
            raise FilesystemError(f"Could not find a free filename in {directory}")
    return candidate


def output_path_for(source: Path, output_dir: str | Path | None, fmt: str) -> Path:
    """Compute a safe, non-existing output path for *source* in the target format."""
    directory = ensure_output_dir(output_dir) or source.parent.resolve()
    pil_fmt = CANONICAL_TO_PIL[normalize_format(fmt)]
    ext = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "AVIF": ".avif",
        "TIFF": ".tiff",
        "BMP": ".bmp",
    }[pil_fmt]
    if not directory.is_dir():
        raise FilesystemError(f"Output directory is not a directory: {directory}")
    return unique_path(directory, source.stem, ext)


def is_protected_pair(source: Path, destination: Path) -> bool:
    """True when writing *destination* would clobber *source*."""
    try:
        return source.resolve() == destination.resolve()
    except OSError:
        return False


def atomic_save(image, destination: Path, pil_format: str, **save_kwargs) -> Path:
    """Save *image* to a temporary file in the destination directory, then
    atomically replace the destination.  Temporary files are cleaned up on
    any failure.  The destination extension is preserved so Pillow and other
    tools keep working on the result.
    """
    destination = Path(destination)
    directory = destination.parent
    tmp_name = f".{destination.stem}.tmp-{uuid.uuid4().hex[:8]}{destination.suffix}"
    tmp_path = directory / tmp_name
    try:
        image.save(tmp_path, format=pil_format, **save_kwargs)
        # Output integrity check: the file must exist and be non-empty.
        if not tmp_path.is_file() or tmp_path.stat().st_size == 0:
            raise FilesystemError(f"Encoder produced an empty file for {destination.name}")
        os.replace(tmp_path, destination)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return destination


def copy_safely(source: Path, destination: Path) -> Path:
    import shutil

    if is_protected_pair(source, destination):
        raise FilesystemError("Refusing to overwrite the source image")
    tmp = destination.with_name(f".{destination.stem}.tmp-{uuid.uuid4().hex[:8]}{destination.suffix}")
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, destination)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return destination

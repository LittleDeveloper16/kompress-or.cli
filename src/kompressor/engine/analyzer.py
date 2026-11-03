"""Image analyzer: real inspection only - nothing is invented.

The "estimated optimization potential" is a *measured probe*: the image is
re-encoded in memory with a standard setting and the actual size delta is
reported.  When no meaningful probe exists, we say so.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from kompressor.utils.filesystem import format_size, validate_source, FilesystemError
from kompressor.utils.metadata import has_transparency


@dataclass
class Analysis:
    path: Path
    name: str
    file_size: int
    width: int = 0
    height: int = 0
    format: str = ""
    mode: str = ""
    bit_depth: str = ""
    aspect_ratio: str = ""
    has_exif: bool = False
    has_icc: bool = False
    has_transparency: bool = False
    is_animated: bool = False
    frame_count: int = 1
    optimization_estimate: str = "No reliable estimate available for this format."
    notes: list[str] = field(default_factory=list)


class AnalyzerError(Exception):
    pass


_MODE_BITS = {
    "1": "1 bit (black/white)",
    "L": "8 bits (grayscale)",
    "LA": "8 bits + alpha (grayscale)",
    "P": "palette-indexed (8 bits or fewer)",
    "RGB": "8 bits per channel (24-bit)",
    "RGBA": "8 bits per channel + alpha (32-bit)",
    "CMYK": "8 bits per channel (32-bit, CMYK)",
    "YCbCr": "8 bits per channel (24-bit, YCbCr)",
    "I": "32-bit integer",
    "F": "32-bit float",
    "LAB": "8 bits per channel (CIE Lab)",
    "HSV": "8 bits per channel (HSV)",
}


def _aspect_ratio(w: int, h: int) -> str:
    if w <= 0 or h <= 0:
        return "n/a"

    def gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a

    g = gcd(w, h)
    rw, rh = w // g, h // g
    if rw <= 40 and rh <= 40:
        return f"{rw}:{rh}"
    # Fall back to a decimal ratio for odd sizes.
    return f"{w / h:.3f}:1"


def _probe_potential(img: Image.Image, fmt: str) -> str:
    """Measure what a standard re-encode would actually save."""
    try:
        fmt_u = (fmt or "").upper()
        buf = io.BytesIO()
        if fmt_u in ("JPEG", "JPG"):
            rgb = img.convert("RGB")
            rgb.save(buf, format="JPEG", quality=80, optimize=True, progressive=True)
            probe = buf.getbuffer().nbytes
            return (
                f"Probe: re-encoding at JPEG quality 80 would give "
                f"{format_size(probe)} (measured in memory; actual result varies "
                "with content)."
            )
        if fmt_u == "PNG":
            img.save(buf, format="PNG", optimize=True, compress_level=9)
            probe = buf.getbuffer().nbytes
            return (
                f"Probe: a fully optimized PNG re-save would give "
                f"{format_size(probe)} (measured in memory)."
            )
        if fmt_u == "WEBP":
            img.save(buf, format="WEBP", quality=80, method=6)
            probe = buf.getbuffer().nbytes
            return f"Probe: WebP quality 80 would give {format_size(probe)} (measured)."
        if fmt_u == "AVIF":
            img.save(buf, format="AVIF", quality=60)
            probe = buf.getbuffer().nbytes
            return f"Probe: AVIF quality 60 would give {format_size(probe)} (measured)."
        return "No probe available for this format; no estimate claimed."
    except Exception:  # noqa: BLE001 - a failed probe never fails the analysis
        return "Probe re-encode failed; no estimate claimed."


def analyze(path: str | Path) -> Analysis:
    try:
        src = validate_source(path)
    except FilesystemError as exc:
        raise AnalyzerError(str(exc)) from exc

    size = src.stat().st_size
    try:
        img = Image.open(src)
        img.load()
    except OSError as exc:
        raise AnalyzerError(f"Cannot read image {src.name}: {exc}") from exc

    try:
        fmt = img.format or "unknown"
        mode = img.mode
        w, h = img.size
        analysis = Analysis(
            path=src,
            name=src.name,
            file_size=size,
            width=w,
            height=h,
            format=fmt,
            mode=mode,
            bit_depth=_MODE_BITS.get(mode, f"unknown for mode {mode}"),
            aspect_ratio=_aspect_ratio(w, h),
            has_exif=bool(img.getexif()),
            has_icc=bool(img.info.get("icc_profile")),
            has_transparency=has_transparency(img),
            is_animated=bool(getattr(img, "is_animated", False)),
            frame_count=getattr(img, "n_frames", 1),
        )
        analysis.optimization_estimate = _probe_potential(img, fmt)
        if analysis.is_animated and fmt in ("GIF", "WEBP", "APNG"):
            analysis.notes.append(
                f"Animated image with {analysis.frame_count} frames; "
                "only the first frame is analyzed."
            )
        if size < 4096:
            analysis.notes.append(
                "File is already very small; further compression may not help."
            )
        return analysis
    finally:
        img.close()

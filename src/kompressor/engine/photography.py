"""Photography-oriented compression presets.

These presets tune the encoder for photographic content (fine detail,
natural gradients, colour fidelity).  They do NOT - and cannot - guarantee
identical visual quality; results depend on the source content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kompressor.engine.compression import CompressionResult, compress_image


@dataclass(frozen=True)
class PhotographyPreset:
    key: str
    label: str
    fmt: str
    quality: int
    description: str
    save_kwargs: dict
    keep_metadata: bool = True


# Subsampling 4:4:4 (subsampling=0) keeps chroma detail; progressive + optimize
# improve decode efficiency and typical size.
PHOTO_PRESETS: dict[str, PhotographyPreset] = {
    "hq-jpeg": PhotographyPreset(
        key="hq-jpeg",
        label="High-quality JPEG",
        fmt="JPEG",
        quality=96,
        description=(
            "Near-transparent quality, 4:4:4 chroma, progressive. "
            "For prints and further editing."
        ),
        save_kwargs={"subsampling": 0, "progressive": True, "optimize": True},
        keep_metadata=True,
    ),
    "balanced": PhotographyPreset(
        key="balanced",
        label="Balanced photography",
        fmt="JPEG",
        quality=88,
        description=(
            "Good detail retention with moderate file size; "
            "4:2:0 chroma subsampling, progressive."
        ),
        save_kwargs={"subsampling": 2, "progressive": True, "optimize": True},
        keep_metadata=True,
    ),
    "web": PhotographyPreset(
        key="web",
        label="Web photography",
        fmt="WebP",
        quality=82,
        description=(
            "Web-friendly WebP: small files, strong visual quality, "
            "metadata kept where the encoder allows."
        ),
        save_kwargs={"method": 6, "quality": 82},
        keep_metadata=True,
    ),
    "archive": PhotographyPreset(
        key="archive",
        label="Archive-oriented output",
        fmt="TIFF",
        quality=100,
        description=(
            "Lossless-ish archival TIFF with deflate compression; "
            "metadata and ICC profile preserved where supported. "
            "Produces the largest files."
        ),
        save_kwargs={"compression": "tiff_deflate"},
        keep_metadata=True,
    ),
}


def apply_preset(
    source: str | Path,
    preset_key: str,
    output_dir: str | Path | None = None,
    background: str = "#FFFFFF",
    preserve_metadata: bool | None = None,
) -> CompressionResult:
    """Run one photography preset against one image."""
    preset = PHOTO_PRESETS.get(preset_key)
    if preset is None:
        return CompressionResult(
            source=Path(source), output=None, ok=False,
            error=(
                f"Unknown photography preset {preset_key!r}. "
                f"Available: {', '.join(PHOTO_PRESETS)}."
            ),
        )
    keep = preset.keep_metadata if preserve_metadata is None else preserve_metadata
    return compress_image(
        source,
        output_dir=output_dir,
        fmt=preset.fmt,
        quality=preset.quality,
        background=background,
        preserve_metadata=keep,
        extra_save_kwargs=dict(preset.save_kwargs),
    )

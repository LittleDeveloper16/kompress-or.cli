"""Single-image compression tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from kompressor.engine.compression import PRESETS, compress_image


def test_jpeg_compression_reduces_size(make_image):
    src = make_image("PNG", "RGB", (200, 200), noise=True)
    result = compress_image(src, fmt="JPEG", quality=60)
    assert result.ok, result.error
    assert result.output is not None and result.output.exists()
    assert result.output.suffix == ".jpg"
    assert result.output_size > 0
    assert result.output_size < result.original_size
    assert result.reduction_percent > 0


def test_png_optimization(make_image):
    src = make_image("PNG", "RGB", (100, 100), color=(5, 5, 5))
    result = compress_image(src, fmt="PNG")
    assert result.ok, result.error
    assert result.output.suffix == ".png"
    with Image.open(result.output) as out:
        assert out.format == "PNG"
        assert out.size == (100, 100)


def test_webp_output(make_image):
    src = make_image("PNG", "RGB", (80, 80), noise=True)
    result = compress_image(src, fmt="WebP", quality=75)
    assert result.ok, result.error
    with Image.open(result.output) as out:
        assert out.format == "WEBP"


def test_source_never_modified_or_overwritten(make_image):
    src = make_image("PNG", "RGB", (64, 64), noise=True)
    before = (src.read_bytes(), src.stat().st_mtime_ns)
    r1 = compress_image(src, fmt="JPEG", quality=70)
    r2 = compress_image(src, fmt="JPEG", quality=70)
    assert r1.ok and r2.ok
    # Both runs produced distinct outputs - no overwrite of previous output
    # and no overwrite of the source.
    assert r1.output != r2.output
    assert src.read_bytes() == before[0]
    assert src.stat().st_mtime_ns == before[1]
    assert src.exists()


def test_invalid_image_fails_safely(tmp_path: Path):
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"this is definitely not a jpeg")
    result = compress_image(bad, fmt="PNG")
    assert not result.ok
    assert result.error
    assert result.output is None


def test_missing_file_fails_safely(tmp_path: Path):
    result = compress_image(tmp_path / "nope.png", fmt="JPEG")
    assert not result.ok
    assert "not exist" in result.error.lower() or "does not exist" in result.error.lower()


def test_invalid_quality_rejected(make_image):
    src = make_image()
    result = compress_image(src, fmt="JPEG", quality=0)
    assert not result.ok
    assert "quality" in result.error.lower()


def test_presets_exist_and_valid():
    assert set(PRESETS) == {"fast", "balanced", "small", "max"}
    for info in PRESETS.values():
        assert 1 <= info["quality"] <= 100


def test_output_unique_names(make_image, tmp_path: Path):
    src = make_image("PNG", "RGB", (50, 50), name="same.png")
    out_dir = tmp_path / "out"
    r1 = compress_image(src, fmt="JPEG", output_dir=out_dir)
    r2 = compress_image(src, fmt="JPEG", output_dir=out_dir)
    assert r1.ok and r2.ok
    assert r1.output.name == "same.jpg"
    assert r2.output.name == "same_1.jpg"

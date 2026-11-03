"""Target-size algorithm tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from kompressor.engine.target_size import target_size


def test_target_size_achievable(noisy_jpeg, tmp_path: Path):
    original = noisy_jpeg.stat().st_size
    target = int(original * 0.4)
    res = target_size(
        noisy_jpeg, target_bytes=target, fmt="JPEG",
        min_quality=20, max_quality=95, max_iterations=8,
        output_dir=tmp_path / "out",
    )
    assert res.ok, res.error
    assert res.achieved, "target should be reachable for this content"
    assert res.actual_bytes <= target
    assert res.iterations <= 8  # bounded search
    assert res.output.exists()
    assert res.output.stat().st_size == res.actual_bytes
    with Image.open(res.output) as out:
        assert out.format == "JPEG"


def test_unrealistic_target_reported_honestly(noisy_jpeg, tmp_path: Path):
    res = target_size(
        noisy_jpeg, target_bytes=50, fmt="JPEG",
        min_quality=30, max_quality=95, max_iterations=8,
        output_dir=tmp_path / "out",
    )
    assert res.ok            # run itself succeeded
    assert not res.achieved  # but the target was NOT met
    assert res.actual_bytes > 50
    assert any("unrealistic" in n.lower() or "not" in n.lower() for n in res.notes)
    assert res.output.exists()  # closest achievable result still delivered


def test_target_size_webp(noisy_jpeg, tmp_path: Path):
    target = noisy_jpeg.stat().st_size // 2
    res = target_size(
        noisy_jpeg, target_bytes=target, fmt="WebP",
        min_quality=20, max_quality=90, output_dir=tmp_path / "out",
    )
    assert res.ok, res.error
    if res.achieved:
        assert res.actual_bytes <= target


def test_target_size_rejects_png_with_explanation(make_image, tmp_path: Path):
    src = make_image("PNG", "RGB", (64, 64), noise=True)
    res = target_size(src, target_bytes=10_000, fmt="PNG")
    assert not res.ok
    assert "not supported" in res.error
    assert "JPEG" in res.error  # offers controllable alternatives


def test_target_size_invalid_input(noisy_jpeg):
    res = target_size(noisy_jpeg, target_bytes=-5, fmt="JPEG")
    assert not res.ok
    res2 = target_size(noisy_jpeg, target_bytes=1000, fmt="JPEG", min_quality=80, max_quality=50)
    assert not res2.ok


def test_target_size_missing_file(tmp_path: Path):
    res = target_size(tmp_path / "absent.jpg", target_bytes=1000, fmt="JPEG")
    assert not res.ok

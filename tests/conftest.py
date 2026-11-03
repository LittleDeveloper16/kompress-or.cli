"""Shared fixtures: programmatic test images (never personal files)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_image(tmp_path: Path):
    """Factory: make_image('png', 'RGBA', (64, 48)) -> Path."""
    counter = {"n": 0}

    def _make(
        fmt: str = "PNG",
        mode: str = "RGB",
        size: tuple[int, int] = (64, 48),
        color=(120, 40, 200),
        noise: bool = False,
        name: str | None = None,
        animate: bool = False,
    ) -> Path:
        counter["n"] += 1
        if mode in ("L", "1", "I", "F") and isinstance(color, tuple):
            color = color[0]
        elif mode in ("RGBA", "LA", "P"):
            color = color if len(color) in (2, 4) else (*color[:3], 255)
        img = Image.new(mode, size, color)
        if noise:
            rnd = random.Random(1234 + counter["n"])
            raw = bytes(rnd.randrange(256) for _ in range(size[0] * size[1] * 3))
            img = Image.frombytes("RGB", size, raw).convert(mode) if mode != "RGB" else Image.frombytes("RGB", size, raw)
        fname = name or f"img_{counter['n']}.{fmt.lower()}"
        path = tmp_path / fname
        img.save(path, format=fmt.upper() if fmt.upper() != "JPG" else "JPEG")
        return path

    return _make


@pytest.fixture
def noisy_jpeg(tmp_path: Path) -> Path:
    """A JPEG whose size clearly depends on quality (noise content)."""
    rnd = random.Random(99)
    size = (128, 128)
    raw = bytes(rnd.randrange(256) for _ in range(size[0] * size[1] * 3))
    img = Image.frombytes("RGB", size, raw)
    path = tmp_path / "noisy.jpg"
    img.save(path, format="JPEG", quality=95)
    return path


@pytest.fixture
def transparent_png(tmp_path: Path) -> Path:
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 0))
    # opaque square in the middle
    for x in range(16, 48):
        for y in range(16, 48):
            img.putpixel((x, y), (0, 128, 255, 255))
    path = tmp_path / "transparent.png"
    img.save(path, format="PNG")
    return path


@pytest.fixture
def exif_jpeg(tmp_path: Path) -> Path:
    """JPEG with EXIF: Orientation=6 plus a make tag."""
    img = Image.new("RGB", (100, 50), (10, 200, 30))
    exif = Image.Exif()
    exif[274] = 6            # Orientation: rotate 90 CW
    exif[271] = "KOMPRESS-TEST"
    path = tmp_path / "exif.jpg"
    img.save(path, format="JPEG", exif=exif.tobytes())
    return path

"""EXIF orientation handling."""

from __future__ import annotations

from PIL import Image

from kompressor.engine.compression import compress_image


def test_orientation_is_applied_to_pixels(exif_jpeg):
    with Image.open(exif_jpeg) as src:
        assert src.size == (100, 50)      # stored pixels
        assert src.getexif().get(274) == 6

    res = compress_image(exif_jpeg, fmt="PNG")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        # Orientation 6 means "rotate 90 CW to display" -> 50x100 displayed.
        assert out.size == (50, 100)
        # Orientation tag cleared so nothing rotates it again.
        assert out.getexif().get(274) in (None, 1)


def test_orientation_metadata_flag(exif_jpeg):
    res = compress_image(exif_jpeg, fmt="JPEG", quality=85)
    assert res.ok
    assert res.metadata is not None
    assert res.metadata.orientation_applied is True


def test_no_orientation_leaves_size(make_image):
    src = make_image("PNG", "RGB", (60, 30))
    res = compress_image(src, fmt="PNG")
    assert res.ok
    with Image.open(res.output) as out:
        assert out.size == (60, 30)
        assert res.metadata.orientation_applied is False

"""Format conversion, transparency and metadata tests."""

from __future__ import annotations

from PIL import Image

from kompressor.engine.conversion import convert_image


def test_png_to_jpeg_conversion(make_image):
    src = make_image("PNG", "RGB", (70, 70))
    res = convert_image(src, "JPEG")
    assert res.ok, res.error
    assert res.output.suffix == ".jpg"
    with Image.open(res.output) as out:
        assert out.format == "JPEG"
        assert out.size == (70, 70)
    # source untouched
    assert src.exists()


def test_transparent_png_to_jpeg_uses_background(transparent_png, tmp_path):
    res = convert_image(transparent_png, "JPEG", background="#FFFFFF")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.mode == "RGB"
        # corner was fully transparent -> background white
        assert out.getpixel((0, 0)) == (255, 255, 255)
        # centre was opaque blue
        assert out.getpixel((32, 32))[2] > 200


def test_transparent_png_to_webp_keeps_alpha(transparent_png):
    res = convert_image(transparent_png, "WebP")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.format == "WEBP"
        assert out.mode == "RGBA"
        assert out.getpixel((0, 0))[3] == 0  # still transparent


def test_convert_to_bmp_and_back(make_image):
    src = make_image("PNG", "RGB", (30, 30))
    res = convert_image(src, "BMP")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.format == "BMP"
    res2 = convert_image(res.output, "PNG")
    assert res2.ok, res2.error


def test_convert_unsupported_target(tmp_path):
    fake = tmp_path / "x.png"
    Image.new("RGB", (10, 10)).save(fake)
    res = convert_image(fake, "GIF")
    assert not res.ok
    assert res.error


def test_metadata_preserved_when_supported(exif_jpeg, tmp_path):
    res = convert_image(exif_jpeg, "WebP", preserve_metadata=True)
    assert res.ok, res.error
    with Image.open(res.output) as out:
        exif = out.getexif()
        assert exif.get(271) == "KOMPRESS-TEST"


def test_metadata_dropped_when_requested(exif_jpeg):
    res = convert_image(exif_jpeg, "WebP", preserve_metadata=False)
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert not out.getexif().get(271)


def test_grayscale_png_to_jpeg(make_image):
    src = make_image("PNG", "L", (40, 40))
    res = convert_image(src, "JPEG")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.format == "JPEG"


def test_cmyk_input_to_png(make_image):
    src = make_image("TIFF", "CMYK", (40, 40))
    res = convert_image(src, "PNG")
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.format == "PNG"
        assert out.mode in ("RGB", "RGBA")

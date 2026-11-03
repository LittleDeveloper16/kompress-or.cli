"""Photography preset tests."""

from __future__ import annotations

from PIL import Image

from kompressor.engine.photography import PHOTO_PRESETS, apply_preset


def test_all_presets_produce_output(noisy_jpeg, tmp_path):
    for key in PHOTO_PRESETS:
        res = apply_preset(noisy_jpeg, key, output_dir=tmp_path / key)
        assert res.ok, f"{key}: {res.error}"
        assert res.output.exists()
        assert res.output_size > 0
        with Image.open(res.output) as out:
            assert out.format is not None


def test_presets_are_distinct_settings():
    assert set(PHOTO_PRESETS) == {"hq-jpeg", "balanced", "web", "archive"}
    hq = PHOTO_PRESETS["hq-jpeg"]
    assert hq.fmt == "JPEG" and hq.quality >= 90
    assert PHOTO_PRESETS["web"].fmt == "WebP"
    assert PHOTO_PRESETS["archive"].fmt == "TIFF"


def test_unknown_preset_fails_cleanly(make_image):
    src = make_image()
    res = apply_preset(src, "does-not-exist")
    assert not res.ok
    assert "Unknown preset" in res.error or "Unknown" in res.error


def test_presets_keep_metadata(exif_jpeg, tmp_path):
    res = apply_preset(exif_jpeg, "balanced", output_dir=tmp_path)
    assert res.ok, res.error
    with Image.open(res.output) as out:
        assert out.getexif().get(271) == "KOMPRESS-TEST"


def test_source_untouched_by_preset(noisy_jpeg):
    before = noisy_jpeg.read_bytes()
    apply_preset(noisy_jpeg, "hq-jpeg")
    assert noisy_jpeg.read_bytes() == before

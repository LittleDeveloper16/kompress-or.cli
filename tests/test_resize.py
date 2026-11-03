"""Resize engine tests."""

from __future__ import annotations

from PIL import Image

from kompressor.engine.resize import compute_dimensions, resize_image


def test_percent_resize(make_image):
    src = make_image("PNG", "RGB", (100, 50))
    res = resize_image(src, percent=50, fmt="PNG")
    assert res.ok, res.error
    assert res.new_size == (50, 25)
    with Image.open(res.output) as out:
        assert out.size == (50, 25)


def test_width_keeps_aspect_ratio(make_image):
    src = make_image("PNG", "RGB", (200, 100))
    res = resize_image(src, width=100, keep_ratio=True, fmt="PNG")
    assert res.ok, res.error
    assert res.new_size == (100, 50)


def test_height_keeps_aspect_ratio(make_image):
    src = make_image("PNG", "RGB", (200, 100))
    res = resize_image(src, height=50, keep_ratio=True, fmt="PNG")
    assert res.ok, res.error
    assert res.new_size == (100, 50)


def test_exact_mode_can_change_ratio(make_image):
    src = make_image("PNG", "RGB", (200, 100))
    res = resize_image(src, width=50, height=50, keep_ratio=False, fmt="PNG")
    assert res.ok, res.error
    assert res.new_size == (50, 50)


def test_zero_dimension_rejected():
    import pytest
    from kompressor.engine.resize import ResizeError

    with pytest.raises(ResizeError):
        compute_dimensions((100, 100), width=0, height=None, percent=None, keep_ratio=True)
    with pytest.raises(ResizeError):
        compute_dimensions((100, 100), width=None, height=-5, percent=None, keep_ratio=True)


def test_no_arguments_rejected():
    import pytest
    from kompressor.engine.resize import ResizeError

    with pytest.raises(ResizeError):
        compute_dimensions((100, 100), None, None, None, True)


def test_unknown_resample_rejected(make_image):
    src = make_image()
    res = resize_image(src, percent=50, resample="magic", fmt="PNG")
    assert not res.ok
    assert "resampling" in res.error.lower()


def test_invalid_percent_rejected():
    import pytest
    from kompressor.engine.resize import ResizeError

    with pytest.raises(ResizeError):
        compute_dimensions((100, 100), None, None, 0, True)
    with pytest.raises(ResizeError):
        compute_dimensions((100, 100), None, None, -10, True)


def test_upscale_allowed(make_image):
    src = make_image("PNG", "RGB", (20, 20))
    res = resize_image(src, percent=200, fmt="PNG")
    assert res.ok, res.error
    assert res.new_size == (40, 40)

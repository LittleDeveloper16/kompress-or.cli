"""Format support detection and unsupported-format handling."""

from __future__ import annotations

import pytest

from kompressor.utils import format_support as fs
from kompressor.utils.format_support import (
    FormatError,
    available_output_formats,
    encoder_available,
    normalize_format,
    require_output_format,
)


@pytest.fixture(autouse=True)
def clear_cache():
    fs.encoder_availability.cache_clear()
    yield
    fs.encoder_availability.cache_clear()


def test_webp_detection_matches_probe():
    assert encoder_available("WebP") is True  # probed, not assumed


def test_avif_detection_matches_probe():
    # Whatever the answer, it must come from a real encode probe.
    expected = fs._probe_encoder("AVIF")
    assert encoder_available("AVIF") is expected


def test_available_formats_are_subset_of_candidates():
    available = available_output_formats()
    assert "JPEG" in available and "PNG" in available
    for name in available:
        assert name in {"JPEG", "PNG", "WebP", "TIFF", "BMP", "AVIF"}


def test_unsupported_format_raises_helpful_error():
    with pytest.raises(FormatError) as exc:
        normalize_format("GIF")
    assert "Supported" in str(exc.value) or "Unknown" in str(exc.value)


def test_require_output_format_missing_encoder(monkeypatch):
    monkeypatch.setattr(fs, "_probe_encoder", lambda fmt: fmt != "AVIF")
    fs.encoder_availability.cache_clear()
    with pytest.raises(FormatError) as exc:
        require_output_format("AVIF")
    msg = str(exc.value)
    assert "not available" in msg
    assert "Supported output formats" in msg
    # alternatives are offered
    assert "JPEG" in msg
    # JPEG still works
    assert require_output_format("JPEG") == "JPEG"


def test_alias_normalization():
    assert normalize_format("jpg") == "JPEG"
    assert normalize_format("jpeg") == "JPEG"
    assert normalize_format("webp") == "WebP"
    assert normalize_format("PNG") == "PNG"


def test_input_support():
    assert fs.supports_input("JPEG")
    assert fs.supports_input("tiff")
    assert not fs.supports_input("GIF")

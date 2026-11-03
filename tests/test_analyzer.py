"""Analyzer tests - results must be real, never invented."""

from __future__ import annotations

import pytest

from kompressor.engine.analyzer import AnalyzerError, analyze


def test_basic_analysis(make_image):
    src = make_image("PNG", "RGB", (120, 60))
    a = analyze(src)
    assert a.name == src.name
    assert a.path == src.resolve()
    assert a.file_size == src.stat().st_size
    assert (a.width, a.height) == (120, 60)
    assert a.aspect_ratio == "2:1"
    assert a.format == "PNG"
    assert a.mode == "RGB"
    assert "8 bits" in a.bit_depth
    assert a.has_exif is False
    assert a.has_icc is False
    assert a.has_transparency is False


def test_analysis_reports_exif_and_transparency(transparent_png, exif_jpeg):
    t = analyze(transparent_png)
    assert t.has_transparency is True
    e = analyze(exif_jpeg)
    assert e.has_exif is True
    assert e.format == "JPEG"


def test_optimization_estimate_is_measured(noisy_jpeg):
    a = analyze(noisy_jpeg)
    assert "Probe" in a.optimization_estimate or "probe" in a.optimization_estimate
    # the probe reports a real number, not a made-up percentage
    assert "measured" in a.optimization_estimate


def test_invalid_file_raises(tmp_path):
    bad = tmp_path / "x.jpg"
    bad.write_bytes(b"junk")
    with pytest.raises(AnalyzerError):
        analyze(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(AnalyzerError):
        analyze(tmp_path / "missing.png")

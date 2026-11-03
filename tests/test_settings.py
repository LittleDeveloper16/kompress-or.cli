"""Configuration loading, persistence and corruption recovery."""

from __future__ import annotations

import json
from pathlib import Path

from kompressor.config import settings as st


def test_missing_settings_returns_defaults(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    loaded = st.load_settings(cfg)
    assert loaded == st.DEFAULTS
    assert not cfg.exists()


def test_save_and_load_roundtrip(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    s = st.load_settings(cfg)
    s["jpeg_quality"] = 42
    s["default_format"] = "WebP"
    s["output_dir"] = "/tmp/somewhere"
    st.save_settings(s, cfg)
    again = st.load_settings(cfg)
    assert again["jpeg_quality"] == 42
    assert again["default_format"] == "WebP"
    assert again["output_dir"] == "/tmp/somewhere"


def test_corrupted_settings_recovered(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    cfg.write_text("{ this is not json !!!", encoding="utf-8")
    loaded = st.load_settings(cfg)
    assert loaded == st.DEFAULTS            # usable defaults returned
    assert not cfg.exists()                 # corrupt file quarantined
    assert list(tmp_path.glob("settings.json.corrupt*"))


def test_corrupted_settings_wrong_type(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    loaded = st.load_settings(cfg)
    assert loaded == st.DEFAULTS


def test_unknown_keys_ignored_and_types_enforced(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(
        json.dumps(
            {
                "jpeg_quality": "not-a-number",
                "evil_key": "drop me",
                "default_format": "PNG",
                "interface": {"show_sizes": False, "hack": True},
            }
        ),
        encoding="utf-8",
    )
    loaded = st.load_settings(cfg)
    assert loaded["jpeg_quality"] == st.DEFAULTS["jpeg_quality"]  # bad type rejected
    assert "evil_key" not in loaded
    assert loaded["default_format"] == "PNG"
    assert loaded["interface"]["show_sizes"] is False
    assert "hack" not in loaded["interface"]


def test_reset_settings(tmp_path: Path):
    cfg = tmp_path / "settings.json"
    s = st.load_settings(cfg)
    s["jpeg_quality"] = 10
    st.save_settings(s, cfg)
    fresh = st.reset_settings(cfg)
    assert fresh == st.DEFAULTS
    assert not cfg.exists()


def test_validate_settings():
    s = dict(st.DEFAULTS)
    assert st.validate_settings(s) == []
    s["jpeg_quality"] = 999
    s["default_format"] = "NOPE"
    problems = st.validate_settings(s)
    assert len(problems) >= 2


def test_settings_path_is_in_config_dir():
    p = st.settings_path()
    assert p.name == "settings.json"
    assert "kompressor" in str(p)

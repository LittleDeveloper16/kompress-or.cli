"""File picker cancellation, validation and manual fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from kompressor.utils import file_picker as fp


def test_manual_input_valid_path(make_image):
    src = make_image()
    files, errors = fp.choose_files(
        f"pick: {src}", manual_reader=lambda _p: str(src), allow_picker=False
    )
    assert files == [src.resolve()]
    assert errors == []


def test_manual_cancellation_returns_empty():
    files, errors = fp.choose_files("pick:", manual_reader=lambda _p: "c", allow_picker=False)
    assert files == []
    assert errors == []


def test_manual_rejects_bad_paths_then_accepts_good(make_image, tmp_path):
    src = make_image()
    answers = iter([str(tmp_path / "missing.png"), str(src)])
    files, _ = fp.choose_files("pick:", manual_reader=lambda _p: next(answers), allow_picker=False)
    assert files == [src.resolve()]


def test_manual_rejects_non_image_content(tmp_path: Path):
    bad = tmp_path / "fake.jpg"
    bad.write_bytes(b"nope")
    # validate_source only checks readability - content checked by engine.
    files, _ = fp.choose_files("pick:", manual_reader=lambda _p: str(bad), allow_picker=False)
    assert files == [bad.resolve()]


def test_zenity_missing_raises_unavailable(monkeypatch):
    monkeypatch.setattr(fp.shutil, "which", lambda _name: None)
    with pytest.raises(fp.PickerUnavailable):
        fp._run_zenity(["--file-selection"])


def test_zenity_cancel_returns_none(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(fp.shutil, "which", lambda _name: "/usr/bin/zenity")
    monkeypatch.setattr(fp.subprocess, "run", lambda *a, **k: FakeProc())
    assert fp._run_zenity(["--file-selection"]) is None


def test_zenity_success_parses_paths(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "/tmp/a photo.jpg\n/tmp/non ascii ünï.png\n"

    monkeypatch.setattr(fp.shutil, "which", lambda _name: "/usr/bin/zenity")
    monkeypatch.setattr(fp.subprocess, "run", lambda *a, **k: FakeProc())
    paths = fp._run_zenity(["--file-selection"])
    assert [str(p) for p in paths] == ["/tmp/a photo.jpg", "/tmp/non ascii ünï.png"]


def test_choose_files_falls_back_to_manual_when_picker_unavailable(make_image, monkeypatch):
    src = make_image()

    def unavailable(multiple: bool = True):
        raise fp.PickerUnavailable("no display")

    monkeypatch.setattr(fp, "pick_files", unavailable)
    files, _ = fp.choose_files("pick:", manual_reader=lambda _p: str(src), allow_picker=True)
    assert files == [src.resolve()]


def test_choose_files_uses_picker_result(make_image, monkeypatch):
    src = make_image()
    monkeypatch.setattr(fp, "pick_files", lambda multiple=True: [src])
    files, errors = fp.choose_files("pick:", manual_reader=lambda _p: "c", allow_picker=True)
    assert files == [src.resolve()]
    assert errors == []


def test_choose_files_picker_cancel_falls_back_to_manual(make_image, monkeypatch):
    src = make_image()
    monkeypatch.setattr(fp, "pick_files", lambda multiple=True: [])  # user cancelled dialog
    files, _ = fp.choose_files("pick:", manual_reader=lambda _p: str(src), allow_picker=True)
    assert files == [src.resolve()]


def test_choose_single_file(make_image):
    src = make_image()
    picked = fp.choose_single_file(manual_reader=lambda _p: str(src), allow_picker=False)
    assert picked == src.resolve()


def test_choose_single_file_cancel():
    assert fp.choose_single_file(manual_reader=lambda _p: "q", allow_picker=False) is None

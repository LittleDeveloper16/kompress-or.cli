"""Batch processing, duplicate names, failure isolation, CSV report."""

from __future__ import annotations

import csv
from pathlib import Path

from kompressor.engine.batch import batch_compress, write_csv_report


def _mk(path: Path, noise: bool = True) -> Path:
    import random

    from PIL import Image

    rnd = random.Random(hash(path.name) % 10_000)
    size = (64, 64)
    raw = bytes(rnd.randrange(256) for _ in range(size[0] * size[1] * 3))
    img = Image.frombytes("RGB", size, raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG" if path.suffix == ".png" else "JPEG", quality=95)
    return path


def test_batch_success_and_totals(tmp_path: Path):
    files = [_mk(tmp_path / "in" / f"img{i}.png") for i in range(3)]
    out = tmp_path / "out"
    report = batch_compress(files, output_dir=out, fmt="JPEG", quality=70)
    assert len(report.items) == 3
    assert len(report.succeeded) == 3
    assert not report.failed
    assert report.total_original > 0
    assert report.total_output > 0
    assert report.total_saved == report.total_original - report.total_output
    assert report.overall_percent > 0
    for item in report.succeeded:
        assert item.output.exists()


def test_batch_failure_isolation(tmp_path: Path):
    good1 = _mk(tmp_path / "a.png")
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not an image at all")
    good2 = _mk(tmp_path / "b.png")
    report = batch_compress([good1, bad, good2], fmt="JPEG", quality=70)
    assert len(report.items) == 3
    assert len(report.succeeded) == 2
    assert len(report.failed) == 1
    assert report.failed[0].source == bad
    assert report.failed[0].error
    # both good files still processed
    assert report.total_original > 0


def test_batch_duplicate_filenames_from_different_dirs(tmp_path: Path):
    d1, d2 = tmp_path / "dir1", tmp_path / "dir2"
    f1 = _mk(d1 / "photo.png")
    f2 = _mk(d2 / "photo.png")
    out = tmp_path / "out"
    report = batch_compress([f1, f2], output_dir=out, fmt="JPEG", quality=75)
    assert len(report.succeeded) == 2
    outputs = [i.output for i in report.succeeded]
    assert outputs[0] != outputs[1]          # no collision, no overwrite
    assert all(p.exists() for p in outputs)
    assert outputs[0].name == "photo.jpg"
    assert outputs[1].name == "photo_1.jpg"


def test_batch_does_not_overwrite_existing_output(tmp_path: Path):
    src = _mk(tmp_path / "photo.png")
    out = tmp_path / "out"
    r1 = batch_compress([src], output_dir=out, fmt="JPEG", quality=75)
    first = r1.succeeded[0].output
    first_bytes = first.read_bytes()
    r2 = batch_compress([src], output_dir=out, fmt="JPEG", quality=30)
    second = r2.succeeded[0].output
    assert second != first                     # existing output kept intact
    assert first.read_bytes() == first_bytes


def test_batch_progress_callback_called(tmp_path: Path):
    files = [_mk(tmp_path / f"p{i}.png") for i in range(4)]
    calls = []
    batch_compress(files, fmt="JPEG", progress_callback=lambda d, t, p: calls.append((d, t)))
    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_csv_report(tmp_path: Path):
    good = _mk(tmp_path / "ok.png")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"garbage")
    report = batch_compress([good, bad], fmt="JPEG", quality=70)
    csv_path = write_csv_report(report, tmp_path / "reports" / "report.csv")
    assert csv_path.exists()
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][0] == "source"
    assert len(rows) == 3  # header + 2 items
    statuses = {row[1] for row in rows[1:]}
    assert statuses == {"ok", "failed"}
    # second CSV gets a unique name instead of overwriting
    csv2 = write_csv_report(report, tmp_path / "reports" / "report.csv")
    assert csv2 != csv_path

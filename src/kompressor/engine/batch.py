"""Batch compression: sequential processing, failure isolation, CSV report."""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path

from kompressor.engine.compression import CompressionResult, compress_image
from kompressor.utils.filesystem import format_size, percent_reduction


@dataclass
class BatchItem:
    source: Path
    ok: bool
    error: str = ""
    original_size: int = 0
    output_size: int = 0
    output: Path | None = None

    @property
    def saved(self) -> int:
        return self.original_size - self.output_size


@dataclass
class BatchReport:
    items: list[BatchItem] = field(default_factory=list)
    elapsed: float = 0.0
    csv_path: Path | None = None

    @property
    def succeeded(self) -> list[BatchItem]:
        return [i for i in self.items if i.ok]

    @property
    def failed(self) -> list[BatchItem]:
        return [i for i in self.items if not i.ok]

    @property
    def total_original(self) -> int:
        return sum(i.original_size for i in self.succeeded)

    @property
    def total_output(self) -> int:
        return sum(i.output_size for i in self.succeeded)

    @property
    def total_saved(self) -> int:
        return self.total_original - self.total_output

    @property
    def overall_percent(self) -> float:
        return percent_reduction(self.total_original, self.total_output)

    def summary_lines(self) -> list[str]:
        return [
            f"Processed: {len(self.items)} file(s)",
            f"Succeeded: {len(self.succeeded)}   Failed: {len(self.failed)}",
            f"Total original size: {format_size(self.total_original)}",
            f"Total output size:   {format_size(self.total_output)}",
            f"Total space saved:   {format_size(self.total_saved)} "
            f"({self.overall_percent:.1f}%)",
            f"Elapsed: {self.elapsed:.2f}s",
        ]


def _one(source: Path, **kwargs) -> CompressionResult:
    return compress_image(source, **kwargs)


def batch_compress(
    sources: list[Path],
    output_dir: str | Path | None = None,
    fmt: str = "JPEG",
    quality: int = 85,
    background: str = "#FFFFFF",
    preserve_metadata: bool = True,
    progress_callback=None,
) -> BatchReport:
    """Compress *sources* sequentially.

    * One failing file never stops the batch (failures are isolated).
    * Duplicate file names from different directories get unique output names
      (handled by ``unique_path``), and no existing output is ever overwritten.
    * ``progress_callback(done, total, current_path)`` is invoked after each
      file so the CLI can render a progress bar.
    """
    started = time.perf_counter()
    report = BatchReport()
    total = len(sources)
    for index, src in enumerate(sources, start=1):
        try:
            result = _one(
                src,
                output_dir=output_dir,
                fmt=fmt,
                quality=quality,
                background=background,
                preserve_metadata=preserve_metadata,
            )
            if result.ok:
                report.items.append(
                    BatchItem(
                        source=result.source,
                        ok=True,
                        original_size=result.original_size,
                        output_size=result.output_size,
                        output=result.output,
                    )
                )
            else:
                original = 0
                try:
                    original = result.source.stat().st_size
                except OSError:
                    pass
                report.items.append(
                    BatchItem(
                        source=result.source,
                        ok=False,
                        error=result.error or "unknown error",
                        original_size=original,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - absolute failure isolation
            report.items.append(
                BatchItem(source=Path(src), ok=False, error=f"unexpected error: {exc}")
            )
        if progress_callback is not None:
            try:
                progress_callback(index, total, report.items[-1].source)
            except Exception:  # noqa: BLE001 - UI failures must not stop the batch
                pass
    report.elapsed = time.perf_counter() - started
    return report


def write_csv_report(report: BatchReport, path: str | Path) -> Path:
    """Write a UTF-8 CSV report of the batch run (never overwrites: unique name)."""
    from kompressor.utils.filesystem import unique_path

    p = Path(path).expanduser()
    directory = p.parent
    directory.mkdir(parents=True, exist_ok=True)
    target = unique_path(directory, p.stem, p.suffix or ".csv")
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["source", "status", "error", "original_bytes", "output_bytes",
             "saved_bytes", "reduction_percent", "output_path"]
        )
        for item in report.items:
            if item.ok:
                writer.writerow(
                    [
                        str(item.source),
                        "ok",
                        "",
                        item.original_size,
                        item.output_size,
                        item.saved,
                        f"{percent_reduction(item.original_size, item.output_size):.2f}",
                        str(item.output) if item.output else "",
                    ]
                )
            else:
                writer.writerow(
                    [str(item.source), "failed", item.error, item.original_size, "", "", "", ""]
                )
    report.csv_path = target
    return target

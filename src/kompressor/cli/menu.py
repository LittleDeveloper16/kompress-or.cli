"""Interactive main menu and feature flows (Rich based, TTY friendly)."""

from __future__ import annotations

from pathlib import Path

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from kompressor import __app_name__, __version__
from kompressor.cli import display as d
from kompressor.config.settings import (
    DEFAULTS,
    VALID_FORMATS,
    load_settings,
    reset_settings,
    save_settings,
    settings_path,
    validate_settings,
)
from kompressor.engine import compression as compression_engine
from kompressor.engine.analyzer import AnalyzerError, analyze
from kompressor.engine.batch import batch_compress, write_csv_report
from kompressor.engine.conversion import convert_image
from kompressor.engine.photography import PHOTO_PRESETS, apply_preset
from kompressor.engine.resize import RESAMPLE_METHODS, resize_image
from kompressor.engine.target_size import target_size
from kompressor.utils import file_picker
from kompressor.utils.filesystem import format_size
from kompressor.utils.format_support import (
    FormatError,
    available_output_formats,
    require_output_format,
)

MENU_ITEMS = [
    "Compress Image",
    "Batch Compress",
    "Target Size",
    "Convert Format",
    "Resize Image",
    "Image Analyzer",
    "Photography Mode",
    "Settings",
    "Exit",
]

PROMPT = "[bold cyan]Choose an option[/] [dim](1-9)[/]: "


# ---------------------------------------------------------------------------
# shared pickers
# ---------------------------------------------------------------------------

def _pick_single() -> Path | None:
    path = file_picker.choose_single_file(allow_picker=file_picker.picker_enabled())
    if path is None:
        d.show_info("No file selected.")
        return None
    return path


def _pick_many() -> list[Path]:
    files, warnings = file_picker.choose_files(
        "Enter image paths separated by commas (or 'p' to pick graphically, 'c' to cancel):",
        allow_picker=file_picker.picker_enabled(),
    )
    for w in warnings:
        d.show_warning(w)
    if not files:
        d.show_info("No files selected.")
    return files


def _choose_format(settings: dict, allow_back: bool = True) -> str | None:
    formats = available_output_formats()
    default_name = settings.get("default_format", "JPEG")
    default_idx = 0
    if default_name in formats:
        default_idx = formats.index(default_name)
    labels = []
    for f in formats:
        labels.append(f"{f}" + (" (encoder available)" if f != "AVIF" else ""))
    if "AVIF" not in formats:
        labels.append("AVIF - unavailable in this Pillow build (not selectable)")
    idx = d.ask_choice("Output format", labels, default_idx)
    if idx is None:
        return None
    if idx >= len(formats):
        d.show_error(
            "AVIF encoder is not available. "
            f"Choose one of: {', '.join(formats)}."
        )
        return None
    return formats[idx]


def _choose_output_dir(settings: dict, label: str = "Output directory") -> str | None:
    default = settings.get("output_dir", "") or ""
    shown = default if default else "same folder as the source image"
    d.show_info(f"Current {label.lower()}: {shown}")
    raw = d.ask_text(
        "Press Enter to keep, type a path to change, 'p' to pick a folder, "
        "'s' for same folder as source"
    )
    if raw.lower() in {"p", "pick", "folder"}:
        if not file_picker.picker_enabled():
            d.show_info("Graphical folder picker is disabled here; keeping current setting.")
            return default or None
        picked = file_picker.pick_directory()
        if picked is None:
            d.show_info("Folder picker cancelled; keeping current setting.")
            return default or None
        return str(picked)
    if raw.lower() in {"s", "same", "source"}:
        return None
    if raw:
        p = Path(raw).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            d.show_error(f"Cannot create directory {p}: {exc}")
            return _choose_output_dir(settings, label)
        return str(p)
    return default or None


def _show_compression_result(result) -> None:
    if not result.ok:
        d.show_error(result.error or "Unknown failure")
        return
    d.console.print(f"[green]OK[/] {result.summary()}")
    d.print_sizes(result.original_size, result.output_size, result.elapsed)
    if result.metadata is not None:
        from kompressor.utils.metadata import describe_metadata

        d.console.print(f"[dim]Metadata:[/] {describe_metadata(result.metadata)}")
    for note in result.notes:
        d.console.print(f"[dim]Note:[/] {note}")


# ---------------------------------------------------------------------------
# 1. Compress Image
# ---------------------------------------------------------------------------

def flow_compress(settings: dict) -> None:
    d.console.print("\n[bold]Compress Image[/] - single file")
    src = _pick_single()
    if src is None:
        return

    preset_labels = [
        f"{key} - {info['description']} (quality {info['quality']})"
        for key, info in compression_engine.PRESETS.items()
    ] + ["Custom quality"]
    idx = d.ask_choice("Compression preset", preset_labels, 1)
    if idx is None:
        return
    preset_keys = list(compression_engine.PRESETS)
    if idx < len(preset_keys):
        preset_key = preset_keys[idx]
        quality = compression_engine.PRESETS[preset_key]["quality"]
    else:
        quality = d.ask_int("JPEG/WebP quality (1-100)", settings.get("jpeg_quality", 85), 1, 100)
        if quality is None:
            return

    fmt = _choose_format(settings)
    if fmt is None:
        return

    out_dir = _choose_output_dir(settings)
    result = compression_engine.compress_image(
        src,
        output_dir=out_dir,
        fmt=fmt,
        quality=quality,
        background=settings.get("jpeg_background", "#FFFFFF"),
        preserve_metadata=settings.get("preserve_metadata", True),
    )
    _show_compression_result(result)


# ---------------------------------------------------------------------------
# 2. Batch Compress
# ---------------------------------------------------------------------------

def flow_batch(settings: dict) -> None:
    d.console.print("\n[bold]Batch Compress[/] - sequential, failure-isolated")
    files = _pick_many()
    if not files:
        return

    fmt = _choose_format(settings)
    if fmt is None:
        return
    quality = d.ask_int("Quality (1-100)", settings.get("jpeg_quality", 85), 1, 100)
    if quality is None:
        return
    out_dir = _choose_output_dir(settings)
    if settings.get("interface", {}).get("confirm_before_batch", True):
        if not d.ask_yes_no(f"Process {len(files)} file(s) now?", True):
            d.show_info("Batch cancelled.")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=d.console,
    ) as progress:
        task = progress.add_task("Compressing...", total=len(files))

        def cb(done: int, total: int, path: Path) -> None:
            progress.update(task, completed=done, description=f"Compressing {path.name}")

        report = batch_compress(
            files,
            output_dir=out_dir,
            fmt=fmt,
            quality=quality,
            background=settings.get("jpeg_background", "#FFFFFF"),
            preserve_metadata=settings.get("preserve_metadata", True),
            progress_callback=cb,
        )

    for line in report.summary_lines():
        d.console.print(f"  {line}")

    if report.failed:
        d.console.print("\n[red]Failures:[/]")
        for item in report.failed:
            d.console.print(f"  - {item.source.name}: {item.error}")

    if report.succeeded and d.ask_yes_no("Write a CSV report?", True):
        raw = d.ask_text("CSV path", "output/batch_report.csv")
        try:
            csv_path = write_csv_report(report, raw)
            d.show_success(f"CSV report written: {csv_path}")
        except OSError as exc:
            d.show_error(f"Could not write CSV: {exc}")


# ---------------------------------------------------------------------------
# 3. Target Size
# ---------------------------------------------------------------------------

def flow_target(settings: dict) -> None:
    d.console.print("\n[bold]Target Size[/] - bounded quality search")
    src = _pick_single()
    if src is None:
        return

    value = d.ask_float("Target size", 500.0, 0.1, 1_000_000.0)
    if value is None:
        return
    unit_idx = d.ask_choice("Unit", ["KB (kibibytes)", "MB (mebibytes)"], 0)
    if unit_idx is None:
        return
    target_bytes = int(value * (1024 if unit_idx == 0 else 1024 * 1024))

    controllable = ["JPEG", "WebP", "AVIF"]
    available = [f for f in controllable if f in available_output_formats()]
    if not available:
        d.show_error("No size-controllable format is available on this system.")
        return
    idx = d.ask_choice("Output format", available, 0)
    if idx is None:
        return
    fmt = available[idx]

    min_quality = d.ask_int("Minimum acceptable quality", 30, 1, 99)
    if min_quality is None:
        return

    d.show_info(
        "Searching: quality is adjusted with a bounded binary search "
        "(max 8 iterations). The result reflects measured output only."
    )
    result = target_size(
        src,
        target_bytes=target_bytes,
        fmt=fmt,
        min_quality=min_quality,
        max_quality=95,
        max_iterations=8,
        output_dir=_choose_output_dir(settings),
        background=settings.get("jpeg_background", "#FFFFFF"),
        preserve_metadata=settings.get("preserve_metadata", True),
    )
    if not result.ok:
        d.show_error(result.error or "Unknown failure")
        return
    d.console.print(f"[bold]{'Target reached' if result.achieved else 'Target NOT reached'}[/]")
    d.console.print(
        f"  Target: {format_size(result.target_bytes)}   "
        f"Actual: {format_size(result.actual_bytes)}   "
        f"Quality: {result.quality}   Iterations: {result.iterations}   "
        f"Time: {result.elapsed:.2f}s"
    )
    if result.output:
        d.console.print(f"  Output: {result.output}")
    for note in result.notes:
        d.show_warning(note)
    if not result.achieved:
        d.show_info(
            "The target could not be met; the file above is the closest "
            "achievable result at the minimum quality. Try a larger target, "
            "a smaller source image, or resizing first."
        )


# ---------------------------------------------------------------------------
# 4. Convert Format
# ---------------------------------------------------------------------------

def flow_convert(settings: dict) -> None:
    d.console.print("\n[bold]Convert Format[/]")
    src = _pick_single()
    if src is None:
        return
    fmt = _choose_format(settings)
    if fmt is None:
        return
    out_dir = _choose_output_dir(settings)

    background = settings.get("jpeg_background", "#FFFFFF")
    if fmt in {"JPEG", "BMP"}:
        d.show_info(
            "The target format cannot store transparency; transparent pixels "
            f"will be flattened onto background {background}."
        )
        if d.ask_yes_no("Change the background color?", False):
            custom = d.ask_text("Hex color (e.g. #FFFFFF)", background)
            if custom:
                try:
                    compression_engine.hex_to_rgb(custom)
                    background = custom
                except compression_engine.CompressionError as exc:
                    d.show_error(str(exc))

    preserve = settings.get("preserve_metadata", True)
    if d.ask_yes_no(
        "Preserve metadata (EXIF/ICC) where the encoder supports it?", preserve
    ):
        preserve = True
    else:
        preserve = False

    result = convert_image(
        src,
        fmt=fmt,
        output_dir=out_dir,
        background=background,
        preserve_metadata=preserve,
    )
    if not result.ok:
        d.show_error(result.error or "Unknown failure")
        return
    d.console.print(f"[green]OK[/] {result.summary()}")
    for note in result.notes:
        d.console.print(f"[dim]Note:[/] {note}")


# ---------------------------------------------------------------------------
# 5. Resize Image
# ---------------------------------------------------------------------------

def flow_resize(settings: dict) -> None:
    d.console.print("\n[bold]Resize Image[/]")
    src = _pick_single()
    if src is None:
        return

    mode_idx = d.ask_choice(
        "Resize mode",
        ["Set width (aspect ratio kept)",
         "Set height (aspect ratio kept)",
         "Set width x height (fit inside box)",
         "Percentage of original size",
         "Exact width x height (aspect ratio may change)"],
        3,
    )
    if mode_idx is None:
        return

    width = height = percent = None
    keep_ratio = True
    if mode_idx == 0:
        width = d.ask_int("Width in pixels", 1920, 1, 100_000)
        if width is None:
            return
    elif mode_idx == 1:
        height = d.ask_int("Height in pixels", 1080, 1, 100_000)
        if height is None:
            return
    elif mode_idx == 2:
        width = d.ask_int("Max width", 1920, 1, 100_000)
        if width is None:
            return
        height = d.ask_int("Max height", 1080, 1, 100_000)
        if height is None:
            return
    elif mode_idx == 3:
        percent = d.ask_float("Percent of original", 50.0, 0.1, 4000.0)
        if percent is None:
            return
    else:
        keep_ratio = False
        width = d.ask_int("Exact width", 800, 1, 100_000)
        if width is None:
            return
        height = d.ask_int("Exact height", 600, 1, 100_000)
        if height is None:
            return

    resample_labels = [
        f"{name} - {desc}"
        for name, desc in {
            "lanczos": "high quality (default)",
            "bicubic": "smooth, good for moderate scaling",
            "bilinear": "fast, softer result",
            "nearest": "fast, pixel-art style",
            "box": "fast averaging, good for large downscale",
            "hamming": "sharp, good for small changes",
        }.items()
    ]
    ridx = d.ask_choice("Resampling method", resample_labels, 0)
    if ridx is None:
        return
    resample = list(RESAMPLE_METHODS)[ridx]

    fmt = _choose_format(settings)
    if fmt is None:
        return
    out_dir = _choose_output_dir(settings)

    result = resize_image(
        src,
        width=width,
        height=height,
        percent=percent,
        keep_ratio=keep_ratio,
        resample=resample,
        output_dir=out_dir,
        fmt=fmt,
        background=settings.get("jpeg_background", "#FFFFFF"),
        preserve_metadata=settings.get("preserve_metadata", True),
    )
    if not result.ok:
        d.show_error(result.error or "Unknown failure")
        return
    d.console.print(f"[green]OK[/] {result.summary()}")
    d.print_sizes(result.file_size_before, result.file_size_after, result.elapsed)
    for note in result.notes:
        d.console.print(f"[dim]Note:[/] {note}")


# ---------------------------------------------------------------------------
# 6. Image Analyzer
# ---------------------------------------------------------------------------

def flow_analyzer(settings: dict) -> None:
    d.console.print("\n[bold]Image Analyzer[/]")
    src = _pick_single()
    if src is None:
        return
    try:
        analysis = analyze(src)
    except AnalyzerError as exc:
        d.show_error(str(exc))
        return
    d.show_analysis(analysis)


# ---------------------------------------------------------------------------
# 7. Photography Mode
# ---------------------------------------------------------------------------

def flow_photography(settings: dict) -> None:
    d.console.print("\n[bold]Photography Mode[/] - quality-first presets")
    d.show_warning(
        "Presets optimise encoder settings for photographic content; "
        "they cannot guarantee identical visual quality on every image."
    )
    src = _pick_single()
    if src is None:
        return
    labels = [
        f"{p.label} ({p.fmt}, quality {p.quality}) - {p.description}"
        for p in PHOTO_PRESETS.values()
    ]
    idx = d.ask_choice("Photography preset", labels, 1)
    if idx is None:
        return
    preset_key = list(PHOTO_PRESETS)[idx]
    out_dir = _choose_output_dir(settings)
    result = apply_preset(
        src,
        preset_key,
        output_dir=out_dir,
        background=settings.get("jpeg_background", "#FFFFFF"),
        preserve_metadata=settings.get("preserve_metadata", True) or None,
    )
    _show_compression_result(result)


# ---------------------------------------------------------------------------
# 8. Settings
# ---------------------------------------------------------------------------

def _settings_table(settings: dict) -> None:
    from rich.table import Table

    table = Table(title=f"Settings ({settings_path()})", header_style="cyan")
    table.add_column("Key", style="dim")
    table.add_row("Default output directory", settings.get("output_dir") or "(same as source)")
    table.add_row("Default format", str(settings.get("default_format")))
    table.add_row("Default JPEG quality", str(settings.get("jpeg_quality")))
    table.add_row("Default preset", str(settings.get("default_preset")))
    table.add_row("Transparent->JPEG background", str(settings.get("jpeg_background")))
    table.add_row("Preserve metadata", "yes" if settings.get("preserve_metadata") else "no")
    iface = settings.get("interface", {})
    table.add_row("Show sizes", "yes" if iface.get("show_sizes") else "no")
    table.add_row("Confirm before batch", "yes" if iface.get("confirm_before_batch") else "no")
    d.console.print(table)


def flow_settings(settings: dict) -> None:
    while True:
        d.console.print("\n[bold]Settings[/]")
        _settings_table(settings)
        idx = d.ask_choice(
            "What to change",
            ["Default output directory",
             "Default format",
             "Default JPEG quality",
             "Default preset",
             "Transparent-to-JPEG background",
             "Preserve metadata",
             "Confirm before batch",
             "Reset all settings to defaults",
             "Back to main menu"],
            8,
        )
        if idx is None or idx == 8:
            return
        if idx == 0:
            new_dir = _choose_output_dir(settings)
            settings["output_dir"] = new_dir or ""
        elif idx == 1:
            formats = list(VALID_FORMATS)
            fidx = d.ask_choice("Default format", formats, max(0, formats.index(settings["default_format"])) if settings["default_format"] in formats else 0)
            if fidx is not None:
                candidate = formats[fidx]
                try:
                    require_output_format(candidate)
                    settings["default_format"] = candidate
                except FormatError as exc:
                    d.show_error(str(exc))
        elif idx == 2:
            q = d.ask_int("Default JPEG quality", settings["jpeg_quality"], 1, 100)
            if q is not None:
                settings["jpeg_quality"] = q
        elif idx == 3:
            presets = list(compression_engine.PRESETS)
            pidx = d.ask_choice(
                "Default preset",
                [f"{k} ({v['quality']})" for k, v in compression_engine.PRESETS.items()],
                presets.index(settings["default_preset"]) if settings["default_preset"] in presets else 1,
            )
            if pidx is not None:
                settings["default_preset"] = presets[pidx]
        elif idx == 4:
            bg = d.ask_text("Background hex color", settings["jpeg_background"])
            try:
                compression_engine.hex_to_rgb(bg)
                settings["jpeg_background"] = bg if bg.startswith("#") else f"#{bg}"
            except compression_engine.CompressionError as exc:
                d.show_error(str(exc))
        elif idx == 5:
            settings["preserve_metadata"] = d.ask_yes_no(
                "Preserve metadata by default?", settings["preserve_metadata"]
            )
        elif idx == 6:
            settings.setdefault("interface", {})["confirm_before_batch"] = d.ask_yes_no(
                "Ask for confirmation before batch runs?",
                settings["interface"].get("confirm_before_batch", True),
            )
        elif idx == 7:
            if d.ask_yes_no("Reset everything to defaults?", False):
                settings.clear()
                settings.update(reset_settings())
                d.show_success("Settings reset to defaults.")
                try:
                    save_settings(settings)
                except Exception as exc:  # noqa: BLE001
                    d.show_error(str(exc))
                return

        problems = validate_settings(settings)
        if problems:
            for p in problems:
                d.show_warning(p)
            continue
        try:
            save_settings(settings)
            d.show_success("Settings saved.")
        except Exception as exc:  # noqa: BLE001
            d.show_error(str(exc))


# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------

FLOWS = {
    1: flow_compress,
    2: flow_batch,
    3: flow_target,
    4: flow_convert,
    5: flow_resize,
    6: flow_analyzer,
    7: flow_photography,
    8: flow_settings,
}


def print_menu() -> None:
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 2))
    for i, item in enumerate(MENU_ITEMS, start=1):
        style = "bold red" if i == 9 else "bold white"
        table.add_row(f"[{style}]{i}[/{style}]", f"[{style}]{item}[/{style}]")
    d.console.print(table)


def run_menu() -> int:
    settings = load_settings()
    d.print_header()
    problems = validate_settings(settings)
    for p in problems:
        d.show_warning(f"Config problem: {p} (using safe value)")
    if not available_output_formats():
        d.show_error("No output encoders are available; the app cannot function.")
        return 1

    while True:
        print_menu()
        try:
            raw = d.console.input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            d.console.print("\n[dim]Goodbye.[/]")
            return 0
        if not raw.isdigit() or not (1 <= int(raw) <= len(MENU_ITEMS)):
            d.show_error(f"Enter a number between 1 and {len(MENU_ITEMS)}.")
            continue
        choice = int(raw)
        if choice == 9:
            d.console.print(f"[dim]Goodbye from {__app_name__} v{__version__}.[/]")
            return 0
        try:
            FLOWS[choice](settings)
        except KeyboardInterrupt:
            d.console.print("\n[yellow]Cancelled.[/]")
        except Exception as exc:  # noqa: BLE001 - menu must never die
            d.show_error(f"Unexpected error: {exc}")
        try:
            d.pause()
        except (EOFError, KeyboardInterrupt):
            d.console.print("\n[dim]Goodbye.[/]")
            return 0

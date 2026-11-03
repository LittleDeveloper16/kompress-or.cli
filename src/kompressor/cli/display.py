"""Rich-based display helpers shared by all menus."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kompressor import __app_name__, __version__
from kompressor.utils.filesystem import format_size

console = Console()

APP_STYLE = "bold cyan"


def print_header() -> None:
    console.print(
        Panel.fit(
            f"[bold white]{__app_name__}[/] [dim]v{__version__}[/]\n"
            "[dim]Offline image compression toolkit - no telemetry, no cloud.[/]",
            border_style=APP_STYLE,
        )
    )


def show_error(message: str) -> None:
    console.print(Panel(f"[red]{message}[/]", title="[red]Error[/]", border_style="red"))


def show_warning(message: str) -> None:
    console.print(Panel(f"[yellow]{message}[/]", title="[yellow]Note[/]", border_style="yellow"))


def show_info(message: str) -> None:
    console.print(f"[cyan]{message}[/]")


def show_success(message: str) -> None:
    console.print(f"[green]{message}[/]")


def ask_text(prompt: str, default: str = "") -> str:
    suffix = f" [dim]({default})[/]" if default else ""
    value = console.input(f"[bold]{prompt}[/]{suffix}: ").strip()
    return value or default


def ask_int(prompt: str, default: int, minimum: int, maximum: int) -> int | None:
    """Ask for an integer in [minimum, maximum]; empty input = default,
    'b' = cancel (returns None)."""
    while True:
        raw = console.input(
            f"[bold]{prompt}[/] [dim](default {default}, 'b' to go back)[/]: "
        ).strip().lower()
        if raw in {"b", "back", "cancel", "q"}:
            return None
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            show_error(f"'{raw}' is not a whole number.")
            continue
        if not (minimum <= value <= maximum):
            show_error(f"Please enter a number between {minimum} and {maximum}.")
            continue
        return value


def ask_float(prompt: str, default: float, minimum: float, maximum: float) -> float | None:
    while True:
        raw = console.input(
            f"[bold]{prompt}[/] [dim](default {default}, 'b' to go back)[/]: "
        ).strip().lower()
        if raw in {"b", "back", "cancel", "q"}:
            return None
        if raw == "":
            return default
        try:
            value = float(raw)
        except ValueError:
            show_error(f"'{raw}' is not a number.")
            continue
        if not (minimum <= value <= maximum):
            show_error(f"Please enter a number between {minimum} and {maximum}.")
            continue
        return value


def ask_choice(prompt: str, options: list[str], default_index: int = 0) -> int | None:
    """Show numbered options; returns chosen index or None on 'b'."""
    for i, opt in enumerate(options, start=1):
        marker = " (default)" if i - 1 == default_index else ""
        console.print(f"  [bold]{i}[/]. {opt}[dim]{marker}[/]")
    while True:
        raw = console.input(f"[bold]{prompt}[/] [dim]({default_index + 1}, 'b' to go back): [/]").strip().lower()
        if raw in {"b", "back", "cancel", "q"}:
            return None
        if raw == "":
            return default_index
        try:
            idx = int(raw)
        except ValueError:
            show_error("Enter a number from the list, or 'b' to go back.")
            continue
        if 1 <= idx <= len(options):
            return idx - 1
        show_error(f"Choose a number between 1 and {len(options)}.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = console.input(f"{prompt} [dim]({hint})[/]: ").strip().lower()
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        show_error("Please answer 'y' or 'n'.")


def pause(message: str = "Press Enter to return to the main menu...") -> None:
    console.input(f"[dim]{message}[/]")


def print_sizes(before: int, after: int, elapsed: float | None = None) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[dim]Before[/]", f"[bold]{format_size(before)}[/]")
    table.add_row("[dim]After[/]",  f"[bold]{format_size(after)}[/]")
    saved = before - after
    pct = (saved / before * 100) if before else 0.0
    style = "green" if saved >= 0 else "yellow"
    table.add_row(
        "[dim]Saved[/]",
        f"[{style}]{format_size(abs(saved))} ({abs(pct):.1f}% "
        f"{'smaller' if saved >= 0 else 'larger'})[/{style}]",
    )
    if elapsed is not None:
        table.add_row("[dim]Time[/]", f"{elapsed:.2f}s")
    console.print(table)


def show_analysis(analysis) -> None:
    table = Table(title=f"Analysis: {analysis.name}", header_style=APP_STYLE)
    table.add_column("Property", style="dim")
    table.add_column("Value")
    table.add_row("Full path", str(analysis.path))
    table.add_row("File size", format_size(analysis.file_size))
    table.add_row("Dimensions", f"{analysis.width} x {analysis.height} px")
    table.add_row("Aspect ratio", analysis.aspect_ratio)
    table.add_row("Format", analysis.format)
    table.add_row("Color mode", analysis.mode)
    table.add_row("Bit depth", analysis.bit_depth)
    table.add_row("EXIF", "yes" if analysis.has_exif else "no")
    table.add_row("ICC profile", "yes" if analysis.has_icc else "no")
    table.add_row("Transparency", "yes" if analysis.has_transparency else "no")
    if analysis.is_animated:
        table.add_row("Animation", f"yes ({analysis.frame_count} frames)")
    console.print(table)
    console.print(f"[dim]Optimization potential:[/] {analysis.optimization_estimate}")
    for note in analysis.notes:
        show_warning(note)


def pause_if_tty() -> None:
    import sys

    if sys.stdin is not None and sys.stdin.isatty():
        pause()

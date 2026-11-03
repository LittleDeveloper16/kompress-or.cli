"""Application entry point for KOMPRESS-OR.CLI."""

from __future__ import annotations

import argparse
import sys

from kompressor import __app_name__, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kompressor",
        description=(
            "KOMPRESS-OR.CLI - offline-first image compression and "
            "optimization toolkit (no telemetry, no cloud)."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"{__app_name__} {__version__}"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print encoder/format availability and exit",
    )
    return parser


def _run_check() -> int:
    from kompressor.utils.format_support import available_output_formats, encoder_availability
    from kompressor.config.settings import settings_path

    print(f"{__app_name__} {__version__}")
    print(f"Settings file: {settings_path()}")
    print("Encoders:")
    for name, ok in encoder_availability().items():
        print(f"  {name}: {'available' if ok else 'UNAVAILABLE'}")
    print(f"Available output formats: {', '.join(available_output_formats())}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        return _run_check()

    from kompressor.cli.menu import run_menu

    try:
        return run_menu()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())

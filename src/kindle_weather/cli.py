"""Command-line entry point of kindle-weather."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from kindle_weather.config import ConfigError, default_config_path, load_config
from kindle_weather.dashboard import build_dashboard, fallback_locale
from kindle_weather.errors import RENDER_FAILED, describe
from kindle_weather.install import (
    InstallError,
    ascii_fold,
    find_kindle,
    install_extension,
    write_kual_files,
)
from kindle_weather.wizard import run_wizard


class RenderError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kindle-weather", description="Weather station for jailbroken Kindle e-readers."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="configuration file (default: %(default)s)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="create the configuration by answering a few questions")

    install_parser = commands.add_parser(
        "install", help="install the station on a Kindle plugged in over USB"
    )
    install_parser.add_argument(
        "mount_path", type=Path, nargs="?", help="Kindle drive, found automatically if omitted"
    )

    render_parser = commands.add_parser("render", help="render the dashboard to a file")
    render_parser.add_argument("--output", type=Path, default=Path("dashboard.png"))

    # Run on the Kindle by station.sh.
    refresh_parser = commands.add_parser(
        "refresh", help="(Kindle) render the dashboard, print the error to display if any"
    )
    refresh_parser.add_argument("--output", type=Path, required=True)
    kual_parser = commands.add_parser(
        "kual-files", help="(Kindle) write the KUAL menu and settings.sh of the configuration"
    )
    kual_parser.add_argument("extension_dir", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            run_wizard(args.config)
            print("Next: plug in the Kindle over USB and run `kindle-weather install`.")
        elif args.command == "install":
            config = load_config(args.config)
            target = install_extension(args.mount_path or find_kindle(), config, args.config)
            print(f"Installed to {target}. Eject the Kindle, then start it from KUAL.")
        elif args.command == "render":
            render(args.config, args.output)
        elif args.command == "refresh":
            message = refresh(args.config, args.output)
            if message:
                print(ascii_fold(message))
        else:
            write_kual_files(args.extension_dir, load_config(args.config))
    except (ConfigError, RenderError, InstallError) as error:
        parser.exit(1, f"error: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\ncancelled\n")
    return 0


def render(config_path: Path, output: Path) -> None:
    """Render the dashboard to output, or else an error screen saying why."""
    output.parent.mkdir(parents=True, exist_ok=True)
    dashboard = build_dashboard(config_path)
    dashboard.image.save(output)
    if dashboard.error is None:
        print(f"Dashboard for {dashboard.place_name} written to {output}")
    elif dashboard.failure is RENDER_FAILED:
        raise dashboard.error  # A bug: keep the traceback.
    else:
        raise RenderError(
            f"{dashboard.failure.code}: {describe(dashboard.error)}"
            f" (error screen written to {output})"
        )


def refresh(config_path: Path, output: Path) -> str | None:
    """Update the Kindle's dashboard; return the error line to show on it, if any.

    On error the last dashboard stays, with the line on top; the error screen
    is written only when there is no dashboard yet. Details go to stderr, the
    station's log.
    """
    try:
        dashboard = build_dashboard(config_path)
    except Exception:
        # Even the error screen failed, such as without cairo.
        traceback.print_exc()
        labels = fallback_locale(config_path).labels
        return f"{labels['error']} {RENDER_FAILED.code}: {labels[RENDER_FAILED.label]}"
    if dashboard.error is None:
        dashboard.image.save(output)
        return None
    print(dashboard.summary, file=sys.stderr)
    if dashboard.failure is RENDER_FAILED:
        traceback.print_exception(
            type(dashboard.error), dashboard.error, dashboard.error.__traceback__
        )
    if not output.exists():
        dashboard.image.save(output)
    return dashboard.message

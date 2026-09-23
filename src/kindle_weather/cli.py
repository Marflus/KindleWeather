"""Command-line entry point of kindle-weather."""

from __future__ import annotations

import argparse
from pathlib import Path

from kindle_weather.config import ConfigError, default_config_path, load_config
from kindle_weather.dashboard import build_dashboard
from kindle_weather.errors import RENDER_FAILED, describe
from kindle_weather.install import (
    DEFAULT_EXTENSION_SOURCE,
    InstallError,
    find_kindle,
    install_extension,
)
from kindle_weather.server import DEFAULT_PORT, serve
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
        help="configuration file (default: %(default)s)",
        default=default_config_path(),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="create the configuration by answering a few questions")

    install_parser = commands.add_parser(
        "install", help="install the KUAL extension on a Kindle plugged in over USB"
    )
    install_parser.add_argument(
        "mount_path", type=Path, nargs="?", help="Kindle drive, found automatically if omitted"
    )
    install_parser.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION_SOURCE)

    serve_parser = commands.add_parser(
        "serve", help="serve the dashboard to the Kindle over the local network"
    )
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    render_parser = commands.add_parser("render", help="render the dashboard to a file")
    render_parser.add_argument("--output", type=Path, default=Path("dashboard.png"))

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            run_wizard(args.config)
            print("Next: plug in the Kindle over USB and run `kindle-weather install`.")
        elif args.command == "install":
            config = load_config(args.config)
            mount_path = args.mount_path or find_kindle()
            target = install_extension(
                args.extension, mount_path, config.locale, config.dashboard_url
            )
            print(f"Installed to {target}. Eject the Kindle, then start it from KUAL.")
            if config.dashboard_url.startswith("http://"):
                print("Keep `kindle-weather serve` running so the Kindle finds its dashboard.")
        elif args.command == "serve":
            load_config(args.config)
            serve(args.config, args.host, args.port)
        else:
            render(args.config, args.output)
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

"""Command-line entry point: `kindle-meteo render` and `kindle-meteo deploy`."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import requests

from kindle_meteo.config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config
from kindle_meteo.deploy import (
    DEFAULT_EXTENSION_SOURCE,
    DeployError,
    deploy_ssh,
    deploy_usb,
    stage_extension,
)
from kindle_meteo.render import render_dashboard
from kindle_meteo.weather import WeatherError, fetch_forecast, geocode, parse_forecast

DEFAULT_IMAGE = Path("dashboard.png")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kindle-meteo", description="Weather dashboard for jailbroken Kindle e-readers."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    render_parser = commands.add_parser("render", help="fetch the forecast and draw the dashboard")
    render_parser.add_argument("--output", type=Path, default=DEFAULT_IMAGE)

    deploy_parser = commands.add_parser("deploy", help="install the dashboard on the Kindle")
    deploy_parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    deploy_parser.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION_SOURCE)
    deploy_parser.add_argument(
        "--wait",
        type=int,
        default=0,
        metavar="SECONDS",
        help="keep retrying the SSH connection for up to SECONDS",
    )

    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "render":
            render(config, args.output)
        else:
            deploy(config, args.image, args.extension, args.wait)
    except (ConfigError, WeatherError, DeployError, requests.RequestException) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


def render(config: Config, output: Path) -> None:
    place = geocode(config.location.city, config.location.country_code, config.locale.code)
    forecast = parse_forecast(fetch_forecast(place), place.name)
    render_dashboard(forecast, config.locale, config.display_size).save(output)
    print(f"Dashboard for {place.name} written to {output}")


def deploy(config: Config, image: Path, extension: Path, wait_seconds: int) -> None:
    if not image.is_file():
        raise DeployError(f"{image} not found, run `kindle-meteo render` first")
    with tempfile.TemporaryDirectory() as workdir:
        staged = stage_extension(extension, image, config.locale, Path(workdir))
        if config.kindle.method == "usb":
            deploy_usb(staged, Path(config.kindle.mount_path))
            print("Copied to the Kindle. Eject it, then open KUAL > KindleMeteo to display it.")
        else:
            deploy_ssh(staged, config.kindle, wait_seconds)
            print(f"Dashboard displayed on {config.kindle.host}")

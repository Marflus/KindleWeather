"""Command-line entry point: `kindle-weather render` and `kindle-weather install`."""

from __future__ import annotations

import argparse
from pathlib import Path

import requests

from kindle_weather.config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config
from kindle_weather.install import DEFAULT_EXTENSION_SOURCE, InstallError, install_extension
from kindle_weather.render import render_dashboard, render_error
from kindle_weather.weather import WeatherError, fetch_forecast, geocode, parse_forecast

# E2 and E3 are raised on the Kindle, see kindle/extension/bin/station.sh.
WEATHER_ERROR_CODE = "E1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kindle-weather", description="Weather station for jailbroken Kindle e-readers."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    render_parser = commands.add_parser("render", help="fetch the forecast and draw the dashboard")
    render_parser.add_argument("--output", type=Path, default=Path("dashboard.png"))

    install_parser = commands.add_parser(
        "install", help="install the KUAL extension on a Kindle mounted over USB"
    )
    install_parser.add_argument("mount_path", type=Path, help="root of the Kindle drive")
    install_parser.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION_SOURCE)

    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "render":
            render(config, args.output)
        else:
            target = install_extension(
                args.extension, args.mount_path, config.locale, config.dashboard_url
            )
            print(f"Installed to {target}. Eject the Kindle, then start it from KUAL.")
    except (ConfigError, WeatherError, InstallError, requests.RequestException) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


def render(config: Config, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        place = geocode(config.location.city, config.location.country_code, config.locale.code)
        forecast = parse_forecast(fetch_forecast(place, config.temperature_unit), place.name)
    except (WeatherError, requests.RequestException) as error:
        # Publish an error screen so the Kindle shows why it has no forecast.
        image = render_error(
            WEATHER_ERROR_CODE, config.locale, config.display_size, config.orientation
        )
        image.save(output)
        raise WeatherError(f"{error} ({WEATHER_ERROR_CODE} screen written to {output})") from error
    image = render_dashboard(
        forecast, config.locale, config.display_size, config.orientation, config.icon_set
    )
    image.save(output)
    print(f"Dashboard for {place.name} written to {output}")

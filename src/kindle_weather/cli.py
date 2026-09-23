"""Command-line entry point: `kindle-weather render` and `kindle-weather install`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kindle_weather.config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from kindle_weather.errors import RENDER_FAILED, classify, describe
from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.install import DEFAULT_EXTENSION_SOURCE, InstallError, install_extension
from kindle_weather.render import render_dashboard, render_error
from kindle_weather.weather import fetch_forecast, geocode, parse_forecast


class RenderError(RuntimeError):
    pass


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
        if args.command == "render":
            render(args.config, args.output)
        else:
            config = load_config(args.config)
            target = install_extension(
                args.extension, args.mount_path, config.locale, config.dashboard_url
            )
            print(f"Installed to {target}. Eject the Kindle, then start it from KUAL.")
    except (ConfigError, RenderError, InstallError) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


def render(config_path: Path, output: Path) -> None:
    """Render the dashboard to output, or else an error screen saying why."""
    output.parent.mkdir(parents=True, exist_ok=True)
    config = None
    try:
        config = load_config(config_path)
        place = geocode(config.location.city, config.location.country_code, config.locale.code)
        forecast = parse_forecast(fetch_forecast(place, config.temperature_unit), place.name)
        image = render_dashboard(
            forecast, config.locale, config.display_size, config.orientation, config.icon_set
        )
    except Exception as error:
        # Publish the error screen so the Kindle shows why it has no forecast.
        failure, detail = classify(error), describe(error)
        if config:
            screen = render_error(
                failure, config.locale, config.display_size, config.orientation, detail=detail
            )
        else:
            screen = render_error(failure, _fallback_locale(config_path), detail=detail)
        screen.save(output)
        if failure is RENDER_FAILED:
            raise  # A bug: keep the traceback.
        raise RenderError(f"{failure.code}: {detail} (error screen written to {output})") from error
    image.save(output)
    print(f"Dashboard for {place.name} written to {output}")


def _fallback_locale(config_path: Path) -> Locale:
    """Language of an invalid configuration, if it can still be read."""
    try:
        language = json.loads(Path(config_path).read_text(encoding="utf-8")).get("language")
    except (OSError, ValueError, AttributeError):
        language = None
    return LOCALES[language] if isinstance(language, str) and language in LOCALES else LOCALES["en"]

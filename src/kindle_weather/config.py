"""Loading and validation of config/config.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS

# Used in a clone of the repository, as by the GitHub Actions workflow.
REPOSITORY_CONFIG_PATH = Path("config/config.json")
ORIENTATIONS = ("portrait", "landscape")
TEMPERATURE_UNITS = ("celsius", "fahrenheit")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Location:
    city: str
    country_code: str | None = None


@dataclass(frozen=True)
class Config:
    locale: Locale
    location: Location
    display_size: tuple[int, int]
    orientation: str
    icon_set: str
    temperature_unit: str
    # Set when the Kindle downloads its dashboard instead of drawing it.
    dashboard_url: str | None = None


def default_config_path() -> Path:
    """config/config.json in a clone of the repository, else in the user's settings folder."""
    if REPOSITORY_CONFIG_PATH.is_file():
        return REPOSITORY_CONFIG_PATH
    if os.name == "nt" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "kindle-weather" / "config.json"


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        hint = (
            " (run `kindle-weather init` to create it)"
            if isinstance(error, FileNotFoundError)
            else ""
        )
        raise ConfigError(f"cannot read {path}: {error}{hint}") from error
    return parse_config(raw)


def parse_config(raw: dict) -> Config:
    _require(isinstance(raw, dict), "the configuration must be a JSON object")
    language = raw.get("language", "en")
    _require(language in LOCALES, f"language must be one of {sorted(LOCALES)}")

    location = raw.get("location", {})
    _require(isinstance(location, dict), "location must be an object")
    city = location.get("city")
    _require(isinstance(city, str) and city.strip(), "location.city is required")
    country_code = location.get("country_code") or None
    _require(
        country_code is None
        or (isinstance(country_code, str) and len(country_code) == 2 and country_code.isalpha()),
        "location.country_code must be a two-letter ISO 3166-1 code",
    )

    display = raw.get("display", {})
    _require(isinstance(display, dict), "display must be an object")
    width, height = display.get("width", 1072), display.get("height", 1448)
    _require(
        isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0,
        "display.width and display.height must be positive integers",
    )
    orientation = display.get("orientation", "portrait")
    _require(orientation in ORIENTATIONS, f"display.orientation must be one of {ORIENTATIONS}")
    icon_set = display.get("icons", DEFAULT_ICON_SET)
    _require(icon_set in ICON_SETS, f"display.icons must be one of {tuple(ICON_SETS)}")

    temperature_unit = raw.get("temperature_unit", "celsius")
    _require(
        temperature_unit in TEMPERATURE_UNITS,
        f"temperature_unit must be one of {TEMPERATURE_UNITS}",
    )

    url = raw.get("dashboard_url") or None
    _require(
        url is None or (isinstance(url, str) and url.startswith(("https://", "http://"))),
        "dashboard_url must be an http(s) URL",
    )

    return Config(
        locale=LOCALES[language],
        location=Location(
            city=city.strip(), country_code=country_code.upper() if country_code else None
        ),
        display_size=(width, height),
        orientation=orientation,
        icon_set=icon_set,
        temperature_unit=temperature_unit,
        dashboard_url=url,
    )


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

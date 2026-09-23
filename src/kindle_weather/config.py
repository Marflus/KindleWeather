"""Loading and validation of config/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS

DEFAULT_CONFIG_PATH = Path("config/config.json")
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
    dashboard_url: str


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    return parse_config(raw)


def parse_config(raw: dict) -> Config:
    language = raw.get("language", "en")
    _require(language in LOCALES, f"language must be one of {sorted(LOCALES)}")

    location = raw.get("location", {})
    city = location.get("city")
    _require(isinstance(city, str) and city.strip(), "location.city is required")

    display = raw.get("display", {})
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

    url = raw.get("dashboard_url")
    _require(
        isinstance(url, str) and url.startswith(("https://", "http://")),
        "dashboard_url must be an http(s) URL",
    )

    return Config(
        locale=LOCALES[language],
        location=Location(city=city.strip(), country_code=location.get("country_code") or None),
        display_size=(width, height),
        orientation=orientation,
        icon_set=icon_set,
        temperature_unit=temperature_unit,
        dashboard_url=url,
    )


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

"""Reads and checks config.json, see the Configuration section of the README."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS

ORIENTATIONS = ("portrait", "landscape")
TEMPERATURE_UNITS = ("celsius", "fahrenheit")
CLOCKS = ("24h", "12h")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    locale: Locale
    city: str
    # Two-letter ISO code picking the right city among homonyms, or None.
    country_code: str | None
    # Screen size in pixels, in portrait.
    display_size: tuple[int, int]
    orientation: str
    icon_set: str
    temperature_unit: str
    # "24h" or "12h", with AM and PM.
    clock: str


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
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

    clock = raw.get("clock", "24h")
    _require(clock in CLOCKS, f"clock must be one of {CLOCKS}")

    return Config(
        locale=LOCALES[language],
        city=city.strip(),
        country_code=country_code.upper() if country_code else None,
        display_size=(width, height),
        orientation=orientation,
        icon_set=icon_set,
        temperature_unit=temperature_unit,
        clock=clock,
    )


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

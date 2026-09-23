"""Loading and validation of config/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kindle_weather.i18n import LOCALES, Locale

DEFAULT_CONFIG_PATH = Path("config/config.json")
ORIENTATIONS = ("portrait", "landscape")


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
        dashboard_url=url,
    )


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

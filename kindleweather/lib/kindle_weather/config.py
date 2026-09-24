"""Reads and checks config.json, see the Configuration section of the README."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS

# The kindleweather folder, holding config.json: lib/kindle_weather/ is two levels down.
EXTENSION_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = EXTENSION_DIR / "config.json"

ORIENTATIONS = ("portrait", "landscape")
UNITS = ("metric", "imperial")
CLOCKS = ("24h", "12h")
THEMES = ("light", "dark")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    locale: Locale
    city: str
    # Two-letter ISO code picking the right city among homonyms, or None.
    country_code: str | None
    # Open-Meteo's identifier of the city, when chosen from a search: the exact
    # place, whatever its homonyms.
    place_id: int | None
    # Screen size in pixels, in portrait.
    display_size: tuple[int, int]
    orientation: str
    icon_set: str
    # "light", or "dark": white on black.
    theme: str
    # "metric" (°C, km/h) or "imperial" (°F, mph).
    units: str
    # "24h" or "12h", with AM and PM.
    clock: str
    # Minutes between two refreshes of the dashboard.
    refresh_minutes: int
    # Whether the dashboard pauses at night, and the hours from and to which it
    # does, such as (23, 6), in the city's time. The hours are kept when off.
    night_pause_enabled: bool
    night_pause_hours: tuple[int, int]

    @property
    def night_pause(self) -> tuple[int, int] | None:
        """The hours of the night pause, or None to refresh around the clock."""
        start, end = self.night_pause_hours
        return self.night_pause_hours if self.night_pause_enabled and start != end else None


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
    place_id = location.get("id")
    _require(
        place_id is None or (isinstance(place_id, int) and not isinstance(place_id, bool)),
        "location.id must be a number",
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

    theme = display.get("theme", "light")
    _require(theme in THEMES, f"display.theme must be one of {THEMES}")

    # Configurations from before "units" had "temperature_unit".
    default_units = "imperial" if raw.get("temperature_unit") == "fahrenheit" else "metric"
    units = raw.get("units", default_units)
    _require(units in UNITS, f"units must be one of {UNITS}")

    clock = raw.get("clock", "24h")
    _require(clock in CLOCKS, f"clock must be one of {CLOCKS}")

    refresh_minutes = raw.get("refresh_minutes", 60)
    _require(
        isinstance(refresh_minutes, int) and 5 <= refresh_minutes <= 1440,
        "refresh_minutes must be a number of minutes, from 5 to 1440",
    )

    night_pause_enabled, night_pause_hours = _night_pause(raw.get("night_pause"))

    return Config(
        locale=LOCALES[language],
        city=city.strip(),
        country_code=country_code.upper() if country_code else None,
        place_id=place_id,
        display_size=(width, height),
        orientation=orientation,
        icon_set=icon_set,
        theme=theme,
        units=units,
        clock=clock,
        refresh_minutes=refresh_minutes,
        night_pause_enabled=night_pause_enabled,
        night_pause_hours=night_pause_hours,
    )


DEFAULT_NIGHT_PAUSE = (23, 6)


def _night_pause(value: object) -> tuple[bool, tuple[int, int]]:
    """night_pause: {"enabled": true, "from": 23, "to": 6}; "off" and "23-6" are
    the forms of older versions."""
    if value is None or value == "off":
        return False, DEFAULT_NIGHT_PAUSE
    if isinstance(value, str):
        try:
            start, end = (int(hour) for hour in value.split("-"))
        except ValueError:
            raise ConfigError('night_pause must be "off" or two hours, such as "23-6"') from None
        value = {"enabled": True, "from": start, "to": end}
    _require(isinstance(value, dict), "night_pause must be an object")
    enabled = value.get("enabled", True)
    start, end = value.get("from", DEFAULT_NIGHT_PAUSE[0]), value.get("to", DEFAULT_NIGHT_PAUSE[1])
    _require(isinstance(enabled, bool), "night_pause.enabled must be true or false")
    _require(
        all(isinstance(hour, int) and 0 <= hour <= 23 for hour in (start, end)),
        "night_pause.from and night_pause.to must be hours, from 0 to 23",
    )
    return enabled, (start, end)


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

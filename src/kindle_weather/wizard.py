"""`kindle-weather init`: writes the configuration from a few questions."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import requests

from kindle_weather.config import ORIENTATIONS, TEMPERATURE_UNITS, parse_config
from kindle_weather.i18n import LOCALES
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS
from kindle_weather.server import dashboard_url
from kindle_weather.weather import WeatherError, geocode

# Screen size in portrait of each Kindle model, see the README.
MODELS = (
    ("Paperwhite 3 or 4, Voyage, Oasis (2016), Kindle (2022)", (1072, 1448)),
    ("Paperwhite 2", (758, 1024)),
    ("Paperwhite 5", (1236, 1648)),
    ("Oasis 2 or 3", (1264, 1680)),
)


def run_wizard(
    config_path: Path,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
) -> dict:
    """Ask for each setting, defaulting to the current configuration, and save it."""
    current = _read(config_path)
    location = current.get("location") or {}
    display = current.get("display") or {}
    say("KindleWeather setup. Press Enter to keep the value in brackets.\n")

    language = _choose(ask, say, "Display language", sorted(LOCALES), current.get("language", "en"))
    city, country_code = _ask_city(ask, say, language, location)

    say("Kindle model:")
    for number, (name, (width, height)) in enumerate(MODELS, start=1):
        say(f"  {number}. {name} ({width}x{height})")
    sizes = [size for _, size in MODELS]
    current_size = (display.get("width"), display.get("height"))
    default = str(sizes.index(current_size) + 1) if current_size in sizes else "1"
    choices = [str(number) for number in range(1, len(MODELS) + 1)]
    width, height = sizes[int(_choose(ask, say, "Model", choices, default)) - 1]

    orientation = display.get("orientation", "portrait")
    orientation = _choose(ask, say, "Orientation", ORIENTATIONS, orientation)
    unit = current.get("temperature_unit", "celsius")
    unit = _choose(ask, say, "Temperature unit", TEMPERATURE_UNITS, unit)
    icons = _choose(ask, say, "Icons", tuple(ICON_SETS), display.get("icons", DEFAULT_ICON_SET))
    # Served by this computer; GitHub Pages users type their Pages address instead.
    url = _ask(ask, "Dashboard URL", dashboard_url())

    config = {
        "language": language,
        "location": {"city": city, **({"country_code": country_code} if country_code else {})},
        "display": {"width": width, "height": height, "orientation": orientation, "icons": icons},
        "temperature_unit": unit,
        "dashboard_url": url,
    }
    parse_config(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", "utf-8")
    say(f"\nSaved {config_path}.")
    return config


def _ask_city(ask, say, language: str, location: dict) -> tuple[str, str | None]:
    city = location.get("city")
    while True:
        city = _ask(ask, "City", city)
        if not city:
            continue
        try:
            place = geocode(city, None, language)
        except WeatherError:
            say(f"  {city} was not found, check the spelling.")
            city = None
            continue
        except requests.RequestException:
            say("  Open-Meteo cannot be reached: the city will be checked when rendering.")
            return city, location.get("country_code")
        say(f"  Found {place.name}, {place.country or '?'} ({place.country_code or '?'}).")
        return city, place.country_code


def _choose(ask, say, question: str, choices, default: str) -> str:
    listed = ", ".join(choices)
    while True:
        answer = _ask(ask, f"{question} ({listed})", default)
        if answer in choices:
            return answer
        say(f"  Choose one of: {listed}.")


def _ask(ask, question: str, default: str | None) -> str | None:
    answer = ask(f"{question} [{default}]: " if default else f"{question}: ").strip()
    return answer or default


def _read(config_path: Path) -> dict:
    try:
        current = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return current if isinstance(current, dict) else {}

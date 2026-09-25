"""The KUAL menu, with a Settings submenu, and the changes made from it.

python3 -m kindle_weather.settings SETTING VALUE   changes config.json, then the menu
python3 -m kindle_weather.settings detect-city     sets the city of the internet connection
python3 -m kindle_weather.settings                 rewrites the menu from config.json

A settings button runs bin/set.sh and confirms the change in KUAL's status
line. KUAL keeps the submenu open: reloading the menu would take it back to
its first page. The submenu titles show the new values the next time KUAL opens.
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path

from kindle_weather.config import CONFIG_PATH, EXTENSION_DIR, Config, load_config
from kindle_weather.location import detect_place
from kindle_weather.weather import Place

MENU_PATH = EXTENSION_DIR / "menu.json"
# web.sh writes the address of the settings page at the top of the screen.
SETTINGS_PAGE = {
    "action": "sh bin/web.sh",
    "internal": "status Starting the settings page...",
    "status": False,
    "exitmenu": False,
}

# For each setting: its menu label, its keys in config.json, and its values with
# their menu labels. KUAL only displays ASCII reliably.
SETTINGS = {
    "language": (
        "Language",
        ("language",),
        {
            "en": "English",
            "fr": "Francais",
            "de": "Deutsch",
            "es": "Espanol",
            "it": "Italiano",
            "pt": "Portugues",
            "nl": "Nederlands",
            "pl": "Polski",
        },
    ),
    "orientation": (
        "Orientation",
        ("display", "orientation"),
        {"portrait": "Portrait", "landscape": "Landscape"},
    ),
    "icons": (
        "Icons",
        ("display", "icons"),
        {"classic": "Classic", "weather-icons": "Weather Icons", "material": "Material"},
    ),
    "theme": (
        "Theme",
        ("display", "theme"),
        {"light": "Light", "dark": "Dark"},
    ),
    "units": (
        "Units",
        ("units",),
        {"metric": "Metric (C, km/h)", "imperial": "Imperial (F, mph)"},
    ),
    "clock": (
        "Clock",
        ("clock",),
        {"24h": "24-hour", "12h": "12-hour (AM/PM)"},
    ),
    "refresh": (
        "Refresh",
        ("refresh_minutes",),
        {
            15: "Every 15 minutes",
            30: "Every 30 minutes",
            60: "Every hour",
            120: "Every 2 hours",
            180: "Every 3 hours",
            360: "Every 6 hours",
            720: "Every 12 hours",
            1440: "Every 24 hours",
        },
    ),
    "night": ("Night pause", ("night_pause", "enabled"), {False: "Off", True: "On"}),
    "night_from": ("Pause from", ("night_pause", "from"), {h: f"{h}:00" for h in range(24)}),
    "night_to": ("Pause until", ("night_pause", "to"), {h: f"{h}:00" for h in range(24)}),
}


def current_values(config: Config) -> dict:
    """The value of each setting in config."""
    return {
        "language": config.locale.code,
        "orientation": config.orientation,
        "icons": config.icon_set,
        "theme": config.theme,
        "units": config.units,
        "clock": config.clock,
        "refresh": config.refresh_minutes,
        "night": config.night_pause_enabled,
        "night_from": config.night_pause_hours[0],
        "night_to": config.night_pause_hours[1],
    }


def change(setting: str, value: str) -> None:
    """Set one setting in config.json, keeping everything else as it is."""
    _, keys, values = SETTINGS[setting]
    # Values come as text from the menu and the page; some are numbers.
    matches = [choice for choice in values if str(choice) == value]
    if not matches:
        raise ValueError(f"{setting} must be one of {tuple(values)}")
    value = matches[0]
    raw = _read_config()
    if not isinstance(raw.get("night_pause"), dict):
        # Older versions wrote "off" or "23-6".
        config = load_config(CONFIG_PATH)
        start, end = config.night_pause_hours
        raw["night_pause"] = {"enabled": config.night_pause_enabled, "from": start, "to": end}
    *parents, key = keys
    section = raw
    for parent in parents:
        section = section.setdefault(parent, {})
    section[key] = value
    _write_config(raw)


def set_place(place: Place) -> None:
    """Make place, found by a search or a detection, the city of the dashboard."""
    raw = _read_config()
    location = {"city": place.name}
    if place.country_code:
        location["country_code"] = place.country_code
    if place.id is not None:
        location["id"] = place.id
    raw["location"] = location
    _write_config(raw)


def _read_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _write_config(raw: dict) -> None:
    _write(CONFIG_PATH, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")


def write_menu() -> None:
    config = load_config(CONFIG_PATH)
    current = current_values(config)
    # A submenu per setting, titled with its current value.
    city = f"{config.city}, {config.country_code}" if config.country_code else config.city
    settings = [
        {
            "name": f"City: {ascii_fold(city)}",
            "priority": 1,
            "items": [
                # city.sh writes the result at the top of the screen.
                {
                    "name": "Detect automatically",
                    "priority": 1,
                    "action": "sh bin/city.sh",
                    "internal": "status Detecting the city...",
                    "status": False,
                    "exitmenu": False,
                },
                {"name": "Search on the settings page", "priority": 2, **SETTINGS_PAGE},
            ],
        }
    ]
    for priority, (setting, (title, _, values)) in enumerate(SETTINGS.items(), start=2):
        choices = [
            {
                "name": name,
                "priority": index,
                "action": f"sh bin/set.sh {setting} {value}",
                # Stay in the submenu: exitmenu:false. "checked" ticks this
                # button right away, for feedback the press worked; a value
                # picked earlier in the same viewing session may stay ticked
                # too, until the submenu is left and reopened, when its title
                # (below) reflects only the saved value. status:false keeps
                # KUAL from also echoing the raw command in the status line.
                "internal": f"status {title}: {name}, saved",
                "status": False,
                "checked": True,
                "exitmenu": False,
            }
            for index, (value, name) in enumerate(values.items(), start=1)
        ]
        # A value set by hand may not be among the choices.
        value = current[setting]
        name = values.get(value, f"Every {value} minutes" if isinstance(value, int) else value)
        settings.append({"name": f"{title}: {name}", "priority": priority, "items": choices})
    settings.append(
        {"name": "Settings page (phone)", "priority": len(settings) + 1, **SETTINGS_PAGE}
    )
    items = [
        {"name": "Start weather station", "priority": 1, "action": "sh bin/start.sh"},
        {"name": "Settings", "priority": 2, "items": settings},
        {"name": "Diagnostic", "priority": 3, "action": "sh bin/diagnose.sh"},
        {
            "name": "Update KindleWeather",
            "priority": 4,
            "action": "sh bin/update.sh",
            "internal": "status Updating KindleWeather...",
            "status": False,
            "exitmenu": False,
        },
    ]
    menu = {"items": [{"name": "KindleWeather", "priority": 1, "items": items}]}
    _write(MENU_PATH, json.dumps(menu, indent=2) + "\n")


def ascii_fold(text: str) -> str:
    """Varsovie, Kraków -> Krakow: KUAL and eips only display ASCII reliably."""
    text = text.translate(str.maketrans({"ł": "l", "Ł": "L", "ß": "ss", "ø": "o", "Ø": "O"}))
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _write(path: Path, text: str) -> None:
    """Replace the file at once, so that KUAL never reads it half written."""
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
    os.replace(temporary, path)


def _detect_city() -> None:
    """Set the detected city, and print a line saying which for city.sh."""
    try:
        place = detect_place(load_config(CONFIG_PATH).locale.code)
    except Exception as error:
        print(f"City not detected: {error}", file=sys.stderr)
        print("City not detected: check the Wi-Fi connection")
        return
    set_place(place)
    print(ascii_fold(f"City: {place.full_name}"))


if __name__ == "__main__":
    if sys.argv[1:] == ["detect-city"]:
        _detect_city()
    elif len(sys.argv) == 3:
        change(sys.argv[1], sys.argv[2])
    write_menu()

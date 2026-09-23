"""The KUAL menu, with a Settings submenu, and the changes made from it.

python3 -m kindle_weather.settings SETTING VALUE   changes config.json, then the menu
python3 -m kindle_weather.settings                 rewrites the menu from config.json

The settings buttons run bin/set.sh. The menu names the current values, which
KUAL displays the next time it opens: it does not wait for the change to reload.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kindle_weather.config import load_config

EXTENSION_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = EXTENSION_DIR / "config.json"
MENU_PATH = EXTENSION_DIR / "menu.json"

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
    "temperature": (
        "Temperature",
        ("temperature_unit",),
        {"celsius": "Celsius", "fahrenheit": "Fahrenheit"},
    ),
    "clock": (
        "Clock",
        ("clock",),
        {"24h": "24-hour", "12h": "12-hour (AM/PM)"},
    ),
}


def change(setting: str, value: str) -> None:
    """Set one setting in config.json, keeping everything else as it is."""
    _, keys, values = SETTINGS[setting]
    if value not in values:
        raise ValueError(f"{setting} must be one of {tuple(values)}")
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    *parents, key = keys
    section = raw
    for parent in parents:
        section = section.setdefault(parent, {})
    section[key] = value
    CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", "utf-8")


def write_menu() -> None:
    config = load_config(CONFIG_PATH)
    current = {
        "language": config.locale.code,
        "orientation": config.orientation,
        "icons": config.icon_set,
        "temperature": config.temperature_unit,
        "clock": config.clock,
    }
    # One submenu per setting, named after its current value.
    settings = []
    for priority, (setting, (label, _, values)) in enumerate(SETTINGS.items(), start=1):
        choices = [
            {
                "name": name,
                "priority": index,
                "action": f"sh bin/set.sh {setting} {value}",
                # Stay in the menu, with a check mark on the chosen value.
                "exitmenu": False,
                "checked": True,
            }
            for index, (value, name) in enumerate(values.items(), start=1)
        ]
        name = values[current[setting]]
        settings.append({"name": f"{label}: {name}", "priority": priority, "items": choices})
    items = [
        {"name": "Start weather station", "priority": 1, "action": "sh bin/start.sh"},
        {"name": "Settings", "priority": 2, "items": settings},
        {"name": "Diagnostic", "priority": 3, "action": "sh bin/diagnose.sh"},
    ]
    menu = {"items": [{"name": "KindleWeather", "priority": 1, "items": items}]}
    with open(MENU_PATH, "w", encoding="utf-8", newline="\n") as file:
        json.dump(menu, file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        change(sys.argv[1], sys.argv[2])
    write_menu()

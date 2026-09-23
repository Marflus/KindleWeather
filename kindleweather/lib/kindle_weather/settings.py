"""The KUAL menu, with a Settings submenu, and the changes made from it.

python3 -m kindle_weather.settings SETTING VALUE   changes config.json, then the menu
python3 -m kindle_weather.settings                 rewrites the menu from config.json

A settings button runs bin/set.sh, then KUAL reloads the menu a quarter of a
second later. That is too soon for Python: set.sh first updates the menu with
sed, which the one-button-per-line layout of menu.json makes simple, then runs
this module.
"""

from __future__ import annotations

import json
import os
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
    _write(CONFIG_PATH, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")


def write_menu() -> None:
    config = load_config(CONFIG_PATH)
    current = {
        "language": config.locale.code,
        "orientation": config.orientation,
        "icons": config.icon_set,
        "temperature": config.temperature_unit,
        "clock": config.clock,
    }
    # A submenu per setting, titled with its current value, which is also
    # marked [x] among the choices. set.sh relies on these names.
    settings = []
    for priority, (setting, (title, _, values)) in enumerate(SETTINGS.items(), start=1):
        choices = [
            {
                "name": f"[{'x' if value == current[setting] else ' '}] {name}",
                "priority": index,
                "action": f"sh bin/set.sh {setting} {value}",
                # Stay in KUAL, and reload the menu to show the change.
                "exitmenu": False,
                "refresh": True,
            }
            for index, (value, name) in enumerate(values.items(), start=1)
        ]
        name = values[current[setting]]
        settings.append({"name": f"{title}: {name}", "priority": priority, "items": choices})
    items = [
        {"name": "Start weather station", "priority": 1, "action": "sh bin/start.sh"},
        {"name": "Settings", "priority": 2, "items": settings},
        {"name": "Diagnostic", "priority": 3, "action": "sh bin/diagnose.sh"},
    ]
    menu = {"items": [{"name": "KindleWeather", "priority": 1, "items": items}]}
    _write(MENU_PATH, _menu_json(menu) + "\n")


def _menu_json(entry: dict, depth: int = 0) -> str:
    """JSON with one button per line, for set.sh to edit with sed."""
    indent = "  " * depth
    if "items" not in entry:
        return indent + json.dumps(entry)
    fields = json.dumps({key: value for key, value in entry.items() if key != "items"})[1:-1]
    children = ",\n".join(_menu_json(child, depth + 1) for child in entry["items"])
    return f'{indent}{{{fields}{", " if fields else ""}"items": [\n{children}\n{indent}]}}'


def _write(path: Path, text: str) -> None:
    """Replace the file at once, so that KUAL never reads it half written."""
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
    os.replace(temporary, path)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        change(sys.argv[1], sys.argv[2])
    write_menu()

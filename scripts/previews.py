"""Regenerate the images in preview/ from sample data: python3 scripts/previews.py

Needs Python 3.9 or newer, with the cairo and FreeType libraries (Linux and
macOS usually have them).
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

from zoneinfo import ZoneInfo  # Python 3.9+: the previews run on a computer.

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kindleweather" / "lib"))

from kindle_weather.canvas import Canvas, Font, Picture
from kindle_weather.i18n import LOCALES
from kindle_weather.icons import ICON_SETS
from kindle_weather.render import ROBOTO_BOLD, render_dashboard
from kindle_weather.weather import parse_forecast

PREVIEW_DIR = ROOT / "preview"
TIMEZONE = "Europe/Warsaw"
NOW = datetime(2026, 12, 3, 15, 2, tzinfo=ZoneInfo(TIMEZONE))
# Snow early in the morning, rain around noon, thunderstorm in the evening.
HOURLY_CODES = [3, 3, 71, 73, 73, 71, 3, 2, 2, 1, 3, 61, 63, 63, 80, 3, 3, 95, 95, 96, 61, 3, 2, 2]
DAYS = range(3, 11)
# Rows of the portrait dashboard shown in the comparison: today, next days, alert.
COMPARISON_ROWS = (16, 546)


def sample_forecast():
    hours = [f"2026-12-{day:02d}T{hour:02d}:00" for day in (3, 4) for hour in range(24)]
    raw = {
        "timezone": TIMEZONE,
        "utc_offset_seconds": 3600,
        "daily": {
            "time": [f"2026-12-{day:02d}" for day in DAYS],
            "weather_code": [73, 3, 0, 2, 61, 95, 71, 45],
            "temperature_2m_max": [6.2, 4.0, 3.1, 5.4, 7.9, 8.6, 0.8, 2.2],
            "temperature_2m_min": [-1.4, -2.0, -4.2, -1.1, 2.3, 3.0, -3.5, -1.0],
            "sunrise": [f"2026-12-{day:02d}T07:31" for day in DAYS],
            "sunset": [f"2026-12-{day:02d}T15:26" for day in DAYS],
        },
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": hours,
            "temperature_2m": [
                2.4 + 3.8 * math.sin((i % 24 - 8) * math.pi / 12) for i in range(len(hours))
            ],
            "weather_code": HOURLY_CODES * 2,
            "relative_humidity_2m": [78 + i % 17 for i in range(len(hours))],
            "wind_speed_10m": [9 + (i * 5) % 14 for i in range(len(hours))],
        },
    }
    return parse_forecast(raw, "Warsaw", now=NOW)


def main() -> None:
    forecast, english = sample_forecast(), LOCALES["en"]
    portraits = {}
    for name in ICON_SETS:
        folder = PREVIEW_DIR / name
        folder.mkdir(parents=True, exist_ok=True)
        portraits[name] = render_dashboard(forecast, english, icon_set=name)
        portraits[name].save(folder / "portrait.png")
        landscape = render_dashboard(forecast, english, orientation="landscape", icon_set=name)
        # Saved upright, as read on the Kindle turned a quarter turn.
        landscape.rotated(clockwise=True).save(folder / "landscape.png")
    comparison(portraits).save(PREVIEW_DIR / "icon-sets.png")


def comparison(portraits: dict[str, Picture]) -> Picture:
    """The top of each portrait preview, stacked under the name of its icon set."""
    width = next(iter(portraits.values())).width
    crop_top, crop_bottom = COMPARISON_ROWS
    section_height = 56 + crop_bottom - crop_top
    font = Font(ROBOTO_BOLD, 30)
    canvas = Canvas(width, len(portraits) * section_height)
    for i, (name, portrait) in enumerate(portraits.items()):
        top = i * section_height
        canvas.paste(portrait.crop((0, crop_top, width, crop_bottom)), (0, top + 56))
        if i:
            canvas.line([(50, top), (width - 50, top)], fill=180, width=2)
        canvas.text((50, top + 16), f'"icons": "{name}"', font=font, fill=0)
    return canvas.picture()


if __name__ == "__main__":
    main()

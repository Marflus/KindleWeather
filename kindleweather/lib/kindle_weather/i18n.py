"""Display strings, one JSON file per language in the locales/ folder."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"


@dataclass(frozen=True)
class Locale:
    code: str
    weekdays: tuple[str, ...]
    short_weekdays: tuple[str, ...]
    months: tuple[str, ...]
    long_date: str
    timestamp: str
    labels: dict[str, str]
    weather: dict[int, str]

    def format_long_date(self, moment: datetime) -> str:
        return self.long_date.format(
            weekday=self.weekdays[moment.weekday()],
            day=moment.day,
            month=self.months[moment.month - 1],
            year=moment.year,
        )

    def format_short_date(self, day: date) -> str:
        return f"{self.short_weekdays[day.weekday()]} {day.day}"

    def format_updated_at(self, moment: datetime) -> str:
        return self.labels["updated"].format(moment.strftime(self.timestamp))

    def describe(self, weather_code: int) -> str:
        return self.weather.get(weather_code, self.labels["variable"])


def _load(path: Path) -> Locale:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Locale(
        code=path.stem,
        weekdays=tuple(data["weekdays"]),
        short_weekdays=tuple(data["short_weekdays"]),
        months=tuple(data["months"]),
        long_date=data["long_date"],
        timestamp=data["timestamp"],
        labels=data["labels"],
        weather={int(code): text for code, text in data["weather"].items()},
    )


LOCALES = {path.stem: _load(path) for path in sorted(LOCALES_DIR.glob("*.json"))}

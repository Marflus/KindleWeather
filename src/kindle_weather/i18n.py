"""User-facing strings of the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Locale:
    code: str
    weekdays: tuple[str, ...]
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
        return f"{self.weekdays[day.weekday()][:3]} {day.day}"

    def format_updated_at(self, moment: datetime) -> str:
        return self.labels["updated"].format(moment.strftime(self.timestamp))

    def describe(self, weather_code: int) -> str:
        return self.weather.get(weather_code, self.labels["variable"])


ENGLISH = Locale(
    code="en",
    weekdays=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    months=(
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    long_date="{weekday}, {month} {day}, {year}",
    timestamp="%Y-%m-%d %H:%M",
    labels={
        "sunrise": "Sunrise",
        "sunset": "Sunset",
        "humidity": "Humidity",
        "wind": "Wind",
        "rain_risk": "Risk of rain in the next 24 hours",
        "storm_risk": "Risk of thunderstorms in the next 24 hours",
        "snow_risk": "Risk of snow in the next 24 hours",
        "no_precipitation": "No precipitation expected in the next 24 hours",
        "rain": "Rain",
        "storm": "Storm",
        "snow": "Snow",
        "updated": "Updated {}",
        "variable": "Variable weather",
        "kual_start": "Start weather station",
    },
    weather={
        0: "Clear sky",
        1: "Mostly sunny",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Freezing fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        56: "Freezing drizzle",
        57: "Freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Light showers",
        81: "Showers",
        82: "Violent showers",
        85: "Snow showers",
        86: "Snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Severe thunderstorm",
    },
)

FRENCH = Locale(
    code="fr",
    weekdays=("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"),
    months=(
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    long_date="{weekday} {day} {month} {year}",
    timestamp="%d/%m/%Y à %H:%M",
    labels={
        "sunrise": "Lever",
        "sunset": "Coucher",
        "humidity": "Humidité",
        "wind": "Vent",
        "rain_risk": "Risque de pluie dans les prochaines 24 h",
        "storm_risk": "Risque d'orage dans les prochaines 24 h",
        "snow_risk": "Risque de neige dans les prochaines 24 h",
        "no_precipitation": "Aucune précipitation prévue dans les prochaines 24 h",
        "rain": "Pluie",
        "storm": "Orage",
        "snow": "Neige",
        "updated": "Mis à jour le {}",
        "variable": "Temps variable",
        # KUAL menu labels stay ASCII: its menu parser is not known to handle accents.
        "kual_start": "Demarrer la station meteo",
    },
    weather={
        0: "Ciel dégagé",
        1: "Plutôt ensoleillé",
        2: "Partiellement nuageux",
        3: "Ciel couvert",
        45: "Brouillard",
        48: "Brouillard givrant",
        51: "Bruine légère",
        53: "Bruine",
        55: "Bruine soutenue",
        56: "Bruine verglaçante",
        57: "Bruine verglaçante",
        61: "Pluie faible",
        63: "Pluie",
        65: "Pluie forte",
        66: "Pluie verglaçante",
        67: "Pluie verglaçante",
        71: "Neige faible",
        73: "Neige",
        75: "Neige forte",
        77: "Grains de neige",
        80: "Averses faibles",
        81: "Averses",
        82: "Averses violentes",
        85: "Averses de neige",
        86: "Averses de neige",
        95: "Orage",
        96: "Orage avec grêle",
        99: "Orage violent",
    },
)

LOCALES = {locale.code: locale for locale in (ENGLISH, FRENCH)}

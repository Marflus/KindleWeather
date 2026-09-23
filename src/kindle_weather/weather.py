"""Open-Meteo client: city geocoding and today's forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 20
HEADERS = {"User-Agent": "KindleWeather"}

# WMO weather interpretation codes, grouped by icon.
FOG_CODES = frozenset({45, 48})
DRIZZLE_CODES = frozenset({51, 53, 55, 56, 57})
RAIN_CODES = frozenset({61, 63, 65, 66, 67, 80, 81, 82})
SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})
THUNDERSTORM_CODES = frozenset({95, 96, 99})

# Precipitation kinds, most important first.
PRECIPITATION_KINDS = ("snow", "storm", "rain")


def precipitation_kind(code: int) -> str | None:
    if code in SNOW_CODES:
        return "snow"
    if code in THUNDERSTORM_CODES:
        return "storm"
    if code in DRIZZLE_CODES or code in RAIN_CODES:
        return "rain"
    return None


class WeatherError(RuntimeError):
    pass


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class HourlyForecast:
    hour: int
    temperature: float
    weather_code: int
    humidity: int
    wind_speed: float


@dataclass(frozen=True)
class DailyForecast:
    place_name: str
    observed_at: datetime
    weather_code: int
    temperature_max: float
    temperature_min: float
    sunrise: str | None
    sunset: str | None
    hours: list[HourlyForecast]
    next_midnight: HourlyForecast | None

    def at(self, hour: int) -> HourlyForecast | None:
        return next((entry for entry in self.hours if entry.hour == hour), None)

    @property
    def precipitation_risk(self) -> str | None:
        """Most important precipitation kind expected today, if any."""
        kinds = {precipitation_kind(entry.weather_code) for entry in self.hours}
        return next((kind for kind in PRECIPITATION_KINDS if kind in kinds), None)


def geocode(city: str, country_code: str | None, language: str) -> Place:
    params = {"name": city, "count": 1, "language": language, "format": "json"}
    if country_code:
        params["countryCode"] = country_code
    results = _get_json(GEOCODING_URL, params).get("results")
    if not results:
        raise WeatherError(f"city not found: {city}")
    best = results[0]
    return Place(name=best["name"], latitude=best["latitude"], longitude=best["longitude"])


def fetch_forecast(place: Place) -> dict:
    return _get_json(
        FORECAST_URL,
        {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "hourly": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
            "timezone": "auto",
            "forecast_days": 2,
        },
    )


def parse_forecast(raw: dict, place_name: str, now: datetime | None = None) -> DailyForecast:
    now = now or datetime.now(ZoneInfo(raw["timezone"]))
    today = now.strftime("%Y-%m-%d")
    hourly, daily = raw["hourly"], raw["daily"]

    def entry(index: int) -> HourlyForecast:
        return HourlyForecast(
            hour=int(hourly["time"][index][11:13]),
            temperature=hourly["temperature_2m"][index],
            weather_code=hourly["weather_code"][index],
            humidity=hourly["relative_humidity_2m"][index],
            wind_speed=hourly["wind_speed_10m"][index],
        )

    indexes = [i for i, time in enumerate(hourly["time"]) if time.startswith(today)]
    if not indexes:
        raise WeatherError(f"no hourly forecast for {today}")
    next_index = indexes[-1] + 1
    day = daily["time"].index(today)

    return DailyForecast(
        place_name=place_name,
        observed_at=now,
        weather_code=daily["weather_code"][day],
        temperature_max=daily["temperature_2m_max"][day],
        temperature_min=daily["temperature_2m_min"][day],
        sunrise=_clock_time(daily["sunrise"][day]),
        sunset=_clock_time(daily["sunset"][day]),
        hours=[entry(i) for i in indexes],
        next_midnight=entry(next_index) if next_index < len(hourly["time"]) else None,
    )


def _clock_time(iso_datetime: str | None) -> str | None:
    return iso_datetime[11:16] if iso_datetime else None


def _get_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()

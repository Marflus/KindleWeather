"""Open-Meteo client: finds the city, then fetches and reads its forecast."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

from kindle_weather import dns

# The Kindle's Python may fail to resolve host names by itself.
dns.install()

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 20
HEADERS = {"User-Agent": "KindleWeather"}

WINDOW_HOURS = 24
UPCOMING_DAYS = 7

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


class LocationNotFound(WeatherError):
    pass


class ServiceUnreachable(WeatherError):
    """No answer from Open-Meteo: network error or timeout."""

    def __init__(self, message: str, tls: bool = False):
        super().__init__(message)
        # The secure connection failed, not the network.
        self.tls = tls


class ServiceError(WeatherError):
    """Open-Meteo answered with an HTTP error."""


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
class DayForecast:
    date: date
    weather_code: int
    temperature_max: float
    temperature_min: float

    @property
    def temperature_mean(self) -> int:
        return round((round(self.temperature_max) + round(self.temperature_min)) / 2)


@dataclass(frozen=True)
class Forecast:
    place_name: str
    observed_at: datetime
    temperature_unit: str
    today: DayForecast
    sunrise: str | None
    sunset: str | None
    # The next 24 hours, starting at the current hour.
    hours: list[HourlyForecast]
    # The hour right after that window, which closes the temperature curve.
    window_end: HourlyForecast | None
    upcoming_days: list[DayForecast]

    @property
    def current(self) -> HourlyForecast:
        """The hour in progress."""
        return self.hours[0]

    @property
    def precipitation_risk(self) -> str | None:
        """Most important precipitation kind expected in the next 24 hours, if any."""
        kinds = {precipitation_kind(entry.weather_code) for entry in self.hours}
        return next((kind for kind in PRECIPITATION_KINDS if kind in kinds), None)


def geocode(city: str, country_code: str | None, language: str) -> Place:
    params = {"name": city, "count": 1, "language": language, "format": "json"}
    if country_code:
        params["countryCode"] = country_code
    results = _get_json(GEOCODING_URL, params).get("results")
    if not results:
        where = f"{city}, {country_code}" if country_code else city
        raise LocationNotFound(f"city not found: {where}")
    try:
        best = results[0]
        return Place(
            name=best["name"],
            latitude=best["latitude"],
            longitude=best["longitude"],
        )
    except (KeyError, IndexError, TypeError) as error:
        raise WeatherError(f"unexpected geocoding data: {error!r}") from error


def fetch_forecast(place: Place, temperature_unit: str) -> Forecast:
    raw = _get_json(
        FORECAST_URL,
        {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "hourly": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
            "temperature_unit": temperature_unit,
            "timezone": "auto",
            "forecast_days": UPCOMING_DAYS + 1,
        },
    )
    return parse_forecast(raw, place.name)


def parse_forecast(raw: dict, place_name: str, now: datetime | None = None) -> Forecast:
    """The forecast from now on, from Open-Meteo's answer."""
    try:
        return _parse_forecast(raw, place_name, now)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise WeatherError(f"unexpected forecast data: {error!r}") from error


def _parse_forecast(raw: dict, place_name: str, now: datetime | None) -> Forecast:
    # The offset rather than the zone name: the Kindle has no time zone database.
    now = now or datetime.now(timezone(timedelta(seconds=raw["utc_offset_seconds"])))
    hourly, daily = raw["hourly"], raw["daily"]

    def hour_entry(index: int) -> HourlyForecast:
        return HourlyForecast(
            hour=int(hourly["time"][index][11:13]),
            temperature=hourly["temperature_2m"][index],
            weather_code=hourly["weather_code"][index],
            humidity=hourly["relative_humidity_2m"][index],
            wind_speed=hourly["wind_speed_10m"][index],
        )

    def day_entry(index: int) -> DayForecast:
        return DayForecast(
            date=date.fromisoformat(daily["time"][index]),
            weather_code=daily["weather_code"][index],
            temperature_max=daily["temperature_2m_max"][index],
            temperature_min=daily["temperature_2m_min"][index],
        )

    current_hour = now.strftime("%Y-%m-%dT%H:00")
    try:
        start = hourly["time"].index(current_hour)
    except ValueError:
        raise WeatherError(f"no hourly forecast for {current_hour}") from None
    end = start + WINDOW_HOURS
    today = daily["time"].index(now.strftime("%Y-%m-%d"))
    last_day = min(today + UPCOMING_DAYS, len(daily["time"]) - 1)

    return Forecast(
        place_name=place_name,
        observed_at=now,
        temperature_unit=raw["hourly_units"]["temperature_2m"],
        today=day_entry(today),
        sunrise=_clock_time(daily["sunrise"][today]),
        sunset=_clock_time(daily["sunset"][today]),
        hours=[hour_entry(i) for i in range(start, min(end, len(hourly["time"])))],
        window_end=hour_entry(end) if end < len(hourly["time"]) else None,
        upcoming_days=[day_entry(i) for i in range(today + 1, last_day + 1)],
    )


def _clock_time(iso_datetime: str | None) -> str | None:
    return iso_datetime[11:16] if iso_datetime else None


def _get_json(url: str, params: dict) -> dict:
    query = urlencode(params)
    try:
        return _request(f"{url}?{query}")
    except ServiceUnreachable as error:
        if not error.tls:
            raise
    # The Kindle's certificates may be too old for the server's: fall back to HTTP.
    return _request(f"http://{url.split('://', 1)[1]}?{query}")


def _request(url: str) -> dict:
    host = urlsplit(url).hostname
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise ServiceError(_http_error_message(error)) from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        tls = isinstance(reason, ssl.SSLError)
        raise ServiceUnreachable(f"{host}: {reason}", tls=tls) from error
    try:
        return json.loads(body)
    except ValueError as error:
        raise WeatherError(f"{host} did not answer with JSON") from error


def _http_error_message(error: urllib.error.HTTPError) -> str:
    message = f"HTTP {error.code} {error.reason or ''}".rstrip()
    try:
        # Open-Meteo explains rejected requests in a "reason" field.
        reason = json.loads(error.read()).get("reason")
    except (ValueError, AttributeError, OSError):
        reason = None
    return f"{message}: {reason}" if reason else message

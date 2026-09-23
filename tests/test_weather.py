from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from kindle_meteo import weather
from kindle_meteo.weather import WeatherError, geocode, parse_forecast


def test_parse_forecast_keeps_today_and_next_midnight(forecast):
    assert [entry.hour for entry in forecast.hours] == list(range(24))
    assert forecast.next_midnight.hour == 0
    assert forecast.temperature_max == 18.4
    assert (forecast.sunrise, forecast.sunset) == ("06:32", "18:41")


def test_forecast_lookup_and_rain_flag(forecast):
    assert forecast.at(10).weather_code == 61
    assert forecast.at(24) is None
    assert forecast.has_rain


def test_parse_forecast_rejects_data_without_today(raw_forecast):
    new_year = datetime(2027, 1, 1, tzinfo=ZoneInfo("Europe/Warsaw"))
    with pytest.raises(WeatherError, match="2027-01-01"):
        parse_forecast(raw_forecast, "Varsovie", now=new_year)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_geocode_returns_localized_name(monkeypatch):
    calls = []

    def fake_get(url, params, **kwargs):
        calls.append(params)
        return FakeResponse(
            {"results": [{"name": "Varsovie", "latitude": 52.2, "longitude": 21.0}]}
        )

    monkeypatch.setattr(weather.requests, "get", fake_get)
    place = geocode("Warsaw", "PL", "fr")

    assert place.name == "Varsovie"
    assert calls[0]["countryCode"] == "PL"
    assert calls[0]["language"] == "fr"


def test_geocode_unknown_city(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", lambda *args, **kwargs: FakeResponse({}))
    with pytest.raises(WeatherError, match="city not found"):
        geocode("Atlantis", None, "en")

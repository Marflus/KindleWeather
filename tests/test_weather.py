from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from kindle_weather import weather
from kindle_weather.weather import LocationNotFound, WeatherError, geocode, parse_forecast


def test_window_starts_at_the_current_hour(forecast):
    # conftest.NOW is 06:04: the window runs from 06:00 to 05:00 the next day.
    assert [entry.hour for entry in forecast.hours] == [*range(6, 24), *range(6)]
    assert forecast.hours[4].weather_code == 61
    assert forecast.window_end.hour == 6


def test_summary_describes_today(forecast):
    assert forecast.today.date == date(2026, 9, 23)
    assert forecast.today.temperature_max == 18.4
    assert forecast.today.temperature_mean == 12
    assert (forecast.sunrise, forecast.sunset) == ("06:32", "18:41")
    assert forecast.temperature_unit == "°C"


def test_upcoming_days_start_tomorrow(forecast):
    assert len(forecast.upcoming_days) == 7
    assert forecast.upcoming_days[0].date == date(2026, 9, 24)
    assert forecast.upcoming_days[-1].date == date(2026, 9, 30)
    assert forecast.upcoming_days[5].weather_code == 71


def test_window_is_cut_short_at_the_end_of_the_data(raw_forecast):
    evening = datetime(2026, 9, 24, 20, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
    forecast = parse_forecast(raw_forecast, "Varsovie", now=evening)
    assert [entry.hour for entry in forecast.hours] == [20, 21, 22, 23]
    assert forecast.window_end is None


@pytest.mark.parametrize(
    ("codes", "risk"),
    [
        ([0, 3, 45], None),
        ([0, 51, 61], "rain"),
        ([61, 95, 63], "storm"),
        ([61, 95, 71], "snow"),
    ],
)
def test_precipitation_risk_priority(forecast, codes, risk):
    hours = [replace(forecast.hours[i], weather_code=code) for i, code in enumerate(codes)]
    assert replace(forecast, hours=hours).precipitation_risk == risk


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
    with pytest.raises(LocationNotFound, match="city not found: Atlantis, GR"):
        geocode("Atlantis", "GR", "en")


def test_geocode_rejects_malformed_results(monkeypatch):
    payload = {"results": [{"name": "Lyon"}]}
    monkeypatch.setattr(weather.requests, "get", lambda *args, **kwargs: FakeResponse(payload))
    with pytest.raises(WeatherError, match="unexpected geocoding data"):
        geocode("Lyon", None, "en")

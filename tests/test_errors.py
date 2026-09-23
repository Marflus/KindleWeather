import pytest
import requests

from kindle_weather import errors
from kindle_weather.config import ConfigError
from kindle_weather.i18n import LOCALES
from kindle_weather.weather import LocationNotFound, WeatherError

FORECAST_REQUEST = requests.Request("GET", "https://api.open-meteo.com/v1/forecast").prepare()


def http_error(status: int, body: bytes) -> requests.HTTPError:
    response = requests.Response()
    response.status_code, response.reason, response._content = status, "Bad Request", body
    return requests.HTTPError(response=response, request=FORECAST_REQUEST)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (requests.ConnectionError(request=FORECAST_REQUEST), errors.WEATHER_UNREACHABLE),
        (requests.ReadTimeout(request=FORECAST_REQUEST), errors.WEATHER_UNREACHABLE),
        (http_error(429, b""), errors.WEATHER_SERVICE),
        (requests.TooManyRedirects(), errors.WEATHER_SERVICE),
        (LocationNotFound("city not found: Atlantis"), errors.LOCATION_NOT_FOUND),
        (WeatherError("no hourly forecast"), errors.INVALID_WEATHER_DATA),
        (requests.JSONDecodeError("Expecting value", "<html>", 0), errors.INVALID_WEATHER_DATA),
        (ConfigError("location.city is required"), errors.INVALID_CONFIG),
        (ZeroDivisionError("division by zero"), errors.RENDER_FAILED),
    ],
)
def test_classify(error, expected):
    assert errors.classify(error) is expected


def test_describe_names_the_unreachable_host():
    error = requests.ConnectionError("very long urllib3 message", request=FORECAST_REQUEST)
    assert errors.describe(error) == "ConnectionError: api.open-meteo.com"


def test_describe_quotes_the_open_meteo_reason():
    error = http_error(400, b'{"error": true, "reason": "Latitude must be in range of -90 to 90"}')
    assert errors.describe(error) == "HTTP 400 Bad Request: Latitude must be in range of -90 to 90"
    assert errors.describe(http_error(400, b"<html>")) == "HTTP 400 Bad Request"


def test_codes_are_unique_and_translated():
    codes = [
        errors.WEATHER_UNREACHABLE,
        errors.WEATHER_SERVICE,
        errors.LOCATION_NOT_FOUND,
        errors.INVALID_WEATHER_DATA,
        errors.INVALID_CONFIG,
        errors.RENDER_FAILED,
        *errors.KINDLE_ERRORS.values(),
    ]
    assert [code.code for code in codes] == [f"E{i}" for i in range(1, len(codes) + 1)]
    for locale in LOCALES.values():
        assert all(locale.labels[code.label] for code in codes)

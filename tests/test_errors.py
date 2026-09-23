import pytest

from kindle_weather import errors
from kindle_weather.config import ConfigError
from kindle_weather.i18n import LOCALES
from kindle_weather.weather import (
    LocationNotFound,
    ServiceError,
    ServiceUnreachable,
    WeatherError,
)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ServiceUnreachable("api.open-meteo.com: timed out"), errors.WEATHER_UNREACHABLE),
        (ServiceError("HTTP 429 Too Many Requests"), errors.WEATHER_SERVICE),
        (LocationNotFound("city not found: Atlantis"), errors.LOCATION_NOT_FOUND),
        (WeatherError("no hourly forecast"), errors.INVALID_WEATHER_DATA),
        (ConfigError("location.city is required"), errors.INVALID_CONFIG),
        (ZeroDivisionError("division by zero"), errors.RENDER_FAILED),
    ],
)
def test_classify(error, expected):
    assert errors.classify(error) is expected


def test_describe():
    assert errors.describe(ServiceError("HTTP 429")) == "HTTP 429"
    assert errors.describe(KeyError()) == "KeyError"


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

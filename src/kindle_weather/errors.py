"""Error codes shown on the Kindle; the README lists them with their causes."""

from __future__ import annotations

from dataclasses import dataclass

from kindle_weather.config import ConfigError
from kindle_weather.i18n import LOCALES
from kindle_weather.weather import (
    LocationNotFound,
    ServiceError,
    ServiceUnreachable,
    WeatherError,
)


@dataclass(frozen=True)
class ErrorCode:
    code: str
    # Locale label describing the error.
    label: str


# Raised while rendering the dashboard, shown full screen instead of it.
WEATHER_UNREACHABLE = ErrorCode("E1", "error_unreachable")
WEATHER_SERVICE = ErrorCode("E2", "error_service")
LOCATION_NOT_FOUND = ErrorCode("E3", "error_location")
INVALID_WEATHER_DATA = ErrorCode("E4", "error_data")
INVALID_CONFIG = ErrorCode("E5", "error_config")
RENDER_FAILED = ErrorCode("E6", "error_render")

# Raised on the Kindle by station.sh, shown on top of the last dashboard,
# by the settings.sh variable holding their message.
KINDLE_ERRORS = {
    "WIFI_ERROR": ErrorCode("E7", "error_wifi"),
    "PYTHON_ERROR": ErrorCode("E8", "error_python"),
}


def classify(error: Exception) -> ErrorCode:
    """Error code for an exception raised while rendering the dashboard."""
    if isinstance(error, ConfigError):
        return INVALID_CONFIG
    if isinstance(error, LocationNotFound):
        return LOCATION_NOT_FOUND
    if isinstance(error, ServiceUnreachable):
        return WEATHER_UNREACHABLE
    if isinstance(error, ServiceError):
        return WEATHER_SERVICE
    if isinstance(error, WeatherError):
        return INVALID_WEATHER_DATA
    return RENDER_FAILED


# Errors are shown in English, whatever the display language.
ERROR_LOCALE = LOCALES["en"]


def message(error: ErrorCode) -> str:
    """The one-line message of an error, such as "Error E1: Weather service unreachable"."""
    labels = ERROR_LOCALE.labels
    return f"{labels['error']} {error.code}: {labels[error.label]}"


def describe(error: Exception) -> str:
    """Short technical detail for the error screen and the log."""
    return str(error) or type(error).__name__

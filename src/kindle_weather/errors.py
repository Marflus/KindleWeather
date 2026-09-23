"""Error codes shown on the Kindle; the README lists them with their causes."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from kindle_weather.config import ConfigError
from kindle_weather.weather import LocationNotFound, WeatherError


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
    "SERVER_ERROR": ErrorCode("E8", "error_server"),
    "NOT_FOUND_ERROR": ErrorCode("E9", "error_not_found"),
    "SECURE_ERROR": ErrorCode("E10", "error_secure"),
    "INVALID_FILE_ERROR": ErrorCode("E11", "error_invalid_file"),
    "OUTDATED_ERROR": ErrorCode("E12", "error_outdated"),
    "DOWNLOAD_ERROR": ErrorCode("E13", "error_download"),
}


def classify(error: Exception) -> ErrorCode:
    """Error code for an exception raised while rendering the dashboard."""
    if isinstance(error, ConfigError):
        return INVALID_CONFIG
    if isinstance(error, LocationNotFound):
        return LOCATION_NOT_FOUND
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return WEATHER_UNREACHABLE
    # A response that is not JSON is bad data, not an unavailable service.
    if isinstance(error, (WeatherError, requests.JSONDecodeError)):
        return INVALID_WEATHER_DATA
    if isinstance(error, requests.RequestException):
        return WEATHER_SERVICE
    return RENDER_FAILED


def describe(error: Exception) -> str:
    """Short technical detail for the error screen and the workflow log."""
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        host = urlparse(error.request.url).hostname if error.request else None
        return f"{type(error).__name__}: {host or 'no response'}"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        response = error.response
        detail = f"HTTP {response.status_code} {response.reason or ''}".rstrip()
        try:
            # Open-Meteo explains rejected requests in a "reason" field.
            reason = response.json().get("reason")
        except (ValueError, AttributeError):
            reason = None
        return f"{detail}: {reason}" if reason else detail
    return str(error) or type(error).__name__

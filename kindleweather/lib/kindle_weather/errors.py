"""Error codes shown on the Kindle, always in English. The README lists them.

E7 (no Wi-Fi) and E8 (no Python) are raised by the shell scripts, see bin/common.sh.
"""

from __future__ import annotations

from dataclasses import dataclass

from kindle_weather.config import ConfigError
from kindle_weather.weather import (
    LocationNotFound,
    ServiceError,
    ServiceUnreachable,
    WeatherError,
)


@dataclass(frozen=True)
class ErrorCode:
    code: str
    text: str

    @property
    def message(self) -> str:
        """One line for the top of the screen, such as "Error E1: Weather service unreachable"."""
        return f"Error {self.code}: {self.text}"


WEATHER_UNREACHABLE = ErrorCode("E1", "Weather service unreachable")
WEATHER_SERVICE = ErrorCode("E2", "Weather service error")
LOCATION_NOT_FOUND = ErrorCode("E3", "Location not found, check the configuration")
INVALID_WEATHER_DATA = ErrorCode("E4", "Invalid weather data")
INVALID_CONFIG = ErrorCode("E5", "Invalid configuration")
RENDER_FAILED = ErrorCode("E6", "Dashboard rendering failed")


def classify(error: Exception) -> ErrorCode:
    """Error code for an exception raised while making the dashboard."""
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

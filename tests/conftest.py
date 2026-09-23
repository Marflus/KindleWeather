import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from kindle_weather.weather import parse_forecast

TIMEZONE = "Europe/Warsaw"
NOW = datetime(2026, 9, 23, 6, 4, tzinfo=ZoneInfo(TIMEZONE))
# Dry night, rain from 09:00 to 15:00, thunderstorm in the evening.
HOURLY_CODES = [0, 0, 1, 1, 2, 2, 3, 3, 45, 61, 61, 63, 63, 80, 81, 3, 2, 1, 0, 0, 95, 96, 3, 0]


@pytest.fixture
def raw_forecast():
    """Open-Meteo /v1/forecast response for two days, as requested by fetch_forecast()."""
    times = [f"2026-09-{day}T{hour:02d}:00" for day in (23, 24) for hour in range(24)]
    return {
        "timezone": TIMEZONE,
        "daily": {
            "time": ["2026-09-23", "2026-09-24"],
            "weather_code": [63, 3],
            "temperature_2m_max": [18.4, 16.0],
            "temperature_2m_min": [6.6, 7.0],
            "sunrise": ["2026-09-23T06:32", "2026-09-24T06:34"],
            "sunset": ["2026-09-23T18:41", "2026-09-24T18:38"],
        },
        "hourly": {
            "time": times,
            "temperature_2m": [12 + 6 * math.sin((i % 24 - 9) * math.pi / 12) for i in range(48)],
            "weather_code": HOURLY_CODES * 2,
            "relative_humidity_2m": [60 + i % 30 for i in range(48)],
            "wind_speed_10m": [5 + i % 15 for i in range(48)],
        },
    }


@pytest.fixture
def forecast(raw_forecast):
    return parse_forecast(raw_forecast, "Varsovie", now=NOW)

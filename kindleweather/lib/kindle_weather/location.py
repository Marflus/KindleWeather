"""Finds the city from the internet connection, for the "Detect automatically" buttons.

A free service locates the connection's IP address, usually to the nearest
large city; that city is then looked up with Open-Meteo, as a search would.
"""

from __future__ import annotations

import math

from kindle_weather.weather import (
    LocationNotFound,
    Place,
    ServiceUnreachable,
    WeatherError,
    get_json,
    search_places,
)

# Tried in order: HTTPS first, then a service that only answers over HTTP.
IP_SERVICES = ("https://ipinfo.io/json", "http://ip-api.com/json/")


def detect_place(language: str) -> Place:
    city, country_code, latitude, longitude = _locate_connection()
    places = search_places(city, language, country_code)
    if not places:
        raise LocationNotFound(f"city not found: {city}, {country_code}")

    # The place of that name nearest to the located position.
    def distance(place: Place) -> float:
        east = (place.longitude - longitude) * math.cos(math.radians(latitude))
        return east**2 + (place.latitude - latitude) ** 2

    return min(places, key=distance)


def _locate_connection() -> tuple[str, str, float, float]:
    """City, country code, latitude and longitude of the internet connection."""
    error: WeatherError = ServiceUnreachable("no location service")
    for url in IP_SERVICES:
        try:
            answer = get_json(url, {})
            if "loc" in answer:  # ipinfo.io: "loc": "52.23,21.01"
                latitude, longitude = map(float, answer["loc"].split(","))
                return answer["city"], answer["country"], latitude, longitude
            return answer["city"], answer["countryCode"], answer["lat"], answer["lon"]
        except WeatherError as failure:
            error = failure
        except (KeyError, ValueError, AttributeError):
            error = WeatherError(f"{url} did not give a location")
    raise error

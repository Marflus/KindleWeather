"""The dashboard for the configured city, or the error screen saying why there is none."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from kindle_weather.config import load_config
from kindle_weather.errors import ErrorCode, classify, describe
from kindle_weather.i18n import LOCALES, Locale
from kindle_weather.render import render_dashboard, render_error
from kindle_weather.weather import fetch_forecast, geocode, parse_forecast


@dataclass(frozen=True)
class Dashboard:
    image: Image.Image
    place_name: str | None = None
    # Set when image is an error screen.
    error: Exception | None = None

    @property
    def failure(self) -> ErrorCode | None:
        return classify(self.error) if self.error else None

    @property
    def summary(self) -> str:
        if self.error is None:
            return f"dashboard for {self.place_name}"
        return f"error {self.failure.code}: {describe(self.error)}"


def build_dashboard(config_path: Path) -> Dashboard:
    config = None
    try:
        config = load_config(config_path)
        place = geocode(config.location.city, config.location.country_code, config.locale.code)
        forecast = parse_forecast(fetch_forecast(place, config.temperature_unit), place.name)
        image = render_dashboard(
            forecast, config.locale, config.display_size, config.orientation, config.icon_set
        )
        return Dashboard(image, place_name=place.name)
    except Exception as error:
        failure, detail = classify(error), describe(error)
        if config:
            screen = render_error(
                failure, config.locale, config.display_size, config.orientation, detail=detail
            )
        else:
            screen = render_error(failure, fallback_locale(config_path), detail=detail)
        return Dashboard(screen, error=error)


def fallback_locale(config_path: Path) -> Locale:
    """Language of an invalid configuration, if it can still be read."""
    try:
        language = json.loads(Path(config_path).read_text(encoding="utf-8")).get("language")
    except (OSError, ValueError, AttributeError):
        language = None
    return LOCALES[language] if isinstance(language, str) and language in LOCALES else LOCALES["en"]

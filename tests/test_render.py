from dataclasses import replace

import pytest
from PIL import ImageChops

from kindle_weather.errors import WEATHER_UNREACHABLE
from kindle_weather.i18n import LOCALES
from kindle_weather.render import precipitation_runs, render_dashboard, render_error

ENGLISH, FRENCH = LOCALES["en"], LOCALES["fr"]


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_output_fits_the_portrait_framebuffer(forecast, orientation):
    image = render_dashboard(forecast, ENGLISH, size=(1236, 1648), orientation=orientation)
    assert image.mode == "L"
    assert image.size == (1236, 1648)
    assert image.getextrema() == (0, 255)


def test_landscape_differs_from_portrait(forecast):
    portrait = render_dashboard(forecast, ENGLISH)
    landscape = render_dashboard(forecast, ENGLISH, orientation="landscape")
    assert ImageChops.difference(portrait, landscape).getbbox() is not None


def test_language_changes_the_output(forecast):
    english = render_dashboard(forecast, ENGLISH)
    french = render_dashboard(forecast, FRENCH)
    assert ImageChops.difference(english, french).getbbox() is not None


@pytest.mark.parametrize("icon_set", ["weather-icons", "material"])
def test_icon_set_changes_the_output(forecast, icon_set):
    classic = render_dashboard(forecast, ENGLISH)
    other = render_dashboard(forecast, ENGLISH, icon_set=icon_set)
    assert ImageChops.difference(classic, other).getbbox() is not None


def test_precipitation_runs_split_by_kind():
    codes = [0, 61, 63, 95, 96, 51, 3, 73, 0]
    assert precipitation_runs(codes) == [
        ("rain", 1, 3),
        ("storm", 3, 5),
        ("rain", 5, 6),
        ("snow", 7, 8),
    ]
    assert precipitation_runs([0, 1, 2, 45]) == []


def test_renders_without_upcoming_days(forecast):
    image = render_dashboard(replace(forecast, upcoming_days=[]), FRENCH)
    assert image.size == (1072, 1448)


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_error_screen_fits_the_framebuffer(orientation):
    image = render_error(
        WEATHER_UNREACHABLE,
        FRENCH,
        size=(1072, 1448),
        orientation=orientation,
        detail="ConnectionError: api.open-meteo.com " * 10,
    )
    assert image.size == (1072, 1448)
    assert image.getextrema() == (0, 255)

from PIL import ImageChops

from kindle_meteo.i18n import ENGLISH, FRENCH
from kindle_meteo.render import rainy_runs, render_dashboard


def test_render_produces_grayscale_image_of_requested_size(forecast):
    image = render_dashboard(forecast, ENGLISH, size=(1236, 1648))
    assert image.mode == "L"
    assert image.size == (1236, 1648)
    assert image.getextrema() == (0, 255)


def test_language_changes_the_output(forecast):
    english = render_dashboard(forecast, ENGLISH)
    french = render_dashboard(forecast, FRENCH)
    assert ImageChops.difference(english, french).getbbox() is not None


def test_rainy_runs_groups_consecutive_rainy_hours():
    assert rainy_runs([0, 61, 63, 3, 95, 0]) == [(1, 3), (4, 5)]
    assert rainy_runs([0, 1, 2]) == []

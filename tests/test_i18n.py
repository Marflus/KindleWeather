from datetime import datetime

import pytest

from kindle_meteo.i18n import ENGLISH, FRENCH, LOCALES

MOMENT = datetime(2026, 9, 23, 6, 4)


def test_locales_define_the_same_strings():
    assert ENGLISH.labels.keys() == FRENCH.labels.keys()
    assert ENGLISH.weather.keys() == FRENCH.weather.keys()


@pytest.mark.parametrize("locale", LOCALES.values(), ids=LOCALES.keys())
def test_kual_label_is_ascii(locale):
    assert locale.labels["kual_show"].isascii()


def test_long_dates():
    assert ENGLISH.format_long_date(MOMENT) == "Wednesday, September 23, 2026"
    assert FRENCH.format_long_date(MOMENT) == "Mercredi 23 septembre 2026"


def test_footer_timestamps():
    assert ENGLISH.format_updated_at(MOMENT) == "Updated 2026-09-23 06:04"
    assert FRENCH.format_updated_at(MOMENT) == "Mis à jour le 23/09/2026 à 06:04"


def test_unknown_weather_code_falls_back():
    assert ENGLISH.describe(1234) == "Variable weather"

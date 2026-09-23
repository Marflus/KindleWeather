from datetime import date, datetime

import pytest

from kindle_weather.i18n import LOCALES

MOMENT = datetime(2026, 9, 23, 6, 4)
ENGLISH = LOCALES["en"]


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_locale_is_complete(code):
    locale = LOCALES[code]
    assert locale.labels.keys() == ENGLISH.labels.keys()
    assert locale.weather.keys() == ENGLISH.weather.keys()
    assert len(locale.weekdays) == len(locale.short_weekdays) == 7
    assert len(locale.months) == 12
    assert locale.format_long_date(MOMENT)
    assert locale.format_updated_at(MOMENT)


def test_available_languages():
    assert set(LOCALES) == {"de", "en", "es", "fr", "it", "nl", "pl", "pt"}


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("en", "Wednesday, September 23, 2026"),
        ("fr", "Mercredi 23 septembre 2026"),
        ("de", "Mittwoch, 23. September 2026"),
        ("pl", "Środa, 23 września 2026"),
    ],
)
def test_long_dates(code, expected):
    assert LOCALES[code].format_long_date(MOMENT) == expected


def test_short_dates():
    assert ENGLISH.format_short_date(date(2026, 9, 24)) == "Thu 24"
    assert LOCALES["fr"].format_short_date(date(2026, 9, 24)) == "Jeu 24"


def test_footer_timestamps():
    assert ENGLISH.format_updated_at(MOMENT) == "Updated 2026-09-23 06:04"
    assert LOCALES["fr"].format_updated_at(MOMENT) == "Mis à jour le 23/09/2026 à 06:04"


def test_unknown_weather_code_falls_back():
    assert ENGLISH.describe(1234) == "Variable weather"

from pathlib import Path

import pytest

from kindle_weather.config import ConfigError, load_config, parse_config

VALID = {
    "language": "en",
    "location": {"city": "Lyon"},
    "dashboard_url": "https://example.org/dashboard.png",
}


def test_repository_config_is_valid():
    config = load_config(Path(__file__).parents[1] / "config" / "config.json")
    assert config.locale.code in ("en", "fr")


def test_defaults():
    config = parse_config(VALID)
    assert config.display_size == (1072, 1448)
    assert config.orientation == "portrait"
    assert config.temperature_unit == "celsius"
    assert config.location.country_code is None


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"language": "de"}, "language"),
        ({"location": {"city": " "}}, "location.city"),
        ({"display": {"width": 0, "height": 1448}}, "display"),
        ({"display": {"orientation": "diagonal"}}, "display.orientation"),
        ({"temperature_unit": "kelvin"}, "temperature_unit"),
        ({"dashboard_url": None}, "dashboard_url"),
        ({"dashboard_url": "ftp://example.org/dashboard.png"}, "dashboard_url"),
    ],
)
def test_invalid_values_are_rejected(override, message):
    with pytest.raises(ConfigError, match=message):
        parse_config({**VALID, **override})


def test_unreadable_file(tmp_path):
    (tmp_path / "config.json").write_text("{not json")
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "config.json")

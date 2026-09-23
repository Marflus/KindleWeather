import os
from pathlib import Path

import pytest

from kindle_weather.config import ConfigError, default_config_path, load_config, parse_config

VALID = {
    "language": "en",
    "location": {"city": "Lyon"},
}


def test_repository_config_is_valid():
    config = load_config(Path(__file__).parents[1] / "config" / "config.json")
    assert config.locale.code in ("en", "fr")


def test_defaults():
    config = parse_config(VALID)
    assert config.display_size == (1072, 1448)
    assert config.orientation == "portrait"
    assert config.icon_set == "classic"
    assert config.temperature_unit == "celsius"
    assert config.location.country_code is None


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"language": "xx"}, "language"),
        ({"location": {"city": " "}}, "location.city"),
        ({"location": "Lyon"}, "location"),
        ({"location": {"city": "Lyon", "country_code": "FRA"}}, "location.country_code"),
        ({"display": [1072, 1448]}, "display"),
        ({"display": {"width": 0, "height": 1448}}, "display"),
        ({"display": {"orientation": "diagonal"}}, "display.orientation"),
        ({"display": {"icons": "emoji"}}, "display.icons"),
        ({"temperature_unit": "kelvin"}, "temperature_unit"),
    ],
)
def test_invalid_values_are_rejected(override, message):
    with pytest.raises(ConfigError, match=message):
        parse_config({**VALID, **override})


def test_country_code_is_normalized():
    config = parse_config({**VALID, "location": {"city": "Lyon", "country_code": "fr"}})
    assert config.location.country_code == "FR"


def test_configuration_must_be_an_object():
    with pytest.raises(ConfigError, match="JSON object"):
        parse_config(["en"])


def test_unreadable_file(tmp_path):
    (tmp_path / "config.json").write_text("{not json")
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "config.json")


def test_default_config_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "settings"))
    assert default_config_path() == tmp_path / "settings" / "kindle-weather" / "config.json"
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.json").write_text("{}")
    assert default_config_path() == Path("config/config.json")


def test_missing_file_suggests_init(tmp_path):
    with pytest.raises(ConfigError, match="kindle-weather init"):
        load_config(tmp_path / "missing.json")

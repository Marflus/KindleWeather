import json

import pytest
import requests

from kindle_weather import wizard
from kindle_weather.config import load_config
from kindle_weather.weather import LocationNotFound, Place


@pytest.fixture(autouse=True)
def local_url(monkeypatch):
    monkeypatch.setattr(wizard, "dashboard_url", lambda: "http://192.168.1.20:8080/dashboard.png")


def answers(*values):
    remaining = list(values)
    return lambda question: remaining.pop(0)


def test_wizard_writes_a_valid_config(tmp_path, monkeypatch):
    def fake_geocode(city, country_code, language):
        if city == "Atlantis":
            raise LocationNotFound(city)
        return Place("Varsovie", 52.2, 21.0, country="Pologne", country_code="PL")

    monkeypatch.setattr(wizard, "geocode", fake_geocode)
    said = []
    path = tmp_path / "config" / "config.json"
    # Language, unknown city then a valid one, model, orientation (invalid then
    # valid), unit, icons, URL.
    ask = answers("fr", "Atlantis", "Warsaw", "3", "sideways", "landscape", "", "material", "")
    config = wizard.run_wizard(path, ask=ask, say=said.append)

    assert json.loads(path.read_text()) == config
    loaded = load_config(path)
    assert loaded.locale.code == "fr"
    assert loaded.location.city == "Warsaw" and loaded.location.country_code == "PL"
    assert loaded.display_size == (1236, 1648)
    assert loaded.orientation == "landscape"
    assert loaded.temperature_unit == "celsius"
    assert loaded.icon_set == "material"
    assert loaded.dashboard_url == "http://192.168.1.20:8080/dashboard.png"
    assert any("Atlantis was not found" in line for line in said)
    assert any("Found Varsovie, Pologne (PL)" in line for line in said)


def test_wizard_defaults_to_the_current_config(tmp_path, monkeypatch):
    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(wizard, "geocode", offline)
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "language": "de",
                "location": {"city": "Berlin", "country_code": "DE"},
                "display": {"width": 758, "height": 1024, "icons": "weather-icons"},
                "temperature_unit": "fahrenheit",
            }
        )
    )
    config = wizard.run_wizard(path, ask=answers(*[""] * 8), say=lambda line: None)
    assert config["language"] == "de"
    assert config["location"] == {"city": "Berlin", "country_code": "DE"}
    assert config["display"] == {
        "width": 758,
        "height": 1024,
        "orientation": "portrait",
        "icons": "weather-icons",
    }
    assert config["temperature_unit"] == "fahrenheit"


def test_wizard_leaves_out_an_unknown_country(tmp_path, monkeypatch):
    monkeypatch.setattr(wizard, "geocode", lambda *args: Place("Lyon", 45.7, 4.8))
    ask = answers("en", "Lyon", *[""] * 6)
    config = wizard.run_wizard(tmp_path / "config.json", ask=ask, say=lambda line: None)
    assert config["location"] == {"city": "Lyon"}

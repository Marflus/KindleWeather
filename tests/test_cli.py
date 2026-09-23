import json

import pytest
import requests
from PIL import Image

from kindle_weather import cli, render
from kindle_weather.weather import LocationNotFound

CONFIG = {"language": "en", "location": {"city": "Lyon"}, "dashboard_url": "https://x.org/d.png"}


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Run `render` with the given config; return the exit code and the error code shown."""
    shown = []
    real_render_error = render.render_error

    def spy(error, *args, **kwargs):
        shown.append(error.code)
        return real_render_error(error, *args, **kwargs)

    monkeypatch.setattr(cli, "render_error", spy)

    def run_render(config):
        path = tmp_path / "config.json"
        path.write_text(config if isinstance(config, str) else json.dumps(config))
        output = tmp_path / "site" / "dashboard.png"
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--config", str(path), "render", "--output", str(output)])
        assert Image.open(output).size == (1072, 1448)
        return exit_info.value.code, shown[-1]

    return run_render


def fail_with(monkeypatch, error):
    def fake_get(*args, **kwargs):
        raise error

    monkeypatch.setattr(requests, "get", fake_get)


def test_offline_render_writes_the_unreachable_screen(run, monkeypatch):
    fail_with(monkeypatch, requests.ConnectionError("no network"))
    assert run(CONFIG) == (1, "E1")


def test_unknown_city_writes_the_location_screen(run, monkeypatch):
    fail_with(monkeypatch, LocationNotFound("city not found: Lyon"))
    assert run(CONFIG) == (1, "E3")


def test_invalid_config_writes_the_config_screen(run):
    assert run({**CONFIG, "language": "fr", "location": {}}) == (1, "E5")
    assert run("{not json") == (1, "E5")


def test_unexpected_errors_keep_their_traceback(tmp_path, monkeypatch):
    fail_with(monkeypatch, ZeroDivisionError("bug"))
    path = tmp_path / "config.json"
    path.write_text(json.dumps(CONFIG))
    output = tmp_path / "dashboard.png"
    with pytest.raises(ZeroDivisionError):
        cli.main(["--config", str(path), "render", "--output", str(output)])
    assert output.exists()


def test_fallback_locale_reads_the_language_of_an_invalid_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"language": "fr"}))
    assert cli._fallback_locale(path).code == "fr"
    path.write_text(json.dumps({"language": ["fr"]}))
    assert cli._fallback_locale(path).code == "en"
    assert cli._fallback_locale(tmp_path / "missing.json").code == "en"

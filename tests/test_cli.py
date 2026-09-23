import json

import pytest
import requests
from PIL import Image

from kindle_weather import cli
from kindle_weather.dashboard import build_dashboard, fallback_locale
from kindle_weather.weather import LocationNotFound

CONFIG = {"language": "en", "location": {"city": "Lyon"}, "dashboard_url": "https://x.org/d.png"}


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(CONFIG))
    return path


def fail_with(monkeypatch, error):
    def fake_get(*args, **kwargs):
        raise error

    monkeypatch.setattr(requests, "get", fake_get)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (requests.ConnectionError("no network"), "E1"),
        (LocationNotFound("city not found: Lyon"), "E3"),
        (ZeroDivisionError("bug"), "E6"),
    ],
)
def test_failures_give_an_error_screen(config_path, monkeypatch, error, code):
    fail_with(monkeypatch, error)
    dashboard = build_dashboard(config_path)
    assert dashboard.failure.code == code
    assert dashboard.summary.startswith(f"error {code}: ")
    assert dashboard.image.size == (1072, 1448)


@pytest.mark.parametrize("content", ['{"language": "fr", "location": {}}', "{not json"])
def test_invalid_config_gives_the_config_screen(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    assert build_dashboard(path).failure.code == "E5"


def test_render_writes_the_error_screen_and_fails(config_path, monkeypatch, tmp_path):
    fail_with(monkeypatch, requests.ConnectionError("no network"))
    output = tmp_path / "site" / "dashboard.png"
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--config", str(config_path), "render", "--output", str(output)])
    assert exit_info.value.code == 1
    assert Image.open(output).size == (1072, 1448)


def test_render_keeps_the_traceback_of_unexpected_errors(config_path, monkeypatch, tmp_path):
    fail_with(monkeypatch, ZeroDivisionError("bug"))
    output = tmp_path / "dashboard.png"
    with pytest.raises(ZeroDivisionError):
        cli.main(["--config", str(config_path), "render", "--output", str(output)])
    assert output.exists()


def test_install_finds_the_kindle(config_path, monkeypatch, tmp_path):
    kindle = tmp_path / "Kindle"
    for folder in ("documents", "system", "extensions"):
        (kindle / folder).mkdir(parents=True)
    monkeypatch.setattr(cli, "find_kindle", lambda: kindle)
    assert cli.main(["--config", str(config_path), "install"]) == 0
    assert (kindle / "extensions" / "kindleweather" / "bin" / "station.sh").exists()


def test_fallback_locale_reads_the_language_of_an_invalid_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"language": "fr"}))
    assert fallback_locale(path).code == "fr"
    path.write_text(json.dumps({"language": ["fr"]}))
    assert fallback_locale(path).code == "en"
    assert fallback_locale(tmp_path / "missing.json").code == "en"

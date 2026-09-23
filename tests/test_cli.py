import json
import urllib.error

import pytest
from conftest import png_size

from kindle_weather import cli
from kindle_weather.dashboard import build_dashboard, fallback_locale

CONFIG = {"language": "fr", "location": {"city": "Lyon"}}
GEOCODED = {"results": [{"name": "Lyon", "latitude": 45.7, "longitude": 4.8}]}


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(CONFIG))
    return path


OFFLINE = urllib.error.URLError(OSError("no network"))


@pytest.mark.parametrize(
    ("answers", "code"),
    [
        ([OFFLINE], "E1"),
        ([{}], "E3"),
        ([GEOCODED, {"hourly": {}}], "E4"),
    ],
)
def test_failures_give_an_error_screen(config_path, http, answers, code):
    http.answers.extend(answers)
    dashboard = build_dashboard(config_path)
    assert dashboard.failure.code == code
    assert dashboard.summary.startswith(f"error {code}: ")
    assert dashboard.image.size == (1072, 1448)


def test_bugs_give_the_render_failed_screen(config_path, monkeypatch):
    def bug(*args):
        raise ZeroDivisionError("bug")

    monkeypatch.setattr("kindle_weather.dashboard.geocode", bug)
    assert build_dashboard(config_path).failure.code == "E6"


@pytest.mark.parametrize("content", ['{"language": "fr", "location": {}}', "{not json"])
def test_invalid_config_gives_the_config_screen(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    assert build_dashboard(path).failure.code == "E5"


def test_render_writes_the_error_screen_and_fails(config_path, http, tmp_path):
    http.answers.append(OFFLINE)
    output = tmp_path / "site" / "dashboard.png"
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--config", str(config_path), "render", "--output", str(output)])
    assert exit_info.value.code == 1
    assert png_size(output) == (1072, 1448)


def test_refresh_draws_the_dashboard(config_path, http, raw_forecast, tmp_path, capsys):
    http.answers.extend([GEOCODED, raw_forecast])
    output = tmp_path / "dashboard.png"
    assert cli.main(["--config", str(config_path), "refresh", "--output", str(output)]) == 0
    assert png_size(output) == (1072, 1448)
    assert capsys.readouterr().out == ""


def test_refresh_keeps_the_last_dashboard_on_error(config_path, http, tmp_path, capsys):
    output = tmp_path / "dashboard.png"
    output.write_bytes(b"last dashboard")
    http.answers.append(OFFLINE)
    cli.main(["--config", str(config_path), "refresh", "--output", str(output)])
    assert output.read_bytes() == b"last dashboard"
    # The line station.sh shows on top of it, in ASCII for eips.
    assert capsys.readouterr().out == "Erreur E1: Service meteo injoignable\n"


def test_refresh_writes_the_error_screen_without_dashboard(config_path, http, tmp_path):
    output = tmp_path / "dashboard.png"
    http.answers.append({})
    cli.main(["--config", str(config_path), "refresh", "--output", str(output)])
    assert png_size(output) == (1072, 1448)


def test_refresh_survives_a_missing_cairo(config_path, monkeypatch, tmp_path, capsys):
    def no_cairo(*args, **kwargs):
        raise OSError("libcairo.so.2: cannot open shared object file")

    monkeypatch.setattr("kindle_weather.dashboard.build_dashboard", no_cairo)
    monkeypatch.setattr(cli, "build_dashboard", no_cairo)
    cli.main(["--config", str(config_path), "refresh", "--output", str(tmp_path / "d.png")])
    assert capsys.readouterr().out.startswith("Erreur E6: ")


def test_kual_files_follow_the_config(config_path, tmp_path):
    cli.main(["--config", str(config_path), "kual-files", str(tmp_path)])
    menu = json.loads((tmp_path / "menu.json").read_text())
    assert menu["items"][0]["items"][0]["name"] == "Demarrer la station meteo"
    assert "E7: Pas de connexion Wi-Fi" in (tmp_path / "settings.sh").read_text()


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

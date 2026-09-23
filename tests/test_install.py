import json
import re

import pytest

from kindle_weather import errors
from kindle_weather.config import load_config
from kindle_weather.i18n import LOCALES
from kindle_weather.install import (
    DEFAULT_EXTENSION_SOURCE,
    InstallError,
    ascii_fold,
    find_kindle,
    install_extension,
)

# Every message the Kindle may show on top of the dashboard.
ALL_ERRORS = [
    errors.WEATHER_UNREACHABLE,
    errors.WEATHER_SERVICE,
    errors.LOCATION_NOT_FOUND,
    errors.INVALID_WEATHER_DATA,
    errors.INVALID_CONFIG,
    errors.RENDER_FAILED,
    *errors.KINDLE_ERRORS.values(),
]

FRENCH_CONFIG = {"language": "fr", "location": {"city": "Lyon"}}


@pytest.fixture
def kindle(tmp_path):
    (tmp_path / "Kindle" / "extensions").mkdir(parents=True)
    return tmp_path / "Kindle"


def install(kindle, tmp_path, **overrides):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({**FRENCH_CONFIG, **overrides}))
    return install_extension(kindle, load_config(config_path), config_path)


def test_installed_extension_layout(kindle, tmp_path):
    target = install(kindle, tmp_path)

    assert target == kindle / "extensions" / "kindleweather"
    files = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()}
    assert {"config.xml", "menu.json", "settings.sh", "config.json", "bin/station.sh"} <= files
    # The Python package that draws the dashboard, with its fonts and texts.
    assert {
        "lib/kindle_weather/__main__.py",
        "lib/kindle_weather/canvas.py",
        "lib/kindle_weather/fonts/Roboto-Bold.ttf",
        "lib/kindle_weather/icon_fonts/weathericons.ttf",
        "lib/kindle_weather/locales/fr.json",
    } <= files
    assert not any("__pycache__" in name or "kindle_extension" in name for name in files)
    assert json.loads((target / "config.json").read_text()) == FRENCH_CONFIG


def test_reinstall_replaces_the_package(kindle, tmp_path):
    target = install(kindle, tmp_path)
    stale = target / "lib" / "kindle_weather" / "removed_module.py"
    stale.write_text("")
    install(kindle, tmp_path)
    assert not stale.exists()


def test_menu_starts_the_station_detached(kindle, tmp_path):
    target = install(kindle, tmp_path)
    item = json.loads((target / "menu.json").read_text())["items"][0]["items"][0]
    assert item["name"] == "Demarrer la station meteo"
    assert item["action"].startswith("setsid ") and "bin/station.sh" in item["action"]


def test_settings_are_a_unix_shell_file(kindle, tmp_path):
    target = install(kindle, tmp_path, dashboard_url="https://x.org/a b.png")
    assert (target / "settings.sh").read_bytes() == (
        b"DASHBOARD_URL='https://x.org/a b.png'\n"
        b"WIFI_ERROR='Erreur E7: Pas de connexion Wi-Fi'\n"
        b"PYTHON_ERROR='Erreur E8: Python 3 absent, installez-le avec MRPI'\n"
        b"SERVER_ERROR='Erreur E9: Serveur du tableau de bord injoignable'\n"
        b"NOT_FOUND_ERROR='Erreur E10: Tableau de bord introuvable sur le serveur'\n"
        b"SECURE_ERROR='Erreur E11: Echec de la connexion securisee'\n"
        b"INVALID_FILE_ERROR='Erreur E12: Fichier du tableau de bord invalide'\n"
        b"OUTDATED_ERROR='Erreur E13: Tableau de bord perime'\n"
        b"DOWNLOAD_ERROR='Erreur E14: Echec du telechargement du tableau de bord'\n"
        b"LOW_BATTERY_WARNING='Batterie faible'\n"
    )


def test_the_kindle_draws_its_dashboard_without_dashboard_url(kindle, tmp_path):
    target = install(kindle, tmp_path)
    assert (target / "settings.sh").read_text().startswith("DASHBOARD_URL=''\n")


def test_settings_define_every_message_station_sh_uses(kindle, tmp_path):
    target = install(kindle, tmp_path)
    defined = {line.split("=")[0] for line in (target / "settings.sh").read_text().splitlines()}
    script = (DEFAULT_EXTENSION_SOURCE / "bin" / "station.sh").read_text()
    used = set(re.findall(r"\$\{?([A-Z_]+(?:_ERROR|_WARNING|_URL))\b", script))
    assert used == defined


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_kindle_side_text_is_ascii(code):
    labels = LOCALES[code].labels
    keys = ["kual_start", "error", "low_battery", *(e.label for e in ALL_ERRORS)]
    for key in keys:
        folded = ascii_fold(labels[key])
        assert folded.isascii()
        assert len(folded) >= len(labels[key]) - 1


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_kindle_messages_fit_on_one_line(code):
    labels = LOCALES[code].labels
    for error in ALL_ERRORS:
        assert len(f"{labels['error']} {error.code}: {labels[error.label]}") <= 60


def test_ascii_fold_keeps_letters_without_decomposition():
    assert ascii_fold("Błąd, Straße") == "Blad, Strasse"


def test_find_kindle_picks_the_kindle_drive(tmp_path):
    usb_stick, kindle = tmp_path / "usb", tmp_path / "Kindle"
    (usb_stick / "documents").mkdir(parents=True)
    for folder in ("documents", "system"):
        (kindle / folder).mkdir(parents=True)
    assert find_kindle([usb_stick, kindle, tmp_path / "missing"]) == kindle
    with pytest.raises(InstallError, match="no Kindle found"):
        find_kindle([usb_stick])
    second = tmp_path / "Kindle2"
    for folder in ("documents", "system"):
        (second / folder).mkdir(parents=True)
    with pytest.raises(InstallError, match="several Kindles"):
        find_kindle([kindle, second])


def test_install_requires_kual(tmp_path):
    with pytest.raises(InstallError, match="KUAL"):
        install(tmp_path, tmp_path)

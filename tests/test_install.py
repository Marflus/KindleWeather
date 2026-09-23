import json
import re
from pathlib import Path

import pytest

from kindle_weather.errors import KINDLE_ERRORS
from kindle_weather.i18n import LOCALES
from kindle_weather.install import InstallError, ascii_fold, install_extension

FRENCH = LOCALES["fr"]

EXTENSION_SOURCE = Path(__file__).parents[1] / "kindle" / "extension"
URL = "https://example.org/dashboard.png"


@pytest.fixture
def kindle(tmp_path):
    (tmp_path / "extensions").mkdir()
    return tmp_path


def test_installed_extension_layout(kindle):
    target = install_extension(EXTENSION_SOURCE, kindle, FRENCH, URL)

    assert target == kindle / "extensions" / "kindleweather"
    files = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()}
    assert files == {"config.xml", "menu.json", "settings.sh", "bin/station.sh"}


def test_menu_starts_the_station_detached(kindle):
    target = install_extension(EXTENSION_SOURCE, kindle, FRENCH, URL)
    item = json.loads((target / "menu.json").read_text())["items"][0]["items"][0]
    assert item["name"] == "Demarrer la station meteo"
    assert item["action"].startswith("setsid ") and "bin/station.sh" in item["action"]


def test_settings_are_a_unix_shell_file(kindle):
    target = install_extension(EXTENSION_SOURCE, kindle, FRENCH, "https://x.org/a b.png")
    assert (target / "settings.sh").read_bytes() == (
        b"DASHBOARD_URL='https://x.org/a b.png'\n"
        b"WIFI_ERROR='Erreur E7: Pas de connexion Wi-Fi'\n"
        b"SERVER_ERROR='Erreur E8: Serveur du tableau de bord injoignable'\n"
        b"NOT_FOUND_ERROR='Erreur E9: Tableau de bord introuvable sur le serveur'\n"
        b"SECURE_ERROR='Erreur E10: Echec de la connexion securisee'\n"
        b"INVALID_FILE_ERROR='Erreur E11: Fichier du tableau de bord invalide'\n"
        b"OUTDATED_ERROR='Erreur E12: Tableau de bord perime'\n"
        b"DOWNLOAD_ERROR='Erreur E13: Echec du telechargement du tableau de bord'\n"
        b"LOW_BATTERY_WARNING='Batterie faible'\n"
    )


def test_settings_define_every_message_station_sh_uses(kindle):
    target = install_extension(EXTENSION_SOURCE, kindle, FRENCH, URL)
    defined = {line.split("=")[0] for line in (target / "settings.sh").read_text().splitlines()}
    script = (EXTENSION_SOURCE / "bin" / "station.sh").read_text()
    used = set(re.findall(r"\$\{?([A-Z_]+(?:_ERROR|_WARNING|_URL))\b", script))
    assert used == defined


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_kindle_side_text_is_ascii(code):
    labels = LOCALES[code].labels
    keys = ["kual_start", "error", "low_battery", *(e.label for e in KINDLE_ERRORS.values())]
    for key in keys:
        folded = ascii_fold(labels[key])
        assert folded.isascii()
        assert len(folded) >= len(labels[key]) - 1


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_kindle_messages_fit_on_one_line(code):
    labels = LOCALES[code].labels
    for error in KINDLE_ERRORS.values():
        assert len(f"{labels['error']} {error.code}: {labels[error.label]}") <= 60


def test_ascii_fold_keeps_letters_without_decomposition():
    assert ascii_fold("Błąd, Straße") == "Blad, Strasse"


def test_install_requires_kual(tmp_path):
    with pytest.raises(InstallError, match="KUAL"):
        install_extension(EXTENSION_SOURCE, tmp_path, FRENCH, URL)

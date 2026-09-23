import json
from pathlib import Path

import pytest

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
        b"WIFI_ERROR='Erreur E2: Pas de connexion Wi-Fi'\n"
        b"DOWNLOAD_ERROR='Erreur E3: Echec du telechargement du tableau de bord'\n"
    )


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_kindle_side_text_is_ascii(code):
    labels = LOCALES[code].labels
    for key in ("kual_start", "error", "error_wifi", "error_download"):
        folded = ascii_fold(labels[key])
        assert folded.isascii()
        assert len(folded) >= len(labels[key]) - 1


def test_ascii_fold_keeps_letters_without_decomposition():
    assert ascii_fold("Błąd, Straße") == "Blad, Strasse"


def test_install_requires_kual(tmp_path):
    with pytest.raises(InstallError, match="KUAL"):
        install_extension(EXTENSION_SOURCE, tmp_path, FRENCH, URL)

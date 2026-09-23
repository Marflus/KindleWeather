import json
from pathlib import Path

import pytest

from kindle_weather.i18n import FRENCH
from kindle_weather.install import InstallError, install_extension

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
    assert item["name"] == FRENCH.labels["kual_start"]
    assert item["action"].startswith("setsid ") and "bin/station.sh" in item["action"]


def test_settings_are_a_unix_shell_file(kindle):
    target = install_extension(EXTENSION_SOURCE, kindle, FRENCH, "https://x.org/a b.png")
    assert (target / "settings.sh").read_bytes() == b"DASHBOARD_URL='https://x.org/a b.png'\n"


def test_install_requires_kual(tmp_path):
    with pytest.raises(InstallError, match="KUAL"):
        install_extension(EXTENSION_SOURCE, tmp_path, FRENCH, URL)

"""Installs the KUAL extension on a Kindle mounted as a USB drive."""

from __future__ import annotations

import json
import shlex
import shutil
import unicodedata
from pathlib import Path

from kindle_weather.i18n import Locale

EXTENSION_NAME = "kindleweather"
DEFAULT_EXTENSION_SOURCE = Path("kindle/extension")
# Letters that Unicode decomposition does not reduce to ASCII.
_ASCII_REPLACEMENTS = str.maketrans({"ł": "l", "Ł": "L", "ß": "ss"})


class InstallError(RuntimeError):
    pass


def install_extension(source: Path, mount_path: Path, locale: Locale, dashboard_url: str) -> Path:
    extensions = mount_path / "extensions"
    if not extensions.is_dir():
        raise InstallError(f"{extensions} not found: is the Kindle mounted and KUAL installed?")
    target = extensions / EXTENSION_NAME
    shutil.copytree(source, target, dirs_exist_ok=True)

    menu = {
        "items": [
            {
                "name": "KindleWeather",
                "priority": 1,
                "items": [
                    {
                        "name": ascii_fold(locale.labels["kual_start"]),
                        "priority": 1,
                        # setsid keeps the loop alive once it stops KUAL and the interface.
                        "action": "setsid sh bin/station.sh &",
                    }
                ],
            }
        ]
    }
    _write_unix_text(target / "menu.json", json.dumps(menu, indent=2) + "\n")
    labels = locale.labels
    settings = {
        "DASHBOARD_URL": dashboard_url,
        "WIFI_ERROR": ascii_fold(f"{labels['error']} E2: {labels['error_wifi']}"),
        "DOWNLOAD_ERROR": ascii_fold(f"{labels['error']} E3: {labels['error_download']}"),
    }
    lines = "".join(f"{name}={shlex.quote(value)}\n" for name, value in settings.items())
    _write_unix_text(target / "settings.sh", lines)
    return target


def ascii_fold(text: str) -> str:
    """Drop accents: KUAL menus and eips only render ASCII reliably."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_ASCII_REPLACEMENTS))
    return decomposed.encode("ascii", "ignore").decode()


def _write_unix_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

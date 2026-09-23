"""Installs the KUAL extension on a Kindle mounted as a USB drive."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

from kindle_weather.i18n import Locale

EXTENSION_NAME = "kindleweather"
DEFAULT_EXTENSION_SOURCE = Path("kindle/extension")


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
                        "name": locale.labels["kual_start"],
                        "priority": 1,
                        # setsid keeps the loop alive once it stops KUAL and the interface.
                        "action": "setsid sh bin/station.sh &",
                    }
                ],
            }
        ]
    }
    _write_unix_text(target / "menu.json", json.dumps(menu, indent=2) + "\n")
    _write_unix_text(target / "settings.sh", f"DASHBOARD_URL={shlex.quote(dashboard_url)}\n")
    return target


def _write_unix_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

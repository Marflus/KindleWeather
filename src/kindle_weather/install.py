"""Installs the KUAL extension on a Kindle mounted as a USB drive."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import string
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from kindle_weather.errors import KINDLE_ERRORS
from kindle_weather.i18n import Locale

EXTENSION_NAME = "kindleweather"
DEFAULT_EXTENSION_SOURCE = Path(__file__).parent / "kindle_extension"
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
    settings = {"DASHBOARD_URL": dashboard_url}
    for name, error in KINDLE_ERRORS.items():
        settings[name] = ascii_fold(f"{labels['error']} {error.code}: {labels[error.label]}")
    settings["LOW_BATTERY_WARNING"] = ascii_fold(labels["low_battery"])
    lines = "".join(f"{name}={shlex.quote(value)}\n" for name, value in settings.items())
    _write_unix_text(target / "settings.sh", lines)
    return target


def find_kindle(candidates: Iterable[Path] | None = None) -> Path:
    """Mount point of the single Kindle plugged in over USB."""
    if candidates is None:
        candidates = _mount_points()
    kindles = sorted({path for path in candidates if _looks_like_kindle(path)})
    if not kindles:
        raise InstallError("no Kindle found: plug it in over USB, or pass its drive path")
    if len(kindles) > 1:
        found = ", ".join(str(path) for path in kindles)
        raise InstallError(f"several Kindles found ({found}): pass the drive path")
    return kindles[0]


def _mount_points() -> list[Path]:
    if os.name == "nt":
        # Drive letters from D:, after the system drive and the floppy letters.
        return [Path(f"{letter}:/") for letter in string.ascii_uppercase[3:]]
    patterns = ("media/*", "media/*/*", "run/media/*/*", "mnt/*", "Volumes/*")
    return [path for pattern in patterns for path in Path("/").glob(pattern)]


def _looks_like_kindle(path: Path) -> bool:
    try:
        return (path / "documents").is_dir() and (path / "system").is_dir()
    except OSError:
        return False


def ascii_fold(text: str) -> str:
    """Drop accents: KUAL menus and eips only render ASCII reliably."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_ASCII_REPLACEMENTS))
    return decomposed.encode("ascii", "ignore").decode()


def _write_unix_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

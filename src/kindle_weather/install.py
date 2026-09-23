"""Installs the KUAL extension, with the Python package that draws the dashboard, on a Kindle."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import string
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from kindle_weather.config import Config
from kindle_weather.errors import KINDLE_ERRORS, message

EXTENSION_NAME = "kindleweather"
PACKAGE_DIR = Path(__file__).parent
DEFAULT_EXTENSION_SOURCE = PACKAGE_DIR / "kindle_extension"
# Letters that Unicode decomposition does not reduce to ASCII.
_ASCII_REPLACEMENTS = str.maketrans({"ł": "l", "Ł": "L", "ß": "ss"})


class InstallError(RuntimeError):
    pass


def install_extension(
    mount_path: Path,
    config: Config,
    config_path: Path,
    source: Path = DEFAULT_EXTENSION_SOURCE,
) -> Path:
    """Copy the extension to the Kindle drive at mount_path; return its folder."""
    extensions = mount_path / "extensions"
    if not extensions.is_dir():
        raise InstallError(
            f"{extensions} not found: is the Kindle mounted and KUAL installed?"
            " Create the folder if KUAL is installed without it."
        )
    target = extensions / EXTENSION_NAME
    build_extension(target, config, config_path, source)
    return target


def build_extension(
    target: Path, config: Config, config_path: Path, source: Path = DEFAULT_EXTENSION_SOURCE
) -> None:
    """Lay out the extension folder: scripts, Python package, configuration, KUAL files."""
    shutil.copytree(source, target, dirs_exist_ok=True)
    package = target / "lib" / "kindle_weather"
    if package.exists():
        shutil.rmtree(package)
    shutil.copytree(
        PACKAGE_DIR,
        package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", source.name),
    )
    shutil.copyfile(config_path, target / "config.json")
    write_kual_files(target, config)


def write_kual_files(target: Path, config: Config) -> None:
    """The KUAL menu and settings.sh, in the configured language."""
    labels = config.locale.labels
    menu = {
        "items": [
            {
                "name": "KindleWeather",
                "priority": 1,
                "items": [
                    {
                        "name": ascii_fold(labels["kual_start"]),
                        "priority": 1,
                        # start.sh detaches the station from KUAL, which it stops.
                        "action": "sh bin/start.sh",
                    },
                    {
                        "name": ascii_fold(labels["kual_diagnostic"]),
                        "priority": 2,
                        "action": "sh bin/diagnose.sh",
                    },
                ],
            }
        ]
    }
    _write_unix_text(target / "menu.json", json.dumps(menu, indent=2) + "\n")
    settings = {}
    for name, error in KINDLE_ERRORS.items():
        settings[name] = message(error)
    settings["LOW_BATTERY_WARNING"] = ascii_fold(labels["low_battery"])
    settings["STARTING_MESSAGE"] = ascii_fold(labels["starting"])
    lines = "".join(f"{name}={shlex.quote(value)}\n" for name, value in settings.items())
    _write_unix_text(target / "settings.sh", lines)


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
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)

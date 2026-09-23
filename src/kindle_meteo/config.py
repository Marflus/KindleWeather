"""Loading and validation of config/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kindle_meteo.i18n import LOCALES, Locale

DEFAULT_CONFIG_PATH = Path("config/config.json")
DEPLOY_METHODS = ("ssh", "usb")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Location:
    city: str
    country_code: str | None = None


@dataclass(frozen=True)
class KindleTarget:
    method: str
    host: str | None = None
    user: str = "root"
    ssh_key: str | None = None
    mount_path: str | None = None


@dataclass(frozen=True)
class Config:
    locale: Locale
    location: Location
    display_size: tuple[int, int]
    kindle: KindleTarget


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    return parse_config(raw)


def parse_config(raw: dict) -> Config:
    language = raw.get("language", "en")
    _require(language in LOCALES, f"language must be one of {sorted(LOCALES)}")

    location = raw.get("location", {})
    city = location.get("city")
    _require(isinstance(city, str) and city.strip(), "location.city is required")

    display = raw.get("display", {})
    width, height = display.get("width", 1072), display.get("height", 1448)
    _require(
        isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0,
        "display.width and display.height must be positive integers",
    )

    kindle = raw.get("kindle", {})
    target = KindleTarget(
        method=kindle.get("method", "ssh"),
        host=kindle.get("host") or None,
        user=kindle.get("user") or "root",
        ssh_key=kindle.get("ssh_key") or None,
        mount_path=kindle.get("mount_path") or None,
    )
    _require(target.method in DEPLOY_METHODS, f"kindle.method must be one of {DEPLOY_METHODS}")
    _require(target.method != "ssh" or target.host, "kindle.host is required for ssh")
    _require(target.method != "usb" or target.mount_path, "kindle.mount_path is required for usb")

    return Config(
        locale=LOCALES[language],
        location=Location(city=city.strip(), country_code=location.get("country_code") or None),
        display_size=(width, height),
        kindle=target,
    )


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)

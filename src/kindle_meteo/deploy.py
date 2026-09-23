"""Installs the KUAL extension and the rendered dashboard on a Kindle."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from kindle_meteo.config import KindleTarget
from kindle_meteo.i18n import Locale

EXTENSION_NAME = "kindlemeteo"
DEFAULT_EXTENSION_SOURCE = Path("kindle/extension")
REMOTE_EXTENSIONS_DIR = "/mnt/us/extensions"
REMOTE_EXTENSION_DIR = f"{REMOTE_EXTENSIONS_DIR}/{EXTENSION_NAME}"
RETRY_DELAY = 10


class DeployError(RuntimeError):
    pass


def stage_extension(source: Path, image: Path, locale: Locale, destination: Path) -> Path:
    """Assemble the extension folder exactly as it must appear on the Kindle."""
    staged = destination / EXTENSION_NAME
    shutil.copytree(source, staged, dirs_exist_ok=True)
    shutil.copyfile(image, staged / "dashboard.png")
    menu = {
        "items": [
            {
                "name": "KindleMeteo",
                "priority": 1,
                "items": [
                    {"name": locale.labels["kual_show"], "priority": 1, "action": "bin/show.sh"}
                ],
            }
        ]
    }
    (staged / "menu.json").write_text(json.dumps(menu, indent=2) + "\n", encoding="utf-8")
    return staged


def deploy_usb(staged: Path, mount_path: Path) -> None:
    extensions = mount_path / "extensions"
    if not extensions.is_dir():
        raise DeployError(f"{extensions} not found: is the Kindle mounted and KUAL installed?")
    shutil.copytree(staged, extensions / EXTENSION_NAME, dirs_exist_ok=True)


def deploy_ssh(staged: Path, target: KindleTarget, wait_seconds: int = 0) -> None:
    options = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    options += ["-o", "ConnectTimeout=10"]
    if target.ssh_key:
        options += ["-i", str(Path(target.ssh_key).expanduser())]
    address = f"{target.user}@{target.host}"

    _run_until_success(
        ["ssh", *options, address, f"mkdir -p {REMOTE_EXTENSIONS_DIR}"], wait_seconds
    )
    _run(["scp", *options, "-r", str(staged), f"{address}:{REMOTE_EXTENSIONS_DIR}/"])
    _run(
        [
            "ssh",
            *options,
            address,
            f"sh {REMOTE_EXTENSION_DIR}/bin/install.sh; "
            "lipc-set-prop com.lab126.powerd flIntensity 0; "
            f"sh {REMOTE_EXTENSION_DIR}/bin/show.sh",
        ]
    )


def _run(command: list[str]) -> None:
    if subprocess.run(command).returncode != 0:
        raise DeployError(f"command failed: {' '.join(command)}")


def _run_until_success(command: list[str], wait_seconds: int) -> None:
    deadline = time.monotonic() + wait_seconds
    while subprocess.run(command).returncode != 0:
        if time.monotonic() >= deadline:
            raise DeployError("the Kindle is unreachable over SSH")
        print(f"Kindle unreachable, retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

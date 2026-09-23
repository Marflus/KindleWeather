import json
import subprocess
from pathlib import Path

import pytest

from kindle_weather.config import KindleTarget
from kindle_weather.deploy import DeployError, deploy_ssh, deploy_usb, stage_extension
from kindle_weather.i18n import FRENCH

EXTENSION_SOURCE = Path(__file__).parents[1] / "kindle" / "extension"


@pytest.fixture
def staged(tmp_path):
    image = tmp_path / "dashboard.png"
    image.write_bytes(b"png")
    return stage_extension(EXTENSION_SOURCE, image, FRENCH, tmp_path / "stage")


def test_staged_extension_layout(staged):
    files = {path.relative_to(staged).as_posix() for path in staged.rglob("*") if path.is_file()}
    assert files == {
        "config.xml",
        "menu.json",
        "dashboard.png",
        "bin/show.sh",
        "bin/watchdog.sh",
        "bin/install.sh",
    }
    item = json.loads((staged / "menu.json").read_text())["items"][0]["items"][0]
    assert item == {"name": FRENCH.labels["kual_show"], "priority": 1, "action": "bin/show.sh"}


def test_usb_deploy_copies_into_kual_extensions(staged, tmp_path):
    mount = tmp_path / "kindle"
    (mount / "extensions").mkdir(parents=True)
    deploy_usb(staged, mount)
    assert (mount / "extensions" / "kindleweather" / "dashboard.png").read_bytes() == b"png"


def test_usb_deploy_requires_kual(staged, tmp_path):
    with pytest.raises(DeployError, match="KUAL"):
        deploy_usb(staged, tmp_path)


def fake_run(commands, returncode):
    def run(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, returncode)

    return run


def test_ssh_deploy_commands(staged, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", fake_run(commands, 0))
    deploy_ssh(staged, KindleTarget(method="ssh", host="kindle", ssh_key="/keys/id"))

    assert [command[0] for command in commands] == ["ssh", "scp", "ssh"]
    for command in commands:
        assert command[command.index("-i") + 1] == "/keys/id"
    assert commands[1][-1] == "root@kindle:/mnt/us/extensions/"
    assert "bin/install.sh" in commands[2][-1]
    assert "bin/show.sh" in commands[2][-1]


def test_ssh_deploy_gives_up_when_unreachable(staged, monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", fake_run(commands, 255))
    with pytest.raises(DeployError, match="unreachable"):
        deploy_ssh(staged, KindleTarget(method="ssh", host="kindle"))
    assert len(commands) == 1

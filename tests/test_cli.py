import json

import pytest
import requests
from PIL import Image

from kindle_weather import cli


def test_render_writes_an_error_screen_without_weather_data(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {"language": "en", "location": {"city": "Lyon"}, "dashboard_url": "https://x.org/d.png"}
        )
    )

    def offline(*args, **kwargs):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(requests, "get", offline)
    output = tmp_path / "site" / "dashboard.png"

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--config", str(config), "render", "--output", str(output)])

    assert exit_info.value.code == 1
    assert Image.open(output).size == (1072, 1448)

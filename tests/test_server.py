import threading
import urllib.request
from email.utils import parsedate_to_datetime

import pytest
from PIL import Image

from kindle_weather import server
from kindle_weather.dashboard import Dashboard


@pytest.fixture
def renders(monkeypatch):
    calls = []

    def fake_build(config_path):
        calls.append(config_path)
        return Dashboard(Image.new("L", (10, 20), 255), place_name="Lyon")

    monkeypatch.setattr(server, "build_dashboard", fake_build)
    return calls


def test_cache_renders_again_once_stale(renders, tmp_path):
    now = [1000.0]
    cache = server.DashboardCache(tmp_path / "config.json", max_age=600, clock=lambda: now[0])
    png, rendered_at = cache.get()
    assert png.startswith(b"\x89PNG") and rendered_at == 1000.0
    now[0] += 599
    cache.get()
    assert len(renders) == 1
    now[0] += 1
    assert cache.get()[1] == 1600.0
    assert len(renders) == 2


def test_server_serves_the_dashboard_and_a_page(renders, tmp_path):
    cache = server.DashboardCache(tmp_path / "config.json", clock=lambda: 1_700_000_000.0)
    http = server.make_server(cache, "127.0.0.1", 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{http.server_port}"
    try:
        with urllib.request.urlopen(f"{base}/dashboard.png?t=1") as response:
            assert response.headers["Content-Type"] == "image/png"
            modified = parsedate_to_datetime(response.headers["Last-Modified"])
            assert modified.timestamp() == 1_700_000_000
            assert Image.open(response).size == (10, 20)
        with urllib.request.urlopen(base) as response:
            assert b'src="dashboard.png"' in response.read()
        with pytest.raises(urllib.error.HTTPError, match="404"):
            urllib.request.urlopen(f"{base}/other")
    finally:
        http.shutdown()
        http.server_close()


def test_dashboard_url_points_at_this_computer(monkeypatch):
    monkeypatch.setattr(server, "local_ip", lambda: "192.168.1.20")
    assert server.dashboard_url(8080) == "http://192.168.1.20:8080/dashboard.png"

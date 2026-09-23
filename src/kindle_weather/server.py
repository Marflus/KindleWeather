"""Serves the dashboard to the Kindle, rendered when it asks for it."""

from __future__ import annotations

import io
import socket
import sys
import threading
import time
import traceback
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from kindle_weather.dashboard import build_dashboard
from kindle_weather.errors import RENDER_FAILED

DEFAULT_PORT = 8080
DASHBOARD_PATH = "/dashboard.png"
# Reuse a dashboard this recent, so a browser refresh does not query Open-Meteo.
CACHE_SECONDS = 600

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>KindleWeather</title>
<style>body{margin:0;background:#eee;text-align:center}img{max-height:100vh;max-width:100%}</style>
<img src="dashboard.png" alt="Dashboard">
"""


class DashboardCache:
    def __init__(self, config_path: Path, max_age: float = CACHE_SECONDS, clock=time.time):
        self.config_path = config_path
        self.max_age = max_age
        self.clock = clock
        self._lock = threading.Lock()
        self._png: bytes | None = None
        self._rendered_at = 0.0

    def get(self) -> tuple[bytes, float]:
        """PNG of the dashboard, rendered again once older than max_age, and its render time."""
        with self._lock:
            if self._png is None or self.clock() - self._rendered_at >= self.max_age:
                dashboard = build_dashboard(self.config_path)
                if dashboard.failure is RENDER_FAILED:
                    traceback.print_exception(dashboard.error, file=sys.stderr)
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} rendered {dashboard.summary}")
                buffer = io.BytesIO()
                dashboard.image.save(buffer, format="PNG")
                self._png, self._rendered_at = buffer.getvalue(), self.clock()
            return self._png, self._rendered_at


def make_server(cache: DashboardCache, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == DASHBOARD_PATH:
                # Error screens are served too: the Kindle shows them.
                png, rendered_at = cache.get()
                # The Kindle dates the file from Last-Modified to spot a stale dashboard.
                self._send(png, "image/png", formatdate(rendered_at, usegmt=True))
            elif path == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            else:
                self.send_error(404)

        def _send(self, body: bytes, content_type: str, last_modified: str | None = None):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if last_modified:
                self.send_header("Last-Modified", last_modified)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.address_string()} {format % args}")

    return ThreadingHTTPServer((host, port), Handler)


def serve(config_path: Path, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    server = make_server(DashboardCache(config_path), host, port)
    print(f"Serving the dashboard at {dashboard_url(port)} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def dashboard_url(port: int = DEFAULT_PORT) -> str:
    return f"http://{local_ip()}:{port}{DASHBOARD_PATH}"


def local_ip() -> str:
    """Address of this computer on the local network."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            # Connecting a UDP socket sends nothing; it only picks the outgoing interface.
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"

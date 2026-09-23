"""The settings page, served by the Kindle: python3 -m kindle_weather.web

bin/web.sh opens it in the Kindle's browser; a phone or a computer on the same
Wi-Fi can open it too. The page is plain HTML forms, without JavaScript, for
the Kindle's basic browser. The server stops with the "Close" button, or after
15 minutes without a request.
"""

from __future__ import annotations

import html
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

from kindle_weather.config import load_config
from kindle_weather.location import detect_place
from kindle_weather.settings import (
    CONFIG_PATH,
    EXTENSION_DIR,
    SETTINGS,
    change,
    current_values,
    set_place,
    write_menu,
)
from kindle_weather.weather import Place, WeatherError, geocode, search_places

PORT = 8765
IDLE_SECONDS = 15 * 60
# Written while the server runs, for bin/web.sh.
PID_FILE = EXTENSION_DIR / "web.pid"
# Lets a phone on the same Wi-Fi reach the page through the Kindle's firewall.
FIREWALL_RULE = ["INPUT", "-p", "tcp", "--dport", str(PORT), "-j", "ACCEPT"]

STYLE = """
body { font-family: sans-serif; font-size: 24px; margin: 24px; max-width: 900px; }
h1 { font-size: 36px; margin: 0 0 12px; }
h2 { font-size: 28px; margin: 32px 0 12px; border-bottom: 2px solid #000; }
input[type=text] { font-size: 24px; padding: 8px; width: 60%; border: 2px solid #000; }
button { font-size: 24px; padding: 10px 18px; margin: 6px 6px 6px 0;
         background: #fff; border: 2px solid #000; border-radius: 8px; }
label { display: inline-block; padding: 8px 24px 8px 0; }
input[type=radio] { width: 24px; height: 24px; vertical-align: middle; }
.message { border: 3px solid #000; padding: 12px; }
.note { color: #444; font-size: 20px; }
"""


# One change at a time to config.json, whatever the number of browsers.
CHANGES = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    # Browsers open connections in advance and may leave them silent: close
    # them after a while, each in its own thread (see main()).
    timeout = 20

    def do_GET(self) -> None:
        self.server.last_request = time.time()
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            self._page(message=query.get("message", [""])[0])
        elif url.path == "/search":
            self._search(query.get("city", [""])[0].strip())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        self.server.last_request = time.time()
        with CHANGES:
            self._post()

    def _post(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        form = {
            key: values[0]
            for key, values in parse_qs(self.rfile.read(length).decode("utf-8")).items()
        }
        path = urlsplit(self.path).path
        if path == "/settings":
            for setting in SETTINGS:
                if setting in form:
                    change(setting, form[setting])
            write_menu()
            self._redirect("Settings saved.")
        elif path == "/city":
            self._choose_city(int(form["id"]))
        elif path == "/detect":
            self._detect_city()
        elif path == "/close":
            self.server.done = True
            self._send(
                "<h1>KindleWeather</h1><p>Settings saved. You can close the browser,"
                " then start the weather station from KUAL.</p>"
            )
        else:
            self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        pass  # Keep station.log for the station; errors still go there.

    def _search(self, name: str) -> None:
        if not name:
            self._redirect("")
            return
        try:
            places = search_places(name, _language())
        except WeatherError as error:
            self._page(message=f"Open-Meteo cannot be reached: {error}")
            return
        if not places:
            self._page(message=f'No city found for "{name}".')
            return
        results = "".join(
            '<form action="/city" method="post">'
            f'<input type="hidden" name="id" value="{place.id}">'
            f"<button>{html.escape(place.full_name)}</button></form>"
            for place in places
            if place.id is not None
        )
        self._page(results=f"<p>Choose the city:</p>{results}", search=name)

    def _choose_city(self, place_id: int) -> None:
        try:
            place = geocode("", None, _language(), place_id)
        except WeatherError as error:
            self._redirect(f"Open-Meteo cannot be reached: {error}")
            return
        self._save_place(place)

    def _detect_city(self) -> None:
        try:
            place = detect_place(_language())
        except WeatherError as error:
            self._redirect(f"City not detected: {error}")
            return
        self._save_place(place)

    def _save_place(self, place: Place) -> None:
        set_place(place)
        write_menu()
        self._redirect(f"City set: {place.full_name}.")

    def _page(self, message: str = "", results: str = "", search: str = "") -> None:
        config = load_config(CONFIG_PATH)
        current = current_values(config)
        city = f"{config.city}, {config.country_code}" if config.country_code else config.city
        settings = "".join(
            f"<p><b>{title}</b><br>"
            + "".join(
                f'<label><input type="radio" name="{setting}" value="{value}"'
                f"{' checked' if value == current[setting] else ''}> {name}</label>"
                for value, name in values.items()
            )
            + "</p>"
            for setting, (title, _, values) in SETTINGS.items()
        )
        address = _address()
        phone = (
            f'<p class="note">From a phone or a computer on the same Wi-Fi: '
            f"http://{address}:{PORT}</p>"
            if address
            else ""
        )
        self._send(
            "<h1>KindleWeather settings</h1>"
            + (f'<p class="message">{html.escape(message)}</p>' if message else "")
            + f"<h2>City</h2><p>Current city: <b>{html.escape(city)}</b></p>"
            + '<form action="/search" method="get" accept-charset="utf-8">'
            + f'<input type="text" name="city" value="{html.escape(search)}"'
            + ' placeholder="City name"> <button>Search</button></form>'
            + results
            + '<form action="/detect" method="post"><button>Detect automatically</button></form>'
            + '<h2>Display</h2><form action="/settings" method="post">'
            + settings
            + "<button>Save</button></form>"
            + '<h2>Done</h2><form action="/close" method="post">'
            + "<button>Close the settings page</button></form>"
            + phone
        )

    def _send(self, body: str) -> None:
        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            f"<title>KindleWeather</title><style>{STYLE}</style></head>"
            f"<body>{body}</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def _redirect(self, message: str) -> None:
        """Back to the page after a change, so that reloading it changes nothing."""
        self.send_response(303)
        self.send_header("Location", f"/?message={quote(message)}" if message else "/")
        self.end_headers()


def _language() -> str:
    return load_config(CONFIG_PATH).locale.code


def _address() -> str | None:
    """The Kindle's address on the Wi-Fi network; no packet is sent."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("1.1.1.1", 53))
            return probe.getsockname()[0]
    except OSError:
        return None


def _firewall(action: str) -> None:
    # No iptables on a computer.
    with suppress(OSError):
        subprocess.run(
            ["iptables", action, *FIREWALL_RULE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def main() -> None:
    # A thread per connection, so that an idle one does not hold up the others.
    server = ThreadingHTTPServer(("", PORT), Handler)
    server.timeout = 30
    server.last_request = time.time()
    server.done = False
    # Stopped by web.sh when a new page opens: clean up as when closed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit())
    PID_FILE.write_text(str(os.getpid()))
    _firewall("-I")
    print(f"settings page at http://127.0.0.1:{PORT}/", flush=True)
    try:
        while not server.done and time.time() - server.last_request < IDLE_SECONDS:
            server.handle_request()
    finally:
        _firewall("-D")
        PID_FILE.unlink(missing_ok=True)
        print("settings page closed", flush=True)


if __name__ == "__main__":
    main()

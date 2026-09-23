"""Draws the dashboard: python3 -m kindle_weather --config config.json --output dashboard.png

Run by bin/station.sh every hour. On success the image is replaced and nothing
is printed. On failure the previous dashboard is kept, the error line to show
on top of it is printed (such as "Error E1: Weather service unreachable"), and
the details go to stderr, which is the station's log. A full-screen error is
written only when there is no dashboard yet.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from kindle_weather.config import load_config
from kindle_weather.errors import RENDER_FAILED, WEATHER_UNREACHABLE, ErrorCode, classify
from kindle_weather.render import SCREEN_SIZE, render_dashboard, render_error
from kindle_weather.weather import fetch_forecast, geocode

# Right after Wi-Fi connects, the network may take a moment to work.
NETWORK_RETRIES = 3
NETWORK_RETRY_SECONDS = 10

EXTENSION_DIR = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(prog="kindle_weather", description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=EXTENSION_DIR / "config.json")
    parser.add_argument("--output", type=Path, default=Path("dashboard.png"))
    args = parser.parse_args()

    for attempt in range(NETWORK_RETRIES + 1):
        try:
            draw(args.config, args.output)
            return
        except Exception as error:
            failure = classify(error)
            print(f"{failure.message}: {error or type(error).__name__}", file=sys.stderr)
            if failure is WEATHER_UNREACHABLE and attempt < NETWORK_RETRIES:
                time.sleep(NETWORK_RETRY_SECONDS)
                continue
            if failure is RENDER_FAILED:
                traceback.print_exc()
            if not args.output.exists():
                draw_error(args.config, args.output, failure, str(error))
            print(failure.message)
            return


def draw(config_path: Path, output: Path) -> None:
    config = load_config(config_path)
    place = geocode(config.city, config.country_code, config.locale.code, config.place_id)
    forecast = fetch_forecast(place, config.temperature_unit)
    image = render_dashboard(
        forecast,
        config.locale,
        config.display_size,
        config.orientation,
        config.icon_set,
        config.clock,
    )
    image.save(output)


def draw_error(config_path: Path, output: Path, failure: ErrorCode, detail: str) -> None:
    """Full-screen error, in the configured screen size if the configuration can be read."""
    try:
        config = load_config(config_path)
        size, orientation = config.display_size, config.orientation
    except Exception:
        size, orientation = SCREEN_SIZE, "portrait"
    try:
        render_error(failure, detail, size, orientation).save(output)
    except Exception:
        # Drawing itself fails, such as without cairo: station.sh shows the line alone.
        traceback.print_exc()


if __name__ == "__main__":
    main()

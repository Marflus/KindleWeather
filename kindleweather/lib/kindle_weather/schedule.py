"""When to refresh next: every refresh_minutes, but not during the night pause.

python3 -m kindle_weather.schedule   prints the seconds to wait, for bin/station.sh

Hours are the city's: its offset from UTC is saved in state.json with each
dashboard, since the Kindle's own clock may be set to another time zone.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from kindle_weather.config import CONFIG_PATH, EXTENSION_DIR, Config, load_config

STATE_PATH = EXTENSION_DIR / "state.json"


def next_refresh(now: datetime, config: Config) -> datetime:
    """The time of the next refresh after now, moved to the end of the night pause."""
    when = now + timedelta(minutes=config.refresh_minutes)
    if config.night_pause and _paused(when.hour, config.night_pause):
        end = when.replace(hour=config.night_pause[1], minute=0, second=0, microsecond=0)
        when = end if end > when else end + timedelta(days=1)
    return when


def _paused(hour: int, pause: tuple[int, int]) -> bool:
    start, end = pause
    # The pause may span midnight, such as from 23 to 6.
    return start <= hour < end if start < end else hour >= start or hour < end


def save_utc_offset(seconds: int) -> None:
    STATE_PATH.write_text(json.dumps({"utc_offset": seconds}))


def city_now() -> datetime:
    """The time in the city, or on the Kindle's clock before the first dashboard."""
    try:
        offset = json.loads(STATE_PATH.read_text())["utc_offset"]
    except (OSError, ValueError, KeyError, TypeError):
        return datetime.now().astimezone()
    return datetime.now(timezone(timedelta(seconds=offset)))


if __name__ == "__main__":
    now = city_now()
    print(round((next_refresh(now, load_config(CONFIG_PATH)) - now).total_seconds()))

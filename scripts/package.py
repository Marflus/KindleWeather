"""Build dist/kindleweather.zip, the extension to copy to the Kindle: python scripts/package.py

The zip holds extensions/kindleweather with a sample config.json to edit, so
installing needs no Python on the computer.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from kindle_weather.config import parse_config
from kindle_weather.install import EXTENSION_NAME, build_extension

DIST = Path(__file__).parents[1] / "dist"
SAMPLE_CONFIG = {
    "language": "en",
    "location": {"city": "London", "country_code": "GB"},
    "display": {"width": 1072, "height": 1448, "orientation": "portrait", "icons": "classic"},
    "temperature_unit": "celsius",
}


def main() -> None:
    DIST.mkdir(exist_ok=True)
    archive = DIST / "kindleweather.zip"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(SAMPLE_CONFIG, indent=2) + "\n", encoding="utf-8")
        target = root / "extensions" / EXTENSION_NAME
        build_extension(target, parse_config(SAMPLE_CONFIG), config_path)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(root).as_posix())
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()

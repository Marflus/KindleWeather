"""Build dist/kindleweather.zip, the extension to copy to the Kindle: python scripts/package.py

The zip holds extensions/kindleweather with a sample config.json to edit, so
installing needs no Python on the computer. With --config, it holds that
configuration instead, ready to copy.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from kindle_weather.config import load_config, parse_config
from kindle_weather.install import EXTENSION_NAME, build_extension

DIST = Path(__file__).parents[1] / "dist"
SAMPLE_CONFIG = {
    "language": "en",
    "location": {"city": "London", "country_code": "GB"},
    "display": {"width": 1072, "height": 1448, "orientation": "portrait", "icons": "classic"},
    "temperature_unit": "celsius",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, help="configuration to ship instead of the sample")
    args = parser.parse_args()
    DIST.mkdir(exist_ok=True)
    archive = DIST / "kindleweather.zip"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path = root / "config.json"
        if args.config:
            shutil.copyfile(args.config, config_path)
            config = load_config(config_path)
        else:
            config_path.write_text(json.dumps(SAMPLE_CONFIG, indent=2) + "\n", encoding="utf-8")
            config = parse_config(SAMPLE_CONFIG)
        target = root / "extensions" / EXTENSION_NAME
        build_extension(target, config, config_path)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(root).as_posix())
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()

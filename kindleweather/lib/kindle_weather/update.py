"""Updates KindleWeather from GitHub, keeping the settings: python3 -m kindle_weather.update

Run by bin/update.sh from the KUAL menu. Downloads the main branch of the
repository and replaces the kindleweather folder with the one it holds,
keeping config.json and the log. Prints one line saying how it went.
"""

from __future__ import annotations

import io
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from kindle_weather.config import EXTENSION_DIR

ARCHIVE_URL = "https://codeload.github.com/Marflus/KindleWeather/zip/refs/heads/main"
# Files of the installed folder that the update keeps.
KEPT_FILES = ("config.json", "station.log", "state.json")
TIMEOUT = 60


class UpdateError(RuntimeError):
    pass


def download() -> bytes:
    try:
        request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "KindleWeather"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as error:
        if not isinstance(getattr(error, "reason", error), ssl.SSLError):
            raise UpdateError(f"GitHub cannot be reached: {error}") from error
    # Python's certificates may be too old for GitHub: the Kindle's curl may do.
    try:
        return subprocess.run(
            ["curl", "-fsSL", "--max-time", str(TIMEOUT), ARCHIVE_URL],
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise UpdateError(f"no secure connection to GitHub: {error}") from error


def install(archive: zipfile.ZipFile, target: Path) -> None:
    """Replace the target folder with the kindleweather folder of archive."""
    # Entries are named "KindleWeather-main/kindleweather/...".
    names = [name for name in archive.namelist() if "/kindleweather/" in name]
    if not any(name.endswith("/kindle_weather/__main__.py") for name in names):
        raise UpdateError("the download does not hold KindleWeather")
    prefix = names[0][: names[0].index("/kindleweather/") + len("/kindleweather/")]

    new = target.with_name(target.name + ".new")
    old = target.with_name(target.name + ".old")
    shutil.rmtree(new, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    for name in names:
        path = new / name[len(prefix) :]
        if name.endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    for kept in KEPT_FILES:
        if (target / kept).exists():
            shutil.copyfile(target / kept, new / kept)
    # Swapped by renaming, so that a failure before leaves the installed folder whole.
    os.rename(target, old)
    os.rename(new, target)
    shutil.rmtree(old, ignore_errors=True)


def main() -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(download())) as archive:
            # GitHub writes the commit in the comment of the archive.
            commit = archive.comment.decode(errors="replace")[:7]
            install(archive, EXTENSION_DIR)
    except (UpdateError, zipfile.BadZipFile, OSError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        print("Update failed: check the Wi-Fi connection")
        return
    installed = EXTENSION_DIR / "lib" / "kindle_weather" / "__init__.py"
    version = next(
        (
            line.split('"')[1]
            for line in installed.read_text().splitlines()
            if "__version__" in line
        ),
        "?",
    )
    print(f"KindleWeather updated to {version}" + (f" ({commit})" if commit else ""))


if __name__ == "__main__":
    main()

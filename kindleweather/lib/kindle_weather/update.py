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
from kindle_weather.weather import tls_context

ARCHIVE_URL = "https://codeload.github.com/Marflus/KindleWeather/zip/refs/heads/main"
# Files of the installed folder that the update keeps.
KEPT_FILES = ("config.json", "station.log", "state.json")
TIMEOUT = 60


class UpdateError(RuntimeError):
    pass


def download() -> bytes:
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "KindleWeather"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=tls_context()) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            # GitHub hides private repositories.
            raise UpdateError("GitHub does not find the repository: is it public?") from error
        raise UpdateError(f"GitHub answered: HTTP {error.code} {error.reason}") from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        if not isinstance(reason, ssl.SSLError):
            raise UpdateError(f"GitHub cannot be reached: {reason}") from error
        python_error = reason
    # The Kindle's curl may have the certificates Python lacks.
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", str(TIMEOUT), ARCHIVE_URL],
            capture_output=True,
            check=False,
        )
    except OSError:
        raise UpdateError(f"no secure connection to GitHub: {python_error}") from None
    if result.returncode:
        curl_error = result.stderr.decode(errors="replace").strip() or f"curl {result.returncode}"
        raise UpdateError(f"no secure connection to GitHub: {python_error}; {curl_error}")
    return result.stdout


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
    new_root = new.resolve()
    for name in names:
        path = (new / name[len(prefix) :]).resolve()
        # Refuse an entry such as "../../etc/passwd" that would write outside
        # the extracted folder ("zip slip"), whatever wrote the archive.
        if path != new_root and new_root not in path.parents:
            raise UpdateError(f"unsafe entry in the download: {name}")
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
        # The whole reason goes to the log, its start on the screen.
        print(f"Update failed: {error}", file=sys.stderr)
        print(f"Update failed: {str(error)[:120]}")
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

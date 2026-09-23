# Shared by the KindleWeather scripts: paths, Python, logging.
# shellcheck disable=SC2034  # Variables used by the scripts sourcing this file.
# The extension folder is found from the script's own path, wherever it was copied.
EXTENSION_DIR=$(cd "$(dirname "$0")/.." && pwd)
CONFIG="$EXTENSION_DIR/config.json"
IMAGE="$EXTENSION_DIR/dashboard.png"
LOG="$EXTENSION_DIR/station.log"
# Written by the station once running, for start.sh to know it is.
PID_FILE="$EXTENSION_DIR/station.pid"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"
}

# Python 3 from MRPI, wherever its package put it.
find_python() {
    for candidate in python3 /mnt/us/python3/bin/python3 /mnt/us/python/bin/python3 \
        /mnt/us/python3.9/bin/python3 /mnt/us/python3.11/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return
        fi
    done
}

kindle_weather() {
    PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather --config "$CONFIG" "$@"
}

# Messages in the configured language, written by `kindle-weather kual-files`;
# these defaults stand in when that file is missing.
WIFI_ERROR="Error E7: No Wi-Fi connection"
PYTHON_ERROR="Error E8: Python 3 is missing, install it with MRPI"
LOW_BATTERY_WARNING="Low battery"
STARTING_MESSAGE="Starting the weather station..."
load_settings() {
    if [ -f "$EXTENSION_DIR/settings.sh" ]; then
        # shellcheck source=/dev/null
        . "$EXTENSION_DIR/settings.sh"
    fi
}

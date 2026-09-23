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

# Python 3.8 or newer, wherever its package put it and whatever its name
# (python3, python3.11...).
find_python() {
    for folder in $(echo "$PATH" | tr ':' ' ') /mnt/us/python3/bin /mnt/us/python/bin \
        /mnt/us/python*/bin /usr/local/bin; do
        for candidate in "$folder"/python3 "$folder"/python3.*; do
            case "$candidate" in *-config) continue ;; esac
            if [ -x "$candidate" ] && "$candidate" -c \
                'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
                echo "$candidate"
                return
            fi
        done
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

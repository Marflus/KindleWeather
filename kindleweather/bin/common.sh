# Shared by the KindleWeather scripts: paths, messages, Python.
# shellcheck disable=SC2034  # Variables used by the scripts sourcing this file.

# The extension folder, found from the script's own path wherever it was copied.
EXTENSION_DIR=$(cd "$(dirname "$0")/.." && pwd)
CONFIG="$EXTENSION_DIR/config.json"
IMAGE="$EXTENSION_DIR/dashboard.png"
LOG="$EXTENSION_DIR/station.log"
# Written by the station once running, so that start.sh knows it started.
PID_FILE="$EXTENSION_DIR/station.pid"

# Messages shown with eips, in English like the error codes of the README.
STARTING_MESSAGE="Starting the weather station..."
LOW_BATTERY_WARNING="Low battery"
WIFI_ERROR="Error E7: No Wi-Fi connection"
PYTHON_ERROR="Error E8: Python 3 is missing, install it with MRPI"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"
}

# Python 3.8 or newer, wherever its package put it and whatever its name
# (python3, python3.9...). NiLuJe's package installs /mnt/us/python3.
find_python() {
    for folder in $(echo "$PATH" | tr ':' ' ') /mnt/us/python3/bin /mnt/us/python*/bin; do
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

# Runs a command in the background, in a session of its own, so that it
# outlives KUAL: KUAL may signal what it started as it closes.
detach() {
    if command -v setsid >/dev/null 2>&1; then
        setsid "$@" </dev/null >>"$LOG" 2>&1 &
    else
        nohup "$@" </dev/null >>"$LOG" 2>&1 &
    fi
}

# Draws the dashboard with the Python package in lib/, see its __main__.py.
kindle_weather() {
    PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather --config "$CONFIG" "$@"
}

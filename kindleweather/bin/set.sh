#!/bin/sh
# KUAL settings buttons: sh bin/set.sh SETTING VALUE, such as orientation landscape.
# Changes config.json and the menu, see kindle_weather/settings.py.
. "$(dirname "$0")/common.sh"
PYTHON=$(find_python)
log "setting $1 to $2"
PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.settings "$1" "$2" >>"$LOG" 2>&1

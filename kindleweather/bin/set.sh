#!/bin/sh
# KUAL settings buttons: sh bin/set.sh SETTING VALUE, such as orientation landscape.
# Saves the setting in config.json and updates the menu, see kindle_weather/settings.py.
. "$(dirname "$0")/common.sh"
log "setting $1 to $2"
PYTHON=$(find_python)
PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.settings "$1" "$2" >>"$LOG" 2>&1

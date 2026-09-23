#!/bin/sh
# KUAL "Search in the browser" and "All settings in the browser": serves the
# settings page (kindle_weather/web.py), then opens it in the Kindle's browser.
. "$(dirname "$0")/common.sh"
WEB_PID="$EXTENSION_DIR/web.pid"
URL="http://127.0.0.1:8765/"
trap '' HUP INT TERM
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    log "$PYTHON_ERROR"
    exit 1
fi

# Replace a page left open.
if [ -f "$WEB_PID" ]; then
    kill "$(cat "$WEB_PID")" 2>/dev/null
    sleep 1
fi
log "opening the settings page"
detach env PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.web
tries=0
while [ ! -f "$WEB_PID" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
lipc-set-prop com.lab126.appmgrd start "app://com.lab126.browser?view=$URL"

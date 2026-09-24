#!/bin/sh
# KUAL "Settings page" buttons: serves the settings page (kindle_weather/web.py)
# and writes its address at the top of the screen, to open on a phone or a
# computer on the same Wi-Fi. The Kindle's own browser does not load it.
. "$(dirname "$0")/common.sh"
WEB_PID="$EXTENSION_DIR/web.pid"
trap '' HUP INT TERM
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    say "$PYTHON_ERROR" ""
    exit 1
fi
address=$(ifconfig wlan0 2>/dev/null | sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p')
if [ -z "$address" ]; then
    say "No Wi-Fi connection: turn Wi-Fi on, then try again." ""
    exit 1
fi

# Replace a page left open.
if [ -f "$WEB_PID" ]; then
    kill "$(cat "$WEB_PID")" 2>/dev/null
    sleep 1
fi
log "opening the settings page at http://$address:8765"
detach env PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.web
tries=0
while [ ! -f "$WEB_PID" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
say "Settings page: http://$address:8765" "Open it on a phone or computer on the same Wi-Fi."

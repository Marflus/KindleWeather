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

# Kill any settings page left running: by its pid file, and by scanning /proc
# in case that file was lost, such as by an update replacing this folder while
# the page was open. Two servers cannot both listen on the same port.
[ -f "$WEB_PID" ] && kill "$(cat "$WEB_PID")" 2>/dev/null
for proc in /proc/[0-9]*; do
    pid=${proc#/proc/}
    if tr '\0' ' ' <"$proc/cmdline" 2>/dev/null | grep -q "kindle_weather.web"; then
        kill "$pid" 2>/dev/null
    fi
done
rm -f "$WEB_PID"
sleep 1

log "opening the settings page at http://$address:8765"
detach env PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.web
tries=0
while [ ! -f "$WEB_PID" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
if [ -f "$WEB_PID" ]; then
    say "Settings page: http://$address:8765" "Open it on a phone or computer on the same Wi-Fi."
else
    say "The settings page did not start." "$(tail -n 1 "$LOG")"
fi

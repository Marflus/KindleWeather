#!/bin/sh
# KUAL "Update KindleWeather" button: downloads the latest version from GitHub
# and replaces this folder with it, keeping config.json. The result is written
# at the top of the screen. See kindle_weather/update.py.
. "$(dirname "$0")/common.sh"
say "Updating KindleWeather..." ""
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    say "$PYTHON_ERROR" ""
    exit 1
fi
log "update requested"
result=$(PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.update 2>>"$LOG")
log "$result"
case "$result" in
    "KindleWeather updated"*)
        # The new version's menu, for this configuration.
        PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.settings >>"$LOG" 2>&1
        say "$result" "Close and reopen KUAL to see the new menu."
        ;;
    *)
        # The reason is long: its first 60 characters on each of two lines.
        reason=${result:-Update failed, see station.log}
        say "$(echo "$reason" | cut -c 1-60)" "$(echo "$reason" | cut -c 61-120)"
        ;;
esac

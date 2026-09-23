#!/bin/sh
# KUAL "Detect automatically" button of the City menu: sets the city of the
# internet connection. Detecting takes too long for KUAL to reload the menu
# with the result, so it is written over KUAL, at the top of the screen.
. "$(dirname "$0")/common.sh"
say() {
    # Spaces erase the end of a longer previous line.
    /usr/sbin/eips 1 1 "$1                                        "
    /usr/sbin/eips 1 2 "$2                                        "
}

say "Detecting the city..." ""
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    say "$PYTHON_ERROR" ""
    exit 1
fi
result=$(PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.settings detect-city 2>>"$LOG")
log "$result"
case "$result" in
    "City: "*) say "$result" "The menu shows it the next time KUAL opens." ;;
    *) say "${result:-City not detected, see station.log}" "" ;;
esac

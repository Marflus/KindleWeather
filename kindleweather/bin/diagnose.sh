#!/bin/sh
# KUAL "Diagnostic" action: checks what the station needs and draws the
# dashboard once, without stopping the Kindle interface. The report goes to
# diagnostic.txt, and its main lines on the screen.
. "$(dirname "$0")/common.sh"
REPORT="$EXTENSION_DIR/diagnostic.txt"
TEST_IMAGE=/tmp/kindleweather-test.png
PYTHON=$(find_python)

# Runs Python code with the package in lib/, printing its last line: the
# result, or the error.
python_check() {
    PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -c "$1" 2>&1 | tail -n 1
}

rm -f "$TEST_IMAGE"
{
    echo "KindleWeather diagnostic, $(date)"
    echo "version: $(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$EXTENSION_DIR/lib/kindle_weather/__init__.py")"
    echo "folder: $EXTENSION_DIR"
    echo "user: $(id -u), the station needs 0 (root)"
    echo "firmware: $(cat /etc/prettyversion.txt 2>/dev/null)"
    echo "python: ${PYTHON:-MISSING, install it with MRPI} $([ -n "$PYTHON" ] && "$PYTHON" -V 2>&1)"
    echo "wifi: $(lipc-get-prop com.lab126.wifid cmState 2>&1)"
    echo "address: $(ifconfig wlan0 2>&1 | grep 'inet ')"
    echo "battery: $(lipc-get-prop com.lab126.powerd battLevel 2>&1) %"
    echo "wake-up clocks: $(echo /dev/rtc*)"
    if [ -n "$PYTHON" ]; then
        # Python loads the Kindle's cairo and FreeType, and draws.
        echo "drawing: $(python_check '
from kindle_weather.canvas import Canvas
Canvas(10, 10).picture()
print("ok")')"
        # The system lookup may fail on the Kindle; the direct one is the fallback.
        echo "dns: $(python_check '
import socket
from kindle_weather import dns
host = "api.open-meteo.com"
try:
    socket.getaddrinfo(host, 443)
    system = "ok"
except OSError as error:
    system = "fails (%s)" % error
print("system %s, direct %s" % (system, dns.resolve(host) or "fails"))')"
    fi
    echo "--- config.json"
    cat "$CONFIG"
    echo "--- test dashboard"
    if [ -n "$PYTHON" ]; then
        started=$(date +%s)
        result=$(kindle_weather --output "$TEST_IMAGE" 2>"$REPORT.log")
        echo "time: $(($(date +%s) - started)) s"
        echo "result: ${result:-ok}"
        cat "$REPORT.log"
        rm -f "$REPORT.log"
    else
        echo "result: skipped, no Python"
    fi
    echo "--- end of station.log"
    tail -n 30 "$LOG" 2>/dev/null
} >"$REPORT" 2>&1

# Sum up on the screen, over the test dashboard; the interface redraws over
# it when the Kindle is used.
if [ -f "$TEST_IMAGE" ]; then
    /usr/sbin/eips -f -g "$TEST_IMAGE"
else
    /usr/sbin/eips -c
fi
row=1
grep -E "^(version|user|python|wifi|drawing|dns|time|result):" "$REPORT" | cut -c 1-60 >"$REPORT.summary"
while IFS= read -r line; do
    /usr/sbin/eips 1 "$row" "$line"
    row=$((row + 1))
done <"$REPORT.summary"
rm -f "$REPORT.summary"
/usr/sbin/eips 1 "$((row + 1))" "Report: extensions/kindleweather/diagnostic.txt"

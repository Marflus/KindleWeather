#!/bin/sh
# KUAL "Diagnostic" action: checks what the station needs and draws the
# dashboard once, without stopping the Kindle interface. The report is
# written to diagnostic.txt and summed up on the screen.
. "$(dirname "$0")/common.sh"
REPORT="$EXTENSION_DIR/diagnostic.txt"
TEST_IMAGE=/tmp/kindleweather-test.png
load_settings
PYTHON=$(find_python)

check() {
    if "$@" >/dev/null 2>&1; then echo ok; else echo MISSING; fi
}

library() {
    for folder in /usr/lib /lib; do
        if [ -e "$folder/$1" ]; then
            echo "ok ($folder/$1)"
            return
        fi
    done
    echo MISSING
}

rm -f "$TEST_IMAGE"
python_version=$([ -n "$PYTHON" ] && "$PYTHON" -V 2>&1)
{
    echo "KindleWeather diagnostic, $(date)"
    echo "folder: $EXTENSION_DIR"
    echo "user: $(id -u) ($(id -un 2>/dev/null)), the station needs 0 (root)"
    echo "firmware: $(cat /etc/prettyversion.txt 2>/dev/null)"
    echo "setsid: $(check command -v setsid)"
    echo "python: ${PYTHON:-MISSING} $python_version"
    echo "pythons found: $(echo /mnt/us/python*/bin/python* /usr/bin/python* /usr/local/bin/python*)"
    echo "libcairo.so.2: $(library libcairo.so.2)"
    echo "libfreetype.so.6: $(library libfreetype.so.6)"
    if [ -n "$PYTHON" ]; then
        # The real test: Python loads cairo and FreeType and draws.
        echo "drawing: $(PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -c '
from kindle_weather.canvas import Canvas
Canvas(10, 10).picture()
print("ok")' 2>&1 | tail -n 1 | sed "s/^kindle_weather.canvas.CanvasError: //")"
    fi
    echo "cairo and freetype files: $(find /usr/lib /lib /usr/local/lib /opt /mnt/us/python3 \
        \( -name 'libcairo*' -o -name 'libfreetype*' \) 2>/dev/null | tr '\n' ' ')"
    echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
    echo "python file: $(ls -l "$PYTHON" 2>/dev/null)"
    echo "wake-up clock: $(echo /dev/rtc*)"
    echo "wifi: $(lipc-get-prop com.lab126.wifid cmState 2>&1)"
    echo "resolv.conf: $(tr '\n' ' ' </etc/resolv.conf 2>&1)"
    if [ -n "$PYTHON" ]; then
        echo "dns: $(PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -c '
import socket
from kindle_weather import dns
host = "api.open-meteo.com"
try:
    socket.getaddrinfo(host, 443)
    system = "ok"
except OSError as error:
    system = "fails (%s)" % error
print("system %s, direct %s" % (system, dns.resolve(host) or "fails"))' 2>&1 | tail -n 1)"
    fi
    echo "battery: $(lipc-get-prop com.lab126.powerd battLevel 2>&1) %"
    echo "--- network"
    echo "address: $(ifconfig wlan0 2>&1 | grep -i 'inet ' | tr -s ' ')"
    echo "routes: $(route -n 2>&1 | tail -n +3 | tr -s ' ' | tr '\n' '|')"
    echo "ping 1.1.1.1: $(ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1 && echo ok || echo fails)"
    echo "nslookup: $(nslookup api.open-meteo.com 2>&1 | tr '\n' ' ' | cut -c 1-200)"
    echo "curl: $(curl -sS -m 15 -o /dev/null -w 'HTTP %{http_code}' \
        'https://api.open-meteo.com/v1/forecast?latitude=52&longitude=21&current=temperature_2m' 2>&1)"
    if [ -n "$PYTHON" ]; then
        echo "python tcp 1.1.1.1:443: $("$PYTHON" -c '
import socket
socket.create_connection(("1.1.1.1", 443), timeout=5).close()
print("ok")' 2>&1 | tail -n 1)"
    fi
    echo "firewall:"
    iptables -S 2>&1 | head -n 30
    echo "--- config.json"
    cat "$CONFIG"
    echo "--- test dashboard"
    if [ -n "$PYTHON" ]; then
        started=$(date +%s)
        result=$(kindle_weather refresh --output "$TEST_IMAGE" 2>>"$REPORT.tmp")
        echo "time: $(($(date +%s) - started)) s"
        echo "result: ${result:-OK}"
        cat "$REPORT.tmp" 2>/dev/null
        rm -f "$REPORT.tmp"
    else
        echo "result: skipped, no Python"
    fi
    echo "--- end of station.log"
    tail -n 30 "$LOG" 2>/dev/null
} >"$REPORT" 2>&1

# Sum up on the screen; the interface redraws over it when used.
if [ -f "$TEST_IMAGE" ]; then
    /usr/sbin/eips -f -g "$TEST_IMAGE"
else
    /usr/sbin/eips -c
fi
grep -E "^(folder|user|setsid|python|drawing|wifi|dns|time|result):" "$REPORT" |
    cut -c 1-60 >"$REPORT.summary"
row=1
while IFS= read -r line; do
    /usr/sbin/eips 1 "$row" "$line"
    row=$((row + 1))
done <"$REPORT.summary"
rm -f "$REPORT.summary"
/usr/sbin/eips 1 "$((row + 1))" "Report: extensions/kindleweather/diagnostic.txt"

#!/bin/sh
# Weather station loop: draw the dashboard, display it, then suspend the
# Kindle until the next refresh. Amazon's interface is stopped for good:
# restart the Kindle to get it back.
# Adapted from https://github.com/mattzzw/kindle-weatherstation by mattzzw.
EXTENSION_DIR=/mnt/us/extensions/kindleweather
CONFIG="$EXTENSION_DIR/config.json"
IMAGE="$EXTENSION_DIR/dashboard.png"
LOG="$EXTENSION_DIR/station.log"
REFRESH_SECONDS=3600
LOW_BATTERY_PERCENT=10
# Wake-capable real-time clock of the Paperwhite 2 and 3.
RTC=/dev/rtc1

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"
}

# Everything the script and its commands complain about ends up in the log.
exec 2>>"$LOG"
log "station starting"

# Python 3 from MRPI, wherever its package put it.
find_python() {
    for candidate in python3 /mnt/us/python3/bin/python3 /mnt/us/python/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return
        fi
    done
}

kindle_weather() {
    PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather --config "$CONFIG" "$@" 2>>"$LOG"
}

# Show the last dashboard, with the non-empty messages on its top lines.
show() {
    lipc-set-prop com.lab126.powerd flIntensity 0
    for rotation in /sys/devices/platform/*_epdc_fb/graphics/fb0/rotate; do
        echo 0 >"$rotation"
    done
    if [ -f "$IMAGE" ]; then
        /usr/sbin/eips -f -g "$IMAGE"
    else
        /usr/sbin/eips -c
    fi
    line=0
    for message in "$@"; do
        [ -n "$message" ] || continue
        /usr/sbin/eips 1 "$line" "$message"
        line=$((line + 1))
    done
}

wait_for_wifi() {
    tries=0
    until lipc-get-prop com.lab126.wifid cmState | grep -q CONNECTED; do
        [ "$tries" -ge 60 ] && return 1
        tries=$((tries + 1))
        sleep 1
    done
}

# Draw the dashboard to $IMAGE with Python, or set $error.
draw() {
    if [ -z "$PYTHON" ]; then
        error="$PYTHON_ERROR"
        return
    fi
    error=$(kindle_weather refresh --output "$IMAGE")
    [ -z "$error" ] && log "dashboard updated"
}

battery_warning() {
    level=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)
    if [ -n "$level" ] && [ "$level" -le "$LOW_BATTERY_PERCENT" ] 2>/dev/null; then
        echo "$LOW_BATTERY_WARNING ($level %)"
    fi
}

# Defines the error messages (E7, E8), LOW_BATTERY_WARNING and
# STARTING_MESSAGE, in the configured language. Written at installation, then again from
# config.json at each start when Python is available.
. "$EXTENSION_DIR/settings.sh"
PYTHON=$(find_python)
if [ -n "$PYTHON" ] && kindle_weather kual-files "$EXTENSION_DIR"; then
    . "$EXTENSION_DIR/settings.sh"
fi

# Without the interface nothing can draw a screensaver over the dashboard,
# and the other services only drain the battery.
for job in lab126_gui otaupd phd tmd x todo mcsd archive dynconfig dpmd appmgrd stackdumpd; do
    stop "$job" >/dev/null 2>&1
done
lipc-set-prop com.lab126.powerd preventScreenSaver 1
log "station started, python: ${PYTHON:-none}"
# Replace the frozen home screen while Wi-Fi connects and the dashboard is drawn.
/usr/sbin/eips -c
/usr/sbin/eips 2 30 "${STARTING_MESSAGE:-KindleWeather...}"

while true; do
    error=""
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    if wait_for_wifi; then
        draw
    else
        error="$WIFI_ERROR"
    fi
    lipc-set-prop com.lab126.cmd wirelessEnable 0
    warning=$(battery_warning)
    [ -n "$error" ] && log "$error"
    [ -n "$warning" ] && log "$warning"
    show "$error" "$warning"

    # Suspending right after a screen update can hang some models.
    sleep 3
    rtcwake -d "$RTC" -m no -s "$REFRESH_SECONDS"
    echo mem >/sys/power/state
done

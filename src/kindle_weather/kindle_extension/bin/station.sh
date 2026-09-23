#!/bin/sh
# Weather station loop: draw the dashboard, display it, then suspend the
# Kindle until the next refresh. Amazon's interface is stopped for good:
# restart the Kindle to get it back.
# Adapted from https://github.com/mattzzw/kindle-weatherstation by mattzzw.
. "$(dirname "$0")/common.sh"
REFRESH_SECONDS=3600
LOW_BATTERY_PERCENT=10
# Wake-capable real-time clock of the Paperwhite 2 and 3.
RTC=/dev/rtc1

# Everything the script and its commands print ends up in the log.
exec >>"$LOG" 2>&1
log "station starting in $EXTENSION_DIR, as user $(id -u)"
echo $$ >"$PID_FILE"
load_settings

# The interface shows the home screen in portrait: keep its screen rotation for
# the dashboard. Rotation 0 is landscape on these Kindles.
ROTATION_FILE=$(echo /sys/devices/platform/*_epdc_fb/graphics/fb0/rotate)
PORTRAIT_ROTATION=$(cat "$ROTATION_FILE" 2>/dev/null)
log "screen rotation: ${PORTRAIT_ROTATION:-unknown} ($ROTATION_FILE)"

# Like kindle-weatherstation: stop the interface first, so nothing draws over
# the dashboard and the other services do not drain the battery.
log "stopping the interface: $(stop lab126_gui 2>&1)"
for job in otaupd phd tmd x todo mcsd archive dynconfig dpmd appmgrd stackdumpd; do
    stop "$job" >/dev/null 2>&1
done
lipc-set-prop com.lab126.powerd preventScreenSaver 1
[ -n "$PORTRAIT_ROTATION" ] && echo "$PORTRAIT_ROTATION" >"$ROTATION_FILE"
/usr/sbin/eips -c
/usr/sbin/eips 2 30 "$STARTING_MESSAGE"

PYTHON=$(find_python)
log "python: ${PYTHON:-not found}"
# Messages in the configured language, from config.json.
if [ -n "$PYTHON" ] && kindle_weather kual-files "$EXTENSION_DIR"; then
    load_settings
fi

# Show the last dashboard, with the non-empty messages on its top lines.
show() {
    lipc-set-prop com.lab126.powerd flIntensity 0
    if [ -n "$PORTRAIT_ROTATION" ] && [ -e "$ROTATION_FILE" ]; then
        echo "$PORTRAIT_ROTATION" >"$ROTATION_FILE"
    fi
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

wifi_connected() {
    lipc-get-prop com.lab126.wifid cmState | grep -q CONNECTED
}

wait_for_wifi() {
    tries=0
    until wifi_connected; do
        if [ "$tries" -eq 30 ]; then
            # Without the interface, reconnection may need a push, as
            # kindle-weatherstation's wifi.sh does: reconnect, then get an address.
            log "wifi state: $(lipc-get-prop com.lab126.wifid cmState), reconnecting"
            wpa_cli -i wlan0 reconnect >/dev/null 2>&1
            udhcpc -i wlan0 -n -q >/dev/null 2>&1
        fi
        if [ "$tries" -ge 60 ]; then
            log "wifi state: $(lipc-get-prop com.lab126.wifid cmState)"
            return 1
        fi
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
    case "$error" in
        "Error E1:"*)
            # The network is not working yet: ask for an address again, as
            # kindle-weatherstation's wifi.sh does, then try once more.
            log "network: $(ifconfig wlan0 2>&1 | grep -i 'inet ' | tr -s ' '), $(tr '\n' ' ' </etc/resolv.conf)"
            udhcpc -i wlan0 -n -q >/dev/null 2>&1
            error=$(kindle_weather refresh --output "$IMAGE")
            ;;
    esac
    [ -z "$error" ] && log "dashboard updated"
}

battery_warning() {
    level=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)
    if [ -n "$level" ] && [ "$level" -le "$LOW_BATTERY_PERCENT" ] 2>/dev/null; then
        echo "$LOW_BATTERY_WARNING ($level %)"
    fi
}

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
    asleep_at=$(date +%s)
    rtcwake -d "$RTC" -m no -s "$REFRESH_SECONDS"
    echo mem >/sys/power/state
    # Suspend can be refused, such as over USB: then wait out the hour.
    awake=$(($(date +%s) - asleep_at))
    if [ "$awake" -lt $((REFRESH_SECONDS - 60)) ]; then
        log "suspend lasted ${awake} s, waiting for the next refresh"
        sleep $((REFRESH_SECONDS - awake))
    fi
done

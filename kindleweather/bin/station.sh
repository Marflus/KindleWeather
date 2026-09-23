#!/bin/sh
# The weather station, started by start.sh. Every hour: Wi-Fi on, draw the
# dashboard, Wi-Fi off, display it, then suspend the Kindle until the next
# hour. Amazon's interface is stopped for good: restart the Kindle to get it back.
# Adapted from https://github.com/mattzzw/kindle-weatherstation by mattzzw.
. "$(dirname "$0")/common.sh"
REFRESH_SECONDS=3600
LOW_BATTERY_PERCENT=10
# Real-time clock able to wake the Paperwhite 2 and 3 from suspend.
RTC=/dev/rtc1

# Everything the script and its commands print goes to the log.
exec >>"$LOG" 2>&1
log "station starting in $EXTENSION_DIR, as user $(id -u)"
echo $$ >"$PID_FILE"

# The interface leaves the screen in portrait: keep that rotation for the
# dashboard, since rotation 0 is landscape on these Kindles.
ROTATION_FILE=$(echo /sys/devices/platform/*_epdc_fb/graphics/fb0/rotate)
ROTATION=$(cat "$ROTATION_FILE" 2>/dev/null)
log "screen rotation: ${ROTATION:-unknown}"

# Shown until the first dashboard, which takes up to a minute.
starting_screen() {
    [ -n "$ROTATION" ] && echo "$ROTATION" >"$ROTATION_FILE"
    /usr/sbin/eips -c
    /usr/sbin/eips 3 27 "$STARTING_MESSAGE"
    /usr/sbin/eips 3 29 "The dashboard appears within a minute."
    /usr/sbin/eips 3 31 "To quit, restart the Kindle."
}
starting_screen

# Stop the interface and its services, so nothing draws over the dashboard
# and the battery lasts. The interface may blank the screen as it stops: show
# the message again.
log "stopping the interface: $(stop lab126_gui 2>&1)"
starting_screen
for job in otaupd phd tmd x todo mcsd archive dynconfig dpmd appmgrd stackdumpd; do
    stop "$job" >/dev/null 2>&1
done
lipc-set-prop com.lab126.powerd preventScreenSaver 1

PYTHON=$(find_python)
log "python: ${PYTHON:-not found}"

# Display the dashboard, with the non-empty messages on its top lines.
show() {
    lipc-set-prop com.lab126.powerd flIntensity 0
    [ -n "$ROTATION" ] && echo "$ROTATION" >"$ROTATION_FILE"
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

# Wait up to a minute for Wi-Fi. Without the interface, it may need a push
# halfway: reconnect, then ask for an address, as kindle-weatherstation does.
wait_for_wifi() {
    tries=0
    until wifi_connected; do
        if [ "$tries" -eq 30 ]; then
            log "wifi: $(lipc-get-prop com.lab126.wifid cmState), reconnecting"
            wpa_cli -i wlan0 reconnect >/dev/null 2>&1
            udhcpc -i wlan0 -n -q >/dev/null 2>&1
        fi
        [ "$tries" -ge 60 ] && return 1
        tries=$((tries + 1))
        sleep 1
    done
}

# Draw the dashboard to $IMAGE, or set $error to the line to show.
draw() {
    if [ -z "$PYTHON" ]; then
        error="$PYTHON_ERROR"
        return
    fi
    error=$(kindle_weather --output "$IMAGE")
    case "$error" in
        "Error E1:"*)
            # Open-Meteo is unreachable: ask for an address again, then retry once.
            log "network: $(ifconfig wlan0 2>&1 | grep 'inet '), $(tr '\n' ' ' </etc/resolv.conf)"
            udhcpc -i wlan0 -n -q >/dev/null 2>&1
            error=$(kindle_weather --output "$IMAGE")
            ;;
    esac
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
    log "${error:-dashboard updated}${warning:+, $warning}"
    show "$error" "$warning"

    # Suspending right after a screen update can hang some models.
    sleep 3
    asleep_at=$(date +%s)
    rtcwake -d "$RTC" -m no -s "$REFRESH_SECONDS"
    echo mem >/sys/power/state
    # Suspend is refused over USB, for one: then wait out the hour.
    awake=$(($(date +%s) - asleep_at))
    if [ "$awake" -lt $((REFRESH_SECONDS - 60)) ]; then
        log "no suspend (${awake} s), waiting for the next refresh"
        sleep $((REFRESH_SECONDS - awake))
    fi
done

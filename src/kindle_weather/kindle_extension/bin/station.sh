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
# A downloaded dashboard older than this means it is no longer published.
OUTDATED_SECONDS=21600
LOW_BATTERY_PERCENT=10
# Wake-capable real-time clock of the Paperwhite 2 and 3.
RTC=/dev/rtc1

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"
}

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

# Download the dashboard from $DASHBOARD_URL to $IMAGE, or set $error.
download() {
    # -R dates the file from the server, to tell when it was last published.
    curl -fsSL -R -o "$IMAGE.part" "$DASHBOARD_URL" 2>>"$LOG"
    case $? in
        0) ;;
        6 | 7 | 28) error="$SERVER_ERROR" ;;
        22) error="$NOT_FOUND_ERROR" ;;
        35 | 51 | 53 | 54 | 58 | 59 | 60 | 64 | 66 | 77 | 80 | 82 | 83 | 90 | 91)
            error="$SECURE_ERROR" ;;
        *) error="$DOWNLOAD_ERROR" ;;
    esac
    if [ -z "$error" ] && ! head -c 8 "$IMAGE.part" | grep -q PNG; then
        # Typically a Wi-Fi login page instead of the image.
        error="$INVALID_FILE_ERROR"
    fi
    if [ -n "$error" ]; then
        rm -f "$IMAGE.part"
        return
    fi
    mv "$IMAGE.part" "$IMAGE"
    log "dashboard updated"

    published=$(date -r "$IMAGE" +%s 2>/dev/null)
    now=$(date +%s)
    if [ -n "$published" ] && [ $((now - published)) -gt "$OUTDATED_SECONDS" ]; then
        error="$OUTDATED_ERROR"
    fi
}

battery_warning() {
    level=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)
    if [ -n "$level" ] && [ "$level" -le "$LOW_BATTERY_PERCENT" ] 2>/dev/null; then
        echo "$LOW_BATTERY_WARNING ($level %)"
    fi
}

# Defines DASHBOARD_URL, the error messages (E7 to E14) and LOW_BATTERY_WARNING,
# in the configured language. Written at installation, then again from
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

while true; do
    error=""
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    if ! wait_for_wifi; then
        error="$WIFI_ERROR"
    elif [ -n "$DASHBOARD_URL" ]; then
        download
    else
        draw
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

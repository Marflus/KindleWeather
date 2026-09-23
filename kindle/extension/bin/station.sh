#!/bin/sh
# Weather station loop: download the dashboard, display it, then suspend the
# Kindle until the next refresh. Amazon's interface is stopped for good:
# restart the Kindle to get it back.
EXTENSION_DIR=/mnt/us/extensions/kindleweather
IMAGE="$EXTENSION_DIR/dashboard.png"
LOG="$EXTENSION_DIR/station.log"
REFRESH_SECONDS=3600
# Wake-capable real-time clock of the Paperwhite 2 and 3.
RTC=/dev/rtc1

# Defines DASHBOARD_URL. Written by `kindle-weather install`.
. "$EXTENSION_DIR/settings.sh"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"
}

wait_for_wifi() {
    tries=0
    until lipc-get-prop com.lab126.wifid cmState | grep -q CONNECTED; do
        [ "$tries" -ge 60 ] && return 1
        tries=$((tries + 1))
        sleep 1
    done
}

# Without the interface nothing can draw a screensaver over the dashboard,
# and the other services only drain the battery.
for job in lab126_gui otaupd phd tmd x todo mcsd archive dynconfig dpmd appmgrd stackdumpd; do
    stop "$job" >/dev/null 2>&1
done
lipc-set-prop com.lab126.powerd preventScreenSaver 1
log "station started"

while true; do
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    if wait_for_wifi && curl -fsS -o "$IMAGE.part" "$DASHBOARD_URL" 2>>"$LOG"; then
        mv "$IMAGE.part" "$IMAGE"
        log "dashboard updated"
    else
        rm -f "$IMAGE.part"
        log "update failed, keeping the previous dashboard"
    fi
    lipc-set-prop com.lab126.cmd wirelessEnable 0

    lipc-set-prop com.lab126.powerd flIntensity 0
    for rotation in /sys/devices/platform/*_epdc_fb/graphics/fb0/rotate; do
        echo 0 >"$rotation"
    done
    /usr/sbin/eips -f -g "$IMAGE"

    # Suspending right after a screen update can hang some models.
    sleep 3
    rtcwake -d "$RTC" -m no -s "$REFRESH_SECONDS"
    echo mem >/sys/power/state
done

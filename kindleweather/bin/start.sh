#!/bin/sh
# KUAL "Start weather station" action: runs station.sh in the background, in a
# session of its own, so it outlives KUAL and the interface it stops.
. "$(dirname "$0")/common.sh"

# KUAL may signal what it started as it closes. Ignored signals stay ignored
# in the station, which runs until the Kindle restarts anyway.
trap '' HUP INT TERM
rm -f "$PID_FILE"
log "start requested from KUAL"
if command -v setsid >/dev/null 2>&1; then
    setsid sh "$EXTENSION_DIR/bin/station.sh" </dev/null >>"$LOG" 2>&1 &
else
    nohup sh "$EXTENSION_DIR/bin/station.sh" </dev/null >>"$LOG" 2>&1 &
fi

# Hand back to KUAL only once the station runs on its own.
tries=0
while [ ! -f "$PID_FILE" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
[ -f "$PID_FILE" ] || log "the station did not start"

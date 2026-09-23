#!/bin/sh
# KUAL "Start weather station" action: runs station.sh in the background, in a
# session of its own, so it outlives KUAL and the interface it stops.
. "$(dirname "$0")/common.sh"

# Ignored signals stay ignored in the station, which runs until the Kindle
# restarts anyway.
trap '' HUP INT TERM
rm -f "$PID_FILE"
log "start requested from KUAL"
detach sh "$EXTENSION_DIR/bin/station.sh"

# Hand back to KUAL only once the station runs on its own.
tries=0
while [ ! -f "$PID_FILE" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
[ -f "$PID_FILE" ] || log "the station did not start"

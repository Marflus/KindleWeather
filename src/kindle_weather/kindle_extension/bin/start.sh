#!/bin/sh
# KUAL "Start" action: run the station in the background, in a session of its
# own so it outlives KUAL and the Kindle interface it stops.
. "$(dirname "$0")/common.sh"

# KUAL may signal what it started as it closes. Ignored signals stay ignored
# in the station, which runs until the Kindle restarts anyway.
trap '' HUP INT TERM
rm -f "$PID_FILE"
log "start requested from KUAL, in $EXTENSION_DIR"
STATION="$EXTENSION_DIR/bin/station.sh"
PYTHON=$(find_python)
if command -v setsid >/dev/null 2>&1; then
    setsid sh "$STATION" </dev/null >>"$LOG" 2>&1 &
elif [ -n "$PYTHON" ]; then
    log "setsid not found, detaching with Python"
    "$PYTHON" -c 'import os, sys; os.setsid(); os.execvp("sh", ["sh", sys.argv[1]])' \
        "$STATION" </dev/null >>"$LOG" 2>&1 &
else
    log "setsid not found, starting with nohup"
    nohup sh "$STATION" </dev/null >>"$LOG" 2>&1 &
fi

# Hand back to KUAL only once the station runs on its own.
tries=0
while [ ! -f "$PID_FILE" ] && [ "$tries" -lt 20 ]; do
    sleep 1
    tries=$((tries + 1))
done
[ -f "$PID_FILE" ] || log "the station did not start"

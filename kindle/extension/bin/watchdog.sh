#!/bin/sh
# Run by cron every 5 minutes. Keeps the Kindle awake and on Wi-Fi around the
# daily update so the GitHub Actions job can reach it over SSH, and lets it
# sleep normally the rest of the day.
# The window must bracket TARGET_TIME in .github/workflows/update.yml.
WINDOW_START=550 # 05:50
WINDOW_END=620   # 06:20

# The leading 1 stops times like 0805 from being parsed as octal.
now=$((1$(date +%H%M) - 10000))

if [ "$now" -ge "$WINDOW_START" ] && [ "$now" -le "$WINDOW_END" ]; then
    lipc-set-prop com.lab126.powerd preventScreenSaver 1
    lipc-send-event com.lab126.powerd resetAutoSuspendTimeout 0
    # Wi-Fi has its own power management, independent of the screen.
    lipc-set-prop com.lab126.wifid enable 1
else
    lipc-set-prop com.lab126.powerd preventScreenSaver 0
fi

#!/bin/sh
# Registers the wake watchdog in root's crontab. Safe to run repeatedly.
WATCHDOG=/mnt/us/extensions/kindlemeteo/bin/watchdog.sh

# Some firmwares keep one crontab file per user under /etc/crontab/.
crontab=/etc/crontab
[ -d "$crontab" ] && crontab=/etc/crontab/root

if ! grep -qF "$WATCHDOG" "$crontab" 2>/dev/null; then
    # The root filesystem is mounted read-only by default.
    mntroot rw >/dev/null
    # Drop the entry left by versions that installed the watchdog elsewhere.
    sed -i '/dashboard_watchdog\.sh/d' "$crontab" 2>/dev/null
    echo "*/5 * * * * sh $WATCHDOG >/dev/null 2>&1" >>"$crontab"
    mntroot ro >/dev/null
fi

if ! ps | grep -q '[c]rond'; then
    echo "warning: crond is not running, the wake watchdog will not run" >&2
fi

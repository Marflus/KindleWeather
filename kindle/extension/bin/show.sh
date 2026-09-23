#!/bin/sh
# Full e-ink refresh with the latest dashboard.
# Absolute path: /usr/sbin is not on PATH in non-interactive SSH sessions.
/usr/sbin/eips -f -g /mnt/us/extensions/kindleweather/dashboard.png

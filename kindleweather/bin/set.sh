#!/bin/sh
# KUAL settings buttons: sh bin/set.sh SETTING VALUE, such as orientation landscape.
# KUAL reloads the menu a quarter of a second after the press, so the menu is
# updated first, with sed; then Python saves the setting in config.json and
# rewrites the menu properly. See kindle_weather/settings.py.
. "$(dirname "$0")/common.sh"
MENU="$EXTENSION_DIR/menu.json"
setting=$1
value=$2
log "setting $setting to $value"

# The name of the chosen value, from its button: [ ] Landscape -> Landscape.
name=$(sed -n "s|.*\"name\": \"\[.\] \([^\"]*\)\".*bin/set.sh $setting $value\".*|\1|p" "$MENU")
# The submenu title: orientation -> Orientation.
title=$(echo "$setting" | awk '{ print toupper(substr($0, 1, 1)) substr($0, 2) }')
if [ -n "$name" ]; then
    sed -i -e "/bin\/set.sh $setting /s/\"\[x\] /\"[ ] /" \
        -e "/bin\/set.sh $setting $value\"/s/\"\[ \] /\"[x] /" \
        -e "s|\"$title: [^\"]*\"|\"$title: $name\"|" "$MENU"
fi

PYTHON=$(find_python)
PYTHONPATH="$EXTENSION_DIR/lib" "$PYTHON" -m kindle_weather.settings "$setting" "$value" >>"$LOG" 2>&1

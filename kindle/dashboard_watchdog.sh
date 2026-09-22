#!/bin/sh
# ============================================================
# dashboard_watchdog.sh — réveil ciblé de la Kindle autour de 6h00
# ------------------------------------------------------------
# Contrairement à une ancienne version de ce projet qui empêchait la
# Kindle de s'endormir en permanence (fiable, mais qui vide la batterie
# en ~1 jour), ce script ne force la connectivité (Wi-Fi, pas de veille
# profonde) que pendant une courte fenêtre quotidienne, le temps que
# GitHub Actions puisse s'y connecter et pousser le nouveau dashboard.
# Le reste de la journée, la liseuse peut dormir normalement (veille
# profonde) pour préserver la batterie.
#
# L'écran de veille natif d'Amazon, lui, est désactivé EN PERMANENCE
# (`preventScreenSaver 1`), pas seulement pendant la fenêtre de réveil.
# Amazon ne peut donc jamais redessiner son propre écran de veille par
# dessus le dashboard : la dernière image affichée par `eips` (le
# dashboard du jour) reste visible sur l'écran e-ink pendant toute la
# veille, sans consommer d'énergie supplémentaire — l'écran ne
# rafraîchit que quand on lui demande explicitement.
#
# Installé par le workflow (.github/workflows/update.yml) comme tâche
# cron exécutée toutes les 5 minutes (voir crontab de la Kindle). À
# chaque exécution :
#   - désactive l'écran de veille par défaut d'Amazon (toujours) ;
#   - si l'heure locale de la liseuse est dans la fenêtre 05:50–06:20
#     (marge autour de la mise à jour de 6h00, pour absorber un
#     éventuel décalage d'horloge ou de traitement du job) :
#       -> repousse la mise en veille profonde et force la réactivation
#          du Wi-Fi, pour que la liseuse reste joignable en SSH.
#
# Important : ceci suppose que l'horloge système de la Kindle est bien
# réglée sur l'heure locale (celle affichée à l'écran). Si la mise à
# jour de 6h00 échoue de façon récurrente, vérifier avec `date` en SSH
# que l'heure de la liseuse correspond bien à l'heure réelle locale.
# ============================================================

WINDOW_START=350   # 05:50 = 5*60 + 50
WINDOW_END=380      # 06:20 = 6*60 + 20

hour="$(date +%H)"
minute="$(date +%M)"
# "10#" force une lecture en base 10 (sinon "08"/"09" sont invalides en
# arithmétique shell, interprétés comme de l'octal).
now_minutes=$((10#$hour * 60 + 10#$minute))

lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null

if [ "$now_minutes" -ge "$WINDOW_START" ] && [ "$now_minutes" -le "$WINDOW_END" ]; then
    lipc-send-event com.lab126.powerd resetAutoSuspendTimeout 0 2>/dev/null

    # Le Wi-Fi a sa propre gestion d'énergie, indépendante de l'écran et
    # de la mise en veille : un écran resté allumé ne garantit pas que le
    # Wi-Fi soit toujours associé. On force explicitement sa réactivation
    # pour que la liseuse soit bien joignable en SSH pendant la fenêtre.
    lipc-set-prop com.lab126.wifid enable 1 2>/dev/null
fi

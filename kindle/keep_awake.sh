#!/bin/sh
# ============================================================
# keep_awake.sh — empêche la Kindle de s'endormir entre deux mises à jour
# ------------------------------------------------------------
# Cette liseuse ne sert qu'à afficher le dashboard météo. Or, laissée à
# elle-même, une Kindle jailbreakée :
#
#   1) part en veille profonde après quelques minutes d'inactivité, ce qui
#      coupe le Wi-Fi (et donc Tailscale) : le job GitHub Actions ne peut
#      alors plus s'y connecter en SSH à l'heure de la mise à jour ;
#   2) affiche son écran de veille par défaut (une image Amazon) au moment
#      de s'endormir, qui remplace visuellement le dashboard à l'écran ;
#   3) génère un rafraîchissement d'écran supplémentaire au réveil, en plus
#      de celui utilisé pour afficher le nouveau dashboard — ce qu'on veut
#      éviter pour préserver la batterie.
#
# Ce petit démon tourne en tâche de fond en continu sur la liseuse et,
# toutes les 60 secondes :
#   - désactive l'affichage de l'écran de veille par défaut,
#   - repousse la minuterie de mise en veille profonde.
#
# Résultat : la liseuse reste allumée, joignable en SSH, avec le dashboard
# affiché en permanence — un seul rafraîchissement d'écran a lieu par jour,
# au moment de la mise à jour.
#
# Il est démarré automatiquement par le workflow GitHub Actions
# (voir .github/workflows/update.yml) s'il n'est pas déjà en cours
# d'exécution — inutile de l'installer manuellement.
# ============================================================

PIDFILE=/mnt/us/dashboard/keep_awake.pid

# Une seule instance à la fois : si un démon tourne déjà, on ne fait rien.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    exit 0
fi
echo $$ > "$PIDFILE"

while true; do
    # Empêche l'écran de veille (fond d'écran par défaut) de s'afficher.
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null

    # Repousse la minuterie d'inactivité pour éviter la veille profonde
    # (et donc la coupure du Wi-Fi / de la connexion Tailscale).
    lipc-send-event com.lab126.powerd resetAutoSuspendTimeout 0 2>/dev/null

    # Rétro-éclairage au minimum en permanence (pas seulement lors de la MAJ).
    lipc-set-prop com.lab126.powerd flIntensity 0 2>/dev/null

    sleep 60
done

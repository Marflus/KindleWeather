#!/bin/sh
# Redessine manuellement le dashboard météo courant (bouton KUAL
# "Afficher le dashboard météo"). Utile pour forcer l'affichage sans
# attendre la prochaine mise à jour automatique de 6h00, ou pour
# vérifier que le mécanisme anti-écran de veille (preventScreenSaver
# permanent, voir kindle/dashboard_watchdog.sh) fonctionne bien.

/usr/sbin/eips -f -g /mnt/us/dashboard/meteo.png

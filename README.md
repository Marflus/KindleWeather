# KindleMeteo

Dashboard météo quotidien affiché sur une liseuse Kindle jailbreakée,
transformée en écran e-ink dédié à la météo du jour.

Chaque matin à **6h (heure de Paris)**, un workflow GitHub Actions génère une
image météo à partir des données [Open-Meteo](https://open-meteo.com/), puis
l'envoie et l'affiche sur la Kindle via SSH, à travers un tunnel
[Tailscale](https://tailscale.com/).

## Comment ça marche

```
 Kindle (dort ~23h30/24, watchdog cron toutes les 5 min)
        │
        └─ vers 05:50–06:20 heure locale : reste éveillée et joignable
           (kindle/dashboard_watchdog.sh), puis se rendort après la fenêtre

 GitHub Actions — job "check-time" (cron 4h ET 5h UTC)
        │
        └─ 6h à Paris aujourd'hui ? ── non ──▶ rien d'autre ne s'exécute
                    │
                   oui
                    ▼
 GitHub Actions — job "update-dashboard"
        ├─ 1. generate_meteo.py  ─── télécharge la météo (Open-Meteo)
        │                            et dessine meteo.png (1072×1448, gris)
        │
        ├─ 2. Connexion Tailscale ── rejoint le réseau privé de la Kindle,
        │                            réveillée par son propre watchdog
        │
        └─ 3. SSH / SCP vers la Kindle (avec quelques tentatives si la
              liseuse n'a pas encore fini de se reconnecter)
                 ├─ (ré)installe kindle/dashboard_watchdog.sh en tâche
                 │  cron si absente (auto-réparation)
                 ├─ envoie meteo.png sur la liseuse
                 ├─ eips -f -g meteo.png  ── un seul rafraîchissement écran
                 └─ si le Screen Saver Hack est installé, synchronise
                    aussi meteo.png comme image de veille (voir plus bas)
```

### `generate_meteo.py`

Script Python autonome qui :

1. interroge l'API Open-Meteo (prévisions du jour + détail horaire) ;
2. dessine le dashboard en niveaux de gris, en 2x la résolution cible puis
   réduit l'image (anticrénelage propre sur écran e-ink) ;
3. enregistre le résultat dans `meteo.png`.

Toute la mise en page (en-tête, bloc météo principal, alerte pluie, courbe
de température, tableau horaire) est commentée directement dans le fichier,
section par section.

Pour changer de ville, modifier les constantes `LATITUDE`, `LONGITUDE` et
`LOCATION_NAME` en haut du fichier.

La date affichée et l'heure du pied de page ("Mis à jour le...") utilisent
le fuseau horaire renvoyé par l'API Open-Meteo pour ces coordonnées (champ
`timezone` de la réponse), pas celui du serveur qui exécute le script —
important car le workflow tourne sur un runner GitHub Actions en UTC.

### `.github/workflows/update.yml`

Orchestre la mise à jour quotidienne, en deux jobs : `check-time` (est-ce
bien 6h à Paris ?) puis `update-dashboard` (génère l'image, se connecte à
la Kindle, et l'affiche) si c'est le cas. Voir la section
[Planification](#planification-le-pourquoi-de-deux-cron) ci-dessous pour
le détail du déclenchement à 6h.

### `kindle/dashboard_watchdog.sh`

Petit script shell déployé automatiquement sur la Kindle par le workflow et
exécuté toutes les 5 minutes via cron (pas d'installation manuelle
nécessaire). Voir [Pourquoi un réveil programmé plutôt qu'une veille
permanente ?](#pourquoi-un-réveil-programmé-plutôt-quune-veille-permanente-)
ci-dessous.

## Prérequis

- Une Kindle jailbreakée avec accès SSH root (ce projet a été testé sur un
  modèle utilisant le rétro-éclairage `max77696-bl`, ex. Paperwhite 2e
  génération) et l'utilitaire `eips` disponible.
- [Tailscale](https://tailscale.com/) installé sur la Kindle et un
  [auth key](https://tailscale.com/kb/1085/auth-keys) réutilisable pour le
  runner GitHub Actions.
- Une paire de clés SSH dont la clé publique est autorisée sur la Kindle.

## Configuration du dépôt

Dans **Settings → Secrets and variables → Actions** :

| Type     | Nom                    | Description                                              |
|----------|------------------------|-----------------------------------------------------------|
| Secret   | `TAILSCALE_AUTHKEY`    | Auth key Tailscale utilisée par le runner GitHub Actions.  |
| Secret   | `KINDLE_SSH_KEY`       | Clé privée SSH (format `id_ed25519`) autorisée sur la Kindle. |
| Variable | `KINDLE_TAILSCALE_IP`  | *(optionnel)* IP Tailscale de la Kindle. Par défaut : `100.74.176.86`. |

## Planification : le pourquoi de deux `cron`

GitHub Actions ne planifie qu'en UTC et ne suit pas les changements
d'heure d'été/hiver. Pour afficher le dashboard à 6h pile heure de Paris
toute l'année, le workflow se déclenche à **4h ET 5h UTC** :

- 4h UTC = 6h à Paris en heure d'été (UTC+2)
- 5h UTC = 6h à Paris en heure d'hiver (UTC+1)

Le job `check-time` calcule l'heure locale réelle avec `TZ='Europe/Paris'
date` : le job `update-dashboard` ne se déclenche que s'il est bien 6h à
Paris — l'autre déclenchement de la journée n'exécute que `check-time`
(quasi instantané) et s'arrête là. Un déclenchement manuel
(`workflow_dispatch`, via l'onglet *Actions*) passe toujours cette
vérification, pour pouvoir tester à n'importe quelle heure.

> Si tu changes l'heure cible (6h), pense à mettre à jour **les deux**
> côtés : la comparaison `"$current_hour" = "06"` dans le job
> `check-time` du workflow, et la fenêtre `WINDOW_START`/`WINDOW_END`
> dans `kindle/dashboard_watchdog.sh`. Ce sont deux horloges
> indépendantes (le runner GitHub et la Kindle) qui doivent rester
> synchronisées sur la même heure cible.

## Pourquoi un réveil programmé plutôt qu'une veille permanente ?

Une première version de ce projet empêchait la Kindle de s'endormir en
permanence (démon tournant 24h/24). Ça réglait la connectivité, mais ça
**vide la batterie en une journée ou deux** : le Wi-Fi et le processeur
restent actifs en continu au lieu de se mettre en veille entre les mises
à jour.

Le compromis retenu ici est différent : la Kindle **dort normalement** le
reste de la journée (donc économise sa batterie), et c'est **elle-même**
qui se réveille brièvement chaque matin autour de 6h, plutôt que de
compter sur GitHub Actions pour la « pousser » depuis l'extérieur pendant
qu'elle dort (une fois le Wi-Fi coupé par la mise en veille, plus aucune
connexion entrante n'est possible, quelle que soit la fréquence des
tentatives côté serveur).

`kindle/dashboard_watchdog.sh` est installé comme tâche cron sur la
liseuse (toutes les 5 minutes, via `/etc/crontab`) et, à chaque
exécution :

- si l'heure locale de la Kindle est dans la fenêtre **05:50–06:20** :
  désactive l'écran de veille (`lipc-set-prop com.lab126.powerd
  preventScreenSaver 1`), repousse la mise en veille profonde
  (`lipc-send-event com.lab126.powerd resetAutoSuspendTimeout 0`) et
  force la réactivation du Wi-Fi (`lipc-set-prop com.lab126.wifid enable
  1` — le Wi-Fi a sa propre gestion d'énergie, indépendante de l'écran :
  un écran resté allumé ne garantit pas à lui seul que le Wi-Fi soit
  toujours associé), le temps que le workflow GitHub Actions s'y
  connecte et pousse le dashboard ;
- en dehors de cette fenêtre : réautorise l'écran de veille normal, pour
  que la liseuse s'endorme le reste du temps.

Côté GitHub Actions, l'étape *Attendre que la Kindle soit joignable*
réessaie la connexion SSH pendant jusqu'à 3 minutes avant d'abandonner,
pour absorber le délai éventuel entre le déclenchement du job et le
prochain cycle de 5 minutes du watchdog.

Le reste de la journée (~23h30 sur 24h), la Kindle dort donc normalement.
C'est un compromis assumé : l'écran de veille par défaut d'Amazon peut
réapparaître pendant cette période (contrairement à l'ancienne version
« toujours éveillée » qui gardait le dashboard affiché en permanence),
mais la batterie est largement préservée puisque le Wi-Fi/CPU ne sont
forcés actifs que ~30 minutes par jour.

> **Prérequis non garanti sur tous les firmwares** : ce mécanisme suppose
> que (1) l'horloge de la Kindle est réglée sur l'heure locale (celle
> affichée à l'écran), et (2) `crond` (busybox) tourne en arrière-plan et
> continue à exécuter les tâches planifiées même quand l'écran est en
> veille — ce qui est le cas sur la plupart des jailbreaks Kindle, mais
> n'a pas pu être vérifié sur du matériel réel depuis cet environnement.
> Si la mise à jour de 6h ne fonctionne pas de façon fiable, voir
> [Dépannage](#dépannage) ci-dessous. Les noms de propriétés
> `lipc-set-prop`/`lipc-send-event` sont ceux couramment utilisés par la
> communauté de jailbreak Kindle ; selon le modèle et la version du
> firmware, il peut être nécessaire de les ajuster (voir [MobileRead
> Wiki](https://www.mobileread.com/forums/forumdisplay.php?f=150)).

## Remplacer l'écran de veille par défaut d'Amazon

Le réveil programmé ci-dessus règle la connectivité et la batterie, mais
en dehors de sa fenêtre de ~30 minutes autour de 6h, la liseuse dort
normalement — et Amazon affiche alors son propre écran de veille par
défaut, qui recouvre le dashboard jusqu'à la prochaine mise à jour.

Pour l'éviter **sans** sacrifier la batterie, la solution est de
remplacer les images de veille d'Amazon par le dashboard lui-même, via le
[« Screen Saver Hack »](https://www.mobileread.com/forums/showthread.php?t=195474)
(aussi appelé « linkss »), une extension très répandue dans la
communauté jailbreak Kindle. Une fois le dashboard placé dans son
dossier d'images, la liseuse continue de dormir normalement (l'écran
e-ink ne consomme rien tant qu'il n'est pas rafraîchi), mais ce qu'elle
affiche en dormant, c'est notre dashboard — plus l'écran par défaut
d'Amazon.

### Installation (à faire une fois, sur la liseuse)

1. Télécharger le paquet correspondant à ton modèle/jailbreak depuis le
   [fil MobileRead « K5 FW 5.x ScreenSavers Hack »](https://www.mobileread.com/forums/showthread.php?t=195474)
   (probablement la même source que celle utilisée pour le jailbreak
   initial).
2. Placer le `.bin` dans le dossier `mrpackages`, puis dans KUAL :
   **Helper → Install MR Packages**.
3. Redémarrer la liseuse (l'installation demande généralement plusieurs
   redémarrages).
4. Vérifier que `/mnt/us/linkss/screensavers/` existe désormais
   (`ls /mnt/us/linkss/screensavers` en SSH).

### Ce que fait le workflow automatiquement ensuite

Une fois le dossier détecté, chaque exécution quotidienne :

- supprime les autres images du dossier `/mnt/us/linkss/screensavers/`
  (celles fournies par défaut avec le hack), pour que le dashboard soit
  la seule image de veille et qu'il n'y ait aucune rotation ;
- y copie le `meteo.png` du jour.

Si le dossier n'existe pas encore (hack non installé), cette étape ne
fait rien — le reste du pipeline continue de fonctionner normalement.

> **Non vérifié sur du matériel réel** : certaines implémentations de ce
> hack nécessitent de déposer un fichier vide nommé `reboot` dans
> `/mnt/us/linkss/` pour qu'un changement de *liste* d'images de veille
> soit pris en compte. Ici, seul le *contenu* d'un fichier de nom
> constant (`meteo.png`) change chaque jour, ce qui ne devrait pas
> nécessiter de redémarrage — mais si l'image de veille ne se met pas à
> jour après un déploiement, essaie de redémarrer la liseuse une fois
> pour vérifier cette hypothèse, et dis-le-moi.

## Développement local

```bash
pip install -r requirements.txt
python generate_meteo.py   # génère meteo.png dans le dossier courant
```

## Dépannage

- **Le job échoue à se connecter en SSH à 6h** :
  - vérifier en SSH direct (pendant que la Kindle est réveillée, ou après
    l'avoir réveillée manuellement en appuyant sur le bouton/l'écran) que
    la tâche cron est bien installée :
    `cat /etc/crontab | grep dashboard_watchdog` ;
  - vérifier que `crond` tourne : `ps | grep crond` — s'il est absent, le
    watchdog ne peut pas s'exécuter (voir le message d'avertissement
    affiché par l'étape *Installer le watchdog de réveil* dans les logs
    GitHub Actions) ;
  - vérifier que l'heure système de la Kindle correspond à l'heure locale
    réelle : `date` en SSH. Si elle est décalée, ajuster la fenêtre
    `WINDOW_START`/`WINDOW_END` dans `kindle/dashboard_watchdog.sh` ou
    corriger l'horloge de la liseuse ;
  - **si la Kindle est visiblement éveillée (écran allumé) et que la
    connexion échoue quand même** : le Wi-Fi peut être coupé
    indépendamment de l'écran par la gestion d'énergie de la Kindle.
    Vérifier avec `tailscale status` et `ps | grep tailscaled` en SSH
    direct que Tailscale tourne et annonce la bonne IP (elle a pu changer
    — mettre à jour la variable de dépôt `KINDLE_TAILSCALE_IP` le cas
    échéant), et que le Wi-Fi est bien actif
    (`lipc-get-prop com.lab126.wifid enable` doit renvoyer `1`).
- **L'écran de veille Amazon apparaît en dehors de la fenêtre de 6h** :
  comportement par défaut (la liseuse dort normalement le reste de la
  journée pour préserver sa batterie — voir [Pourquoi un réveil
  programmé plutôt qu'une veille permanente
  ?](#pourquoi-un-réveil-programmé-plutôt-quune-veille-permanente-)). Pour
  l'éviter complètement, voir [Remplacer l'écran de veille par défaut
  d'Amazon](#remplacer-lécran-de-veille-par-défaut-damazon) ci-dessous.
- **Le job échoue à se connecter en SSH en général** : vérifier que la
  Kindle est bien visible sur le réseau Tailscale (`tailscale status`) et
  que `KINDLE_TAILSCALE_IP` correspond à son IP actuelle.
- **Le dashboard ne se met pas à jour à 6h pile** : vérifier dans l'onglet
  *Actions* que le job `update-dashboard` s'est bien déclenché à
  l'horaire correspondant à 6h à Paris (4h ou 5h UTC selon la saison) —
  l'autre horaire de la journée ne doit exécuter que `check-time`, qui
  se termine immédiatement sans lancer `update-dashboard`.

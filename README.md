# KindleMeteo

Dashboard météo quotidien affiché sur une liseuse Kindle jailbreakée,
transformée en écran e-ink dédié à la météo du jour.

Chaque matin à **6h (heure de Paris)**, un workflow GitHub Actions génère une
image météo à partir des données [Open-Meteo](https://open-meteo.com/), puis
l'envoie et l'affiche sur la Kindle via SSH, à travers un tunnel
[Tailscale](https://tailscale.com/).

## Comment ça marche

```
 GitHub Actions (cron 6h Paris)
        │
        ├─ 1. generate_meteo.py  ─── télécharge la météo (Open-Meteo)
        │                            et dessine meteo.png (1072×1448, gris)
        │
        ├─ 2. Connexion Tailscale ── rejoint le réseau privé de la Kindle
        │
        └─ 3. SSH / SCP vers la Kindle
                 ├─ installe kindle/dashboard_watchdog.sh en tâche cron
                 │  (si absente) — réveil ciblé autour de 6h, pas de
                 │  veille permanente (préserve la batterie)
                 ├─ envoie meteo.png sur la liseuse
                 └─ eips -f -g meteo.png  ── un seul rafraîchissement écran
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

### `.github/workflows/update.yml`

Orchestre la mise à jour quotidienne : génère l'image, se connecte à la
Kindle, et l'affiche. Voir la section [Planification](#planification-le-pourquoi-de-deux-cron)
ci-dessous pour le détail du déclenchement à 6h.

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

La première étape du job (`Vérifier qu'il est bien 6h à Paris`) calcule
l'heure locale réelle avec `TZ='Europe/Paris' date` et n'exécute la suite
du job que si elle correspond à 6h — l'autre déclenchement de la journée est
ignoré silencieusement. Un déclenchement manuel (`workflow_dispatch`, via
l'onglet *Actions*) passe toujours cette vérification, pour pouvoir tester
à n'importe quelle heure.

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
  preventScreenSaver 1`) et repousse la mise en veille profonde
  (`lipc-send-event com.lab126.powerd resetAutoSuspendTimeout 0`), le
  temps que le workflow GitHub Actions s'y connecte et pousse le
  dashboard ;
- en dehors de cette fenêtre : réautorise l'écran de veille normal, pour
  que la liseuse s'endorme le reste du temps.

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

## Développement local

```bash
pip install -r requirements.txt
python generate_meteo.py   # génère meteo.png dans le dossier courant
```

## Dépannage

- **Le job échoue à se connecter en SSH à 6h (la Kindle dormait)** :
  - vérifier en SSH (pendant que la Kindle est réveillée, ou après l'avoir
    réveillée manuellement) que la tâche cron est bien installée :
    `cat /etc/crontab | grep dashboard_watchdog` ;
  - vérifier que `crond` tourne : `ps | grep crond` — s'il est absent, le
    watchdog ne peut pas s'exécuter (voir le message d'avertissement
    affiché par l'étape *Installer le watchdog de réveil* dans les logs
    GitHub Actions) ;
  - vérifier que l'heure système de la Kindle correspond à l'heure locale
    réelle : `date` en SSH. Si elle est décalée, ajuster la fenêtre
    `WINDOW_START`/`WINDOW_END` dans `kindle/dashboard_watchdog.sh` ou
    corriger l'horloge de la liseuse.
- **L'écran de veille Amazon apparaît en dehors de la fenêtre de 6h** :
  c'est le comportement attendu (voir [Pourquoi un réveil programmé
  plutôt qu'une veille permanente
  ?](#pourquoi-un-réveil-programmé-plutôt-quune-veille-permanente-)) — la
  liseuse dort normalement le reste de la journée pour préserver sa
  batterie.
- **Le job échoue à se connecter en SSH en général** : vérifier que la
  Kindle est bien visible sur le réseau Tailscale (`tailscale status`) et
  que `KINDLE_TAILSCALE_IP` correspond à son IP actuelle.
- **Le dashboard ne se met pas à jour à 6h pile** : vérifier dans l'onglet
  *Actions* que le job du bon horaire (4h ou 5h UTC selon la saison) est
  bien celui qui a exécuté toutes les étapes (l'autre doit s'arrêter dès
  la première étape).

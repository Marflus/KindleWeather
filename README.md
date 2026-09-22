# KindleMeteo

Dashboard météo quotidien affiché sur une liseuse Kindle jailbreakée,
transformée en écran e-ink dédié à la météo du jour.

Chaque matin à **6h00 (heure de Paris)**, un workflow GitHub Actions génère
une image météo à partir des données [Open-Meteo](https://open-meteo.com/),
puis l'envoie et l'affiche sur la Kindle via SSH, à travers un tunnel
[Tailscale](https://tailscale.com/). Le reste de la journée, l'écran de
veille natif d'Amazon est désactivé en permanence : la dernière image
dessinée (le dashboard) reste donc affichée sur l'écran e-ink jusqu'à la
mise à jour du lendemain, sans consommer d'énergie supplémentaire.

## Comment ça marche

```
 Kindle (dort ~23h/24, watchdog cron toutes les 5 min)
        │
        ├─ en permanence : écran de veille natif d'Amazon désactivé
        │  (preventScreenSaver 1) — la dernière image dessinée par eips
        │  reste affichée pendant toute la veille
        │
        └─ vers 05:50–06:20 heure locale : reste éveillée et joignable
           (kindle/dashboard_watchdog.sh), puis se rendort après la fenêtre

 GitHub Actions — job "check-time" (cron 4h00 ET 5h00 UTC)
        │
        └─ 6h00 à Paris aujourd'hui ? ── non ──▶ rien d'autre ne s'exécute
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
                 ├─ si le Screen Saver Hack (linkss) est installé,
                 │  synchronise aussi meteo.png comme image de veille
                 │  (voir plus bas — inopérant sur les firmwares récents)
                 └─ si KUAL est installé, (ré)installe le bouton "Afficher
                    le dashboard météo" (voir plus bas)
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
bien 6h00 à Paris ?) puis `update-dashboard` (génère l'image, se connecte à
la Kindle, et l'affiche) si c'est le cas. Voir la section
[Planification](#planification-le-pourquoi-de-deux-cron) ci-dessous pour
le détail du déclenchement à 6h00.

### `kindle/dashboard_watchdog.sh`

Petit script shell déployé automatiquement sur la Kindle par le workflow et
exécuté toutes les 5 minutes via cron (pas d'installation manuelle
nécessaire). Désactive en permanence l'écran de veille natif d'Amazon et
gère la fenêtre de réveil quotidienne. Voir [Pourquoi un réveil programmé
plutôt qu'une veille
permanente ?](#pourquoi-un-réveil-programmé-plutôt-quune-veille-permanente-)
ci-dessous.

### `kindle/kual/`

Bouton [KUAL](https://www.mobileread.com/forums/showthread.php?t=203326)
optionnel ("Afficher le dashboard météo") qui redessine manuellement le
dashboard courant depuis le menu de la liseuse. Installé automatiquement
par le workflow si KUAL est déjà présent sur la Kindle — voir [Bouton KUAL
"Afficher le dashboard"](#bouton-kual-afficher-le-dashboard) ci-dessous.

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
d'heure d'été/hiver. Pour afficher le dashboard à 6h00 pile heure de Paris
toute l'année, le workflow se déclenche à **4h00 ET 5h00 UTC** :

- 4h00 UTC = 6h00 à Paris en heure d'été (UTC+2)
- 5h00 UTC = 6h00 à Paris en heure d'hiver (UTC+1)

Le job `check-time` calcule l'heure locale réelle avec `TZ='Europe/Paris'
date` : le job `update-dashboard` ne se déclenche que s'il est bien 6h00 à
Paris — l'autre déclenchement de la journée n'exécute que `check-time`
(quasi instantané) et s'arrête là. Un déclenchement manuel
(`workflow_dispatch`, via l'onglet *Actions*) passe toujours cette
vérification, pour pouvoir tester à n'importe quelle heure.

> Si tu changes l'heure cible (6h00), pense à mettre à jour **les deux**
> côtés : la comparaison `"$current_time" = "06:00"` dans le job
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
qui se réveille brièvement chaque matin autour de 6h00, plutôt que de
compter sur GitHub Actions pour la « pousser » depuis l'extérieur pendant
qu'elle dort (une fois le Wi-Fi coupé par la mise en veille, plus aucune
connexion entrante n'est possible, quelle que soit la fréquence des
tentatives côté serveur).

`kindle/dashboard_watchdog.sh` est installé comme tâche cron sur la
liseuse (toutes les 5 minutes, via `/etc/crontab`) et, à chaque
exécution :

- désactive **en permanence** l'écran de veille natif d'Amazon
  (`lipc-set-prop com.lab126.powerd preventScreenSaver 1`), pour que la
  dernière image dessinée par `eips` (le dashboard) reste affichée
  pendant toute la veille, sans qu'Amazon puisse la remplacer par son
  propre écran de veille ;
- si l'heure locale de la Kindle est dans la fenêtre **05:50–06:20** :
  repousse en plus la mise en veille profonde (`lipc-send-event
  com.lab126.powerd resetAutoSuspendTimeout 0`) et force la réactivation
  du Wi-Fi (`lipc-set-prop com.lab126.wifid enable 1` — le Wi-Fi a sa
  propre gestion d'énergie, indépendante de l'écran : un écran resté
  allumé ne garantit pas à lui seul que le Wi-Fi soit toujours associé),
  le temps que le workflow GitHub Actions s'y connecte et pousse le
  dashboard.

Côté GitHub Actions, l'étape *Attendre que la Kindle soit joignable*
réessaie la connexion SSH pendant jusqu'à 3 minutes avant d'abandonner,
pour absorber le délai éventuel entre le déclenchement du job et le
prochain cycle de 5 minutes du watchdog.

Le reste de la journée (~23h30 sur 24h), la Kindle dort donc en veille
profonde (batterie préservée, Wi-Fi/CPU forcés actifs seulement ~30
minutes par jour), tout en gardant le dashboard affiché à l'écran grâce
au `preventScreenSaver` permanent décrit ci-dessus — contrairement à
l'ancienne version « toujours éveillée » qui obtenait le même résultat
visuel mais en vidant la batterie en 1 à 2 jours.

> **Prérequis non garanti sur tous les firmwares** : ce mécanisme suppose
> que (1) l'horloge de la Kindle est réglée sur l'heure locale (celle
> affichée à l'écran), et (2) `crond` (busybox) tourne en arrière-plan et
> continue à exécuter les tâches planifiées même quand l'écran est en
> veille — ce qui est le cas sur la plupart des jailbreaks Kindle, mais
> n'a pas pu être vérifié sur du matériel réel depuis cet environnement.
> Si la mise à jour de 6h00 ne fonctionne pas de façon fiable, voir
> [Dépannage](#dépannage) ci-dessous. Les noms de propriétés
> `lipc-set-prop`/`lipc-send-event` sont ceux couramment utilisés par la
> communauté de jailbreak Kindle ; selon le modèle et la version du
> firmware, il peut être nécessaire de les ajuster (voir [MobileRead
> Wiki](https://www.mobileread.com/forums/forumdisplay.php?f=150)).

## Remplacer l'écran de veille par défaut d'Amazon

Le réveil programmé ci-dessus règle la connectivité et la batterie, mais
en dehors de sa fenêtre de ~30 minutes autour de 6h00, la liseuse dort
normalement — sans intervention supplémentaire, Amazon afficherait alors
son propre écran de veille par défaut, qui recouvrirait le dashboard
jusqu'à la prochaine mise à jour.

### Méthode actuelle : désactivation permanente de l'écran de veille natif

C'est la méthode active par défaut dans ce projet, déjà en place via
`kindle/dashboard_watchdog.sh` (voir [Pourquoi un réveil programmé plutôt
qu'une veille
permanente ?](#pourquoi-un-réveil-programmé-plutôt-quune-veille-permanente-)
ci-dessus) : le watchdog désactive `preventScreenSaver` en permanence, pas
seulement pendant la fenêtre de réveil. Amazon ne peut donc jamais
redessiner son écran de veille par-dessus le dashboard — la dernière image
affichée par `eips` reste visible sur l'écran e-ink tant qu'aucun nouveau
rafraîchissement n'est demandé, sans consommer d'énergie supplémentaire
(l'écran e-ink ne consomme rien entre deux rafraîchissements) et sans
empêcher la liseuse de passer en veille profonde le reste du temps.

Rien à installer pour cette méthode : elle fonctionne dès que le watchdog
est déployé (automatique, voir plus haut). Si l'ancien écran de veille
Amazon apparaît quand même, voir [Dépannage](#dépannage) ci-dessous.

### Bouton KUAL "Afficher le dashboard" (optionnel)

Si [KUAL](https://www.mobileread.com/forums/showthread.php?t=203326)
(Kindle Unified Application Launcher) est installé sur la liseuse, le
workflow y déploie automatiquement un bouton **KindleMeteo → Afficher le
dashboard météo** qui redessine à la demande le `meteo.png` courant (utile
pour tester la méthode ci-dessus sans attendre le prochain cycle, ou pour
forcer l'affichage après une manipulation manuelle). Sans effet
(silencieux) si KUAL n'est pas installé.

Fichiers correspondants, déployés dans `/mnt/us/extensions/kindlemeteo/` :
`kindle/kual/config.xml` (déclare l'extension à KUAL — **indispensable**,
sans lui KUAL ne scanne même pas le dossier), `kindle/kual/menu.json`
(définition du menu) et `kindle/kual/show_dashboard.sh` (`eips -f -g
/mnt/us/dashboard/meteo.png`).

### Ancienne méthode : Screen Saver Hack / linkss (legacy)

Avant la méthode ci-dessus, ce projet s'appuyait sur le [« Screen Saver
Hack »](https://www.mobileread.com/forums/showthread.php?t=195474) (aussi
appelé « linkss »), une extension très répandue dans la communauté
jailbreak Kindle, qui remplace les images de veille d'Amazon par le
dashboard.

> **Testé sur du matériel réel : ne fonctionne pas sur les firmwares
> récents.** Sur une Paperwhite 3 avec un firmware de janvier 2025, on a
> confirmé que le hack (dernière version disponible, datée de janvier
> 2023) monte bien correctement `meteo.png` à l'emplacement système
> attendu (`/usr/share/blanket/screensaver`), mais l'écran de veille
> réellement affiché reste celui d'Amazon — signe que ce firmware récent
> n'utilise plus cet emplacement pour choisir l'image affichée. C'est la
> raison d'être de la méthode « désactivation permanente » ci-dessus, qui
> elle fonctionne indépendamment de ce mécanisme.

Le code de synchronisation reste en place dans le workflow (il ne fait
rien de nuisible et pourrait fonctionner sur un firmware plus ancien, ou
si un hack mis à jour apparaît un jour) :

1. Télécharger le paquet correspondant à ton modèle/jailbreak depuis le
   [fil MobileRead « K5 FW 5.x ScreenSavers Hack »](https://www.mobileread.com/forums/showthread.php?t=195474).
2. Placer le `.bin` dans le dossier `mrpackages`, puis dans KUAL :
   **Helper → Install MR Packages**.
3. Redémarrer la liseuse (l'installation demande généralement plusieurs
   redémarrages).
4. Vérifier que `/mnt/us/linkss/screensavers/` existe désormais
   (`ls /mnt/us/linkss/screensavers` en SSH).

Une fois le dossier détecté, chaque exécution quotidienne supprime les
autres images de `/mnt/us/linkss/screensavers/` et y copie le `meteo.png`
du jour. Si le dossier n'existe pas (hack non installé), cette étape ne
fait rien — le reste du pipeline continue de fonctionner normalement.

## Développement local

```bash
pip install -r requirements.txt
python generate_meteo.py   # génère meteo.png dans le dossier courant
```

## Dépannage

- **Le job échoue à se connecter en SSH à 6h00** :
  - vérifier en SSH direct (pendant que la Kindle est réveillée, ou après
    l'avoir réveillée manuellement en appuyant sur le bouton/l'écran) que
    la tâche cron est bien installée. **Attention** : sur certains
    firmwares, `/etc/crontab` est un *dossier* (un fichier de tâches par
    utilisateur, ex. `/etc/crontab/root`) et non un fichier unique —
    vérifier lequel des deux s'applique avant de chercher dedans :
    `ls -la /etc/crontab` (si c'est un dossier : `cat /etc/crontab/root |
    grep dashboard_watchdog`, sinon `cat /etc/crontab | grep
    dashboard_watchdog`) ;
  - vérifier que `crond` tourne : `ps | grep crond` — s'il est absent, le
    watchdog ne peut pas s'exécuter (voir le message d'avertissement
    affiché par l'étape *Installer le watchdog de réveil* dans les logs
    GitHub Actions). Sur certains firmwares, rien ne démarre `crond`
    automatiquement au boot (pas de script `/etc/init.d/crond`), et le
    binaire ne se daemonise pas correctement sans l'option `-f` (il se
    termine aussitôt, sans erreur ni log) — d'où le lancement en `nohup
    /usr/sbin/crond -c /etc/crontab -f >/dev/null 2>&1 &` utilisé par le
    workflow. Autre piège sur ces firmwares : la racine est montée en
    lecture seule par défaut, donc écrire dans `/etc/crontab` échoue
    silencieusement sans `mntroot rw` au préalable ;
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
- **L'écran de veille Amazon apparaît quand même** (le `preventScreenSaver`
  permanent ne fonctionne pas comme attendu) :
  - vérifier que le watchdog tourne bien récemment (`date` puis comparer
    avec la dernière exécution attendue, toutes les 5 minutes) et que la
    propriété est bien positionnée : `lipc-get-prop com.lab126.powerd
    preventScreenSaver` doit renvoyer `1`, y compris en dehors de la
    fenêtre de réveil ;
  - si la propriété est bien à `1` mais que l'écran de veille Amazon
    s'affiche quand même, c'est que ce firmware ignore purement et
    simplement `preventScreenSaver` (comportement déjà observé sur
    certains firmwares récents avec le Screen Saver Hack, voir [Ancienne
    méthode : Screen Saver Hack /
    linkss](#ancienne-méthode--screen-saver-hack--linkss-legacy)) — dans
    ce cas, il n'existe pas encore de contournement connu pour ce projet ;
  - le bouton KUAL "Afficher le dashboard" (voir [Remplacer l'écran de
    veille par défaut d'Amazon](#remplacer-lécran-de-veille-par-défaut-damazon))
    permet de vérifier rapidement, en le pressant juste avant une mise en
    veille manuelle, si le dashboard reste bien affiché.
- **Le job échoue à se connecter en SSH en général** : vérifier que la
  Kindle est bien visible sur le réseau Tailscale (`tailscale status`) et
  que `KINDLE_TAILSCALE_IP` correspond à son IP actuelle.
- **Le dashboard ne se met pas à jour à 6h00 pile** : vérifier dans l'onglet
  *Actions* que le job `update-dashboard` s'est bien déclenché à
  l'horaire correspondant à 6h00 à Paris (4h00 ou 5h00 UTC selon la
  saison) — l'autre horaire de la journée ne doit exécuter que
  `check-time`, qui se termine immédiatement sans lancer `update-dashboard`.

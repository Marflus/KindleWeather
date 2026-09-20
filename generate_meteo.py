"""
Dashboard météo pour liseuse Kindle (écran e-ink, niveaux de gris)
Ville : Varsovie — Source des données : Open-Meteo

Ce script est la seule brique "métier" du projet : il télécharge les
prévisions du jour puis dessine une image PNG prête à être affichée sur
l'écran e-ink de la Kindle. Il est appelé une fois par jour par le
workflow GitHub Actions (.github/workflows/update.yml), qui se charge
ensuite d'envoyer l'image sur la liseuse via SSH/Tailscale et de
l'afficher — voir le README pour le fonctionnement d'ensemble.

Contenu du dashboard :
  - en-tête (lieu + date)
  - bloc météo du jour (icône + température + description)
  - alerte pluie / temps calme
  - courbe de température sur 24h
  - tableau détaillé par tranche horaire

Choix de rendu :
  - rendu 2x puis réduction -> anticrénelage propre sur l'écran e-ink
  - icônes redessinées en silhouettes pleines (plus lisibles en gris)
  - mise en page en "cartes" avec un vrai fond, un panneau lever/coucher
    du soleil + humidité/vent moyens, courbe avec aire remplie et repère
    sur l'heure actuelle, tableau horaire avec lignes alternées légères
    au lieu d'un bandeau noir plein
"""

import os
import math
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIGURATION
# ============================================================
# Pour changer de ville : mettre à jour ces trois constantes (coordonnées
# GPS à récupérer par ex. sur https://open-meteo.com/en/docs).
LATITUDE = 52.2297
LONGITUDE = 21.0122
LOCATION_NAME = "Varsovie"

SCALE = 2                       # facteur de sur-échantillonnage (anticrénelage)
BASE_W, BASE_H = 1072, 1448     # résolution cible de la liseuse
WIDTH, HEIGHT = BASE_W * SCALE, BASE_H * SCALE


def S(v):
    """Convertit une coordonnée/dimension pensée en pixels 'écran' en pixels de rendu."""
    return round(v * SCALE)


# Palette de gris (0 = noir, 255 = blanc)
BLACK, INK = 0, 25
GRAY_DARK, GRAY_MID = 90, 150
GRAY_LIGHT, GRAY_PALE = 205, 236
WHITE = 255

FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
FONT_REGULAR_PATH = "Roboto-Regular.ttf"
FONT_BOLD_PATH = "Roboto-Bold.ttf"


def ensure_fonts():
    for path, url in ((FONT_REGULAR_PATH, FONT_REGULAR_URL), (FONT_BOLD_PATH, FONT_BOLD_URL)):
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
            except Exception:
                pass


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def draw_centered_text(draw, cx, y, text, font, fill):
    """Dessine `text` parfaitement centré horizontalement sur cx (compense
    le petit décalage de calage gauche que certaines polices introduisent)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2 - bbox[0], y), text, font=font, fill=fill)


# ============================================================
# RÉCUPÉRATION DES DONNÉES
# ============================================================
def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset"
        "&hourly=temperature_2m,apparent_temperature,weathercode,relativehumidity_2m,windspeed_10m"
        "&timezone=auto"
    )
    headers = {"User-Agent": "KindleDashboard-GitHubActions/4.0"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


# ============================================================
# ICÔNES MÉTÉO — silhouettes pleines (lisibles en niveaux de gris)
# ============================================================
def _cloud_puffs(cx, cy, r):
    return [
        (cx - r * 0.55, cy + r * 0.15, r * 0.55),
        (cx - r * 0.05, cy - r * 0.20, r * 0.68),
        (cx + r * 0.55, cy + r * 0.10, r * 0.52),
    ]


def draw_cloud_shape(draw, cx, cy, r, fill=BLACK):
    for x, y, rr in _cloud_puffs(cx, cy, r):
        draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)
    draw.rounded_rectangle(
        [cx - r * 0.95, cy, cx + r * 0.95, cy + r * 0.55], radius=r * 0.3, fill=fill
    )


def draw_sun(draw, cx, cy, r, fill=INK):
    w = max(2, round(r * 0.16))
    for i in range(8):
        a = i * math.pi / 4
        x1, y1 = cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35
        x2, y2 = cx + math.cos(a) * r * 1.9, cy + math.sin(a) * r * 1.9
        draw.line([x1, y1, x2, y2], fill=fill, width=w)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def draw_icon(draw, code, cx, cy, r):
    if code == 0:
        draw_sun(draw, cx, cy, r)
    elif code == 1:
        # Plutôt ensoleillé : grand soleil, petit nuage discret
        draw_sun(draw, cx - r * 0.12, cy - r * 0.08, r * 0.85, fill=GRAY_DARK)
        draw_cloud_shape(draw, cx + r * 0.35, cy + r * 0.42, r * 0.55)
    elif code == 2:
        # Partiellement nuageux : soleil et nuage à parts égales
        draw_sun(draw, cx - r * 0.28, cy - r * 0.22, r * 0.62, fill=GRAY_DARK)
        draw_cloud_shape(draw, cx + r * 0.2, cy + r * 0.28, r * 0.78)
    elif code == 3:
        # Ciel couvert : nuage seul, plus large
        draw_cloud_shape(draw, cx, cy, r)
    elif code in (45, 48):
        for i in range(4):
            y = cy - r * 0.5 + i * r * 0.35
            w = r * (1.3 - i * 0.12)
            draw.rounded_rectangle([cx - w, y - r * 0.06, cx + w, y + r * 0.06],
                                    radius=r * 0.06, fill=GRAY_DARK)
    elif code in (51, 53, 55, 56, 57):
        draw_cloud_shape(draw, cx, cy - r * 0.15, r * 0.85)
        for i in range(3):
            x = cx - r * 0.5 + i * r * 0.5
            draw.line([x, cy + r * 0.5, x - r * 0.15, cy + r * 0.85],
                       fill=GRAY_DARK, width=max(2, round(r * 0.12)))
    elif code in (61, 63, 65, 66, 67, 80, 81, 82):
        draw_cloud_shape(draw, cx, cy - r * 0.15, r * 0.85)
        for i in range(3):
            x = cx - r * 0.5 + i * r * 0.5
            draw.line([x, cy + r * 0.5, x - r * 0.2, cy + r * 1.05],
                       fill=BLACK, width=max(3, round(r * 0.15)))
    elif code in (71, 73, 75, 77, 85, 86):
        draw_cloud_shape(draw, cx, cy - r * 0.15, r * 0.85)
        for i in range(3):
            x = cx - r * 0.5 + i * r * 0.5
            y = cy + r * 0.75
            rr = r * 0.09
            draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=GRAY_DARK)
    elif code in (95, 96, 99):
        draw_cloud_shape(draw, cx, cy - r * 0.2, r * 0.85)
        draw.polygon([
            (cx + r * 0.1, cy + r * 0.35), (cx - r * 0.25, cy + r * 0.95),
            (cx + r * 0.05, cy + r * 0.95), (cx - r * 0.2, cy + r * 1.5),
            (cx + r * 0.4, cy + r * 0.7), (cx + r * 0.1, cy + r * 0.7),
        ], fill=BLACK)
    else:
        draw_sun(draw, cx, cy, r)


def draw_droplet(draw, cx, cy, r, fill=INK):
    draw.polygon([(cx, cy - r * 1.3), (cx - r * 0.85, cy + r * 0.25),
                  (cx + r * 0.85, cy + r * 0.25)], fill=fill)
    draw.ellipse([cx - r * 0.85, cy - r * 0.35, cx + r * 0.85, cy + r * 1.35], fill=fill)


def draw_wind_icon(draw, cx, cy, r, fill=INK):
    for i, wf in enumerate((1.4, 0.85)):
        y = cy - r * 0.35 + i * r * 0.7
        x0, x1 = cx - r * wf * 0.65, cx + r * wf * 0.65
        draw.line([x0, y, x1, y], fill=fill, width=max(2, round(r * 0.22)))
        d = r * 0.28
        draw.polygon([(x1, y - d), (x1, y + d), (x1 + d, y)], fill=fill)


def draw_sun_horizon(draw, cx, cy, r, rising, fill=INK):
    draw.line([cx - r * 1.3, cy, cx + r * 1.3, cy], fill=fill, width=max(2, round(r * 0.12)))
    draw.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=fill)
    ay = cy - r * 1.15 if rising else cy - r * 0.35
    ady = -r * 0.5 if rising else r * 0.5
    draw.line([cx, ay, cx, ay + ady], fill=fill, width=max(2, round(r * 0.14)))
    tip = ay + ady
    d = r * 0.22
    if rising:
        draw.polygon([(cx - d, tip + d), (cx + d, tip + d), (cx, tip - d)], fill=fill)
    else:
        draw.polygon([(cx - d, tip - d), (cx + d, tip - d), (cx, tip + d)], fill=fill)


WEATHER_LABELS = {
    0: "Ciel dégagé", 1: "Plutôt ensoleillé", 2: "Partiellement nuageux",
    3: "Ciel couvert", 45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine", 55: "Bruine soutenue",
    56: "Bruine verglaçante", 57: "Bruine verglaçante",
    61: "Pluie faible", 63: "Pluie", 65: "Pluie forte",
    66: "Pluie verglaçante", 67: "Pluie verglaçante",
    71: "Neige faible", 73: "Neige", 75: "Neige forte", 77: "Grains de neige",
    80: "Averses faibles", 81: "Averses", 82: "Averses violentes",
    85: "Averses de neige", 86: "Averses de neige",
    95: "Orage", 96: "Orage avec grêle", 99: "Orage violent",
}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def weather_label(code):
    return WEATHER_LABELS.get(code, "Temps variable")


def french_date_parts(now):
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    return jours[now.weekday()], f"{now.day} {mois[now.month - 1]} {now.year}"


def hhmm(iso_str):
    return iso_str.split("T")[1]


# ============================================================
# CONSTRUCTION DE L'IMAGE
# ============================================================
def create_image(data, out_path="meteo.png"):
    ensure_fonts()
    img = Image.new("L", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    # "Maintenant" dans le fuseau horaire du lieu affiché (celui que l'API
    # a résolu via timezone=auto), pas celui du serveur qui exécute ce
    # script (le runner GitHub Actions tourne en UTC) : sinon la date du
    # jour et l'heure du pied de page seraient fausses pour l'utilisateur.
    now_local = datetime.now(ZoneInfo(data.get("timezone", "UTC")))

    f_date = load_font(FONT_BOLD_PATH, S(34))
    f_location = load_font(FONT_BOLD_PATH, S(26))
    f_temp_huge = load_font(FONT_BOLD_PATH, S(100))
    f_desc = load_font(FONT_REGULAR_PATH, S(30))
    f_minmax = load_font(FONT_BOLD_PATH, S(22))
    f_panel_label = load_font(FONT_REGULAR_PATH, S(20))
    f_panel_value = load_font(FONT_BOLD_PATH, S(24))
    f_section = load_font(FONT_BOLD_PATH, S(24))
    f_axis = load_font(FONT_REGULAR_PATH, S(18))
    f_row_hour = load_font(FONT_BOLD_PATH, S(26))
    f_row_temp = load_font(FONT_BOLD_PATH, S(26))
    f_row_small = load_font(FONT_REGULAR_PATH, S(19))
    f_alert = load_font(FONT_BOLD_PATH, S(24))
    f_footer = load_font(FONT_REGULAR_PATH, S(16))

    M = S(50)  # marge latérale

    # ---------- Préparation des données ----------
    daily_code = data["daily"]["weathercode"][0]
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    t_mean = round((t_max + t_min) / 2)
    sunrise = data["daily"].get("sunrise", [None])[0]
    sunset = data["daily"].get("sunset", [None])[0]

    hourly_times = data["hourly"]["time"]
    today_str = now_local.strftime("%Y-%m-%d")
    day_idx = [i for i, t in enumerate(hourly_times) if t.startswith(today_str)]
    if not day_idx:
        day_idx = list(range(min(24, len(hourly_times))))
    # premier point du lendemain (00h), pour boucler la courbe/le tableau jusqu'à minuit
    next_idx = day_idx[-1] + 1 if day_idx[-1] + 1 < len(hourly_times) else None

    def hour_of(i):
        return int(hourly_times[i].split("T")[1][:2])

    hour_to_index = {hour_of(i): i for i in day_idx}

    codes_today = [data["hourly"]["weathercode"][i] for i in day_idx]
    humid_today = [data["hourly"]["relativehumidity_2m"][i] for i in day_idx]
    wind_today = [data["hourly"]["windspeed_10m"][i] for i in day_idx]
    avg_humid = round(sum(humid_today) / len(humid_today)) if humid_today else 0
    avg_wind = round(sum(wind_today) / len(wind_today)) if wind_today else 0
    has_rain = any(c in RAIN_CODES for c in codes_today)

    # ============== EN-TÊTE ==============
    # Centré : l'horloge et la batterie de la liseuse recouvrent les coins,
    # on garde donc le centre de l'écran libre de toute info utile.
    jour, date_str = french_date_parts(now_local)
    top_y = S(56)
    date_line = f"{jour} {date_str}"
    draw_centered_text(draw, WIDTH // 2, top_y, date_line, f_date, INK)
    loc_line = LOCATION_NAME.upper()
    draw_centered_text(draw, WIDTH // 2, top_y + S(48), loc_line, f_location, GRAY_DARK)
    rule_y = top_y + S(96)
    draw.line([(M, rule_y), (WIDTH - M, rule_y)], fill=GRAY_LIGHT, width=S(2))

    # ============== BLOC PRINCIPAL (icône + température + panneau) ==============
    # La carte est divisée en deux zones séparées par un fin séparateur
    # vertical : à gauche l'icône + la température (centrées comme un seul
    # groupe, quelle que soit la longueur de la description), à droite le
    # panneau lever/coucher/humidité/vent. Cela évite le "trou" visuel qui
    # apparaissait entre les deux blocs avec un positionnement à offsets fixes.
    hero_top, hero_h = rule_y + S(18), S(220)
    panel_w = S(340)
    zone_pad = S(20)  # marge interne de chaque côté du séparateur
    draw.rounded_rectangle([M, hero_top, WIDTH - M, hero_top + hero_h],
                            radius=S(22), fill=GRAY_PALE)

    divider_x = (WIDTH - M) - panel_w - 2 * zone_pad
    draw.line([(divider_x, hero_top + S(24)), (divider_x, hero_top + hero_h - S(24))],
              fill=GRAY_LIGHT, width=S(2))

    # -- icône (ancrée à gauche) + température + min/max à droite du
    #    nombre + description en dessous --
    icon_r = S(72)
    gap_icon_text = S(38)
    desc = weather_label(daily_code)
    temp_str = f"{t_mean}°"
    left_zone_left = M + zone_pad

    icon_cx, icon_cy = left_zone_left + icon_r, hero_top + hero_h // 2
    draw_icon(draw, daily_code, icon_cx, icon_cy, icon_r)

    text_x = left_zone_left + icon_r * 2 + gap_icon_text
    temp_y = hero_top + S(28)
    draw.text((text_x, temp_y), temp_str, font=f_temp_huge, fill=INK)

    # Min/max empilés et centrés verticalement sur le nombre de
    # température (calculé à partir des boîtes englobantes réelles, pas
    # d'un décalage fixe, pour un alignement propre quelle que soit la
    # police).
    temp_bbox = draw.textbbox((0, 0), temp_str, font=f_temp_huge)
    temp_center_y = temp_y + (temp_bbox[1] + temp_bbox[3]) / 2
    max_str, min_str = f"Max {t_max}°", f"Min {t_min}°"
    max_bbox = draw.textbbox((0, 0), max_str, font=f_minmax)
    min_bbox = draw.textbbox((0, 0), min_str, font=f_minmax)
    max_h, min_h = max_bbox[3] - max_bbox[1], min_bbox[3] - min_bbox[1]
    line_gap = S(10)
    stack_top = temp_center_y - (max_h + line_gap + min_h) / 2
    minmax_x = text_x + text_w(draw, temp_str, f_temp_huge) + S(28)
    draw.text((minmax_x, stack_top - max_bbox[1]), max_str, font=f_minmax, fill=INK)
    draw.text((minmax_x, stack_top + max_h + line_gap - min_bbox[1]), min_str,
              font=f_minmax, fill=GRAY_DARK)

    draw.text((text_x, hero_top + S(150)), desc, font=f_desc, fill=INK)

    # -- panneau lever/coucher + humidité/vent, à droite du séparateur --
    # Grille à positions fixes (icône et texte à la même abscisse pour les
    # deux lignes d'une même colonne) plutôt qu'un centrage par cellule :
    # sinon des libellés de largeurs différentes ("Lever" vs "Humidité")
    # décalent l'icône d'une ligne à l'autre et cassent l'alignement
    # vertical entre les 4 éléments.
    panel_shift_x, panel_shift_y = S(8), S(20)  # recentrage fin : un peu à droite et vers le bas
    region_left = divider_x + zone_pad + panel_shift_x
    region_right = region_left + panel_w
    col_w = panel_w // 2
    cell_h = S(64)
    content_h = cell_h * 2
    panel_top = hero_top + (hero_h - content_h) // 2 + panel_shift_y
    mini_icon_r = S(16)  # même taille pour les 4 icônes du panneau
    icon_d = mini_icon_r * 2
    icon_inset = S(14)   # même abscisse d'icône pour les 2 lignes d'une colonne
    gap = S(12)
    cells = [
        ("Lever", hhmm(sunrise) if sunrise else "—", "sunrise"),
        ("Coucher", hhmm(sunset) if sunset else "—", "sunset"),
        ("Humidité", f"{avg_humid} %", "humidity"),
        ("Vent", f"{avg_wind} km/h", "wind"),
    ]
    for i, (label, value, kind) in enumerate(cells):
        row, col = divmod(i, 2)
        col_left = region_left + col * col_w
        cy = panel_top + row * cell_h
        icon_cx2, icon_cy2 = col_left + icon_inset + mini_icon_r, cy + S(20)
        text_x2 = col_left + icon_inset + icon_d + gap
        if kind == "sunrise":
            draw_sun_horizon(draw, icon_cx2, icon_cy2, mini_icon_r, rising=True)
        elif kind == "sunset":
            draw_sun_horizon(draw, icon_cx2, icon_cy2, mini_icon_r, rising=False)
        elif kind == "humidity":
            draw_droplet(draw, icon_cx2, icon_cy2, mini_icon_r)
        else:
            draw_wind_icon(draw, icon_cx2, icon_cy2, mini_icon_r)
        draw.text((text_x2, cy + S(2)), label, font=f_panel_label, fill=GRAY_DARK)
        draw.text((text_x2, cy + S(24)), value, font=f_panel_value, fill=INK)

    # ============== BANDEAU ALERTE ==============
    alert_top = hero_top + hero_h + S(12)
    alert_h = S(46)
    if has_rain:
        alert_text = "Pluie prévue dans la journée"
    else:
        alert_text = "Aucune précipitation prévue aujourd'hui"
    draw.rounded_rectangle([M, alert_top, WIDTH - M, alert_top + alert_h],
                            radius=alert_h // 2, outline=INK, width=S(3))
    # Centrage vertical calculé à partir de la boîte englobante réelle du
    # texte (et non d'un décalage fixe) : la hauteur de ligne d'une police
    # inclut une marge au-dessus du texte qui, si on l'ignore, fait
    # paraître le texte trop bas dans le bandeau.
    alert_bbox = draw.textbbox((0, 0), alert_text, font=f_alert)
    alert_text_y = alert_top + (alert_h - (alert_bbox[3] - alert_bbox[1])) // 2 - alert_bbox[1]
    draw_centered_text(draw, WIDTH // 2, alert_text_y, alert_text, f_alert, INK)

    # ============== COURBE DE TEMPÉRATURE (00h → 00h) ==============
    sep1_y = alert_top + alert_h + S(22)
    draw.line([(M, sep1_y), (WIDTH - M, sep1_y)], fill=GRAY_LIGHT, width=S(2))

    gx0, gx1 = M + S(50), WIDTH - M - S(10)
    gy0, gy1 = sep1_y + S(30), sep1_y + S(366)

    # Points de la courbe positionnés par heure réelle (0 à 24) afin que le
    # tracé couvre toute la journée, du premier point (00h) jusqu'à minuit.
    chart_idx = list(day_idx)
    chart_frac = [hour_of(i) / 24.0 for i in chart_idx]
    if next_idx is not None:
        chart_idx.append(next_idx)
        chart_frac.append(1.0)
    chart_temps = [data["hourly"]["temperature_2m"][i] for i in chart_idx]

    if chart_temps:
        tmin_c, tmax_c = min(chart_temps), max(chart_temps)
        rng = max(tmax_c - tmin_c, 1)

        for frac in (0, 0.5, 1):
            y = gy1 - frac * (gy1 - gy0)
            draw.line([gx0, y, gx1, y], fill=GRAY_LIGHT, width=S(1))
        draw.text((M, gy0 - S(12)), f"{round(tmax_c)}°", font=f_axis, fill=GRAY_DARK)
        draw.text((M, gy1 - S(12)), f"{round(tmin_c)}°", font=f_axis, fill=GRAY_DARK)

        points = [
            (gx0 + f * (gx1 - gx0), gy1 - (t - tmin_c) / rng * (gy1 - gy0))
            for f, t in zip(chart_frac, chart_temps)
        ]

        area = [(gx0, gy1)] + points + [(gx1, gy1)]
        draw.polygon(area, fill=GRAY_PALE)
        draw.line(points, fill=INK, width=S(4), joint="curve")

        # Repères toutes les 3h + point final à 00h (minuit)
        tick_hours = [0, 3, 6, 9, 12, 15, 18, 21]
        for th in tick_hours:
            if th not in hour_to_index:
                continue
            f = th / 24.0
            x = gx0 + f * (gx1 - gx0)
            t = data["hourly"]["temperature_2m"][hour_to_index[th]]
            y = gy1 - (t - tmin_c) / rng * (gy1 - gy0)
            draw.ellipse([x - S(4), y - S(4), x + S(4), y + S(4)], fill=INK)
            label = f"{th:02d}:00"
            lw = text_w(draw, label, f_axis)
            draw.text((x - lw / 2, gy1 + S(12)), label, font=f_axis, fill=GRAY_DARK)
        if next_idx is not None:
            x, y = points[-1]
            draw.ellipse([x - S(4), y - S(4), x + S(4), y + S(4)], fill=INK)
            label = "00:00"
            lw = text_w(draw, label, f_axis)
            draw.text((min(x - lw / 2, gx1 - lw), gy1 + S(12)), label, font=f_axis, fill=GRAY_DARK)

    # ============== TABLEAU DÉTAIL HORAIRE (toutes les 2h, matin | après-midi) ==============
    # Deux colonnes côte à côte pour tenir 12 points (2h à 22h) sans
    # allonger le tableau : matin à gauche (2h→12h), après-midi/soir à
    # droite (14h→minuit). Pas de "ressenti" ici (manque de place sur une
    # demi-largeur) ; humidité + vent sont groupés vers la droite de
    # chaque mini-colonne.
    sep2_y = gy1 + S(36)
    draw.line([(M, sep2_y), (WIDTH - M, sep2_y)], fill=GRAY_LIGHT, width=S(2))

    row_top = sep2_y + S(18)
    row_h = S(66)

    col_gap = S(40)
    col_w = (WIDTH - 2 * M - col_gap) // 2
    col_lefts = [M, M + col_w + col_gap]
    hour_columns = [[2, 4, 6, 8, 10, 12], [14, 16, 18, 20, 22, 0]]
    n_rows = len(hour_columns[0])

    def resolve_hour_index(h):
        # 0 = minuit du lendemain (fin de la colonne après-midi/soir).
        return next_idx if h == 0 else hour_to_index.get(h)

    for n in range(n_rows):
        y = row_top + n * row_h
        if n % 2 == 1:
            draw.rectangle([M, y, WIDTH - M, y + row_h], fill=GRAY_PALE)

        for col_left, hours in zip(col_lefts, hour_columns):
            abs_i = resolve_hour_index(hours[n])
            if abs_i is None:
                continue
            hour_str = "00:00" if hours[n] == 0 else f"{hours[n]:02d}:00"
            temp = round(data["hourly"]["temperature_2m"][abs_i])
            code = data["hourly"]["weathercode"][abs_i]
            humidity = data["hourly"]["relativehumidity_2m"][abs_i]
            wind = round(data["hourly"]["windspeed_10m"][abs_i])

            # Icône, heure puis température, chacune positionnée après la
            # largeur réelle de la précédente (une largeur fixe pour
            # "02:00" fait se chevaucher heure et température : leur
            # police est assez grande pour que 5 caractères dépassent un
            # écart de ~66px).
            icon_r = S(15)
            icon_cx = col_left + S(16)
            draw_icon(draw, code, icon_cx, y + row_h // 2, icon_r)

            hour_x = icon_cx + icon_r + S(12)
            draw.text((hour_x, y + S(21)), hour_str, font=f_row_hour, fill=INK)

            temp_x = hour_x + text_w(draw, hour_str, f_row_hour) + S(16)
            draw.text((temp_x, y + S(21)), f"{temp}°C", font=f_row_temp, fill=INK)

            # Cluster humidité + vent, ancré à droite de la mini-colonne
            # (largeurs de texte variables -> positions calculées, pas
            # de décalages fixes, pour ne jamais se chevaucher).
            wind_str = f"{wind} km/h"
            wind_value_x = col_left + col_w - text_w(draw, wind_str, f_row_small)
            wind_icon_cx = wind_value_x - S(20)
            humidity_str = f"{humidity} %"
            humidity_value_x = wind_icon_cx - S(24) - text_w(draw, humidity_str, f_row_small)
            droplet_cx = humidity_value_x - S(18)

            draw_droplet(draw, droplet_cx, y + row_h // 2, S(11), fill=GRAY_DARK)
            draw.text((humidity_value_x, y + S(23)), humidity_str, font=f_row_small, fill=GRAY_DARK)
            draw_wind_icon(draw, wind_icon_cx, y + row_h // 2, S(13), fill=GRAY_DARK)
            draw.text((wind_value_x, y + S(23)), wind_str, font=f_row_small, fill=GRAY_DARK)

    # Séparateur vertical entre les deux demi-journées.
    col_div_x = M + col_w + col_gap // 2
    draw.line([(col_div_x, row_top + S(6)), (col_div_x, row_top + n_rows * row_h - S(6))],
              fill=GRAY_LIGHT, width=S(2))

    # ============== PIED DE PAGE ==============
    footer_y = row_top + n_rows * row_h + S(14)
    footer = f"Mis à jour le {now_local.strftime('%d/%m/%Y à %H:%M')}"
    draw_centered_text(draw, WIDTH // 2, footer_y, footer, f_footer, GRAY_MID)

    # ---------- Réduction finale (anticrénelage) ----------
    final = img.resize((BASE_W, BASE_H), Image.LANCZOS)
    final.save(out_path)
    return out_path


def main():
    print(f"Récupération des prévisions météo pour {LOCATION_NAME}...")
    data = get_weather()
    print("Génération de l'image du dashboard...")
    path = create_image(data)
    print(f"Dashboard généré avec succès : {path}")


if __name__ == "__main__":
    main()

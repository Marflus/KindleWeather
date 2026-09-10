"""
Dashboard météo pour liseuse Kindle (écran e-ink, niveaux de gris)
Ville : Varsovie — Source des données : Open-Meteo

Idée reprise du script d'origine :
  - en-tête (lieu + date)
  - bloc météo du jour (icône + température + description)
  - alerte pluie / temps calme
  - courbe de température sur 24h
  - tableau détaillé par tranche horaire

Ce qui change :
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

import requests
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIGURATION
# ============================================================
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
    return draw.textbbox((0, 0), text, font=font)[2]


# ============================================================
# RÉCUPÉRATION DES DONNÉES
# ============================================================
def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset"
        "&hourly=temperature_2m,weathercode,relativehumidity_2m,windspeed_10m"
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


def french_date_parts():
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    now = datetime.now()
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

    f_date = load_font(FONT_BOLD_PATH, S(34))
    f_location = load_font(FONT_BOLD_PATH, S(26))
    f_temp_huge = load_font(FONT_BOLD_PATH, S(100))
    f_desc = load_font(FONT_REGULAR_PATH, S(30))
    f_minmax = load_font(FONT_BOLD_PATH, S(22))
    f_panel_label = load_font(FONT_REGULAR_PATH, S(19))
    f_panel_value = load_font(FONT_BOLD_PATH, S(24))
    f_section = load_font(FONT_BOLD_PATH, S(24))
    f_axis = load_font(FONT_REGULAR_PATH, S(18))
    f_row_hour = load_font(FONT_BOLD_PATH, S(26))
    f_row_temp = load_font(FONT_BOLD_PATH, S(26))
    f_row_small = load_font(FONT_REGULAR_PATH, S(18))
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
    today_str = datetime.now().strftime("%Y-%m-%d")
    day_idx = [i for i, t in enumerate(hourly_times) if t.startswith(today_str)]
    if not day_idx:
        day_idx = list(range(min(24, len(hourly_times))))

    temps = [data["hourly"]["temperature_2m"][i] for i in day_idx]
    codes_today = [data["hourly"]["weathercode"][i] for i in day_idx]
    humid_today = [data["hourly"]["relativehumidity_2m"][i] for i in day_idx]
    wind_today = [data["hourly"]["windspeed_10m"][i] for i in day_idx]
    avg_humid = round(sum(humid_today) / len(humid_today)) if humid_today else 0
    avg_wind = round(sum(wind_today) / len(wind_today)) if wind_today else 0
    has_rain = any(c in RAIN_CODES for c in codes_today)

    current_hour = datetime.now().hour
    now_pos = current_hour if current_hour < len(day_idx) else None

    # ============== EN-TÊTE ==============
    jour, date_str = french_date_parts()
    draw.text((M, S(38)), f"{jour} {date_str}", font=f_date, fill=INK)
    loc_w = text_w(draw, LOCATION_NAME.upper(), f_location)
    draw.text((WIDTH - M - loc_w, S(44)), LOCATION_NAME.upper(), font=f_location, fill=GRAY_DARK)
    draw.line([(M, S(96)), (WIDTH - M, S(96))], fill=GRAY_LIGHT, width=S(2))

    # ============== BLOC PRINCIPAL (icône + température + panneau) ==============
    hero_top, hero_h = S(126), S(230)
    panel_w = S(340)
    draw.rounded_rectangle([M, hero_top, WIDTH - M, hero_top + hero_h],
                            radius=S(22), fill=GRAY_PALE)

    draw_icon(draw, daily_code, M + S(110), hero_top + hero_h // 2, S(72))
    temp_x = M + S(210)
    draw.text((temp_x, hero_top + S(28)), f"{t_mean}°", font=f_temp_huge, fill=INK)
    tw = text_w(draw, f"{t_mean}°", f_temp_huge)
    desc = weather_label(daily_code)
    draw.text((temp_x, hero_top + S(150)), desc, font=f_desc, fill=INK)
    draw.text((temp_x, hero_top + S(190)),
               f"Min {t_min}°   ·   Max {t_max}°", font=f_minmax, fill=GRAY_DARK)

    # -- panneau lever/coucher + humidité/vent, à droite --
    panel_x0 = WIDTH - M - panel_w
    px, py = panel_x0 + S(18), hero_top + S(24)
    cell_h = S(88)
    cells = [
        ("Lever", hhmm(sunrise) if sunrise else "—", "sunrise"),
        ("Coucher", hhmm(sunset) if sunset else "—", "sunset"),
        ("Humidité", f"{avg_humid} %", "humidity"),
        ("Vent", f"{avg_wind} km/h", "wind"),
    ]
    for i, (label, value, kind) in enumerate(cells):
        row, col = divmod(i, 2)
        cx = px + col * (panel_w // 2)
        cy = py + row * cell_h
        icon_cx, icon_cy = cx + S(20), cy + S(24)
        if kind == "sunrise":
            draw_sun_horizon(draw, icon_cx, icon_cy, S(15), rising=True)
        elif kind == "sunset":
            draw_sun_horizon(draw, icon_cx, icon_cy, S(15), rising=False)
        elif kind == "humidity":
            draw_droplet(draw, icon_cx, icon_cy, S(14))
        else:
            draw_wind_icon(draw, icon_cx, icon_cy, S(16))
        draw.text((cx + S(44), cy + S(2)), label, font=f_panel_label, fill=GRAY_DARK)
        draw.text((cx + S(44), cy + S(24)), value, font=f_panel_value, fill=INK)

    # ============== BANDEAU ALERTE ==============
    alert_top = hero_top + hero_h + S(16)
    alert_h = S(48)
    if has_rain:
        alert_text = "Pluie prévue dans la journée"
    else:
        alert_text = "Aucune précipitation prévue aujourd'hui"
    draw.rounded_rectangle([M, alert_top, WIDTH - M, alert_top + alert_h],
                            radius=alert_h // 2, outline=INK, width=S(3))
    aw = text_w(draw, alert_text, f_alert)
    draw.text(((WIDTH - aw) // 2, alert_top + S(14)), alert_text, font=f_alert, fill=INK)

    # ============== COURBE DE TEMPÉRATURE 24H ==============
    chart_title_y = alert_top + alert_h + S(24)
    draw.text((M, chart_title_y), "TEMPÉRATURES — 24 HEURES", font=f_section, fill=INK)

    gx0, gx1 = M + S(50), WIDTH - M - S(10)
    gy0, gy1 = chart_title_y + S(44), chart_title_y + S(268)

    if temps:
        tmin_c, tmax_c = min(temps), max(temps)
        rng = max(tmax_c - tmin_c, 1)

        for frac in (0, 0.5, 1):
            y = gy1 - frac * (gy1 - gy0)
            draw.line([gx0, y, gx1, y], fill=GRAY_LIGHT, width=S(1))
        draw.text((M, gy0 - S(12)), f"{round(tmax_c)}°", font=f_axis, fill=GRAY_DARK)
        draw.text((M, gy1 - S(12)), f"{round(tmin_c)}°", font=f_axis, fill=GRAY_DARK)

        step = (gx1 - gx0) / max(len(temps) - 1, 1)
        points = []
        for i, t in enumerate(temps):
            px_ = gx0 + i * step
            py_ = gy1 - (t - tmin_c) / rng * (gy1 - gy0)
            points.append((px_, py_))

        area = [(gx0, gy1)] + points + [(gx1, gy1)]
        draw.polygon(area, fill=GRAY_PALE)
        draw.line(points, fill=INK, width=S(4), joint="curve")

        for i, (px_, py_) in enumerate(points):
            if i % 3 == 0:
                draw.ellipse([px_ - S(4), py_ - S(4), px_ + S(4), py_ + S(4)], fill=INK)
                label = hhmm(hourly_times[day_idx[i]])[:5]
                lw = text_w(draw, label, f_axis)
                draw.text((px_ - lw / 2, gy1 + S(12)), label, font=f_axis, fill=GRAY_DARK)

        if now_pos is not None and now_pos < len(points):
            nx, ny = points[now_pos]
            for y in range(int(gy0), int(gy1), S(14)):
                draw.line([nx, y, nx, min(y + S(7), gy1)], fill=GRAY_DARK, width=S(2))
            draw.ellipse([nx - S(7), ny - S(7), nx + S(7), ny + S(7)], outline=INK, width=S(3))
            label = "maintenant"
            lw = text_w(draw, label, f_axis)
            label_x = min(nx + S(10), gx1 - lw)
            draw.text((label_x, gy0 - S(4)), label, font=f_axis, fill=GRAY_DARK)

    # ============== TABLEAU DÉTAIL HORAIRE ==============
    table_title_y = gy1 + S(44)
    draw.text((M, table_title_y), "DÉTAIL PAR TRANCHE HORAIRE", font=f_section, fill=INK)

    row_top = table_title_y + S(36)
    row_h = S(72)
    hours_to_show = [0, 3, 6, 9, 12, 15, 18, 21]

    for n, h in enumerate(hours_to_show):
        if h >= len(day_idx):
            continue
        abs_i = day_idx[h]
        hour_str = hhmm(hourly_times[abs_i])[:5]
        temp = round(data["hourly"]["temperature_2m"][abs_i])
        code = data["hourly"]["weathercode"][abs_i]
        humidity = data["hourly"]["relativehumidity_2m"][abs_i]
        wind = round(data["hourly"]["windspeed_10m"][abs_i])

        y = row_top + n * row_h
        if n % 2 == 1:
            draw.rectangle([M, y, WIDTH - M, y + row_h], fill=GRAY_PALE)
        if h == now_pos:
            draw.rectangle([M, y, S(6) + M, y + row_h], fill=INK)

        icon_cx = M + S(46)
        draw_icon(draw, code, icon_cx, y + row_h // 2, S(22))

        draw.text((M + S(100), y + S(22)), hour_str, font=f_row_hour, fill=INK)
        draw.text((M + S(210), y + S(22)), f"{temp}°C", font=f_row_temp, fill=INK)

        draw_droplet(draw, M + S(400), y + row_h // 2, S(11), fill=GRAY_DARK)
        draw.text((M + S(420), y + S(24)), f"{humidity} %", font=f_row_small, fill=GRAY_DARK)

        draw_wind_icon(draw, M + S(560), y + row_h // 2, S(13), fill=GRAY_DARK)
        draw.text((M + S(590), y + S(24)), f"{wind} km/h", font=f_row_small, fill=GRAY_DARK)

    # ============== PIED DE PAGE ==============
    footer_y = row_top + len(hours_to_show) * row_h + S(14)
    footer = f"Mis à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — données Open-Meteo"
    fw = text_w(draw, footer, f_footer)
    draw.text(((WIDTH - fw) // 2, footer_y), footer, font=f_footer, fill=GRAY_MID)

    # ---------- Réduction finale (anticrénelage) ----------
    final = img.resize((BASE_W, BASE_H), Image.LANCZOS)
    final.save(out_path)
    return out_path


def main():
    data = get_weather()
    path = create_image(data)
    print(f"Dashboard généré avec succès : {path}")


if __name__ == "__main__":
    main()

import os
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests

# --- CONFIGURATION (Varsovie) ---
LATITUDE = 52.2297
LONGITUDE = 21.0122
LOCATION_NAME = "Varsovie"

WIDTH, HEIGHT = 1072, 1448

# Téléchargement de la police Roboto
FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"

if not os.path.exists("Roboto-Regular.ttf"):
    urllib.request.urlretrieve(FONT_REGULAR_URL, "Roboto-Regular.ttf")
if not os.path.exists("Roboto-Bold.ttf"):
    urllib.request.urlretrieve(FONT_BOLD_URL, "Roboto-Bold.ttf")

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&daily=weathercode,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,weathercode,relativehumidity_2m,windspeed_10m&timezone=auto"
    headers = {"User-Agent": "KindleDashboard-GitHubActions/3.0"}
    response = requests.get(url, headers=headers)
    return response.json()

def draw_sun(draw, x, y, size):
    # Dessine un soleil minimaliste
    r = size // 3
    draw.ellipse([x - r, y - r, x + r, y + r], outline=0, width=3)
    for i in range(8):
        angle = i * 3.14159 / 4
        import math
        x1 = x + int((r + 4) * math.cos(angle))
        y1 = y + int((r + 4) * math.sin(angle))
        x2 = x + int((r + 12) * math.cos(angle))
        y2 = y + int((r + 12) * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=0, width=3)

def draw_cloud(draw, x, y, size):
    # Dessine un nuage élégant
    draw.arc([x - size//2, y - size//4, x, y + size//4], 180, 360, fill=0, width=3)
    draw.arc([x - size//3, y - size//2, x + size//3, y], 180, 360, fill=0, width=3)
    draw.arc([x, y - size//4, x + size//2, y + size//4], 180, 360, fill=0, width=3)
    draw.line([x - size//2, y + size//4, x + size//2, y + size//4], fill=0, width=3)

def draw_rain(draw, x, y, size):
    draw_cloud(draw, x, y - 5, size)
    # Petites gouttes
    for i in range(3):
        gx = x - size//3 + i * (size//3)
        draw.line([gx, y + size//4 + 5, gx - 4, y + size//4 + 15], fill=0, width=3)

def draw_snow(draw, x, y, size):
    draw_cloud(draw, x, y - 5, size)
    for i in range(3):
        sx = x - size//3 + i * (size//3)
        draw.ellipse([sx-2, y + size//4 + 5, sx+2, y + size//4 + 9], fill=0)

def draw_weather_icon(draw, code, x, y, size):
    if code == 0:
        draw_sun(draw, x, y, size)
    elif code in [1, 2, 3, 45, 48]:
        draw_cloud(draw, x, y, size)
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        draw_rain(draw, x, y, size)
    elif code in [71, 73, 75, 77, 85, 86]:
        draw_snow(draw, x, y, size)
    else:
        draw_sun(draw, x, y, size)

def weather_label(code):
    if code == 0: return "Grand soleil"
    elif code in [1, 2, 3, 45, 48]: return "Ciel nuageux"
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return "Pluie prévue"
    elif code in [71, 73, 75, 77, 85, 86]: return "Chutes de neige"
    else: return "Temps variable"

def create_image():
    data = get_weather()
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("Roboto-Bold.ttf", 60)
    font_huge = ImageFont.truetype("Roboto-Bold.ttf", 100)
    font_large = ImageFont.truetype("Roboto-Bold.ttf", 40)
    font_med = ImageFont.truetype("Roboto-Regular.ttf", 34)
    font_small = ImageFont.truetype("Roboto-Regular.ttf", 26)

    # --- EN-TÊTE ---
    today_str = datetime.now().strftime("%A %d %B %Y").capitalize()
    draw.text((60, 45), LOCATION_NAME.upper(), font=font_title, fill=0)
    draw.text((WIDTH - 420, 65), today_str, font=font_med, fill=0)
    draw.line([(60, 130), (WIDTH - 60, 130)], fill=0, width=4)

    # --- BLOC PRINCIPAL MÉTÉO DU JOUR ---
    daily_code = data["daily"]["weathercode"][0]
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    t_mean = (t_max + t_min) // 2
    w_desc = weather_label(daily_code)

    # Icône météo vectorielle principale
    draw_weather_icon(draw, daily_code, 130, 240, 90)
    
    draw.text((260, 185), f"{t_mean}°C", font=font_huge, fill=0)
    draw.text((260, 295), w_desc, font=font_large, fill=0)
    draw.text((260, 350), f"Min : {t_min}°C   •   Max : {t_max}°C", font=font_med, fill=0)

    # --- BANDEAU ALERTE / INFO UTILE ---
    hourly_codes = data["hourly"]["weathercode"]
    has_rain = any(c in [51, 53, 55, 61, 63, 65, 80, 81, 82] for c in hourly_codes[:24])
    
    if has_rain:
        alert_text = "🌧️  Pluie prévue dans la journée — Pensez à vos précautions"
    else:
        alert_text = "✨  Conditions stables — Aucune intempérie majeure"

    draw.rounded_rectangle([(60, 430), (WIDTH - 60, 510)], radius=15, outline=0, width=3)
    draw.text((90, 452), alert_text, font=font_med, fill=0)

    # --- GRAPHIQUE DE TEMPÉRATURE (00h à 00h) ---
    draw.text((60, 550), "ÉVOLUTION DES TEMPÉRATURES (24H)", font=font_large, fill=0)
    draw.line([(60, 600), (WIDTH - 60, 600)], fill=0, width=2)

    # On prend les 24 heures de la journée en cours (de index 0 à 23 ou l'index actuel)
    # Pour faire un vrai 00h - 00h de la journée :
    current_day_start = 0 # ou l'index de minuit dans hourly['time']
    # Cherchons l'index de 00:00 aujourd'hui
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    hourly_times = data["hourly"]["time"]
    
    day_indices = [i for i, t in enumerate(hourly_times) if t.startswith(today_date_str)]
    if not day_indices:
        day_indices = list(range(24))

    temps = [data["hourly"]["temperature_2m"][i] for i in day_indices[:24]]
    
    # Dessin du mini graphique de température
    gx_start, gx_end = 100, WIDTH - 100
    gy_top, gy_bottom = 630, 780
    
    if temps:
        min_t, max_t = min(temps), max(temps)
        t_range = max(max_t - min_t, 1)
        
        points = []
        step_x = (gx_end - gx_start) / max(len(temps) - 1, 1)
        
        for idx, t in enumerate(temps):
            px = gx_start + int(idx * step_x)
            # Inversé car l'axe Y va vers le bas en informatique
            py = gy_bottom - int((t - min_t) / t_range * (gy_bottom - gy_top))
            points.append((px, py))
            
        # Ligne de tendance
        if len(points) > 1:
            draw.line(points, fill=0, width=4)
            # Petits points sur les heures paires pour les repères
            for idx, (px, py) in enumerate(points):
                if idx % 3 == 0:
                    draw.ellipse([px-4, py-4, px+4, py+4], fill=0)
                    hour_label = hourly_times[day_indices[idx]].split("T")[1]
                    draw.text((px - 18, gy_bottom + 10), hour_label, font=font_small, fill=0)

    # --- TABLEAU DÉTAIL HEURE PAR HEURE (00h à 00h par pas de 3h) ---
    draw.line([(60, 840), (WIDTH - 60, 840)], fill=0, width=2)
    draw.text((60, 870), "DÉTAIL HORAIRE", font=font_large, fill=0)

    y_offset = 930
    row_h = 75

    # Affichage par blocs de 3h de 00h à 21h pour couvrir toute la journée
    hours_to_show = [0, 3, 6, 9, 12, 15, 18, 21]
    
    for h in hours_to_show:
        if h < len(day_indices):
            abs_idx = day_indices[h]
            time_iso = hourly_times[abs_idx]
            hour_str = time_iso.split("T")[1]
            temp = round(data["hourly"]["temperature_2m"][abs_idx])
            code = data["hourly"]["weathercode"][abs_idx]
            humidity = data["hourly"]["relativehumidity_2m"][abs_idx]
            wind = data["hourly"]["windspeed_10m"][abs_idx]

            # Highlight noir si pluie ou neige
            is_bad = code in [51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82]
            bg_color = 0 if is_bad else 255
            txt_color = 255 if is_bad else 0

            if is_bad:
                draw.rounded_rectangle([(60, y_offset - 4), (WIDTH - 60, y_offset + row_h - 8)], radius=10, fill=bg_color)
            else:
                draw.rectangle([(60, y_offset - 4), (WIDTH - 60, y_offset + row_h - 8)], outline=200)

            # Dessin de la petite icône vectorielle à gauche de la ligne
            draw_weather_icon(draw, code, 110, y_offset + 28, 25)

            draw.text((170, y_offset + 12), hour_str, font=font_med, fill=txt_color)
            draw.text((360, y_offset + 12), f"{temp}°C", font=font_med, fill=txt_color)
            draw.text((580, y_offset + 12), f"Humidité : {humidity}%", font=font_small, fill=txt_color)
            draw.text((820, y_offset + 12), f"Vent : {wind} km/h", font=font_small, fill=txt_color)

            y_offset += row_h

    img.save("meteo.png")
    print("Dashboard HD 24h généré avec succès !")

if __name__ == "__main__":
    create_image()

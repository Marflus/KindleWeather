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

FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"

if not os.path.exists("Roboto-Regular.ttf"):
    urllib.request.urlretrieve(FONT_REGULAR_URL, "Roboto-Regular.ttf")
if not os.path.exists("Roboto-Bold.ttf"):
    urllib.request.urlretrieve(FONT_BOLD_URL, "Roboto-Bold.ttf")

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&daily=weathercode,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,weathercode,relativehumidity_2m,windspeed_10m&timezone=auto"
    headers = {"User-Agent": "KindleDashboard-GitHubActions/3.2"}
    response = requests.get(url, headers=headers)
    return response.json()

def draw_sun(draw, x, y, size):
    r = size // 3
    draw.ellipse([x - r, y - r, x + r, y + r], outline=0, width=4)
    for i in range(8):
        angle = i * 3.14159 / 4
        import math
        x1 = x + int((r + 5) * math.cos(angle))
        y1 = y + int((r + 5) * math.sin(angle))
        x2 = x + int((r + 15) * math.cos(angle))
        y2 = y + int((r + 15) * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=0, width=4)

def draw_cloud(draw, x, y, size):
    draw.arc([x - size//2, y - size//4, x, y + size//4], 180, 360, fill=0, width=4)
    draw.arc([x - size//3, y - size//2, x + size//3, y], 180, 360, fill=0, width=4)
    draw.arc([x, y - size//4, x + size//2, y + size//4], 180, 360, fill=0, width=4)
    draw.line([x - size//2, y + size//4, x + size//2, y + size//4], fill=0, width=4)

def draw_rain(draw, x, y, size):
    draw_cloud(draw, x, y - 5, size)
    for i in range(3):
        gx = x - size//3 + i * (size//3)
        draw.line([gx, y + size//4 + 5, gx - 5, y + size//4 + 18], fill=0, width=4)

def draw_snow(draw, x, y, size):
    draw_cloud(draw, x, y - 5, size)
    for i in range(3):
        sx = x - size//3 + i * (size//3)
        draw.ellipse([sx-3, y + size//4 + 5, sx+3, y + size//4 + 11], fill=0)

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

def get_french_date():
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    now = datetime.now()
    return f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"

def create_image():
    data = get_weather()
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("Roboto-Bold.ttf", 60)
    font_huge = ImageFont.truetype("Roboto-Bold.ttf", 95)
    font_large = ImageFont.truetype("Roboto-Bold.ttf", 36)
    font_med = ImageFont.truetype("Roboto-Regular.ttf", 32)
    font_small = ImageFont.truetype("Roboto-Regular.ttf", 22)

    # --- EN-TÊTE ---
    date_str = get_french_date()
    draw.text((60, 45), LOCATION_NAME.upper(), font=font_title, fill=0)
    draw.text((WIDTH - 450, 65), date_str, font=font_med, fill=0)
    
    # Ligne de démarqualification nette sous l'en-tête
    draw.line([(60, 130), (WIDTH - 60, 130)], fill=0, width=4)

    # --- BLOC PRINCIPAL MÉTÉO DU JOUR ---
    daily_code = data["daily"]["weathercode"][0]
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    t_mean = (t_max + t_min) // 2
    w_desc = weather_label(daily_code)

    # Grand logo bien visible et bien positionné à gauche
    draw_weather_icon(draw, daily_code, 130, 240, 100)
    
    draw.text((270, 175), f"{t_mean}°C", font=font_huge, fill=0)
    draw.text((270, 285), w_desc, font=font_large, fill=0)
    draw.text((270, 340), f"Min : {t_min}°C   •   Max : {t_max}°C", font=font_med, fill=0)

    # --- ALERTE PLUIE PROPRE (Boîte élargie à droite) ---
    hourly_codes = data["hourly"]["weathercode"]
    has_rain = any(c in [51, 53, 55, 61, 63, 65, 80, 81, 82] for c in hourly_codes[:24])
    
    if has_rain:
        alert_text = "🌧️ Pluie prévue aujourd'hui"
    else:
        alert_text = "✨ Temps calme et dégagé"

    # Boîte élargie pour éviter que le texte ne dépasse
    draw.rounded_rectangle([(630, 210), (WIDTH - 60, 310)], radius=15, outline=0, width=3)
    draw.text((660, 242), alert_text, font=font_large, fill=0)

    # --- LIGNE DE DÉMARCATION AVEC LE GRAPHIQUE ---
    draw.line([(60, 410), (WIDTH - 60, 410)], fill=0, width=3)

    # --- GRAPHIQUE DE TEMPÉRATURE 24H (00h à 00h) ---
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    hourly_times = data["hourly"]["time"]
    day_indices = [i for i, t in enumerate(hourly_times) if t.startswith(today_date_str)]
    if not day_indices:
        day_indices = list(range(24))

    # On prend toutes les heures disponibles de la journée (jusqu'à 24 points)
    day_indices = day_indices[:24]
    temps = [data["hourly"]["temperature_2m"][i] for i in day_indices]

    gx_start, gx_end = 110, WIDTH - 80
    gy_top, gy_bottom = 460, 600

    if temps:
        min_t, max_t = min(temps), max(temps)
        t_range = max(max_t - min_t, 1)
        
        # Échelle horizontale discrète
        draw.line([gx_start, gy_top, gx_end, gy_top], fill=200, width=1)
        draw.line([gx_start, gy_bottom, gx_end, gy_bottom], fill=200, width=1)
        
        draw.text((gx_start - 85, gy_top - 10), f"{max_t}°", font=font_small, fill=0)
        draw.text((gx_start - 85, gy_bottom - 10), f"{min_t}°", font=font_small, fill=0)

        points = []
        step_x = (gx_end - gx_start) / max(len(temps) - 1, 1)
        
        for idx, t in enumerate(temps):
            px = gx_start + int(idx * step_x)
            py = gy_bottom - int((t - min_t) / t_range * (gy_bottom - gy_top))
            points.append((px, py))
            
        if len(points) > 1:
            draw.line(points, fill=0, width=4)
            for idx, (px, py) in enumerate(points):
                # Repères sur l'axe toutes les 3 heures (00h, 03h, 06h... jusqu'à 00h)
                if idx % 3 == 0:
                    draw.ellipse([px-3, py-3, px+3, py+3], fill=0)
                    hour_label = hourly_times[day_indices[idx]].split("T")[1]
                    draw.text((px - 22, gy_bottom + 12), hour_label, font=font_small, fill=0)

    # --- LIGNE DE DÉMARCATION AVEC LES DÉTAILS ---
    draw.line([(60, 660), (WIDTH - 60, 660)], fill=0, width=3)

    # --- TABLEAU DÉTAIL HORAIRE (00h jusqu'à 00h) ---
    y_offset = 690
    row_h = 68

    # On couvre toute la journée de 00h à 00h par pas de 3h (9 lignes : 00, 03, 06, 09, 12, 15, 18, 21, 00)
    hours_to_show = [0, 3, 6, 9, 12, 15, 18, 21, 23]
    
    for h in hours_to_show:
        if h < len(day_indices):
            abs_idx = day_indices[h]
            time_iso = hourly_times[abs_idx]
            hour_str = time_iso.split("T")[1]
            if hour_str == "00:00" and h > 0:
                hour_str = "00:00" # Fin de journée
                
            temp = round(data["hourly"]["temperature_2m"][abs_idx])
            code = data["hourly"]["weathercode"][abs_idx]
            humidity = data["hourly"]["relativehumidity_2m"][abs_idx]
            wind = data["hourly"]["windspeed_10m"][abs_idx]

            # Plus de bloc noir forcé à 06h, uniquement propre et alterné / encadré
            draw.rectangle([(60, y_offset - 2), (WIDTH - 60, y_offset + row_h - 6)], outline=200, width=1)

            # Petite icône vectorielle à gauche de chaque ligne
            draw_weather_icon(draw, code, 100, y_offset + 25, 20)

            draw.text((150, y_offset + 12), hour_str, font=font_med, fill=0)
            draw.text((340, y_offset + 12), f"{temp}°C", font=font_med, fill=0)
            draw.text((560, y_offset + 12), f"Humidité : {humidity}%", font=font_small, fill=0)
            draw.text((800, y_offset + 12), f"Vent : {wind} km/h", font=font_small, fill=0)

            y_offset += row_h

    img.save("meteo.png")
    print("Dashboard HD final généré avec succès !")

if __name__ == "__main__":
    create_image()

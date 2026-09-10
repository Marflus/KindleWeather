import os
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests

# --- CONFIGURATION (Varsovie) ---
LATITUDE = 52.2297
LONGITUDE = 21.0122
LOCATION_NAME = "Varsovie"

# Résolution parfaitement ajustée pour l'écran de la Kindle
WIDTH, HEIGHT = 1072, 1448

# --- TELECHARGEMENT DES POLICES & ICONES ---
FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
FONT_WEATHER_URL = "https://github.com/erikflowers/weather-icons/raw/master/font/weathericons-regular-webfont.ttf"

if not os.path.exists("Roboto-Regular.ttf"):
    urllib.request.urlretrieve(FONT_REGULAR_URL, "Roboto-Regular.ttf")
if not os.path.exists("Roboto-Bold.ttf"):
    urllib.request.urlretrieve(FONT_BOLD_URL, "Roboto-Bold.ttf")
if not os.path.exists("weathericons.ttf"):
    urllib.request.urlretrieve(FONT_WEATHER_URL, "weathericons.ttf")

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&daily=weathercode,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,weathercode&timezone=auto"
    headers = {"User-Agent": "KindleDashboard-GitHubActions/2.1"}
    
    response = requests.get(url, headers=headers)
    data = response.json()
    if "error" in data:
        print("ERREUR API Open-Meteo :", data)
        exit(1)
    return data

def get_weather_icon(code):
    if code == 0: return "\uf00d" # Soleil
    elif code in [1, 2]: return "\uf002" # Nuageux
    elif code == 3: return "\uf041" # Très nuageux
    elif code in [45, 48]: return "\uf014" # Brouillard
    elif code in [51, 53, 55, 56, 57]: return "\uf019" # Bruine
    elif code in [61, 63, 65, 66, 67, 80, 81, 82]: return "\uf01a" # Pluie
    elif code in [71, 73, 75, 77, 85, 86]: return "\uf01b" # Neige
    elif code in [95, 96, 99]: return "\uf01e" # Orage
    else: return "\uf00c"

def weather_text(code):
    if code == 0: return "Soleil", "SOLEIL"
    elif code in [1, 2, 3, 45, 48]: return "Nuageux", "NUAGES"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]: return "Pluie", "PLUIE"
    elif code in [71, 73, 75, 77, 85, 86]: return "Neige", "NEIGE"
    else: return "Variable", "VARIABLE"

def create_image():
    data = get_weather()
    img = Image.new("L", (WIDTH, HEIGHT), 255) # Fond blanc pur
    draw = ImageDraw.Draw(img)

    # Polices proportionnées pour ne pas surcharger
    font_title = ImageFont.truetype("Roboto-Bold.ttf", 65)
    font_huge = ImageFont.truetype("Roboto-Bold.ttf", 110)
    font_large = ImageFont.truetype("Roboto-Bold.ttf", 45)
    font_med = ImageFont.truetype("Roboto-Regular.ttf", 36)
    font_small = ImageFont.truetype("Roboto-Regular.ttf", 30)

    font_icon_huge = ImageFont.truetype("weathericons.ttf", 180)
    font_icon_med = ImageFont.truetype("weathericons.ttf", 55)

    # --- EN-TÊTE ÉLÉGANT ---
    today_str = datetime.now().strftime("%d / %m / %Y")
    draw.text((60, 45), LOCATION_NAME.upper(), font=font_title, fill=0)
    draw.text((WIDTH - 280, 60), today_str, font=font_med, fill=0)
    draw.line([(60, 135), (WIDTH - 60, 135)], fill=0, width=4)

    # --- MÉTÉO DU JOUR ---
    daily_code = data["daily"]["weathercode"][0]
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    t_mean = (t_max + t_min) // 2
    w_label, w_type = weather_text(daily_code)
    main_icon = get_weather_icon(daily_code)

    draw.text((80, 175), main_icon, font=font_icon_huge, fill=0)
    draw.text((320, 185), f"{t_mean}°", font=font_huge, fill=0)
    draw.text((320, 305), w_label, font=font_large, fill=0)
    draw.text((320, 365), f"Min: {t_min}°   |   Max: {t_max}°", font=font_med, fill=0)

    # --- ALERTE ÉPURÉE ---
    hourly_codes = data["hourly"]["weathercode"]
    has_rain = any(c in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99] for c in hourly_codes[:24])
    has_snow = any(c in [71, 73, 75, 77, 85, 86] for c in hourly_codes[:24])

    if has_snow: alert_msg = "❄️ Neige prévue aujourd'hui"
    elif has_rain: alert_msg = "🌧️ Pluie prévue aujourd'hui"
    else: alert_msg = "✨ Temps calme et dégagé"

    draw.rounded_rectangle([(60, 460), (WIDTH - 60, 540)], radius=20, outline=0, width=3)
    draw.text((90, 482), alert_msg, font=font_med, fill=0)

    # --- DÉTAIL HEURE PAR HEURE (Compact et lisible) ---
    draw.text((60, 605), "ÉVOLUTION HEURE PAR HEURE", font=font_large, fill=0)
    draw.line([(60, 670), (WIDTH - 60, 670)], fill=0, width=3)

    current_hour_idx = datetime.now().hour
    y_offset = 710
    row_height = 80 # Hauteur réduite pour que tout tienne sans dépasser en bas

    # On affiche un peu plus de détails (jusqu'à 7-8 lignes) espacées proprement
    for i in range(current_hour_idx, current_hour_idx + 21, 3):
        if i >= len(data["hourly"]["time"]): break
        time_iso = data["hourly"]["time"][i]
        hour_str = time_iso.split("T")[1]
        temp = round(data["hourly"]["temperature_2m"][i])
        code = data["hourly"]["weathercode"][i]
        desc, type_w = weather_text(code)
        icon = get_weather_icon(code)

        # Highlight noir si pluie ou neige
        if type_w in ["PLUIE", "NEIGE"]:
            draw.rounded_rectangle([(60, y_offset - 5), (WIDTH - 60, y_offset + row_height - 12)], radius=12, fill=0)
            text_color = 255
        else:
            text_color = 0

        draw.text((90, y_offset + 5), hour_str, font=font_med, fill=text_color)
        draw.text((320, y_offset - 2), icon, font=font_icon_med, fill=text_color)
        draw.text((480, y_offset + 5), f"{temp}°C", font=font_med, fill=text_color)
        draw.text((680, y_offset + 5), desc, font=font_med, fill=text_color)
        
        y_offset += row_height

    img.save("meteo.png")
    print("Dashboard météo élégant généré !")

if __name__ == "__main__":
    create_image()

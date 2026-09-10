import os
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests

# --- CONFIGURATION (Varsovie) ---
LATITUDE = 52.2297
LONGITUDE = 21.0122
LOCATION_NAME = "Varsovie"

# Résolution Haute Définition (pour prendre tout l'écran)
WIDTH, HEIGHT = 1080, 1440

# --- TELECHARGEMENT DES POLICES & ICONES ---
FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
# Une police dédiée avec de superbes icônes météo
FONT_WEATHER_URL = "https://github.com/erikflowers/weather-icons/raw/master/font/weathericons-regular-webfont.ttf"

if not os.path.exists("Roboto-Regular.ttf"):
    urllib.request.urlretrieve(FONT_REGULAR_URL, "Roboto-Regular.ttf")
if not os.path.exists("Roboto-Bold.ttf"):
    urllib.request.urlretrieve(FONT_BOLD_URL, "Roboto-Bold.ttf")
if not os.path.exists("weathericons.ttf"):
    urllib.request.urlretrieve(FONT_WEATHER_URL, "weathericons.ttf")

def get_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&daily=weathercode,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,weathercode&timezone=auto"
    headers = {"User-Agent": "KindleDashboard-GitHubActions/2.0"}
    
    response = requests.get(url, headers=headers)
    data = response.json()
    if "error" in data:
        print("ERREUR API Open-Meteo :", data)
        exit(1)
    return data

def get_weather_icon(code):
    # Mapping des codes météo vers les icônes de la police "Weather Icons"
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
    img = Image.new("L", (WIDTH, HEIGHT), 255) # Fond blanc
    draw = ImageDraw.Draw(img)

    # Polices beaucoup plus grandes pour un design plein écran
    font_huge = ImageFont.truetype("Roboto-Bold.ttf", 130)
    font_title = ImageFont.truetype("Roboto-Bold.ttf", 85)
    font_large = ImageFont.truetype("Roboto-Bold.ttf", 60)
    font_med = ImageFont.truetype("Roboto-Regular.ttf", 45)

    # Police spéciale pour les icônes
    font_icon_huge = ImageFont.truetype("weathericons.ttf", 250)
    font_icon_med = ImageFont.truetype("weathericons.ttf", 80)

    # --- EN-TÊTE ---
    today_str = datetime.now().strftime("%d/%m/%Y")
    draw.text((60, 50), LOCATION_NAME.upper(), font=font_title, fill=0)
    draw.text((WIDTH - 280, 80), today_str, font=font_med, fill=0)
    draw.line([(60, 160), (WIDTH - 60, 160)], fill=0, width=6)

    # --- MÉTÉO ACTUELLE ---
    daily_code = data["daily"]["weathercode"][0]
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    t_mean = (t_max + t_min) // 2
    w_label, w_type = weather_text(daily_code)
    main_icon = get_weather_icon(daily_code)

    # Grande icône à gauche, texte à droite
    draw.text((80, 200), main_icon, font=font_icon_huge, fill=0)
    draw.text((420, 220), f"{t_mean}°", font=font_huge, fill=0)
    draw.text((420, 360), w_label, font=font_large, fill=0)
    draw.text((420, 440), f"Min: {t_min}°   |   Max: {t_max}°", font=font_med, fill=0)

    # --- ALERTE (Rectangle arrondi) ---
    hourly_codes = data["hourly"]["weathercode"]
    has_rain = any(c in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99] for c in hourly_codes[:24])
    has_snow = any(c in [71, 73, 75, 77, 85, 86] for c in hourly_codes[:24])

    if has_snow: alert_msg = "⚠️ Alerte Neige : Couvrez-vous bien !"
    elif has_rain: alert_msg = "⚠️ Pluie prévue : Pensez au parapluie !"
    else: alert_msg = "✨ Belle journée : Aucune intempérie prévue."

    draw.rounded_rectangle([(60, 550), (WIDTH - 60, 650)], radius=25, outline=0, width=4)
    draw.text((100, 575), alert_msg, font=font_med, fill=0)

    # --- DÉTAIL HEURE PAR HEURE ---
    draw.text((60, 750), "ÉVOLUTION HEURE PAR HEURE", font=font_large, fill=0)
    draw.line([(60, 830), (WIDTH - 60, 830)], fill=0, width=4)

    current_hour_idx = datetime.now().hour
    y_offset = 880

    for i in range(current_hour_idx, current_hour_idx + 18, 3):
        if i >= len(data["hourly"]["time"]): break
        time_iso = data["hourly"]["time"][i]
        hour_str = time_iso.split("T")[1]
        temp = round(data["hourly"]["temperature_2m"][i])
        code = data["hourly"]["weathercode"][i]
        desc, type_w = weather_text(code)
        icon = get_weather_icon(code)

        # Inversion des couleurs si pluie/neige
        if type_w in ["PLUIE", "NEIGE"]:
            draw.rounded_rectangle([(60, y_offset - 10), (WIDTH - 60, y_offset + 90)], radius=15, fill=0)
            text_color = 255
        else:
            text_color = 0

        # Ligne horaire bien alignée avec de superbes icônes
        draw.text((100, y_offset + 15), hour_str, font=font_med, fill=text_color)
        draw.text((320, y_offset - 25), icon, font=font_icon_med, fill=text_color)
        draw.text((500, y_offset + 15), f"{temp}°C", font=font_med, fill=text_color)
        draw.text((700, y_offset + 15), desc, font=font_med, fill=text_color)
        
        y_offset += 130

    img.save("meteo.png")
    print("Image météo HD générée avec succès !")

if __name__ == "__main__":
    create_image()

import os
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests

# --- CONFIGURATION ---
LATITUDE = 52.2297
LONGITUDE = 21.0122
LOCATION_NAME = "Varsovie"

# Résolution de l'écran (600x800 standard Kindle Paperwhite/Basic)
WIDTH, HEIGHT = 600, 800

# --- TELECHARGEMENT DE BELLES POLICES ---
# Pour éviter la police moche par défaut de Linux/GitHub
FONT_REGULAR_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
FONT_BOLD_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"

if not os.path.exists("Roboto-Regular.ttf"):
    urllib.request.urlretrieve(FONT_REGULAR_URL, "Roboto-Regular.ttf")
if not os.path.exists("Roboto-Bold.ttf"):
    urllib.request.urlretrieve(FONT_BOLD_URL, "Roboto-Bold.ttf")

def get_weather():
    # Récupération de la météo (moyenne, min, max et horaire)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&daily=weathercode,temperature_2m_max,temperature_2m_min,temperature_2m_mean&hourly=temperature_2m,weathercode&timezone=auto"
    response = requests.get(url)
    return response.json()

def weather_text(code):
    # Correspondance des codes météo de l'Organisation Météorologique Mondiale
    if code in [0]:
        return "Soleil ☀️", "SOLEIL"
    elif code in [1, 2, 3, 45, 48]:
        return "Nuageux ⛅", "NUAGES"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]:
        return "Pluie 🌧️", "PLUIE"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "Neige ❄️", "NEIGE"
    else:
        return "Variable 🌤️", "VARIABLE"

def create_image():
    data = get_weather()

    # Image blanche (fond pur e-ink)
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    # Chargement des polices téléchargées
    font_title = ImageFont.truetype("Roboto-Bold.ttf", 46)
    font_large = ImageFont.truetype("Roboto-Bold.ttf", 32)
    font_med = ImageFont.truetype("Roboto-Regular.ttf", 24)
    font_small = ImageFont.truetype("Roboto-Regular.ttf", 20)

    # --- EN-TÊTE : Lieu & Date ---
    today_str = datetime.now().strftime("%d/%m/%Y")
    draw.text((30, 20), LOCATION_NAME.upper(), font=font_title, fill=0)
    draw.text((WIDTH - 180, 40), today_str, font=font_med, fill=0)
    draw.line([(30, 80), (WIDTH - 30, 80)], fill=0, width=4)

    # --- BLOC PRINCIPAL : Météo du jour ---
    daily_code = data["daily"]["weathercode"][0]
    t_mean = round(data["daily"]["temperature_2m_mean"][0])
    t_max = round(data["daily"]["temperature_2m_max"][0])
    t_min = round(data["daily"]["temperature_2m_min"][0])
    
    w_label, w_type = weather_text(daily_code)

    draw.text((30, 100), f"Aujourd'hui : {w_label}", font=font_large, fill=0)
    draw.text((30, 150), f"Moy: {t_mean}°C   |   Min: {t_min}°C   |   Max: {t_max}°C", font=font_med, fill=0)

    # --- MESSAGE ALERTE ---
    hourly_codes = data["hourly"]["weathercode"]
    
    # On regarde les 24 prochaines heures pour les alertes
    has_rain = any(c in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99] for c in hourly_codes[:24])
    has_snow = any(c in [71, 73, 75, 77, 85, 86] for c in hourly_codes[:24])

    alert_msg = ""
    if has_snow:
        alert_msg = "⚠️ Alerte Neige : Couvrez-vous bien !"
    elif has_rain:
        alert_msg = "⚠️ Pluie prévue : Pensez au parapluie !"
    else:
        alert_msg = "✨ Belle journée : Aucune intempérie prévue."

    # Dessiner la boîte d'alerte
    draw.rectangle([(30, 200), (WIDTH - 30, 250)], outline=0, width=2)
    draw.text((50, 212), alert_msg, font=font_med, fill=0)

    # --- DÉTAIL HEURE PAR HEURE ---
    draw.text((30, 290), "ÉVOLUTION HEURE PAR HEURE", font=font_large, fill=0)
    draw.line([(30, 335), (WIDTH - 30, 335)], fill=0, width=2)

    current_hour_idx = datetime.now().hour
    y_offset = 360

    # Affichage par pas de 3 heures
    for i in range(current_hour_idx, current_hour_idx + 18, 3):
        if i >= len(data["hourly"]["time"]):
            break
            
        time_iso = data["hourly"]["time"][i]
        hour_str = time_iso.split("T")[1] # Récupère "HH:MM"
        temp = round(data["hourly"]["temperature_2m"][i])
        code = data["hourly"]["weathercode"][i]
        desc, type_w = weather_text(code)

        is_bad_weather = type_w in ["PLUIE", "NEIGE"]

        # Encadré inversé (noir, texte blanc) pour mettre en évidence la pluie/neige
        if is_bad_weather:
            draw.rectangle([(30, y_offset - 5), (WIDTH - 30, y_offset + 35)], fill=0)
            text_color = 255 # Blanc
        else:
            text_color = 0   # Noir

        row_text = f"  {hour_str}      {temp}°C      {desc}"
        draw.text((40, y_offset), row_text, font=font_med, fill=text_color)
        
        y_offset += 60

    # Sauvegarde finale
    img.save("meteo.png")
    print("Image météo pour Varsovie générée avec succès !")

if __name__ == "__main__":
    create_image()

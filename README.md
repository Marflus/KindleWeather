# KindleWeather

Turn a jailbroken Kindle into a standalone, battery-powered weather station.
Every hour, or at the interval you choose, the Kindle wakes up, fetches the forecast from
[Open-Meteo](https://open-meteo.com/), draws a grayscale dashboard tuned for
e-ink, displays it and goes back to sleep. No computer, server, account or API
key is needed.

<p align="center">
  <img src="preview/classic/portrait.png" alt="Portrait dashboard" height="380">
  <img src="preview/classic/landscape.png" alt="Landscape dashboard" height="380">
</p>
<p align="center"><sub>Portrait and landscape layouts, rendered from sample data.</sub></p>

## Features

- Now: weather, temperature, humidity and wind of the current hour, with the day's min, max, sunrise and sunset
- The next 7 days, with their weather icon and mean temperature
- A precipitation alert for the next 24 hours: snow, thunderstorm or rain
- A temperature chart and an hourly table for the next 24 hours, with rain, snow and thunderstorm hours shaded
- Portrait or landscape, Celsius or Fahrenheit, 24-hour or 12-hour clock, three [icon sets](#icon-sets), eight [languages](#languages), all set on the Kindle, see [Settings](#settings)
- An [error code](#error-codes) on the screen when something goes wrong, and a low battery warning

## How it works

```
Kindle, every hour (or 15 minutes to 24 hours)
 1. wake up, Wi-Fi on
 2. Open-Meteo -> forecast -> dashboard.png, drawn by Python with the Kindle's own cairo library
 3. Wi-Fi off, display the dashboard
 4. suspend until the next refresh
```

KindleWeather is a [KUAL](https://www.mobileread.com/forums/showthread.php?t=203326)
extension. When started, it stops Amazon's interface and its background
services, so that nothing draws over the dashboard and the battery lasts. The
Kindle's real-time clock wakes it up for each refresh, and the e-ink screen keeps the
image without power in between. The approach comes from
[kindle-weatherstation](https://github.com/mattzzw/kindle-weatherstation).

## Compatibility

You need a **jailbroken** Kindle with **KUAL** and **MRPI**, and Wi-Fi. Whether
a jailbreak exists depends on your firmware version: see
[Kindle Modding](https://kindlemodding.org/) and the
[MobileRead forums](https://www.mobileread.com/forums/forumdisplay.php?f=150).

| Model | Screen | Notes |
|---|---|---|
| Kindle Paperwhite 3 (7th gen, 2015) | 1072×1448 | Tested |
| Kindle Voyage (2014), Oasis (2016), Paperwhite 4 (2018), Kindle (2022) | 1072×1448 | |
| Kindle Paperwhite 2 (6th gen, 2013) | 758×1024 | Set `display` in `config.json` |
| Kindle Paperwhite 5 (2021) | 1236×1648 | Set `display` in `config.json` |
| Kindle Oasis 2 and 3 (2017, 2019) | 1264×1680 | Set `display` in `config.json` |

The station wakes up with the clock at `/dev/rtc1`, as on the Paperwhite 2 and
3. On other models, check `RTC` at the top of
[`station.sh`](kindleweather/bin/station.sh).

## Installation

1. **Install Python 3 on the Kindle.** Install NiLuJe's Python package with
   MRPI, as explained on [Python on Kindle](https://wiki.mobileread.com/wiki/Python_on_Kindle).
   For a Paperwhite 2 or later, it is the `Update_python3_..._install_pw2_and_up.bin`
   file of the package: copy it to the `mrpackages` folder of the Kindle, then
   run **KUAL > Helper > Install MR Packages**.
2. **Download KindleWeather**: [KindleWeather-main.zip](https://github.com/Marflus/KindleWeather/archive/refs/heads/main.zip),
   and extract it.
3. **Copy the `kindleweather` folder** of the zip into the `extensions` folder
   of the Kindle, next to `documents`, with the Kindle plugged in over USB.
   KUAL creates `extensions` when it is installed; if it is missing, create it.
4. **Set your city**: eject the Kindle and unplug it, open
   **KUAL > KindleWeather > Settings > City**, then press
   **Detect automatically**, or **Search in the browser** to type its name
   (see [Settings](#settings)).
5. **Start the station**: press **KUAL > KindleWeather > Start weather
   station**. KUAL closes, the screen shows "Starting the weather station..."
   and the dashboard appears within a minute.

To stop the station and get the normal Kindle back, restart it: hold the power
button for about 15 seconds.

While plugged in over USB, the Kindle does not suspend: the station then waits
for the next refresh instead.

### If the station does not start

Run **KUAL > KindleWeather > Diagnostic**. It checks Python, drawing, Wi-Fi and
the configuration, draws the dashboard once without stopping the Kindle
interface, sums up on the screen, and writes the details to
`extensions/kindleweather/diagnostic.txt`. The station itself logs to
`extensions/kindleweather/station.log`.

### Updating

Save your `config.json`, replace the `kindleweather` folder with the new one,
put your `config.json` back, then restart the Kindle and start the station
again.

With [USBNetwork](https://www.mobileread.com/forums/showthread.php?t=225030)
and SSH, from the folder holding the new `kindleweather` folder (with the Kindle
restarted first, since the station turns Wi-Fi off between refreshes):

```sh
ssh root@KINDLE_IP "cp /mnt/us/extensions/kindleweather/config.json /mnt/us/config.json.bak && rm -rf /mnt/us/extensions/kindleweather"
scp -r kindleweather root@KINDLE_IP:/mnt/us/extensions/
ssh root@KINDLE_IP "mv /mnt/us/config.json.bak /mnt/us/extensions/kindleweather/config.json"
```

## Settings

Change the settings before starting the station: KUAL is closed while it runs.

### From the KUAL menu

```
KindleWeather
  Start weather station
  Settings
    City: Lyon, FR          > Detect automatically, Search in the browser
    Language: English       > English, Francais, Deutsch, Espanol...
    Orientation: Portrait   > Portrait, Landscape
    Icons: Classic          > Classic, Weather Icons, Material
    Temperature: Celsius    > Celsius, Fahrenheit
    Clock: 24-hour          > 24-hour, 12-hour (AM/PM)
    Refresh: Every hour     > Every 15 minutes, Every 30 minutes, Every hour... Every 24 hours
    All settings in the browser
  Diagnostic
```

Pressing a value saves it, and KUAL's status line confirms it, such as
"Orientation: Landscape, saved". The submenu stays open; the titles show the
new values the next time KUAL opens (reloading the menu at once would take
KUAL back to its first page).

**Detect automatically** finds the city from the internet connection, with
[ipinfo.io](https://ipinfo.io/) or [ip-api.com](https://ip-api.com/): usually
the nearest large city. The result is written at the top of the screen; the
menu shows it the next time KUAL opens.

### From the browser

**Search in the browser** and **All settings in the browser** open a settings
page in the Kindle's browser. Type the name of the city with the Kindle's
keyboard, press **Search**, then choose it among the cities of that name,
listed with their region and country. The other settings are on the same page.
Press **Close the settings page** when done.

The page is served by the Kindle itself, on port 8765 of its Wi-Fi address,
such as `http://192.168.1.23:8765/`. A phone or a computer on the same Wi-Fi
can open it too, at the address given at the bottom of the page. It stops after 15 minutes without use.

## Configuration

Every setting is saved in `config.json`, in the `kindleweather` folder, which
can also be edited by hand.

```json
{
  "language": "en",
  "location": { "city": "Lyon", "country_code": "FR" },
  "display": { "width": 1072, "height": 1448, "orientation": "portrait", "icons": "classic" },
  "temperature_unit": "celsius",
  "clock": "24h",
  "refresh_minutes": 60
}
```

| Key | Description |
|---|---|
| `language` | Language of the dashboard and of the city name, see [Languages](#languages). |
| `location.city` | City name, looked up with Open-Meteo. |
| `location.country_code` | Optional two-letter country code (`"FR"`, `"US"`...) to pick the right city among homonyms. |
| `location.id` | Optional Open-Meteo identifier of the city, set when it is chosen from the settings: the exact place, whatever its homonyms. |
| `display.width`, `display.height` | Screen size in pixels, in portrait, see [Compatibility](#compatibility). |
| `display.orientation` | `"portrait"` (default) or `"landscape"`. In landscape, read the Kindle turned a quarter turn clockwise. |
| `display.icons` | `"classic"` (default), `"weather-icons"` or `"material"`, see [Icon sets](#icon-sets). |
| `temperature_unit` | `"celsius"` (default) or `"fahrenheit"`. |
| `clock` | `"24h"` (default) or `"12h"`, with AM and PM. |
| `refresh_minutes` | Minutes between two refreshes, from 5 to 1440; 60 by default. The menu offers 15 minutes to 24 hours. Frequent refreshes drain the battery faster, and Open-Meteo's forecast changes little within an hour. |

Changes made to the file while the station runs apply at the next refresh.

## Languages

The dashboard is available in English (`en`), French (`fr`), German (`de`),
Spanish (`es`), Italian (`it`), Portuguese (`pt`, Brazilian), Dutch (`nl`) and
Polish (`pl`). Each language is a file in
[`kindleweather/lib/kindle_weather/locales`](kindleweather/lib/kindle_weather/locales):
to add one, copy `en.json`, translate the values, name the file after the
language code and add it to the language menu in
[`settings.py`](kindleweather/lib/kindle_weather/settings.py). The KUAL menu and the messages of the station are in English.

## Icon sets

- `classic`: filled shapes with shades of gray, drawn by KindleWeather;
- `weather-icons`: outline icons from [Weather Icons](https://erikflowers.github.io/weather-icons/);
- `material`: rounded icons from [Material Design Icons](https://pictogrammers.com/library/mdi/).

<p align="center">
  <img src="preview/icon-sets.png" alt="The top of the dashboard with each icon set" width="640">
</p>

Full previews of each set, in portrait and landscape, are in [`preview/`](preview).

## Error codes

Errors are written in English on the top line of the last dashboard, or on a
full screen when there is no dashboard yet. Each one is retried at the next
refresh, and logged with its details in `station.log`.

| Code | Meaning | What to do |
|---|---|---|
| E1 | Open-Meteo could not be reached (network error or timeout). | Check that the Wi-Fi network has internet access. Usually temporary. |
| E2 | Open-Meteo rejected the request, such as when too many requests are made. | The log quotes Open-Meteo's reason. |
| E3 | The city was not found. | Check `location.city` and `location.country_code`. |
| E4 | Open-Meteo's answer could not be read, such as a Wi-Fi login page instead. | Use a network without a login page. |
| E5 | `config.json` is not valid JSON, or has an invalid value. | The log names the key. |
| E6 | The dashboard could not be drawn. | The log has the details: please open an issue. |
| E7 | No Wi-Fi connection within a minute. | Check that the Kindle knows the network and is in range. |
| E8 | Python 3 is not installed. | See step 1 of the [installation](#installation). |

## Project structure

```
kindleweather/            the KUAL extension, copied as is to the Kindle
  config.json               settings
  config.xml, menu.json     KUAL menu, written by settings.py
  bin/
    start.sh                  starts station.sh in the background
    station.sh                the refresh loop: Wi-Fi, drawing, display, suspend
    diagnose.sh               the Diagnostic action
    set.sh, city.sh           the settings buttons, and Detect automatically
    web.sh                    opens the settings page in the browser
    common.sh                 paths, messages and Python lookup
  lib/kindle_weather/       Python package drawing the dashboard, standard library only
    __main__.py               entry point: draws dashboard.png or reports the error
    config.py                 reads config.json
    settings.py               KUAL menu and settings buttons
    web.py                    the settings page
    location.py               finds the city of the internet connection
    weather.py, dns.py        Open-Meteo requests
    render.py                 dashboard layout
    graphics.py, icons.py     drawn icons and icon sets (icon_fonts/)
    canvas.py                 drawing with the Kindle's cairo and FreeType, through ctypes
    errors.py, i18n.py        error codes, languages (locales/)
preview/                  dashboard previews, one folder per icon set
scripts/previews.py       regenerates preview/
```

## Development

The package runs on Python 3.8, as on the Kindle, and needs no module besides
the standard library. On a computer with the cairo and FreeType libraries
(Linux and macOS usually have them):

```sh
PYTHONPATH=kindleweather/lib python3 -m kindle_weather --output dashboard.png   # uses kindleweather/config.json
python3 scripts/previews.py                                                    # regenerates preview/
```

## Credits

- The station loop (stopping the Kindle interface, waking up with the real-time
  clock, suspending) is adapted from
  [kindle-weatherstation](https://github.com/mattzzw/kindle-weatherstation) by
  [mattzzw](https://github.com/mattzzw), itself based on
  [Matthew Petroff's Kindle weather display](https://mpetroff.net/2012/09/kindle-weather-display/)
  and [kindle-kt3_weatherdisplay_battery-optimized](https://github.com/nicoh88/kindle-kt3_weatherdisplay_battery-optimized)
  by nicoh88.
- Weather data by [Open-Meteo](https://open-meteo.com/), under CC BY 4.0.
- [Roboto](https://github.com/googlefonts/roboto) font by Google, under the Apache License 2.0.
- [Weather Icons](https://github.com/erikflowers/weather-icons) by Erik Flowers, under the SIL Open Font License 1.1.
- [Material Design Icons](https://github.com/Templarian/MaterialDesign) by Pictogrammers, under the Apache License 2.0.
- [KUAL](https://www.mobileread.com/forums/showthread.php?t=203326), NiLuJe's
  Python package and the MobileRead community for the Kindle jailbreak tooling.

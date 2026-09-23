# KindleWeather

[![CI](https://github.com/Marflus/KindleWeather/actions/workflows/ci.yml/badge.svg)](https://github.com/Marflus/KindleWeather/actions/workflows/ci.yml)

Turn a jailbroken Kindle into a battery-powered weather station. A computer on
your network, such as a Raspberry Pi, renders a grayscale dashboard tuned for
e-ink from [Open-Meteo](https://open-meteo.com/) data. Every hour, the Kindle
downloads it, displays it, and sleeps until the next refresh.

<p align="center">
  <img src="preview/classic/portrait.png" alt="Portrait dashboard" height="380">
  <img src="preview/classic/landscape.png" alt="Landscape dashboard" height="380">
</p>
<p align="center"><sub>Portrait and landscape layouts, rendered from sample data.</sub></p>

## Features

- Today's conditions, min/max, sunrise and sunset, average humidity and wind
- Forecast for the next 7 days: weather icon and mean temperature
- Precipitation alert for the next 24 hours with its icon, by priority: snow, then thunderstorm, then rain
- Temperature chart and 2-hourly table for the next 24 hours, starting at the current hour; rain, thunderstorm and snow hours get distinct patterns
- Portrait or landscape layout, Celsius or Fahrenheit
- Three icon sets to choose from (see [Icon sets](#icon-sets))
- Display in 8 languages (see [Languages](#languages))
- Error screen and error codes for each failure: weather service, location, configuration, Wi-Fi, download, outdated dashboard; low battery warning
- City set by name; its coordinates and localized name come from the Open-Meteo geocoding API
- Hourly refresh, with the Kindle suspended to RAM in between
- Guided setup, no account or API key needed

## How it works

```
Computer on your network                   Kindle, every hour
 kindle-weather serve            <-------   1. Wi-Fi on, request dashboard.png
   Open-Meteo -> dashboard.png   ------->   2. Wi-Fi off, display it (eips)
                                            3. suspend to RAM, wake up 1 hour later
```

The computer renders a fresh dashboard each time the Kindle asks for it.
Without a computer that stays on, GitHub Actions can render it every hour and
publish it on GitHub Pages instead, see
[the alternative](#alternative-publish-with-github-actions).

The station is a KUAL extension. When started, it stops Amazon's interface and
background services, so nothing covers the dashboard and the battery lasts.
Between refreshes the Kindle is suspended to RAM and woken up by its real-time
clock; the e-ink screen keeps the image without power. To get the normal
Kindle back, restart it. The approach comes from
[kindle-weatherstation](https://github.com/mattzzw/kindle-weatherstation).

## Compatibility

You need a **jailbroken** Kindle with **KUAL** and Wi-Fi. Whether a jailbreak
exists depends on your firmware version: see [Kindle Modding](https://kindlemodding.org/)
and the [MobileRead Kindle Developer's Corner](https://www.mobileread.com/forums/forumdisplay.php?f=150).

| Model | Screen | Notes |
|---|---|---|
| Kindle Paperwhite 3 (7th gen, 2015) | 1072×1448 | Main target |
| Kindle Paperwhite 2 (6th gen, 2013) | 758×1024 | Set `display` in the config |
| Kindle Voyage (2014), Oasis (2016), Paperwhite 4 (2018), Kindle (2022) | 1072×1448 | Same resolution |
| Kindle Paperwhite 5 (2021) | 1236×1648 | Set `display` in the config |
| Kindle Oasis 2 and 3 (2017, 2019) | 1264×1680 | Set `display` in the config |

The layouts are designed for a 1072×1448 screen and scaled to the configured
size. The station expects the wake-up clock at `/dev/rtc1`, as on the
Paperwhite 2 and 3; on other models, check `RTC` in
[`station.sh`](src/kindle_weather/kindle_extension/bin/station.sh).

## Installation

You need:

- a jailbroken Kindle with KUAL, see [Compatibility](#compatibility);
- a computer that stays on, on the same network as the Kindle: a Raspberry
  Pi, a NAS, a home server or a PC left on;
- Python 3.10 or newer on that computer.

### 1. Install KindleWeather on the computer

```bash
pipx install git+https://github.com/Marflus/KindleWeather.git
```

[pipx](https://pipx.pypa.io/) installs the `kindle-weather` command in its own
environment. `pip install git+https://github.com/Marflus/KindleWeather.git`
works too.

### 2. Configure it

```bash
kindle-weather init
```

Answer a few questions: language, city (checked online), Kindle model,
orientation, temperature unit and icons. Press Enter to keep the suggested
value. The dashboard address defaults to this computer, for example
`http://192.168.1.20:8080/dashboard.png`.

The configuration is saved in `~/.config/kindle-weather/config.json`
(`%APPDATA%\kindle-weather\config.json` on Windows). Run `kindle-weather init`
again to change it, or edit the file, see [Configuration](#configuration).

### 3. Install the station on the Kindle

Plug the Kindle in over USB, then run:

```bash
kindle-weather install
```

The Kindle drive is found automatically; if not, pass its path, such as
`kindle-weather install E:/` or `kindle-weather install /media/you/Kindle`.
Eject the Kindle and restart it so KUAL picks up the new extension.

### 4. Serve the dashboard

```bash
kindle-weather serve
```

Open the address it prints, without `dashboard.png`, in a browser to check the
dashboard. Leave the command running: the Kindle downloads its dashboard from
it every hour. On Windows, allow Python through the firewall on private
networks when asked.

Give the computer a fixed address on your network (a DHCP reservation in your
router settings), since the Kindle keeps the address it was installed with.

To start the server with the computer on Linux, including Raspberry Pi OS,
create `~/.config/systemd/user/kindle-weather.service`:

```ini
[Unit]
Description=KindleWeather dashboard server
After=network-online.target

[Service]
ExecStart=%h/.local/bin/kindle-weather serve
Restart=on-failure

[Install]
WantedBy=default.target
```

Then enable it, and keep it running after you log out:

```bash
systemctl --user enable --now kindle-weather
sudo loginctl enable-linger $USER
```

### 5. Start the station

Open **KUAL > KindleWeather > Start weather station**. The interface
disappears and the dashboard shows up within a minute. A log is kept in
`extensions/kindleweather/station.log` on the Kindle drive.

To stop the station, hold the power button until the Kindle restarts (10 to
20 seconds).

### Alternative: publish with GitHub Actions

Without a computer that stays on, a GitHub workflow can render the dashboard
every hour and publish it on GitHub Pages.

1. Fork this repository and edit [`config/config.json`](config/config.json).
   Set `dashboard_url` to your GitHub Pages address:
   `https://<user>.github.io/<repository>/dashboard.png`.
2. In **Settings > Pages**, set **Source** to **GitHub Actions**. GitHub Pages
   requires a public repository on the free plan.
3. Run **Actions > Publish dashboard > Run workflow**, then open `dashboard_url`
   in a browser to check the image. The workflow then runs every hour.
4. From a clone of your fork, install the station on the Kindle:
   `pip install .`, then `kindle-weather install`. In a clone, commands use
   `config/config.json`.

GitHub may delay scheduled workflows, so the dashboard can be older than an
hour, and it disables them after 60 days without activity in the repository
(error E12 on the Kindle): re-enable the workflow from the **Actions** tab.
Some Kindles also fail HTTPS connections with their outdated certificates
(error E10).

## Configuration

```json
{
  "language": "en",
  "location": { "city": "Lyon", "country_code": "FR" },
  "display": { "width": 1072, "height": 1448, "orientation": "portrait", "icons": "classic" },
  "temperature_unit": "celsius",
  "dashboard_url": "https://you.github.io/KindleWeather/dashboard.png"
}
```

| Key | Description |
|---|---|
| `language` | Display language, see [Languages](#languages). Applies to the dashboard, the city name and the KUAL menu. |
| `location.city` | City name, geocoded by Open-Meteo. The name shown is fetched in the chosen language. |
| `location.country_code` | Optional ISO 3166-1 alpha-2 code (`"FR"`, `"US"`...) to pick the right city among homonyms. |
| `display.width`, `display.height` | Screen resolution in pixels, in portrait (see [Compatibility](#compatibility)). |
| `display.orientation` | `"portrait"` (default) or `"landscape"`. In landscape, read the Kindle turned a quarter turn clockwise. |
| `display.icons` | `"classic"` (default), `"weather-icons"` or `"material"`, see [Icon sets](#icon-sets). |
| `temperature_unit` | `"celsius"` (default) or `"fahrenheit"`. |
| `dashboard_url` | Where the Kindle downloads the dashboard: `kindle-weather serve`, GitHub Pages or any HTTP(S) host. |

The other settings apply at the next refresh; after changing `language` or
`dashboard_url`, run `kindle-weather install` again. With GitHub Actions,
commit the file.

## Languages

The display is available in English (`en`), French (`fr`), German (`de`),
Spanish (`es`), Italian (`it`), Portuguese (`pt`, Brazilian), Dutch (`nl`) and
Polish (`pl`). Each language is a JSON file in
[`src/kindle_weather/locales`](src/kindle_weather/locales): to add one, copy
`en.json`, translate the values and name the file after the language code.

## Icon sets

Set `display.icons` to pick the icons:

- `classic`: filled shapes drawn by the renderer, with shades of gray;
- `weather-icons`: outline icons from [Weather Icons](https://erikflowers.github.io/weather-icons/);
- `material`: rounded icons from [Material Design Icons](https://pictogrammers.com/library/mdi/).

<p align="center">
  <img src="preview/icon-sets.png" alt="The top of the dashboard with each icon set" width="640">
</p>

Full previews of each set, in portrait and landscape, are in
[`preview/`](preview).

The icon fonts are vendored in
[`src/kindle_weather/icon_fonts`](src/kindle_weather/icon_fonts) with their
licenses. To add a set, map the WMO weather codes and the four detail icons to
glyphs in [`icons.py`](src/kindle_weather/icons.py).

## Error codes

Errors raised while rendering the dashboard replace it with a full-screen
error, with a technical detail underneath, so the Kindle shows it. The server
prints it too; with GitHub Actions, the workflow publishes the screen, then
fails, so GitHub also notifies you.

| Code | Meaning | What to do |
|---|---|---|
| E1 | The Open-Meteo servers could not be reached (network error or timeout). | Usually temporary. Check [Open-Meteo's status](https://open-meteo.com/) if it lasts. |
| E2 | Open-Meteo rejected the request (HTTP error, such as 429 when rate-limited). | The detail line quotes Open-Meteo's reason. |
| E3 | The city was not found by the geocoding API. | Check the spelling of `location.city` and `location.country_code`. |
| E4 | Open-Meteo answered with incomplete or unreadable data. | Usually temporary. |
| E5 | The configuration is not valid JSON or has an invalid value. | The detail line names the key. Run `kindle-weather init` to rewrite it. |
| E6 | Unexpected rendering failure. | A bug: the server output or the workflow log has the traceback, please open an issue. |

Errors raised on the Kindle are written on the top line of the last
dashboard, and logged in `extensions/kindleweather/station.log`.

| Code | Meaning | What to do |
|---|---|---|
| E7 | No Wi-Fi connection within a minute. | Check that the Kindle remembers the network and is in range. |
| E8 | The dashboard server could not be reached (DNS, connection or timeout). | Check that `kindle-weather serve` is running and the computer kept its address. With GitHub Pages, check that the network has internet access. |
| E9 | The server answered with an HTTP error, typically 404. | Check `dashboard_url`, and with GitHub Actions that GitHub Pages is enabled. |
| E10 | The HTTPS connection failed, often because of the Kindle's outdated certificates. | Update the firmware, or use an `http://` URL. |
| E11 | The downloaded file is not a PNG image, such as a Wi-Fi login page. | Log in to the network from another device, or use another network. |
| E12 | The dashboard has not been updated for over 6 hours. | With GitHub Actions, check the **Actions** tab: GitHub disables scheduled workflows after 60 days without activity. |
| E13 | Any other download error. | The reason is in `station.log`. |

Every code is retried at the next hourly refresh. Below 10 % battery, the
Kindle also shows a low battery warning.

## Usage

```bash
kindle-weather init                             # create or update the configuration
kindle-weather install [DRIVE]                  # install the KUAL extension on the Kindle
kindle-weather serve [--port 8080]              # serve the dashboard on the local network
kindle-weather render [--output dashboard.png]  # render the dashboard to a file
```

Every command takes `--config PATH` to use another configuration file.

## Project structure

```
.github/workflows/    ci.yml (lint, tests), publish.yml (GitHub Actions alternative)
config/               config.json, used in a clone of the repository
preview/              dashboard previews, one folder per icon set; scripts/previews.py makes them
src/kindle_weather/   Python package
  cli.py                commands
  wizard.py             kindle-weather init
  server.py             kindle-weather serve
  dashboard.py          dashboard or error screen for the configuration
  config.py, weather.py, errors.py, i18n.py (locales/*.json)
  render.py, graphics.py, icons.py (icon_fonts/*.ttf)
  install.py, kindle_extension/  KUAL extension; bin/station.sh is the station loop
tests/                pytest suite, runs offline
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
shellcheck --shell=sh --severity=warning src/kindle_weather/kindle_extension/bin/*.sh
python scripts/previews.py    # regenerate the previews
```

CI runs these checks on every push and pull request.

## Known limitations

- While the station runs, the Kindle cannot be used as an e-reader.
- The computer running `kindle-weather serve` must be on when the Kindle
  wakes up; otherwise the Kindle keeps the last dashboard and shows E8.
- If the Kindle does not wake up by itself, press the power button: the
  station refreshes, then goes back to sleep. Check `RTC` in `station.sh`
  for your model.

## Credits

- The weather station loop (stopping the Kindle interface, waking up with the
  real-time clock, suspending to RAM) is adapted from
  [kindle-weatherstation](https://github.com/mattzzw/kindle-weatherstation) by
  [mattzzw](https://github.com/mattzzw), itself based on
  [Matthew Petroff's Kindle weather display](https://mpetroff.net/2012/09/kindle-weather-display/)
  and [kindle-kt3_weatherdisplay_battery-optimized](https://github.com/nicoh88/kindle-kt3_weatherdisplay_battery-optimized)
  by nicoh88.
- Weather data by [Open-Meteo](https://open-meteo.com/), under CC BY 4.0.
- [Roboto](https://github.com/googlefonts/roboto) font, packaged for Python by
  [Pimoroni](https://github.com/pimoroni/fonts-python).
- [Weather Icons](https://github.com/erikflowers/weather-icons) by Erik
  Flowers, under the SIL Open Font License 1.1.
- [Material Design Icons](https://github.com/Templarian/MaterialDesign) by
  Pictogrammers, under the Apache License 2.0 (weather glyphs only).
- [KUAL](https://www.mobileread.com/forums/showthread.php?t=203326) and the
  MobileRead community for the Kindle jailbreak tooling.


"""Dashboard layout, drawn at 2x and downscaled for clean e-ink anti-aliasing."""

from __future__ import annotations

from itertools import groupby

import font_roboto
from PIL import Image, ImageDraw, ImageFont

from kindle_weather.graphics import (
    GRAY_DARK,
    GRAY_LIGHT,
    GRAY_MID,
    GRAY_PALE,
    INK,
    WHITE,
    draw_centered_text,
    draw_droplet,
    draw_sun_horizon,
    draw_weather_icon,
    draw_wind,
    text_width,
)
from kindle_weather.i18n import Locale
from kindle_weather.weather import RAINY_CODES, DailyForecast

LAYOUT_SIZE = (1072, 1448)
SUPERSAMPLING = 2
WIDTH, HEIGHT = LAYOUT_SIZE[0] * SUPERSAMPLING, LAYOUT_SIZE[1] * SUPERSAMPLING
MARGIN = 50 * SUPERSAMPLING

FONT_SPECS = {
    "date": (font_roboto.RobotoBold, 34),
    "location": (font_roboto.RobotoBold, 26),
    "temperature": (font_roboto.RobotoBold, 100),
    "description": (font_roboto.Roboto, 30),
    "min_max": (font_roboto.RobotoBold, 38),
    "panel_label": (font_roboto.Roboto, 20),
    "panel_value": (font_roboto.RobotoBold, 24),
    "banner": (font_roboto.RobotoBold, 24),
    "axis": (font_roboto.Roboto, 18),
    "row": (font_roboto.RobotoBold, 26),
    "row_small": (font_roboto.Roboto, 19),
    "footer": (font_roboto.Roboto, 16),
}

TABLE_HOURS = ((2, 4, 6, 8, 10, 12), (14, 16, 18, 20, 22, 0))


def px(value: float) -> int:
    return round(value * SUPERSAMPLING)


def render_dashboard(
    forecast: DailyForecast, locale: Locale, size: tuple[int, int] = LAYOUT_SIZE
) -> Image.Image:
    return _Dashboard(forecast, locale).render(size)


def rainy_runs(codes: list[int]) -> list[tuple[int, int]]:
    """Return [start, end) index ranges of consecutive rainy codes."""
    runs, start = [], 0
    for rainy, group in groupby(codes, key=lambda code: code in RAINY_CODES):
        end = start + len(list(group))
        if rainy:
            runs.append((start, end))
        start = end
    return runs


class _Dashboard:
    def __init__(self, forecast: DailyForecast, locale: Locale):
        self.forecast = forecast
        self.locale = locale
        self.image = Image.new("L", (WIDTH, HEIGHT), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {
            name: ImageFont.truetype(path, px(size)) for name, (path, size) in FONT_SPECS.items()
        }

    def render(self, size: tuple[int, int]) -> Image.Image:
        y = self._header()
        y = self._summary(y + px(18))
        y = self._rain_banner(y + px(12))
        y = self._temperature_chart(y + px(22))
        y = self._hourly_table(y + px(80))
        self._footer(y + px(54))
        return self.image.resize(size, Image.Resampling.LANCZOS)

    def _separator(self, y: float) -> None:
        self.draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=GRAY_LIGHT, width=px(2))

    def _header(self) -> int:
        # Centered: the Kindle status bar covers the top corners.
        top = px(56)
        date = self.locale.format_long_date(self.forecast.observed_at)
        place = self.forecast.place_name.upper()
        draw_centered_text(self.draw, WIDTH // 2, top, date, self.fonts["date"], INK)
        draw_centered_text(
            self.draw, WIDTH // 2, top + px(48), place, self.fonts["location"], GRAY_DARK
        )
        bottom = top + px(96)
        self._separator(bottom)
        return bottom

    def _summary(self, top: int) -> int:
        draw, fonts, forecast = self.draw, self.fonts, self.forecast
        height, panel_width, padding = px(220), px(340), px(20)
        draw.rounded_rectangle(
            [MARGIN, top, WIDTH - MARGIN, top + height], radius=px(22), fill=GRAY_PALE
        )
        divider_x = WIDTH - MARGIN - panel_width - 2 * padding
        draw.line(
            [(divider_x, top + px(24)), (divider_x, top + height - px(24))],
            fill=GRAY_LIGHT,
            width=px(2),
        )

        t_max = round(forecast.temperature_max)
        t_min = round(forecast.temperature_min)
        temperature = f"{round((t_max + t_min) / 2)}°"
        description = self.locale.describe(forecast.weather_code)

        icon_r = px(72)
        icon_cx, center_y = MARGIN + padding + icon_r, top + height // 2
        draw_weather_icon(draw, forecast.weather_code, icon_cx, center_y, icon_r)

        text_x = icon_cx + icon_r + px(38)
        temp_box = draw.textbbox((0, 0), temperature, font=fonts["temperature"])
        desc_box = draw.textbbox((0, 0), description, font=fonts["description"])
        temp_height, desc_height = temp_box[3] - temp_box[1], desc_box[3] - desc_box[1]
        stack_top = center_y - (temp_height + px(18) + desc_height) / 2
        draw.text(
            (text_x, stack_top - temp_box[1]), temperature, font=fonts["temperature"], fill=INK
        )
        draw.text(
            (text_x, stack_top + temp_height + px(18) - desc_box[1]),
            description,
            font=fonts["description"],
            fill=INK,
        )

        max_text, min_text = f"Max {t_max}°", f"Min {t_min}°"
        max_box = draw.textbbox((0, 0), max_text, font=fonts["min_max"])
        min_box = draw.textbbox((0, 0), min_text, font=fonts["min_max"])
        max_height, min_height = max_box[3] - max_box[1], min_box[3] - min_box[1]
        min_max_x = text_x + text_width(draw, temperature, fonts["temperature"]) + px(30)
        min_max_top = center_y - (max_height + px(14) + min_height) / 2
        draw.text((min_max_x, min_max_top - max_box[1]), max_text, font=fonts["min_max"], fill=INK)
        draw.text(
            (min_max_x, min_max_top + max_height + px(14) - min_box[1]),
            min_text,
            font=fonts["min_max"],
            fill=GRAY_DARK,
        )

        self._details_panel(divider_x + padding + px(8), top, height, panel_width)
        return top + height

    def _details_panel(self, left: int, card_top: int, card_height: int, width: int) -> None:
        hours = self.forecast.hours
        labels = self.locale.labels
        humidity = round(sum(h.humidity for h in hours) / len(hours))
        wind = round(sum(h.wind_speed for h in hours) / len(hours))
        cells = (
            (labels["sunrise"], self.forecast.sunrise or "—", "sunrise"),
            (labels["sunset"], self.forecast.sunset or "—", "sunset"),
            (labels["humidity"], f"{humidity} %", "humidity"),
            (labels["wind"], f"{wind} km/h", "wind"),
        )
        cell_height, icon_r, inset = px(64), px(16), px(14)
        top = card_top + (card_height - 2 * cell_height) // 2 + px(20)
        # Fixed grid so icons and labels stay aligned across rows of different text widths.
        for i, (label, value, kind) in enumerate(cells):
            row, column = divmod(i, 2)
            cell_left = left + column * (width // 2)
            y = top + row * cell_height
            icon_cx, icon_cy = cell_left + inset + icon_r, y + px(20)
            if kind == "humidity":
                draw_droplet(self.draw, icon_cx, icon_cy, icon_r)
            elif kind == "wind":
                draw_wind(self.draw, icon_cx, icon_cy, icon_r)
            else:
                draw_sun_horizon(self.draw, icon_cx, icon_cy, icon_r, rising=kind == "sunrise")
            text_x = cell_left + inset + 2 * icon_r + px(12)
            self.draw.text(
                (text_x, y + px(2)), label, font=self.fonts["panel_label"], fill=GRAY_DARK
            )
            self.draw.text((text_x, y + px(24)), value, font=self.fonts["panel_value"], fill=INK)

    def _rain_banner(self, top: int) -> int:
        height = px(46)
        font = self.fonts["banner"]
        text = self.locale.labels["rain_expected" if self.forecast.has_rain else "no_rain"]
        self.draw.rounded_rectangle(
            [MARGIN, top, WIDTH - MARGIN, top + height],
            radius=height // 2,
            outline=INK,
            width=px(3),
        )
        box = self.draw.textbbox((0, 0), text, font=font)
        text_y = top + (height - (box[3] - box[1])) // 2 - box[1]
        draw_centered_text(self.draw, WIDTH // 2, text_y, text, font, INK)
        return top + height

    def _temperature_chart(self, separator_y: int) -> int:
        draw, forecast, font = self.draw, self.forecast, self.fonts["axis"]
        self._separator(separator_y)
        left, right = MARGIN + px(50), WIDTH - MARGIN - px(10)
        top, bottom = separator_y + px(30), separator_y + px(366)

        samples = [(h.hour / 24, h) for h in forecast.hours]
        if forecast.next_midnight:
            samples.append((1.0, forecast.next_midnight))
        low = min(h.temperature for _, h in samples)
        high = max(h.temperature for _, h in samples)
        span = max(high - low, 1)

        def y_of(temperature: float) -> float:
            return bottom - (temperature - low) / span * (bottom - top)

        for fraction in (0, 0.5, 1):
            y = bottom - fraction * (bottom - top)
            draw.line([left, y, right, y], fill=GRAY_LIGHT, width=px(1))
        draw.text((MARGIN, top - px(12)), f"{round(high)}°", font=font, fill=GRAY_DARK)
        draw.text((MARGIN, bottom - px(12)), f"{round(low)}°", font=font, fill=GRAY_DARK)

        points = [(left + f * (right - left), y_of(h.temperature)) for f, h in samples]
        draw.polygon([(left, bottom), *points, (right, bottom)], fill=GRAY_PALE)
        # Segment k (point k to k+1) takes the weather of its starting hour.
        segment_codes = [h.weather_code for _, h in samples[:-1]]
        self._hatch_rain(points, rainy_runs(segment_codes), left, right, top, bottom)
        draw.line(points, fill=INK, width=px(4), joint="curve")

        for hour in range(0, 24, 3):
            entry = forecast.at(hour)
            if entry:
                x = left + hour / 24 * (right - left)
                self._chart_tick(x, y_of(entry.temperature), f"{hour:02d}:00", right, bottom)
        if forecast.next_midnight:
            self._chart_tick(*points[-1], "00:00", right, bottom)
        return bottom

    def _chart_tick(self, x: float, y: float, label: str, right: int, axis_y: int) -> None:
        font = self.fonts["axis"]
        self.draw.ellipse([x - px(4), y - px(4), x + px(4), y + px(4)], fill=INK)
        label_width = text_width(self.draw, label, font)
        label_x = min(x - label_width / 2, right - label_width)
        self.draw.text((label_x, axis_y + px(12)), label, font=font, fill=GRAY_DARK)

    def _hatch_rain(self, points, runs, left: int, right: int, top: int, bottom: int) -> None:
        if not runs:
            return
        mask = Image.new("L", self.image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        for start, end in runs:
            run = points[start : end + 1]
            mask_draw.polygon([(run[0][0], bottom), *run, (run[-1][0], bottom)], fill=255)

        hatched = self.image.copy()
        hatch_draw = ImageDraw.Draw(hatched)
        rise = bottom - top
        for x in range(left - rise, right, px(9)):
            hatch_draw.line([(x, bottom), (x + rise, top)], fill=GRAY_DARK, width=px(2))
        self.image.paste(hatched, (0, 0), mask)

    def _hourly_table(self, separator_y: int) -> int:
        draw, fonts = self.draw, self.fonts
        self._separator(separator_y)
        top, row_height, gap = separator_y + px(18), px(66), px(40)
        column_width = (WIDTH - 2 * MARGIN - gap) // 2
        icon_zone = px(42)
        cell_width = (column_width - icon_zone) // 4

        for row in range(len(TABLE_HOURS[0])):
            y = top + row * row_height
            middle = y + row_height // 2
            if row % 2:
                draw.rectangle([MARGIN, y, WIDTH - MARGIN, y + row_height], fill=GRAY_PALE)
            for column, hours in enumerate(TABLE_HOURS):
                hour = hours[row]
                entry = self.forecast.next_midnight if hour == 0 else self.forecast.at(hour)
                if entry is None:
                    continue
                column_left = MARGIN + column * (column_width + gap)
                draw_weather_icon(
                    draw, entry.weather_code, column_left + icon_zone // 2, middle, px(13)
                )
                hour_x, temp_x, humidity_x, wind_x = (
                    column_left + icon_zone + i * cell_width for i in range(4)
                )
                draw.text((hour_x, y + px(21)), f"{hour:02d}:00", font=fonts["row"], fill=INK)
                draw.text(
                    (temp_x, y + px(21)),
                    f"{round(entry.temperature)}°C",
                    font=fonts["row"],
                    fill=INK,
                )
                draw_droplet(draw, humidity_x + px(11), middle, px(11), fill=GRAY_DARK)
                draw.text(
                    (humidity_x + px(28), y + px(23)),
                    f"{entry.humidity} %",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )
                draw_wind(draw, wind_x + px(13), middle, px(13), fill=GRAY_DARK)
                draw.text(
                    (wind_x + px(30), y + px(23)),
                    f"{round(entry.wind_speed)} km/h",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )

        bottom = top + len(TABLE_HOURS[0]) * row_height
        divider_x = MARGIN + column_width + gap // 2
        draw.line(
            [(divider_x, top + px(6)), (divider_x, bottom - px(6))], fill=GRAY_LIGHT, width=px(2)
        )
        return bottom

    def _footer(self, y: int) -> None:
        text = self.locale.format_updated_at(self.forecast.observed_at)
        draw_centered_text(self.draw, WIDTH // 2, y, text, self.fonts["footer"], GRAY_MID)

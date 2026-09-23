"""Dashboard layout, drawn at 2x and downscaled for clean e-ink anti-aliasing."""

from __future__ import annotations

from dataclasses import dataclass
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
    draw_diagonal_hatch,
    draw_dot_grid,
    draw_droplet,
    draw_sun_horizon,
    draw_weather_icon,
    draw_wind,
    icon_bounds,
    text_width,
)
from kindle_weather.i18n import Locale
from kindle_weather.weather import PRECIPITATION_KINDS, DailyForecast, precipitation_kind

SUPERSAMPLING = 2
SCREEN_SIZE = (1072, 1448)

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

# Icon shown in the precipitation banner for each kind.
BANNER_ICONS = {"snow": 73, "storm": 95, "rain": 63}

# Start of the hour, temperature, humidity and wind cells, as a share of a table
# column; wind gets the widest cell since it holds an icon and "km/h".
TABLE_CELLS = (0, 0.24, 0.47, 0.71)


@dataclass(frozen=True)
class Layout:
    size: tuple[int, int]
    header_top: int
    panel_width: int
    chart_height: int
    table_hours: tuple[tuple[int, ...], ...]
    row_height: int
    column_gap: int
    footer_gap: int


LAYOUTS = {
    "portrait": Layout(
        size=(1072, 1448),
        header_top=56,
        panel_width=340,
        chart_height=336,
        table_hours=((2, 4, 6, 8, 10, 12), (14, 16, 18, 20, 22, 0)),
        row_height=66,
        column_gap=40,
        footer_gap=54,
    ),
    "landscape": Layout(
        size=(1448, 1072),
        header_top=40,
        panel_width=520,
        chart_height=170,
        table_hours=((2, 4, 6, 8), (10, 12, 14, 16), (18, 20, 22, 0)),
        row_height=60,
        column_gap=24,
        footer_gap=40,
    ),
}


def px(value: float) -> int:
    return round(value * SUPERSAMPLING)


MARGIN = px(50)


def render_dashboard(
    forecast: DailyForecast,
    locale: Locale,
    size: tuple[int, int] = SCREEN_SIZE,
    orientation: str = "portrait",
) -> Image.Image:
    """Render for a portrait framebuffer of `size`; landscape output is rotated to fit it."""
    image = _Dashboard(forecast, locale, LAYOUTS[orientation]).render()
    if orientation == "landscape":
        # Read with the Kindle turned a quarter turn clockwise.
        width, height = size
        return image.resize((height, width), Image.Resampling.LANCZOS).transpose(
            Image.Transpose.ROTATE_90
        )
    return image.resize(size, Image.Resampling.LANCZOS)


def precipitation_runs(codes: list[int]) -> list[tuple[str, int, int]]:
    """Return (kind, start, end) for each run of consecutive codes of the same precipitation."""
    runs, start = [], 0
    for kind, group in groupby(codes, key=precipitation_kind):
        end = start + len(list(group))
        if kind:
            runs.append((kind, start, end))
        start = end
    return runs


class _Dashboard:
    def __init__(self, forecast: DailyForecast, locale: Locale, layout: Layout):
        self.forecast = forecast
        self.locale = locale
        self.layout = layout
        self.width, self.height = px(layout.size[0]), px(layout.size[1])
        self.image = Image.new("L", (self.width, self.height), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {
            name: ImageFont.truetype(path, px(size)) for name, (path, size) in FONT_SPECS.items()
        }

    def render(self) -> Image.Image:
        y = self._header()
        y = self._summary(y + px(18))
        y = self._precipitation_banner(y + px(12))
        y = self._temperature_chart(y + px(22))
        y = self._hourly_table(y + px(80))
        self._footer(y + px(self.layout.footer_gap))
        return self.image

    def _separator(self, y: float) -> None:
        self.draw.line([(MARGIN, y), (self.width - MARGIN, y)], fill=GRAY_LIGHT, width=px(2))

    def _header(self) -> int:
        # Centered: the Kindle status bar covers the top corners.
        top = px(self.layout.header_top)
        center = self.width // 2
        date = self.locale.format_long_date(self.forecast.observed_at)
        place = self.forecast.place_name.upper()
        draw_centered_text(self.draw, center, top, date, self.fonts["date"], INK)
        draw_centered_text(
            self.draw, center, top + px(48), place, self.fonts["location"], GRAY_DARK
        )
        bottom = top + px(96)
        self._separator(bottom)
        return bottom

    def _summary(self, top: int) -> int:
        draw, fonts, forecast = self.draw, self.fonts, self.forecast
        height, panel_width, padding = px(220), px(self.layout.panel_width), px(20)
        draw.rounded_rectangle(
            [MARGIN, top, self.width - MARGIN, top + height], radius=px(22), fill=GRAY_PALE
        )
        divider_x = self.width - MARGIN - panel_width - 2 * padding
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

    def _precipitation_banner(self, top: int) -> int:
        height = px(46)
        font = self.fonts["banner"]
        risk = self.forecast.precipitation_risk
        text = self.locale.labels[f"{risk}_risk" if risk else "no_precipitation"]
        self.draw.rounded_rectangle(
            [MARGIN, top, self.width - MARGIN, top + height],
            radius=height // 2,
            outline=INK,
            width=px(3),
        )
        box = self.draw.textbbox((0, 0), text, font=font)
        text_y = top + (height - (box[3] - box[1])) // 2 - box[1]
        if not risk:
            draw_centered_text(self.draw, self.width // 2, text_y, text, font, INK)
            return top + height

        # Center icon and text as one group; the icon is placed by its actual ink bounds.
        code, icon_r, gap = BANNER_ICONS[risk], px(13), px(12)
        icon_left, icon_top, icon_right, icon_bottom = icon_bounds(code, icon_r)
        icon_width = icon_right - icon_left
        group_left = self.width / 2 - (icon_width + gap + box[2] - box[0]) / 2
        draw_weather_icon(
            self.draw,
            code,
            group_left - icon_left,
            top + height / 2 - (icon_top + icon_bottom) / 2,
            icon_r,
        )
        self.draw.text((group_left + icon_width + gap - box[0], text_y), text, font=font, fill=INK)
        return top + height

    def _temperature_chart(self, separator_y: int) -> int:
        draw, forecast, font = self.draw, self.forecast, self.fonts["axis"]
        self._separator(separator_y)
        left, right = MARGIN + px(50), self.width - MARGIN - px(10)
        top = separator_y + px(30)
        bottom = top + px(self.layout.chart_height)

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
        runs = precipitation_runs([h.weather_code for _, h in samples[:-1]])
        self._pattern_under_curve(points, runs, (left, top, right, bottom))
        draw.line(points, fill=INK, width=px(4), joint="curve")

        for hour in range(0, 24, 3):
            entry = forecast.at(hour)
            if entry:
                x = left + hour / 24 * (right - left)
                self._chart_tick(x, y_of(entry.temperature), f"{hour:02d}:00", right, bottom)
        if forecast.next_midnight:
            self._chart_tick(*points[-1], "00:00", right, bottom)

        kinds = [kind for kind in PRECIPITATION_KINDS if any(run[0] == kind for run in runs)]
        if kinds:
            self._legend(kinds, (left + right) / 2, bottom + px(44))
        return bottom

    def _chart_tick(self, x: float, y: float, label: str, right: int, axis_y: int) -> None:
        font = self.fonts["axis"]
        self.draw.ellipse([x - px(4), y - px(4), x + px(4), y + px(4)], fill=INK)
        label_width = text_width(self.draw, label, font)
        label_x = min(x - label_width / 2, right - label_width)
        self.draw.text((label_x, axis_y + px(12)), label, font=font, fill=GRAY_DARK)

    def _pattern_under_curve(self, points, runs, box) -> None:
        bottom = box[3]
        for kind in PRECIPITATION_KINDS:
            mask = Image.new("L", self.image.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            for run_kind, start, end in runs:
                if run_kind == kind:
                    run = points[start : end + 1]
                    mask_draw.polygon([(run[0][0], bottom), *run, (run[-1][0], bottom)], fill=255)
            if mask.getbbox():
                self._fill_pattern(kind, mask, box)

    def _fill_pattern(self, kind: str, mask: Image.Image, box) -> None:
        layer = self.image.copy()
        draw = ImageDraw.Draw(layer)
        if kind == "rain":
            draw_diagonal_hatch(draw, box, spacing=px(9), width=px(2))
        elif kind == "storm":
            draw_diagonal_hatch(draw, box, spacing=px(12), width=px(2))
            draw_diagonal_hatch(draw, box, spacing=px(12), width=px(2), rising=False)
        else:
            draw_dot_grid(draw, box, spacing=px(12), radius=px(2.5))
        self.image.paste(layer, (0, 0), mask)

    def _legend(self, kinds: list[str], center_x: float, top: int) -> None:
        font = self.fonts["axis"]
        swatch_width, swatch_height, gap, spacing = px(34), px(18), px(8), px(28)
        labels = [self.locale.labels[kind] for kind in kinds]
        widths = [swatch_width + gap + text_width(self.draw, label, font) for label in labels]
        x = round(center_x - (sum(widths) + spacing * (len(kinds) - 1)) / 2)
        for kind, label, width in zip(kinds, labels, widths, strict=True):
            box = (x, top, x + swatch_width, top + swatch_height)
            self.draw.rectangle(box, fill=GRAY_PALE)
            mask = Image.new("L", self.image.size, 0)
            ImageDraw.Draw(mask).rectangle(box, fill=255)
            self._fill_pattern(kind, mask, box)
            self.draw.rectangle(box, outline=GRAY_MID, width=px(1))
            text_box = self.draw.textbbox((0, 0), label, font=font)
            text_y = top + (swatch_height - (text_box[3] - text_box[1])) / 2 - text_box[1]
            self.draw.text((box[2] + gap - text_box[0], text_y), label, font=font, fill=GRAY_DARK)
            x += round(width) + spacing

    def _hourly_table(self, separator_y: int) -> int:
        draw, fonts = self.draw, self.fonts
        self._separator(separator_y)
        columns = self.layout.table_hours
        row_height = px(self.layout.row_height)
        top, gap, icon_zone = separator_y + px(18), px(self.layout.column_gap), px(42)
        column_width = (self.width - 2 * MARGIN - (len(columns) - 1) * gap) // len(columns)

        for row in range(len(columns[0])):
            y = top + row * row_height
            middle = y + row_height // 2
            if row % 2:
                draw.rectangle([MARGIN, y, self.width - MARGIN, y + row_height], fill=GRAY_PALE)
            for column, hours in enumerate(columns):
                hour = hours[row]
                entry = self.forecast.next_midnight if hour == 0 else self.forecast.at(hour)
                if entry is None:
                    continue
                column_left = MARGIN + column * (column_width + gap)
                draw_weather_icon(
                    draw, entry.weather_code, column_left + icon_zone // 2, middle, px(13)
                )
                hour_x, temp_x, humidity_x, wind_x = (
                    column_left + icon_zone + round(share * (column_width - icon_zone))
                    for share in TABLE_CELLS
                )
                draw.text((hour_x, middle - px(12)), f"{hour:02d}:00", font=fonts["row"], fill=INK)
                draw.text(
                    (temp_x, middle - px(12)),
                    f"{round(entry.temperature)}°C",
                    font=fonts["row"],
                    fill=INK,
                )
                draw_droplet(draw, humidity_x + px(11), middle, px(11), fill=GRAY_DARK)
                draw.text(
                    (humidity_x + px(28), middle - px(10)),
                    f"{entry.humidity} %",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )
                draw_wind(draw, wind_x + px(13), middle, px(13), fill=GRAY_DARK)
                draw.text(
                    (wind_x + px(30), middle - px(10)),
                    f"{round(entry.wind_speed)} km/h",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )

        bottom = top + len(columns[0]) * row_height
        for column in range(1, len(columns)):
            divider_x = MARGIN + column * (column_width + gap) - gap // 2
            draw.line(
                [(divider_x, top + px(6)), (divider_x, bottom - px(6))],
                fill=GRAY_LIGHT,
                width=px(2),
            )
        return bottom

    def _footer(self, y: int) -> None:
        text = self.locale.format_updated_at(self.forecast.observed_at)
        draw_centered_text(self.draw, self.width // 2, y, text, self.fonts["footer"], GRAY_MID)

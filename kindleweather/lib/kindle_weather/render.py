"""Dashboard layout, drawn in the units of a 1072x1448 screen and scaled to the display."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from kindle_weather.canvas import Canvas, Font, Picture
from kindle_weather.errors import ErrorCode
from kindle_weather.graphics import (
    GRAY_DARK,
    GRAY_LIGHT,
    GRAY_MID,
    GRAY_PALE,
    INK,
    draw_asterisk,
    draw_bolt,
    draw_centered_text,
    draw_diagonal_hatch,
    draw_symbol_grid,
    text_width,
)
from kindle_weather.i18n import Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS
from kindle_weather.weather import (
    PRECIPITATION_KINDS,
    WINDOW_HOURS,
    Forecast,
    precipitation_kind,
)

# The Paperwhite 3 screen, in portrait.
SCREEN_SIZE = (1072, 1448)
MARGIN = 50
FONT_DIR = Path(__file__).parent / "fonts"
ROBOTO, ROBOTO_BOLD = FONT_DIR / "Roboto-Regular.ttf", FONT_DIR / "Roboto-Bold.ttf"

FONT_SPECS = {
    "date": (ROBOTO_BOLD, 34),
    "location": (ROBOTO_BOLD, 26),
    "temperature": (ROBOTO_BOLD, 100),
    "description": (ROBOTO, 30),
    "min_max": (ROBOTO_BOLD, 38),
    "panel_label": (ROBOTO, 20),
    "panel_value": (ROBOTO_BOLD, 24),
    "day": (ROBOTO_BOLD, 22),
    "day_temperature": (ROBOTO_BOLD, 30),
    "banner": (ROBOTO_BOLD, 24),
    "axis": (ROBOTO, 18),
    "row": (ROBOTO_BOLD, 26),
    "row_small": (ROBOTO, 19),
    "footer": (ROBOTO, 16),
}

# Left to right order of the chart legend.
LEGEND_KINDS = ("rain", "snow", "storm")

# Icon shown in the precipitation banner for each kind.
BANNER_ICONS = {"snow": 73, "storm": 95, "rain": 63}

# Start of the hour, temperature, humidity and wind cells, as a share of a table
# column; wind gets the widest cell since it holds an icon and "km/h".
TABLE_CELLS = (0, 0.24, 0.47, 0.71)


@dataclass(frozen=True)
class Layout:
    """Sizes of the dashboard sections for one orientation, in layout units."""

    size: tuple[int, int]
    top: int
    card_height: int
    panel_width: int
    days_height: int
    chart_height: int
    table_columns: int
    row_height: int
    column_gap: int
    footer_gap: int


LAYOUTS = {
    "portrait": Layout(
        size=(1072, 1448),
        top=36,
        card_height=270,
        panel_width=300,
        days_height=150,
        chart_height=270,
        table_columns=2,
        row_height=66,
        column_gap=40,
        footer_gap=44,
    ),
    "landscape": Layout(
        size=(1448, 1072),
        top=28,
        card_height=250,
        panel_width=520,
        days_height=130,
        chart_height=130,
        table_columns=3,
        row_height=52,
        column_gap=24,
        footer_gap=34,
    ),
}


def render_dashboard(
    forecast: Forecast,
    locale: Locale,
    size: tuple[int, int] = SCREEN_SIZE,
    orientation: str = "portrait",
    icon_set: str = DEFAULT_ICON_SET,
) -> Picture:
    """Render for a portrait framebuffer of `size`; landscape output is rotated to fit it."""
    canvas = _framebuffer_canvas(size, orientation)
    return _Dashboard(forecast, locale, LAYOUTS[orientation], icon_set, canvas).render()


def render_error(
    error: ErrorCode,
    detail: str,
    size: tuple[int, int] = SCREEN_SIZE,
    orientation: str = "portrait",
) -> Picture:
    """Full-screen error, in English, shown when there is no dashboard to keep."""
    width, height = LAYOUTS[orientation].size
    draw = _framebuffer_canvas(size, orientation)
    max_width = width - 2 * MARGIN
    detail_font = Font(ROBOTO, 20)
    lines = [
        (f"Error {error.code}", Font(ROBOTO_BOLD, 90), INK),
        (error.text, _shrink_to_fit(draw, error.text, Font(ROBOTO_BOLD, 34), max_width), INK),
        ("Next attempt in one hour", Font(ROBOTO, 26), GRAY_DARK),
        (_truncate(draw, " ".join(detail.split()), detail_font, max_width), detail_font, GRAY_MID),
    ]
    # The lines stacked and centered on the screen.
    boxes = [draw.textbbox((0, 0), text, font=font) for text, font, _ in lines]
    gap = 36
    y = (height - sum(box[3] - box[1] for box in boxes) - gap * (len(lines) - 1)) / 2
    for (text, font, fill), box in zip(lines, boxes):
        draw_centered_text(draw, width / 2, y - box[1], text, font, fill)
        y += box[3] - box[1] + gap

    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
    draw_centered_text(draw, width / 2, height - 60, stamp, Font(ROBOTO, 16), GRAY_MID)
    return draw.picture()


def _framebuffer_canvas(size: tuple[int, int], orientation: str) -> Canvas:
    """Canvas in layout units for a portrait framebuffer of size."""
    layout_width, layout_height = LAYOUTS[orientation].size
    width, height = size
    if orientation == "landscape":
        # Turned a quarter turn: read with the Kindle turned a quarter turn clockwise.
        scale = (height / layout_width, width / layout_height)
        return Canvas(layout_width, layout_height, scale=scale, quarter_turns=1)
    return Canvas(layout_width, layout_height, scale=(width / layout_width, height / layout_height))


def _precipitation_runs(codes: list[int]) -> list[tuple[str, int, int]]:
    """Return (kind, start, end) for each run of consecutive codes of the same precipitation."""
    runs, start = [], 0
    for kind, group in groupby(codes, key=precipitation_kind):
        end = start + len(list(group))
        if kind:
            runs.append((kind, start, end))
        start = end
    return runs


def _legend_kinds(codes: list[int]) -> list[str]:
    """Precipitation kinds among codes, in legend order."""
    present = {precipitation_kind(code) for code in codes}
    return [kind for kind in LEGEND_KINDS if kind in present]


def _shrink_to_fit(draw, text: str, font: Font, max_width: float) -> Font:
    while text_width(draw, text, font) > max_width and font.size > 16:
        font = font.variant(font.size - 1)
    return font


def _truncate(draw, text: str, font: Font, max_width: float) -> str:
    if text_width(draw, text, font) <= max_width:
        return text
    while text and text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _draw_symbol(draw, kind: str, x: float, y: float) -> None:
    if kind == "storm":
        draw_bolt(draw, x, y, 16)
    else:
        draw_asterisk(draw, x, y, 5.5, 1.5)


class _Dashboard:
    def __init__(
        self, forecast: Forecast, locale: Locale, layout: Layout, icon_set: str, canvas: Canvas
    ):
        self.forecast = forecast
        self.locale = locale
        self.layout = layout
        self.icons = ICON_SETS[icon_set]
        self.width, self.height = layout.size
        self.draw = canvas
        self.fonts = {name: Font(path, size) for name, (path, size) in FONT_SPECS.items()}

    def render(self) -> Picture:
        y = self._summary(self.layout.top)
        if self.forecast.upcoming_days:
            y = self._upcoming_days(y + 14)
        y = self._precipitation_banner(y + 14)
        y = self._temperature_chart(y + 22)
        y = self._hourly_table(y + 80)
        self._footer(y + self.layout.footer_gap)
        return self.draw.picture()

    def _separator(self, y: float) -> None:
        self.draw.line([(MARGIN, y), (self.width - MARGIN, y)], fill=GRAY_LIGHT, width=2)

    def _summary(self, top: int) -> int:
        """Today's card: date on top; city and icon, temperature, min and max; details panel."""
        draw, fonts, forecast = self.draw, self.fonts, self.forecast
        bottom = top + self.layout.card_height
        panel_width, padding = self.layout.panel_width, 24
        draw.rounded_rectangle(
            [MARGIN, top, self.width - MARGIN, bottom], radius=22, fill=GRAY_PALE
        )
        date = self.locale.format_long_date(forecast.observed_at)
        draw_centered_text(draw, self.width // 2, top + 20, date, fonts["date"], INK)

        body_top, body_bottom = top + 70, bottom - 18
        center_y = (body_top + body_bottom) // 2
        divider_x = self.width - MARGIN - panel_width - 2 * padding
        draw.line([(divider_x, body_top), (divider_x, body_bottom)], fill=GRAY_LIGHT, width=2)
        left, right = MARGIN + padding, divider_x - padding

        place = forecast.place_name.upper()
        place_box = draw.textbbox((0, 0), place, font=fonts["location"])
        place_column = max(130, place_box[2] - place_box[0])
        draw_centered_text(
            draw,
            left + place_column / 2,
            body_top - place_box[1],
            place,
            fonts["location"],
            GRAY_DARK,
        )
        icon_top = body_top + place_box[3] - place_box[1] + 12
        self.icons.draw(
            draw, forecast.today.weather_code, (left, icon_top, left + place_column, body_bottom)
        )

        max_text = f"Max {round(forecast.today.temperature_max)}°"
        min_text = f"Min {round(forecast.today.temperature_min)}°"
        min_max_width = max(text_width(draw, t, fonts["min_max"]) for t in (max_text, min_text))
        min_max_x = right - min_max_width
        min_max = [(max_text, fonts["min_max"], INK), (min_text, fonts["min_max"], GRAY_DARK)]
        self._text_stack(min_max_x, center_y, min_max, 14)

        # Temperature and description, centered between the city column and min/max.
        temperature = f"{forecast.today.temperature_mean}°"
        description = self.locale.describe(forecast.today.weather_code)
        space_left, space_right = left + place_column + 30, min_max_x - 30
        description_font = _shrink_to_fit(
            draw, description, fonts["description"], space_right - space_left
        )
        block_width = max(
            text_width(draw, temperature, fonts["temperature"]),
            text_width(draw, description, description_font),
        )
        block_x = (space_left + space_right - block_width) / 2
        main = [(temperature, fonts["temperature"], INK), (description, description_font, INK)]
        self._text_stack(block_x, center_y, main, 18)

        self._details_panel(divider_x + padding, center_y, panel_width)
        return bottom

    def _text_stack(self, x: float, center_y: float, lines, gap: int) -> None:
        """Draw (text, font, fill) lines left-aligned at x, centered on center_y by their ink."""
        boxes = [self.draw.textbbox((0, 0), text, font=font) for text, font, _ in lines]
        heights = [box[3] - box[1] for box in boxes]
        y = center_y - (sum(heights) + gap * (len(lines) - 1)) / 2
        for (text, font, fill), box, height in zip(lines, boxes, heights):
            self.draw.text((x, y - box[1]), text, font=font, fill=fill)
            y += height + gap

    def _details_panel(self, left: int, center_y: int, width: int) -> None:
        hours = self.forecast.hours
        labels = self.locale.labels
        humidity = round(sum(h.humidity for h in hours) / len(hours))
        wind = round(sum(h.wind_speed for h in hours) / len(hours))
        # Row by row: sunrise and humidity, then sunset and wind.
        cells = (
            (labels["sunrise"], self.forecast.sunrise or "—", "sunrise"),
            (labels["humidity"], f"{humidity} %", "humidity"),
            (labels["sunset"], self.forecast.sunset or "—", "sunset"),
            (labels["wind"], f"{wind} km/h", "wind"),
        )
        cell_height, icon_size, inset = 64, 34, 14
        top = center_y - (cell_height + 50) // 2
        # Fixed grid so icons and labels stay aligned across rows of different text widths.
        for i, (label, value, kind) in enumerate(cells):
            row, column = divmod(i, 2)
            cell_left = left + column * (width // 2)
            y = top + row * cell_height
            icon_left, icon_top = cell_left + inset, y + 20 - icon_size // 2
            self.icons.draw(
                self.draw, kind, (icon_left, icon_top, icon_left + icon_size, icon_top + icon_size)
            )
            text_x = icon_left + icon_size + 10
            self.draw.text((text_x, y + 2), label, font=self.fonts["panel_label"], fill=GRAY_DARK)
            self.draw.text((text_x, y + 24), value, font=self.fonts["panel_value"], fill=INK)

    def _upcoming_days(self, top: int) -> int:
        """One box per upcoming day: short date, weather icon, mean temperature."""
        days = self.forecast.upcoming_days
        height, gap = self.layout.days_height, 12
        width = (self.width - 2 * MARGIN - (len(days) - 1) * gap) / len(days)
        date_font, temperature_font = self.fonts["day"], self.fonts["day_temperature"]
        for i, day in enumerate(days):
            left = round(MARGIN + i * (width + gap))
            right, bottom = round(left + width), top + height
            center_x = (left + right) / 2
            self.draw.rounded_rectangle(
                [left, top, right, bottom], radius=16, outline=GRAY_LIGHT, width=2
            )
            label = self.locale.format_short_date(day.date)
            draw_centered_text(self.draw, center_x, top + 12, label, date_font, INK)
            temperature = f"{day.temperature_mean}°"
            temperature_box = self.draw.textbbox((0, 0), temperature, font=temperature_font)
            temperature_y = bottom - 12 - temperature_box[3]
            draw_centered_text(
                self.draw, center_x, temperature_y, temperature, temperature_font, INK
            )
            icon_box = (
                left + 18,
                top + 46,
                right - 18,
                temperature_y + temperature_box[1] - 10,
            )
            self.icons.draw(self.draw, day.weather_code, icon_box)
        return top + height

    def _precipitation_banner(self, top: int) -> int:
        height = 46
        font = self.fonts["banner"]
        risk = self.forecast.precipitation_risk
        text = self.locale.labels[f"{risk}_risk" if risk else "no_precipitation"]
        self.draw.rounded_rectangle(
            [MARGIN, top, self.width - MARGIN, top + height],
            radius=height // 2,
            outline=INK,
            width=3,
        )
        box = self.draw.textbbox((0, 0), text, font=font)
        text_y = top + (height - (box[3] - box[1])) // 2 - box[1]
        if not risk:
            draw_centered_text(self.draw, self.width // 2, text_y, text, font, INK)
            return top + height

        # Center icon and text as one group, the icon sized by its actual ink.
        code, gap = BANNER_ICONS[risk], 12
        icon_top, icon_bottom = top + 9, top + height - 9
        icon_width, _ = self.icons.ink_size(code, (0, icon_top, 44, icon_bottom))
        group_left = self.width / 2 - (icon_width + gap + box[2] - box[0]) / 2
        icon_box = (group_left, icon_top, group_left + icon_width, icon_bottom)
        self.icons.draw(self.draw, code, icon_box)
        self.draw.text((group_left + icon_width + gap - box[0], text_y), text, font=font, fill=INK)
        return top + height

    def _temperature_chart(self, separator_y: int) -> int:
        draw, forecast, font = self.draw, self.forecast, self.fonts["axis"]
        self._separator(separator_y)
        left, right = MARGIN + 50, self.width - MARGIN - 10
        top = separator_y + 30
        bottom = top + self.layout.chart_height

        samples = [(i / WINDOW_HOURS, h) for i, h in enumerate(forecast.hours)]
        if forecast.window_end:
            samples.append((1.0, forecast.window_end))
        low = min(h.temperature for _, h in samples)
        high = max(h.temperature for _, h in samples)
        span = max(high - low, 1)

        def y_of(temperature: float) -> float:
            return bottom - (temperature - low) / span * (bottom - top)

        for fraction in (0, 0.5, 1):
            y = bottom - fraction * (bottom - top)
            draw.line([left, y, right, y], fill=GRAY_LIGHT, width=1)
        draw.text((MARGIN, top - 12), f"{round(high)}°", font=font, fill=GRAY_DARK)
        draw.text((MARGIN, bottom - 12), f"{round(low)}°", font=font, fill=GRAY_DARK)

        points = [(left + f * (right - left), y_of(h.temperature)) for f, h in samples]
        draw.polygon([(left, bottom), *points, (right, bottom)], fill=GRAY_PALE)
        # Segment k (point k to k+1) takes the weather of its starting hour.
        runs = _precipitation_runs([h.weather_code for _, h in samples[:-1]])
        self._pattern_under_curve(points, runs, (left, top, right, bottom))
        draw.line(points, fill=INK, width=4)

        for (x, y), (_, entry) in list(zip(points, samples))[::3]:
            self._chart_tick(x, y, f"{entry.hour:02d}:00", right, bottom)

        kinds = _legend_kinds([entry.weather_code for entry in forecast.hours])
        if kinds:
            self._legend(kinds, (left + right) / 2, bottom + 44)
        return bottom

    def _chart_tick(self, x: float, y: float, label: str, right: int, axis_y: int) -> None:
        font = self.fonts["axis"]
        self.draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=INK)
        label_width = text_width(self.draw, label, font)
        label_x = min(x - label_width / 2, right - label_width)
        self.draw.text((label_x, axis_y + 12), label, font=font, fill=GRAY_DARK)

    def _pattern_under_curve(self, points, runs, box) -> None:
        bottom = box[3]
        for kind in PRECIPITATION_KINDS:
            areas = [
                [(run[0][0], bottom), *run, (run[-1][0], bottom)]
                for run in (points[start : end + 1] for k, start, end in runs if k == kind)
            ]
            if areas:
                self._fill_pattern(kind, areas, box)

    def _fill_pattern(self, kind: str, areas, box) -> None:
        """Draw the pattern of kind over box, only inside the areas polygons."""
        with self.draw.clip(areas):
            if kind == "rain":
                draw_diagonal_hatch(self.draw, box, spacing=9, width=2)
            else:
                spacing = 22 if kind == "storm" else 17
                draw_symbol_grid(
                    self.draw, box, spacing, lambda d, x, y: _draw_symbol(d, kind, x, y)
                )

    def _legend(self, kinds: list[str], center_x: float, top: int) -> None:
        font = self.fonts["axis"]
        swatch_width, swatch_height, gap, spacing = 34, 18, 8, 28
        labels = [self.locale.labels[kind] for kind in kinds]
        widths = [swatch_width + gap + text_width(self.draw, label, font) for label in labels]
        x = round(center_x - (sum(widths) + spacing * (len(kinds) - 1)) / 2)
        for kind, label, width in zip(kinds, labels, widths):
            box = (x, top, x + swatch_width, top + swatch_height)
            self.draw.rectangle(box, fill=GRAY_PALE)
            if kind == "rain":
                left, top_, right, bottom = box
                self._fill_pattern(
                    kind, [[(left, top_), (right, top_), (right, bottom), (left, bottom)]], box
                )
            else:
                _draw_symbol(self.draw, kind, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            self.draw.rectangle(box, outline=GRAY_MID, width=1)
            text_box = self.draw.textbbox((0, 0), label, font=font)
            text_y = top + (swatch_height - (text_box[3] - text_box[1])) / 2 - text_box[1]
            self.draw.text((box[2] + gap - text_box[0], text_y), label, font=font, fill=GRAY_DARK)
            x += round(width) + spacing

    def _hourly_table(self, separator_y: int) -> int:
        draw, fonts = self.draw, self.fonts
        self._separator(separator_y)
        # Every other hour of the window, read down each column.
        entries = self.forecast.hours[::2]
        columns = self.layout.table_columns
        rows = -(-len(entries) // columns)
        row_height = self.layout.row_height
        top, gap, icon_zone = separator_y + 18, self.layout.column_gap, 42
        column_width = (self.width - 2 * MARGIN - (columns - 1) * gap) // columns

        for row in range(rows):
            y = top + row * row_height
            middle = y + row_height // 2
            if row % 2:
                draw.rectangle([MARGIN, y, self.width - MARGIN, y + row_height], fill=GRAY_PALE)
            for column in range(columns):
                index = column * rows + row
                if index >= len(entries):
                    continue
                entry = entries[index]
                column_left = MARGIN + column * (column_width + gap)
                icon_box = (column_left, middle - 17, column_left + 34, middle + 17)
                self.icons.draw(draw, entry.weather_code, icon_box)
                hour_x, temp_x, humidity_x, wind_x = (
                    column_left + icon_zone + round(share * (column_width - icon_zone))
                    for share in TABLE_CELLS
                )
                draw.text(
                    (hour_x, middle - 12), f"{entry.hour:02d}:00", font=fonts["row"], fill=INK
                )
                draw.text(
                    (temp_x, middle - 12),
                    f"{round(entry.temperature)}{self.forecast.temperature_unit}",
                    font=fonts["row"],
                    fill=INK,
                )
                self.icons.draw(
                    draw,
                    "humidity",
                    (humidity_x, middle - 13, humidity_x + 22, middle + 13),
                    fill=GRAY_DARK,
                )
                draw.text(
                    (humidity_x + 28, middle - 10),
                    f"{entry.humidity} %",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )
                self.icons.draw(
                    draw,
                    "wind",
                    (wind_x, middle - 13, wind_x + 26, middle + 13),
                    fill=GRAY_DARK,
                )
                draw.text(
                    (wind_x + 30, middle - 10),
                    f"{round(entry.wind_speed)} km/h",
                    font=fonts["row_small"],
                    fill=GRAY_DARK,
                )

        bottom = top + rows * row_height
        for column in range(1, columns):
            divider_x = MARGIN + column * (column_width + gap) - gap // 2
            draw.line(
                [(divider_x, top + 6), (divider_x, bottom - 6)],
                fill=GRAY_LIGHT,
                width=2,
            )
        return bottom

    def _footer(self, y: int) -> None:
        text = self.locale.format_updated_at(self.forecast.observed_at)
        draw_centered_text(self.draw, self.width // 2, y, text, self.fonts["footer"], GRAY_MID)

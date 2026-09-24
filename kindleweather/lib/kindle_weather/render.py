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
    draw_battery,
    draw_bolt,
    draw_centered_text,
    draw_diagonal_hatch,
    draw_symbol_grid,
    text_width,
)
from kindle_weather.i18n import Locale
from kindle_weather.icons import DEFAULT_ICON_SET, ICON_SETS, IconSet
from kindle_weather.weather import (
    PRECIPITATION_KINDS,
    WINDOW_HOURS,
    Forecast,
    moon_phase,
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
    "day_temperature": (ROBOTO_BOLD, 28),
    "banner": (ROBOTO_BOLD, 24),
    "axis": (ROBOTO, 18),
    "row": (ROBOTO_BOLD, 26),
    "row_small": (ROBOTO, 19),
    "footer": (ROBOTO, 16),
}

# Upper bounds of the UV index levels (low, moderate, high, very high; then
# extreme), and of the European air quality index levels (good, fair,
# moderate, poor, very poor; then extremely poor).
UV_LEVELS = (3, 6, 8, 11)
AIR_LEVELS = (20, 40, 60, 80, 100)

# Left to right order of the chart legend.
LEGEND_KINDS = ("rain", "snow", "storm")

# Icon shown in the precipitation banner for each kind.
BANNER_ICONS = {"snow": 73, "storm": 95, "rain": 63}

# Start of the hour, temperature, humidity and wind cells, as a share of a table
# column; wind gets the widest cell since it holds an icon and "km/h".
TABLE_CELLS = (0, 0.26, 0.48, 0.71)


@dataclass(frozen=True)
class Layout:
    """Sizes of the dashboard sections for one orientation, in layout units."""

    size: tuple[int, int]
    top: int
    # Today's card: the current weather, then two rows of details.
    main_height: int
    detail_row_height: int
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
        main_height=160,
        detail_row_height=62,
        days_height=150,
        chart_height=190,
        table_columns=2,
        row_height=62,
        column_gap=40,
        footer_gap=44,
    ),
    "landscape": Layout(
        size=(1448, 1072),
        top=28,
        main_height=140,
        detail_row_height=56,
        days_height=130,
        chart_height=80,
        table_columns=3,
        row_height=48,
        column_gap=24,
        footer_gap=26,
    ),
}


def render_dashboard(
    forecast: Forecast,
    locale: Locale,
    *,
    size: tuple[int, int] = SCREEN_SIZE,
    orientation: str = "portrait",
    icon_set: str = DEFAULT_ICON_SET,
    clock: str = "24h",
    theme: str = "light",
    next_update: datetime | None = None,
    battery: int | None = None,
) -> Picture:
    """Render for a portrait framebuffer of `size`; landscape output is rotated to fit it."""
    canvas = _framebuffer_canvas(size, orientation)
    dashboard = _Dashboard(
        forecast,
        locale,
        LAYOUTS[orientation],
        ICON_SETS[icon_set],
        canvas,
        clock,
        next_update,
        dark=theme == "dark",
    )
    return _themed(dashboard.render(battery), theme)


def render_error(
    error: ErrorCode,
    detail: str,
    size: tuple[int, int] = SCREEN_SIZE,
    orientation: str = "portrait",
    theme: str = "light",
) -> Picture:
    """Full-screen error, in English, shown when there is no dashboard to keep."""
    width, height = LAYOUTS[orientation].size
    draw = _framebuffer_canvas(size, orientation)
    max_width = width - 2 * MARGIN
    detail_font = Font(ROBOTO, 20)
    lines = [
        (f"Error {error.code}", Font(ROBOTO_BOLD, 90), INK),
        (error.text, _shrink_to_fit(draw, error.text, Font(ROBOTO_BOLD, 34), max_width), INK),
        ("Next attempt at the next refresh", Font(ROBOTO, 26), GRAY_DARK),
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
    return _themed(draw.picture(), theme)


def _themed(picture: Picture, theme: str) -> Picture:
    """The dark theme is the light one inverted: white on black, grays swapped."""
    return picture.inverted() if theme == "dark" else picture


def _level(value: float, bounds: tuple[int, ...]) -> int:
    """Index of the level of value, given the upper bound of each level but the last."""
    return next((i for i, bound in enumerate(bounds) if value < bound), len(bounds))


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


def _time_text(hour: int, minute: int, clock: str) -> str:
    """ "14:05" with the 24-hour clock, "2:05 PM" with the 12-hour one."""
    if clock == "12h":
        return f"{(hour - 1) % 12 + 1}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    return f"{hour:02d}:{minute:02d}"


def _hour_text(hour: int, clock: str) -> str:
    """ "14:00" with the 24-hour clock, the shorter "2 PM" with the 12-hour one."""
    if clock == "12h":
        return f"{(hour - 1) % 12 + 1} {'AM' if hour < 12 else 'PM'}"
    return f"{hour:02d}:00"


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
        self,
        forecast: Forecast,
        locale: Locale,
        layout: Layout,
        icons: IconSet,
        canvas: Canvas,
        clock: str,
        next_update: datetime | None,
        dark: bool,
    ):
        self.forecast = forecast
        self.locale = locale
        self.layout = layout
        self.icons = icons
        self.clock = clock
        self.next_update = next_update
        self.dark = dark
        self.width, self.height = layout.size
        self.draw = canvas
        self.fonts = {name: Font(path, size) for name, (path, size) in FONT_SPECS.items()}

    def render(self, battery: int | None) -> Picture:
        y = self._summary(self.layout.top)
        if self.forecast.upcoming_days:
            y = self._upcoming_days(y + 14)
        y = self._precipitation_banner(y + 14)
        y = self._temperature_chart(y + 22)
        y = self._hourly_table(y + 80)
        self._footer(y + self.layout.footer_gap, battery)
        return self.draw.picture()

    def _clock_time(self, text: str | None) -> str:
        """An "HH:MM" time of the forecast, on the configured clock."""
        if not text:
            return "—"
        hour, minute = text.split(":")
        return _time_text(int(hour), int(minute), self.clock)

    def _separator(self, y: float) -> None:
        self.draw.line([(MARGIN, y), (self.width - MARGIN, y)], fill=GRAY_LIGHT, width=2)

    def _summary(self, top: int) -> int:
        """Today's card: the date; the current weather with the day's max and min;
        then two rows of details, from sunrise to the moon phase."""
        draw, fonts, forecast, layout = self.draw, self.fonts, self.forecast, self.layout
        main_top = top + 70
        main_bottom = main_top + layout.main_height
        grid_top = main_bottom + 16
        bottom = grid_top + 2 * layout.detail_row_height + 12
        draw.rounded_rectangle(
            [MARGIN, top, self.width - MARGIN, bottom], radius=22, fill=GRAY_PALE
        )
        date = self.locale.format_long_date(forecast.observed_at)
        draw_centered_text(draw, self.width // 2, top + 20, date, fonts["date"], INK)
        left, right = MARGIN + 24, self.width - MARGIN - 24
        center_y = (main_top + main_bottom) / 2

        # The city over the weather icon, on the left.
        place = forecast.place_name.upper()
        place_box = draw.textbbox((0, 0), place, font=fonts["location"])
        place_column = max(150, place_box[2] - place_box[0])
        draw_centered_text(
            draw,
            left + place_column / 2,
            main_top - place_box[1],
            place,
            fonts["location"],
            GRAY_DARK,
        )
        icon_top = main_top + place_box[3] - place_box[1] + 12
        self.icons.draw(
            draw, forecast.current.weather_code, (left, icon_top, left + place_column, main_bottom)
        )

        # The day's max and min, on the right.
        max_text = f"Max {self._temperature(forecast.today.temperature_max)}"
        min_text = f"Min {self._temperature(forecast.today.temperature_min)}"
        min_max_width = max(text_width(draw, t, fonts["min_max"]) for t in (max_text, min_text))
        min_max_x = right - min_max_width
        min_max = [(max_text, fonts["min_max"], INK), (min_text, fonts["min_max"], GRAY_DARK)]
        self._text_stack(min_max_x, center_y, min_max, 14)

        # The temperature and description, centered between them; both shrink
        # if needed, such as for "-12°C" or a long description.
        temperature = self._temperature(forecast.current.temperature)
        description = self.locale.describe(forecast.current.weather_code)
        space_left, space_right = left + place_column + 30, min_max_x - 30
        space = space_right - space_left
        temperature_font = _shrink_to_fit(draw, temperature, fonts["temperature"], space)
        description_font = _shrink_to_fit(draw, description, fonts["description"], space)
        block_width = max(
            text_width(draw, temperature, temperature_font),
            text_width(draw, description, description_font),
        )
        block_x = (space_left + space_right - block_width) / 2
        main = [(temperature, temperature_font, INK), (description, description_font, INK)]
        self._text_stack(block_x, center_y, main, 18)

        draw.line([(left, main_bottom + 6), (right, main_bottom + 6)], fill=GRAY_LIGHT, width=2)
        self._details_grid(left, right, grid_top)
        return bottom

    def _text_stack(self, x: float, center_y: float, lines, gap: int) -> None:
        """Draw (text, font, fill) lines left-aligned at x, centered on center_y by their ink."""
        boxes = [self.draw.textbbox((0, 0), text, font=font) for text, font, _ in lines]
        heights = [box[3] - box[1] for box in boxes]
        y = center_y - (sum(heights) + gap * (len(lines) - 1)) / 2
        for (text, font, fill), box, height in zip(lines, boxes, heights):
            self.draw.text((x, y - box[1]), text, font=font, fill=fill)
            y += height + gap

    def _details_grid(self, left: float, right: float, top: float) -> None:
        """Two rows of four details, each an icon over its label and value."""
        forecast, labels, locale = self.forecast, self.locale.labels, self.locale
        current = forecast.current
        uv, air = forecast.uv_index, forecast.air_quality
        phase = round(moon_phase(forecast.observed_at.date()) * 8) % 8
        # The moon's lit part must end up light: black before the dark theme
        # inverts the picture. Half a cycle later, the shadow has the lit
        # part's shape.
        moon_icon = (phase + 4) % 8 if self.dark != self.icons.moon_draws_lit else phase
        rows = (
            (
                ("sunrise", labels["sunrise"], self._clock_time(forecast.sunrise)),
                ("sunset", labels["sunset"], self._clock_time(forecast.sunset)),
                ("humidity", labels["humidity"], f"{round(current.humidity)} %"),
                ("wind", labels["wind"], f"{round(current.wind_speed)} {forecast.wind_unit}"),
            ),
            (
                ("feels_like", labels["feels_like"], self._temperature(current.feels_like)),
                (
                    "uv",
                    labels["uv"],
                    "—"
                    if uv is None
                    else f"{round(uv)} · {locale.uv_levels[_level(uv, UV_LEVELS)]}",
                ),
                (
                    "air",
                    labels["air"],
                    "—" if air is None else f"{air} · {locale.air_levels[_level(air, AIR_LEVELS)]}",
                ),
                (f"moon{moon_icon}", labels["moon"], locale.moon_phases[phase]),
            ),
        )

        # Columns as wide as their widest cell, plus an equal share of the
        # rest: the cells line up in both rows, and a long moon phase name
        # keeps its size.
        label_font, value_font = self.fonts["panel_label"], self.fonts["panel_value"]
        icon_size, gap, padding = 34, 10, 20

        def need(cell) -> float:
            _, label, value = cell
            words = max(
                text_width(self.draw, label, label_font), text_width(self.draw, value, value_font)
            )
            return icon_size + gap + words + padding

        needs = [max(need(row[column]) for row in rows) for column in range(4)]
        room, spare = right - left, right - left - sum(needs)
        widths = [need + spare / 4 if spare > 0 else need * room / sum(needs) for need in needs]
        row_height = self.layout.detail_row_height
        x = left
        for column, width in enumerate(widths):
            if column:
                self.draw.line(
                    [(x - padding / 2, top + 4), (x - padding / 2, top + 2 * row_height - 4)],
                    fill=GRAY_LIGHT,
                    width=2,
                )
            for row_index, row in enumerate(rows):
                icon, label, value = row[column]
                middle = top + row_index * row_height + row_height / 2
                self.icons.draw(
                    self.draw,
                    icon,
                    (x, middle - icon_size / 2, x + icon_size, middle + icon_size / 2),
                )
                text_x = x + icon_size + gap
                space = x + width - padding - text_x
                fitted_label = _shrink_to_fit(self.draw, label, label_font, space)
                fitted_value = _shrink_to_fit(self.draw, value, value_font, space)
                # Fixed lines, so that the cells line up.
                self.draw.text((text_x, middle - 24), label, font=fitted_label, fill=GRAY_DARK)
                self.draw.text((text_x, middle - 2), value, font=fitted_value, fill=INK)
            x += width

    def _temperature(self, value: float) -> str:
        return f"{round(value)}{self.forecast.temperature_unit}"

    def _upcoming_days(self, top: int) -> int:
        """One box per upcoming day: short date, weather icon, max and min temperatures."""
        days = self.forecast.upcoming_days
        height, gap = self.layout.days_height, 12
        width = (self.width - 2 * MARGIN - (len(days) - 1) * gap) / len(days)
        date_font = self.fonts["day"]
        for i, day in enumerate(days):
            left = round(MARGIN + i * (width + gap))
            right, bottom = round(left + width), top + height
            center_x = (left + right) / 2
            self.draw.rounded_rectangle(
                [left, top, right, bottom], radius=16, outline=GRAY_LIGHT, width=2
            )
            label = self.locale.format_short_date(day.date)
            draw_centered_text(self.draw, center_x, top + 12, label, date_font, INK)
            # The max in black and the min in gray, of the same size, side by side.
            high, low = (
                self._temperature(day.temperature_max),
                self._temperature(day.temperature_min),
            )
            space = right - left - 28
            high_font = low_font = self.fonts["day_temperature"]
            while (
                text_width(self.draw, high, high_font) + 8 + text_width(self.draw, low, low_font)
                > space
                and high_font.size > 14
            ):
                high_font, low_font = (
                    high_font.variant(high_font.size - 1),
                    low_font.variant(low_font.size - 1),
                )
            high_width = text_width(self.draw, high, high_font)
            pair_left = center_x - (high_width + 8 + text_width(self.draw, low, low_font)) / 2
            high_box = self.draw.textbbox((0, 0), high, font=high_font)
            baseline = bottom - 14
            self.draw.text(
                (pair_left - high_box[0], baseline - high_box[3]), high, font=high_font, fill=INK
            )
            low_box = self.draw.textbbox((0, 0), low, font=low_font)
            self.draw.text(
                (pair_left + high_width + 8 - low_box[0], baseline - low_box[3]),
                low,
                font=low_font,
                fill=GRAY_MID,
            )
            icon_box = (
                left + 18,
                top + 46,
                right - 18,
                baseline - (high_box[3] - high_box[1]) - 10,
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
        unit = forecast.temperature_unit
        draw.text((MARGIN, top - 12), f"{round(high)}{unit}", font=font, fill=GRAY_DARK)
        draw.text((MARGIN, bottom - 12), f"{round(low)}{unit}", font=font, fill=GRAY_DARK)

        points = [(left + f * (right - left), y_of(h.temperature)) for f, h in samples]
        draw.polygon([(left, bottom), *points, (right, bottom)], fill=GRAY_PALE)
        # Segment k (point k to k+1) takes the weather of its starting hour.
        runs = _precipitation_runs([h.weather_code for _, h in samples[:-1]])
        self._pattern_under_curve(points, runs, (left, top, right, bottom))
        draw.line(points, fill=INK, width=4)

        for (x, y), (_, entry) in list(zip(points, samples))[::3]:
            self._chart_tick(x, y, _hour_text(entry.hour, self.clock), right, bottom)

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
                    (hour_x, middle - 12),
                    _hour_text(entry.hour, self.clock),
                    font=fonts["row"],
                    fill=INK,
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
                    f"{round(entry.wind_speed)} {self.forecast.wind_unit}",
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

    def _footer(self, y: int, battery: int | None) -> None:
        """When updated and when next, and the battery of the Kindle, on one line."""
        font = self.fonts["footer"]
        moment = self.forecast.observed_at
        parts = [
            self.locale.format_updated_at(
                moment, _time_text(moment.hour, moment.minute, self.clock)
            )
        ]
        if self.next_update:
            upcoming = self.next_update
            parts.append(
                self.locale.labels["next_update"].format(
                    _time_text(upcoming.hour, upcoming.minute, self.clock)
                )
            )
        text = "  ·  ".join(parts)
        battery_text = f"{battery} %" if battery is not None else ""
        icon_width, icon_height, gap = 26, 13, 6
        extra = (
            (24 + icon_width + gap + text_width(self.draw, battery_text, font))
            if battery_text
            else 0
        )
        left = self.width / 2 - (text_width(self.draw, text, font) + extra) / 2
        box = self.draw.textbbox((0, 0), text, font=font)
        self.draw.text((left - box[0], y), text, font=font, fill=GRAY_MID)
        if battery_text:
            x = left + box[2] - box[0] + 24
            middle = y + (box[1] + box[3]) / 2
            draw_battery(
                self.draw, x, middle - icon_height / 2, icon_width, icon_height, battery, GRAY_MID
            )
            self.draw.text((x + icon_width + gap, y), battery_text, font=font, fill=GRAY_MID)

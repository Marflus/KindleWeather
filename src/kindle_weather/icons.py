"""Icon sets: the built-in drawn icons and two vendored icon fonts.

Every set draws weather icons, by WMO code, and detail icons, by name, scaled to
the largest size whose ink fits a box and centered on it.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from kindle_weather.graphics import (
    INK,
    WHITE,
    draw_droplet,
    draw_sun_horizon,
    draw_weather_icon,
    draw_wind,
)

DETAIL_ICONS = ("sunrise", "sunset", "humidity", "wind")
FONT_DIR = Path(__file__).parent / "icon_fonts"
DEFAULT_ICON_SET = "classic"

# A WMO weather code, or one of DETAIL_ICONS.
Icon = int | str
Box = tuple[float, float, float, float]


class IconSet(ABC):
    def __init__(self) -> None:
        self._bounds_cache: dict[tuple[Icon, float], Box] = {}

    @abstractmethod
    def _paint(self, draw, icon: Icon, x: float, y: float, size: float, fill: int) -> None:
        """Paint icon at size; the ink stays within 3 * size of (x, y)."""

    def _quantize(self, size: float) -> float:
        return size

    def _bounds(self, icon: Icon, size: float) -> Box:
        """Ink bounds of icon painted at size, relative to the point it is painted at."""
        key = (icon, size)
        if key not in self._bounds_cache:
            # Measured on a scratch image: font bounding boxes include the advance, not ink.
            extent = math.ceil(size * 3)
            scratch = Image.new("L", (2 * extent, 2 * extent), WHITE)
            self._paint(ImageDraw.Draw(scratch), icon, extent, extent, size, INK)
            left, top, right, bottom = ImageChops.invert(scratch).getbbox()
            self._bounds_cache[key] = (left - extent, top - extent, right - extent, bottom - extent)
        return self._bounds_cache[key]

    def _fit(self, icon: Icon, box: Box) -> float:
        left, top, right, bottom = box
        reference = 100
        ink_left, ink_top, ink_right, ink_bottom = self._bounds(icon, reference)
        scale = min(
            (right - left) / (ink_right - ink_left), (bottom - top) / (ink_bottom - ink_top)
        )
        return self._quantize(reference * scale)

    def ink_size(self, icon: Icon, box: Box) -> tuple[float, float]:
        """Width and height of the ink draw() would put in box."""
        left, top, right, bottom = self._bounds(icon, self._fit(icon, box))
        return right - left, bottom - top

    def draw(self, draw, icon: Icon, box: Box, fill: int = INK) -> None:
        size = self._fit(icon, box)
        ink_left, ink_top, ink_right, ink_bottom = self._bounds(icon, size)
        x = (box[0] + box[2]) / 2 - (ink_left + ink_right) / 2
        y = (box[1] + box[3]) / 2 - (ink_top + ink_bottom) / 2
        self._paint(draw, icon, x, y, size, fill)


class DrawnIcons(IconSet):
    """The built-in icons, drawn with shapes; weather icons keep their own shades of gray."""

    def _paint(self, draw, icon: Icon, x: float, y: float, r: float, fill: int) -> None:
        if icon == "humidity":
            draw_droplet(draw, x, y, r, fill=fill)
        elif icon == "wind":
            draw_wind(draw, x, y, r, fill=fill)
        elif icon in ("sunrise", "sunset"):
            draw_sun_horizon(draw, x, y, r, rising=icon == "sunrise", fill=fill)
        elif isinstance(icon, int):
            draw_weather_icon(draw, icon, x, y, r)
        else:
            raise KeyError(icon)


class FontIcons(IconSet):
    """Glyphs of an icon font, in a single shade."""

    def __init__(self, font_file: str, weather: dict[int, int], details: dict[str, int]):
        super().__init__()
        self.font_path = str(FONT_DIR / font_file)
        self.weather = weather
        self.details = details
        # Unknown codes fall back to the clear-sky glyph, like the drawn set.
        self.fallback = weather[0]

    def _glyph(self, icon: Icon) -> str:
        if isinstance(icon, str):
            return chr(self.details[icon])
        return chr(self.weather.get(icon, self.fallback))

    def _quantize(self, size: float) -> float:
        return max(1, math.floor(size))

    def _paint(self, draw, icon: Icon, x: float, y: float, size: float, fill: int) -> None:
        draw.text((x, y), self._glyph(icon), font=_font(self.font_path, int(size)), fill=fill)


@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _by_code(groups: dict[tuple[int, ...], int]) -> dict[int, int]:
    return {code: glyph for codes, glyph in groups.items() for code in codes}


# Weather Icons 2.1.0 by Erik Flowers (SIL OFL 1.1), day variants.
WEATHER_ICONS = FontIcons(
    "weathericons.ttf",
    weather=_by_code(
        {
            (0,): 0xF00D,  # day-sunny
            (1,): 0xF00C,  # day-sunny-overcast
            (2,): 0xF002,  # day-cloudy
            (3,): 0xF013,  # cloudy
            (45, 48): 0xF014,  # fog
            (51, 53, 55): 0xF01C,  # sprinkle
            (56, 57): 0xF0B5,  # sleet
            (61, 63, 65): 0xF019,  # rain
            (66, 67): 0xF017,  # rain-mix
            (71, 73, 75, 77, 85, 86): 0xF01B,  # snow
            (80, 81, 82): 0xF01A,  # showers
            (95, 99): 0xF01E,  # thunderstorm
            (96,): 0xF015,  # hail
        }
    ),
    details={"sunrise": 0xF051, "sunset": 0xF052, "humidity": 0xF07A, "wind": 0xF050},
)

# Material Design Icons 7.4.47 by Pictogrammers (Apache 2.0), subset to these glyphs.
MATERIAL_ICONS = FontIcons(
    "materialdesignicons-weather.ttf",
    weather=_by_code(
        {
            (0,): 0xF0599,  # weather-sunny
            (1, 2): 0xF0595,  # weather-partly-cloudy
            (3,): 0xF0590,  # weather-cloudy
            (45, 48): 0xF0591,  # weather-fog
            (51, 53, 55, 61, 63, 80, 81): 0xF0597,  # weather-rainy
            (65, 82): 0xF0596,  # weather-pouring
            (56, 57, 66, 67): 0xF067F,  # weather-snowy-rainy
            (71, 73, 77, 85): 0xF0598,  # weather-snowy
            (75, 86): 0xF0F36,  # weather-snowy-heavy
            (95,): 0xF0593,  # weather-lightning
            (96,): 0xF0592,  # weather-hail
            (99,): 0xF067E,  # weather-lightning-rainy
        }
    ),
    details={"sunrise": 0xF059C, "sunset": 0xF059B, "humidity": 0xF058E, "wind": 0xF059D},
)

ICON_SETS: dict[str, IconSet] = {
    "classic": DrawnIcons(),
    "weather-icons": WEATHER_ICONS,
    "material": MATERIAL_ICONS,
}

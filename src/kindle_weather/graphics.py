"""Grayscale palette, weather icons and text helpers."""

from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw, ImageFont

from kindle_weather.weather import (
    DRIZZLE_CODES,
    FOG_CODES,
    RAIN_CODES,
    SNOW_CODES,
    THUNDERSTORM_CODES,
)

BLACK, INK = 0, 25
GRAY_DARK, GRAY_MID = 90, 150
GRAY_LIGHT, GRAY_PALE = 205, 236
WHITE = 255

# Lightning bolt of the thunderstorm icon, in icon radii from the icon center.
BOLT_SHAPE = ((0.1, 0.35), (-0.25, 0.95), (0.05, 0.95), (-0.2, 1.5), (0.4, 0.7), (0.1, 0.7))


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def draw_centered_text(draw, center_x, y, text, font, fill) -> None:
    # Offset by the bbox left bearing so the ink, not the advance box, is centered.
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    draw.text((center_x - (right - left) / 2 - left, y), text, font=font, fill=fill)


def draw_weather_icon(draw, code: int, cx: float, cy: float, r: float) -> None:
    if code == 1:
        draw_sun(draw, cx - r * 0.12, cy - r * 0.08, r * 0.85, fill=GRAY_DARK)
        draw_cloud(draw, cx + r * 0.35, cy + r * 0.42, r * 0.55)
    elif code == 2:
        draw_sun(draw, cx - r * 0.28, cy - r * 0.22, r * 0.62, fill=GRAY_DARK)
        draw_cloud(draw, cx + r * 0.2, cy + r * 0.28, r * 0.78)
    elif code == 3:
        draw_cloud(draw, cx, cy, r)
    elif code in FOG_CODES:
        for i in range(4):
            y = cy - r * 0.5 + i * r * 0.35
            half = r * (1.3 - i * 0.12)
            draw.rounded_rectangle(
                [cx - half, y - r * 0.06, cx + half, y + r * 0.06], radius=r * 0.06, fill=GRAY_DARK
            )
    elif code in DRIZZLE_CODES:
        draw_cloud(draw, cx, cy - r * 0.15, r * 0.85)
        for x in _three_columns(cx, r):
            draw.line(
                [x, cy + r * 0.5, x - r * 0.15, cy + r * 0.85],
                fill=GRAY_DARK,
                width=max(2, round(r * 0.12)),
            )
    elif code in RAIN_CODES:
        draw_cloud(draw, cx, cy - r * 0.15, r * 0.85)
        for x in _three_columns(cx, r):
            draw.line(
                [x, cy + r * 0.5, x - r * 0.2, cy + r * 1.05],
                fill=BLACK,
                width=max(3, round(r * 0.15)),
            )
    elif code in SNOW_CODES:
        draw_cloud(draw, cx, cy - r * 0.15, r * 0.85)
        flake = r * 0.09
        for x in _three_columns(cx, r):
            y = cy + r * 0.75
            draw.ellipse([x - flake, y - flake, x + flake, y + flake], fill=GRAY_DARK)
    elif code in THUNDERSTORM_CODES:
        draw_cloud(draw, cx, cy - r * 0.2, r * 0.85)
        draw.polygon([(cx + r * dx, cy + r * dy) for dx, dy in BOLT_SHAPE], fill=BLACK)
    else:
        draw_sun(draw, cx, cy, r)


def draw_sun(draw, cx, cy, r, fill=INK) -> None:
    width = max(2, round(r * 0.16))
    for i in range(8):
        angle = i * math.pi / 4
        cos, sin = math.cos(angle), math.sin(angle)
        draw.line(
            [cx + cos * r * 1.35, cy + sin * r * 1.35, cx + cos * r * 1.9, cy + sin * r * 1.9],
            fill=fill,
            width=width,
        )
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def draw_cloud(draw, cx, cy, r, fill=BLACK) -> None:
    puffs = (
        (cx - r * 0.55, cy + r * 0.15, r * 0.55),
        (cx - r * 0.05, cy - r * 0.20, r * 0.68),
        (cx + r * 0.55, cy + r * 0.10, r * 0.52),
    )
    for x, y, radius in puffs:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)
    draw.rounded_rectangle(
        [cx - r * 0.95, cy, cx + r * 0.95, cy + r * 0.55], radius=r * 0.3, fill=fill
    )


def draw_droplet(draw, cx, cy, r, fill=INK) -> None:
    draw.polygon(
        [(cx, cy - r * 1.3), (cx - r * 0.85, cy + r * 0.25), (cx + r * 0.85, cy + r * 0.25)],
        fill=fill,
    )
    draw.ellipse([cx - r * 0.85, cy - r * 0.35, cx + r * 0.85, cy + r * 1.35], fill=fill)


def draw_wind(draw, cx, cy, r, fill=INK) -> None:
    head = r * 0.28
    for i, length in enumerate((1.4, 0.85)):
        y = cy - r * 0.35 + i * r * 0.7
        tail, tip = cx - r * length * 0.65, cx + r * length * 0.65
        draw.line([tail, y, tip, y], fill=fill, width=max(2, round(r * 0.22)))
        draw.polygon([(tip, y - head), (tip, y + head), (tip + head, y)], fill=fill)


def draw_sun_horizon(draw, cx, cy, r, rising: bool, fill=INK) -> None:
    draw.line([cx - r * 1.3, cy, cx + r * 1.3, cy], fill=fill, width=max(2, round(r * 0.12)))
    draw.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=fill)
    start = cy - r * 1.15 if rising else cy - r * 0.35
    tip = start + (-r * 0.5 if rising else r * 0.5)
    draw.line([cx, start, cx, tip], fill=fill, width=max(2, round(r * 0.14)))
    head = r * 0.22
    if rising:
        draw.polygon(
            [(cx - head, tip + head), (cx + head, tip + head), (cx, tip - head)], fill=fill
        )
    else:
        draw.polygon(
            [(cx - head, tip - head), (cx + head, tip - head), (cx, tip + head)], fill=fill
        )


def icon_bounds(code: int, r: float) -> tuple[int, int, int, int]:
    """Ink bounding box of a weather icon, relative to the center it is drawn at."""
    size = math.ceil(r * 6)
    scratch = Image.new("L", (size, size), WHITE)
    draw_weather_icon(ImageDraw.Draw(scratch), code, size / 2, size / 2, r)
    left, top, right, bottom = ImageChops.invert(scratch).getbbox()
    return left - size / 2, top - size / 2, right - size / 2, bottom - size / 2


def draw_diagonal_hatch(draw, box, spacing, width, rising=True, fill=GRAY_DARK) -> None:
    left, top, right, bottom = box
    rise = bottom - top
    for x in range(left - rise, right, spacing):
        if rising:
            draw.line([(x, bottom), (x + rise, top)], fill=fill, width=width)
        else:
            draw.line([(x, top), (x + rise, bottom)], fill=fill, width=width)


def draw_symbol_grid(draw, box, spacing, draw_symbol) -> None:
    """Repeat draw_symbol(draw, x, y) over box on a staggered grid."""
    left, top, right, bottom = box
    for row, y in enumerate(range(top + spacing // 2, bottom, spacing)):
        offset = spacing // 2 if row % 2 else 0
        for x in range(left + offset, right, spacing):
            draw_symbol(draw, x, y)


def draw_asterisk(draw, x, y, radius, width, fill=GRAY_DARK) -> None:
    for angle in (90, 30, 150):
        dx = radius * math.cos(math.radians(angle))
        dy = radius * math.sin(math.radians(angle))
        draw.line([x - dx, y - dy, x + dx, y + dy], fill=fill, width=width)


def draw_bolt(draw, x, y, height, fill=GRAY_DARK) -> None:
    # BOLT_SHAPE spans 1.15 radii, centered on (0.075, 0.925).
    scale = height / 1.15
    draw.polygon(
        [(x + (dx - 0.075) * scale, y + (dy - 0.925) * scale) for dx, dy in BOLT_SHAPE],
        fill=fill,
    )


def _three_columns(cx: float, r: float) -> tuple[float, float, float]:
    return (cx - r * 0.5, cx, cx + r * 0.5)

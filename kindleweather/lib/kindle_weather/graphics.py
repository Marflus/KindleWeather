"""Gray levels, the drawn icons of the "classic" set, chart patterns and text helpers.

Functions take a Canvas as `draw`, and a center and a radius for the icons.
"""

from __future__ import annotations

import math

from kindle_weather.weather import (
    DRIZZLE_CODES,
    FOG_CODES,
    RAIN_CODES,
    SNOW_CODES,
    THUNDERSTORM_CODES,
)

# Gray levels, from 0 (black) to 255 (white).
BLACK, INK = 0, 25
GRAY_DARK, GRAY_MID = 90, 150
GRAY_LIGHT, GRAY_PALE = 205, 236
WHITE = 255

# Lightning bolt of the thunderstorm icon, in icon radii from the icon center.
BOLT_SHAPE = ((0.1, 0.35), (-0.25, 0.95), (0.05, 0.95), (-0.2, 1.5), (0.4, 0.7), (0.1, 0.7))


def text_width(draw, text: str, font) -> float:
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


def draw_thermometer(draw, cx, cy, r, fill=INK) -> None:
    stem = r * 0.28
    draw.rounded_rectangle(
        [cx - stem, cy - r * 1.3, cx + stem, cy + r * 0.5], radius=stem, fill=fill
    )
    draw.ellipse([cx - r * 0.55, cy + r * 0.1, cx + r * 0.55, cy + r * 1.2], fill=fill)
    # The mercury column, in white inside the tube.
    draw.line([cx, cy - r * 1.0, cx, cy + r * 0.6], fill=WHITE, width=max(2, round(r * 0.18)))


def draw_uv(draw, cx, cy, r, fill=INK) -> None:
    """A sun with long rays."""
    width = max(2, round(r * 0.14))
    for i in range(12):
        angle = i * math.pi / 6
        cos, sin = math.cos(angle), math.sin(angle)
        length = 1.9 if i % 2 == 0 else 1.55
        draw.line(
            [cx + cos * r, cy + sin * r, cx + cos * r * length, cy + sin * r * length],
            fill=fill,
            width=width,
        )
    draw.ellipse([cx - r * 0.75, cy - r * 0.75, cx + r * 0.75, cy + r * 0.75], fill=fill)


def draw_leaf(draw, cx, cy, r, fill=INK) -> None:
    """A leaf pointing up and right, with its vein in white."""
    points = []
    for step in range(21):
        t = step / 20
        along, across = (t - 0.5) * 2.6 * r, math.sin(math.pi * t) * 0.8 * r
        points.append((along, across))
    outline = points + [(x, -y) for x, y in reversed(points)]
    # Turned 45 degrees.
    turn = math.radians(-45)
    cos, sin = math.cos(turn), math.sin(turn)
    draw.polygon([(cx + x * cos - y * sin, cy + x * sin + y * cos) for x, y in outline], fill=fill)
    tip, base = (1.3 * r, 0), (-1.75 * r, 0)
    draw.line(
        [(cx + x * cos - y * sin, cy + x * sin + y * cos) for x, y in (base, tip)],
        fill=WHITE,
        width=max(2, round(r * 0.1)),
    )
    draw.line(
        [
            (cx + x * cos - y * sin, cy + x * sin + y * cos)
            for x, y in ((-1.75 * r, 0), (-2.2 * r, 0))
        ],
        fill=fill,
        width=max(2, round(r * 0.14)),
    )


def draw_moon(draw, cx, cy, r, phase: float, fill=INK) -> None:
    """The moon at phase (0 new, 0.5 full): shadow in fill, lit part in white,
    as seen from the northern hemisphere."""
    box = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(box, fill=fill)
    # The terminator is a half ellipse; its width follows the lit fraction.
    terminator = abs(math.cos(2 * math.pi * phase)) * r
    lit_right = phase < 0.5
    draw.pieslice(box, -90 if lit_right else 90, 90 if lit_right else 270, fill=WHITE)
    crescent = phase < 0.25 or phase > 0.75
    draw.ellipse(
        [cx - terminator, cy - r, cx + terminator, cy + r], fill=fill if crescent else WHITE
    )
    draw.ellipse(box, outline=fill, width=max(2, round(r * 0.12)))


def draw_battery(draw, left, top, width, height, level: int, fill=INK) -> None:
    """A battery lying down, filled to level percent."""
    nub = max(2, round(width * 0.08))
    line = max(1, round(height * 0.12))
    body_right = left + width - nub
    draw.rectangle([left, top, body_right, top + height], outline=fill, width=line)
    draw.rectangle([body_right, top + height * 0.3, left + width, top + height * 0.7], fill=fill)
    inset = line * 2
    charge = (body_right - left - 2 * inset) * max(0, min(level, 100)) / 100
    if charge > 0:
        draw.rectangle(
            [left + inset, top + inset, left + inset + charge, top + height - inset], fill=fill
        )

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont

from kindle_weather.i18n import LOCALES
from kindle_weather.icons import DETAIL_ICONS, ICON_SETS

WEATHER_CODES = sorted(int(code) for code in LOCALES["en"].weather)
BOXES = [(20, 30, 80, 70), (10, 10, 40, 90)]


@pytest.mark.parametrize("name", ICON_SETS)
@pytest.mark.parametrize("icon", [*WEATHER_CODES, 12345, *DETAIL_ICONS])
@pytest.mark.parametrize("box", BOXES)
def test_icon_is_drawn_inside_its_box(name, icon, box):
    image = Image.new("L", (100, 100), 255)
    ICON_SETS[name].draw(ImageDraw.Draw(image), icon, box)
    ink = ImageChops.invert(image).getbbox()
    assert ink is not None
    left, top, right, bottom = box
    assert left - 1 <= ink[0] and top - 1 <= ink[1]
    assert ink[2] <= right + 1 and ink[3] <= bottom + 1
    # Fitted to the box: the ink fills at least one of its dimensions.
    fill = max((ink[2] - ink[0]) / (right - left), (ink[3] - ink[1]) / (bottom - top))
    assert fill > 0.8


def _render_glyph(icons, glyph):
    image = Image.new("L", (60, 60), 255)
    ImageDraw.Draw(image).text((5, 5), glyph, font=ImageFont.truetype(icons.font_path, 40))
    return image


@pytest.mark.parametrize("name", ["weather-icons", "material"])
def test_font_sets_map_every_icon_to_a_real_glyph(name):
    icons = ICON_SETS[name]
    assert set(WEATHER_CODES) <= set(icons.weather)
    missing = _render_glyph(icons, chr(0xE000))
    for icon in [*WEATHER_CODES, *DETAIL_ICONS]:
        glyph = _render_glyph(icons, icons._glyph(icon))
        assert ImageChops.difference(glyph, missing).getbbox() is not None, icon


def test_unknown_detail_icon_is_rejected():
    image = Image.new("L", (50, 50), 255)
    for icons in ICON_SETS.values():
        with pytest.raises(KeyError):
            icons.draw(ImageDraw.Draw(image), "moon", (0, 0, 50, 50))

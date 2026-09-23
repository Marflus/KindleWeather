"""Grayscale drawing with cairo and FreeType, called through ctypes.

The Kindle ships both libraries for its own interface, so the dashboard is
drawn on the Kindle with Python's standard library alone: no Pillow to
install. The drawing methods follow Pillow's ImageDraw: coordinates are (x, y)
pairs or flat lists, gray levels go from 0 (black) to 255 (white), and text is
placed by the top-left corner of its line.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import struct
import sys
import zlib
from contextlib import contextmanager, suppress
from functools import lru_cache
from pathlib import Path

WHITE = 255

_FORMAT_RGB24 = 1
_LINE_JOIN_ROUND = 1
_ANTIALIAS_GRAY = 2
# Offset of the blue byte in a native-endian RGB24 pixel; R = G = B in grayscale.
_CHANNEL = 0 if sys.byteorder == "little" else 3


class CanvasError(RuntimeError):
    pass


class _TextExtents(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_double)
        for name in ("x_bearing", "y_bearing", "width", "height", "x_advance", "y_advance")
    ]


class _FontExtents(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_double)
        for name in ("ascent", "descent", "height", "max_x_advance", "max_y_advance")
    ]


# System library folders, the Kindle's first.
LIBRARY_FOLDERS = (
    "/usr/lib",
    "/lib",
    "/usr/local/lib",
    *sorted(str(path) for path in Path("/usr/lib").glob("*-linux-gnu*")),
    *sorted(str(path) for path in Path("/lib").glob("*-linux-gnu*")),
)
# Loaded by Python itself, never replaced.
_CORE_LIBRARIES = ("libc.so", "libm.so", "libdl.so", "libpthread.so", "librt.so", "ld-linux")


def _system_library(soname: str) -> str | None:
    for folder in LIBRARY_FOLDERS:
        path = Path(folder) / soname
        if path.exists():
            return str(path)
    return None


def _needed(path: str) -> list[str]:
    """The DT_NEEDED entries of an ELF shared library: the libraries it links to."""
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF":
        return []
    wide, order = data[4] == 2, "<" if data[5] == 1 else ">"
    if wide:
        (header_offset,) = struct.unpack_from(order + "Q", data, 0x20)
        entry_size, count = struct.unpack_from(order + "HH", data, 0x36)
    else:
        (header_offset,) = struct.unpack_from(order + "I", data, 0x1C)
        entry_size, count = struct.unpack_from(order + "HH", data, 0x2A)
    loads, dynamic = [], None
    for index in range(count):
        offset = header_offset + index * entry_size
        if wide:
            kind, _, file_offset, address, _, size = struct.unpack_from(
                order + "IIQQQQ", data, offset
            )
        else:
            kind, file_offset, address, _, size = struct.unpack_from(order + "IIIII", data, offset)
        if kind == 1:  # PT_LOAD
            loads.append((address, file_offset, size))
        elif kind == 2:  # PT_DYNAMIC
            dynamic = (file_offset, size)
    if dynamic is None:
        return []
    entry_format = order + ("qQ" if wide else "iI")
    step = struct.calcsize(entry_format)
    needed, strings = [], None
    for offset in range(dynamic[0], dynamic[0] + dynamic[1], step):
        tag, value = struct.unpack_from(entry_format, data, offset)
        if tag == 0:  # DT_NULL
            break
        if tag == 1:  # DT_NEEDED
            needed.append(value)
        elif tag == 5:  # DT_STRTAB, an address
            strings = next(
                (
                    base + value - start
                    for start, base, size in loads
                    if start <= value < start + size
                ),
                None,
            )
    if strings is None:
        return []
    return [data[strings + name : data.index(b"\0", strings + name)].decode() for name in needed]


def _preload_dependencies(path: str, seen: set[str]) -> None:
    """Load the system's copies of a library's dependencies, deepest first.

    A Python package may bring its own copies of some libraries, such as
    NiLuJe's Python for Kindle with its FreeType, found first when cairo is
    loaded. The Kindle's cairo needs the Kindle's own FreeType: loaded first,
    by path, it is the copy cairo gets.
    """
    try:
        dependencies = _needed(path)
    except (OSError, struct.error, ValueError):
        return
    for soname in dependencies:
        if soname in seen or soname.startswith(_CORE_LIBRARIES):
            continue
        seen.add(soname)
        system_path = _system_library(soname)
        if system_path is None:
            continue
        _preload_dependencies(system_path, seen)
        with suppress(OSError):
            ctypes.CDLL(system_path, mode=ctypes.RTLD_GLOBAL)


def _load(name: str, soname: str) -> ctypes.CDLL:
    """The library, the system's copy first; find_library covers macOS for the previews."""
    candidates = [_system_library(soname), soname, ctypes.util.find_library(name)]
    errors = []
    for candidate in dict.fromkeys(filter(None, candidates)):
        if candidate.startswith("/"):
            _preload_dependencies(candidate, set())
        try:
            return ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
        except OSError as error:
            errors.append(str(error))
    # The errors say why, such as a missing dependency.
    details = "; ".join(dict.fromkeys(errors)) or "not found"
    raise CanvasError(f"cannot load the {name} library: {details}")


class _Libraries:
    """cairo and FreeType functions, with their C signatures."""

    def __init__(self) -> None:
        # FreeType first, the system's: the copy cairo links to, faces included.
        freetype = _load("freetype", "libfreetype.so.6")
        cairo = _load("cairo", "libcairo.so.2")
        p, d, i = ctypes.c_void_p, ctypes.c_double, ctypes.c_int
        signatures = {
            "cairo_image_surface_create": (p, [i, i, i]),
            "cairo_image_surface_get_data": (ctypes.POINTER(ctypes.c_ubyte), [p]),
            "cairo_image_surface_get_stride": (i, [p]),
            "cairo_surface_flush": (None, [p]),
            "cairo_surface_status": (i, [p]),
            "cairo_surface_destroy": (None, [p]),
            "cairo_create": (p, [p]),
            "cairo_destroy": (None, [p]),
            "cairo_save": (None, [p]),
            "cairo_restore": (None, [p]),
            "cairo_scale": (None, [p, d, d]),
            "cairo_translate": (None, [p, d, d]),
            "cairo_rotate": (None, [p, d]),
            "cairo_set_source_rgb": (None, [p, d, d, d]),
            "cairo_set_source_surface": (None, [p, p, d, d]),
            "cairo_set_line_width": (None, [p, d]),
            "cairo_set_line_join": (None, [p, i]),
            "cairo_new_path": (None, [p]),
            "cairo_new_sub_path": (None, [p]),
            "cairo_move_to": (None, [p, d, d]),
            "cairo_line_to": (None, [p, d, d]),
            "cairo_arc": (None, [p, d, d, d, d, d]),
            "cairo_close_path": (None, [p]),
            "cairo_rectangle": (None, [p, d, d, d, d]),
            "cairo_fill": (None, [p]),
            "cairo_stroke": (None, [p]),
            "cairo_paint": (None, [p]),
            "cairo_clip": (None, [p]),
            "cairo_set_font_face": (None, [p, p]),
            "cairo_set_font_size": (None, [p, d]),
            "cairo_set_font_options": (None, [p, p]),
            "cairo_font_options_create": (p, []),
            "cairo_font_options_set_antialias": (None, [p, i]),
            "cairo_show_text": (None, [p, ctypes.c_char_p]),
            "cairo_text_extents": (None, [p, ctypes.c_char_p, ctypes.POINTER(_TextExtents)]),
            "cairo_font_extents": (None, [p, ctypes.POINTER(_FontExtents)]),
            "cairo_ft_font_face_create_for_ft_face": (p, [p, i]),
        }
        for name, (restype, argtypes) in signatures.items():
            function = getattr(cairo, name)
            function.restype, function.argtypes = restype, argtypes
            setattr(self, name[len("cairo_") :], function)
        self.FT_Init_FreeType = freetype.FT_Init_FreeType
        self.FT_Init_FreeType.argtypes = [ctypes.POINTER(p)]
        self.FT_New_Face = freetype.FT_New_Face
        self.FT_New_Face.argtypes = [p, ctypes.c_char_p, ctypes.c_long, ctypes.POINTER(p)]
        library = p()
        if self.FT_Init_FreeType(ctypes.byref(library)):
            raise CanvasError("FreeType could not be initialized")
        self.freetype = library
        self.font_options = self.font_options_create()
        self.font_options_set_antialias(self.font_options, _ANTIALIAS_GRAY)


@lru_cache(maxsize=None)
def _libraries() -> _Libraries:
    return _Libraries()


@lru_cache(maxsize=None)
def _font_face(path: str) -> int:
    libs = _libraries()
    face = ctypes.c_void_p()
    if libs.FT_New_Face(libs.freetype, path.encode(), 0, ctypes.byref(face)):
        raise CanvasError(f"cannot load font {path}")
    # The FreeType face stays loaded for the life of the process, as cairo requires.
    return libs.ft_font_face_create_for_ft_face(face, 0)


class Font:
    """A TrueType font at a size in pixels, like ImageFont.truetype."""

    def __init__(self, path: str | Path, size: float):
        self.path = str(path)
        self.size = size

    def variant(self, size: float) -> Font:
        return Font(self.path, size)


class Picture:
    """An 8-bit grayscale image, one byte per pixel, row after row."""

    def __init__(self, width: int, height: int, pixels: bytes):
        self.width, self.height, self.pixels = width, height, pixels

    def rows(self):
        for y in range(self.height):
            yield self.pixels[y * self.width : (y + 1) * self.width]

    def ink_bbox(self) -> tuple[int, int, int, int] | None:
        """Bounds of the non-white pixels, as Pillow's getbbox on the inverted image."""
        white = bytes([WHITE])
        left, right, top, bottom = self.width, 0, None, 0
        for y, row in enumerate(self.rows()):
            ink = row.rstrip(white)
            if ink:
                top = y if top is None else top
                bottom = y + 1
                right = max(right, len(ink))
                left = min(left, self.width - len(row.lstrip(white)))
        return None if top is None else (left, top, right, bottom)

    # Used by scripts/previews.py.

    def crop(self, box: tuple[int, int, int, int]) -> Picture:
        left, top, right, bottom = box
        rows = list(self.rows())[top:bottom]
        return Picture(right - left, bottom - top, b"".join(row[left:right] for row in rows))

    def rotated(self, clockwise: bool) -> Picture:
        """The picture turned a quarter turn."""
        canvas = Canvas(self.width, self.height, quarter_turns=-1 if clockwise else 1)
        canvas.paste(self, (0, 0))
        return canvas.picture()

    def png(self) -> bytes:
        """The picture as an 8-bit grayscale PNG, the format eips displays."""

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 0, 0, 0, 0)
        # Filter type 0 (none) at the start of every row.
        raw = b"".join(b"\x00" + row for row in self.rows())
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.png())


class Canvas:
    """A white grayscale drawing surface of width x height drawing units.

    scale maps drawing units to pixels. With quarter_turns, the drawing is
    turned counterclockwise that many quarter turns on the surface, like
    Pillow's ROTATE_90; the surface is then height x width.
    """

    def __init__(
        self,
        width: int,
        height: int,
        scale: tuple[float, float] = (1.0, 1.0),
        quarter_turns: int = 0,
    ):
        self._libs = libs = _libraries()
        pixel_width, pixel_height = round(width * scale[0]), round(height * scale[1])
        if quarter_turns % 2:
            pixel_width, pixel_height = pixel_height, pixel_width
        self.width, self.height = pixel_width, pixel_height
        self._surface = libs.image_surface_create(_FORMAT_RGB24, pixel_width, pixel_height)
        if libs.surface_status(self._surface):
            raise CanvasError(f"cannot create a {width}x{height} surface")
        self._cr = libs.create(self._surface)
        libs.set_font_options(self._cr, libs.font_options)
        libs.set_line_join(self._cr, _LINE_JOIN_ROUND)
        self._fill(WHITE)
        libs.paint(self._cr)
        turns = quarter_turns % 4
        if turns:
            # Move the origin to the corner the drawing's top-left lands on.
            origin = {1: (0, pixel_height), 2: (pixel_width, pixel_height), 3: (pixel_width, 0)}
            libs.translate(self._cr, *origin[turns])
            libs.rotate(self._cr, -turns * math.pi / 2)
        libs.scale(self._cr, *scale)

    def __del__(self) -> None:
        libs = getattr(self, "_libs", None)
        if libs and getattr(self, "_cr", None):
            libs.destroy(self._cr)
            libs.surface_destroy(self._surface)

    # Shapes

    def line(self, xy, fill: int, width: float = 1) -> None:
        self._path(_points(xy), close=False)
        self._stroke(fill, width)

    def polygon(self, xy, fill: int) -> None:
        self._path(_points(xy), close=True)
        self._fill(fill)
        self._libs.fill(self._cr)

    def rectangle(self, xy, fill: int | None = None, outline: int | None = None, width=1):
        self.rounded_rectangle(xy, 0, fill=fill, outline=outline, width=width)

    def rounded_rectangle(
        self, xy, radius: float, fill: int | None = None, outline: int | None = None, width=1
    ) -> None:
        (left, top), (right, bottom) = _points(xy)
        if fill is not None:
            self._rounded_path(left, top, right, bottom, radius)
            self._fill(fill)
            self._libs.fill(self._cr)
        if outline is not None:
            # Like Pillow, the outline is drawn inside the box.
            inset = width / 2
            self._rounded_path(
                left + inset, top + inset, right - inset, bottom - inset, max(0, radius - inset)
            )
            self._stroke(outline, width)

    def ellipse(self, xy, fill: int) -> None:
        (left, top), (right, bottom) = _points(xy)
        cr, libs = self._cr, self._libs
        libs.save(cr)
        libs.new_path(cr)
        # A unit circle, stretched to the box.
        libs.translate(cr, (left + right) / 2, (top + bottom) / 2)
        libs.scale(cr, max((right - left) / 2, 0.01), max((bottom - top) / 2, 0.01))
        libs.arc(cr, 0, 0, 1, 0, 2 * math.pi)
        # The path keeps its shape once the stretching is undone.
        libs.restore(cr)
        self._fill(fill)
        libs.fill(cr)

    def pieslice(self, xy, start: float, end: float, fill: int) -> None:
        """Circular sector; angles in degrees, clockwise from 3 o'clock."""
        (left, top), (right, bottom) = _points(xy)
        cx, cy, r = (left + right) / 2, (top + bottom) / 2, (right - left) / 2
        cr, libs = self._cr, self._libs
        libs.new_path(cr)
        libs.move_to(cr, cx, cy)
        libs.arc(cr, cx, cy, r, math.radians(start), math.radians(end))
        libs.close_path(cr)
        self._fill(fill)
        libs.fill(cr)

    @contextmanager
    def clip(self, polygons):
        """Restrict drawing to the union of polygons."""
        cr, libs = self._cr, self._libs
        libs.save(cr)
        libs.new_path(cr)
        for polygon in polygons:
            self._path(_points(polygon), close=True, new=False)
        libs.clip(cr)
        try:
            yield
        finally:
            libs.restore(cr)

    def paste(self, picture: Picture, xy: tuple[float, float]) -> None:
        other = Canvas.from_picture(picture)
        cr, libs = self._cr, self._libs
        libs.save(cr)
        libs.set_source_surface(cr, other._surface, xy[0], xy[1])
        libs.paint(cr)
        libs.restore(cr)

    # Text

    def text(self, xy, text: str, font: Font, fill: int) -> None:
        cr, libs = self._cr, self._libs
        self._use_font(font)
        libs.new_path(cr)
        libs.move_to(cr, xy[0], xy[1] + self._ascent(font))
        self._fill(fill)
        libs.show_text(cr, text.encode())

    def textbbox(self, xy, text: str, font: Font) -> tuple[float, float, float, float]:
        """Ink bounds of text drawn at xy, like ImageDraw.textbbox."""
        extents = _TextExtents()
        self._use_font(font)
        self._libs.text_extents(self._cr, text.encode(), ctypes.byref(extents))
        left = xy[0] + extents.x_bearing
        top = xy[1] + self._ascent(font) + extents.y_bearing
        return left, top, left + extents.width, top + extents.height

    # Output

    def picture(self) -> Picture:
        libs = self._libs
        libs.surface_flush(self._surface)
        stride = libs.image_surface_get_stride(self._surface)
        data = ctypes.string_at(libs.image_surface_get_data(self._surface), stride * self.height)
        rows = (data[y * stride : y * stride + 4 * self.width] for y in range(self.height))
        return Picture(self.width, self.height, b"".join(row[_CHANNEL::4] for row in rows))

    @classmethod
    def from_picture(cls, picture: Picture) -> Canvas:
        canvas = cls(picture.width, picture.height)
        libs = canvas._libs
        stride = libs.image_surface_get_stride(canvas._surface)
        pixels = bytearray(stride * picture.height)
        for y, row in enumerate(picture.rows()):
            start = y * stride
            for offset in range(3):
                channel = start + (_CHANNEL + offset if _CHANNEL == 0 else _CHANNEL - offset)
                pixels[channel : start + 4 * picture.width : 4] = row
        ctypes.memmove(libs.image_surface_get_data(canvas._surface), bytes(pixels), len(pixels))
        return canvas

    # Helpers

    def _fill(self, gray: int) -> None:
        level = gray / 255
        self._libs.set_source_rgb(self._cr, level, level, level)

    def _stroke(self, gray: int, width: float) -> None:
        self._fill(gray)
        self._libs.set_line_width(self._cr, width)
        self._libs.stroke(self._cr)

    def _path(self, points, close: bool, new: bool = True) -> None:
        cr, libs = self._cr, self._libs
        if new:
            libs.new_path(cr)
        libs.move_to(cr, *points[0])
        for point in points[1:]:
            libs.line_to(cr, *point)
        if close:
            libs.close_path(cr)

    def _rounded_path(self, left, top, right, bottom, radius) -> None:
        cr, libs = self._cr, self._libs
        libs.new_path(cr)
        radius = min(radius, (right - left) / 2, (bottom - top) / 2)
        if radius <= 0:
            libs.rectangle(cr, left, top, right - left, bottom - top)
            return
        libs.new_sub_path(cr)
        for cx, cy, angle in (
            (right - radius, top + radius, -90),
            (right - radius, bottom - radius, 0),
            (left + radius, bottom - radius, 90),
            (left + radius, top + radius, 180),
        ):
            libs.arc(cr, cx, cy, radius, math.radians(angle), math.radians(angle + 90))
        libs.close_path(cr)

    def _use_font(self, font: Font) -> None:
        self._libs.set_font_face(self._cr, _font_face(font.path))
        self._libs.set_font_size(self._cr, font.size)

    def _ascent(self, font: Font) -> float:
        extents = _FontExtents()
        self._use_font(font)
        self._libs.font_extents(self._cr, ctypes.byref(extents))
        return extents.ascent


def _points(xy) -> list[tuple[float, float]]:
    """Pillow's coordinate forms: [(x, y), ...] or [x0, y0, x1, y1, ...]."""
    xy = list(xy)
    if xy and not isinstance(xy[0], (tuple, list)):
        return [(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]
    return [tuple(point) for point in xy]

"""8x8 effect glyphs: the digits a hit floats up, and the spark round them.

Drawn as sprites rather than rendered as text so they are pixels like
everything else - a font would blur at 3x and sit in a different world from
the sword that caused the number. Each glyph is a 3x5 bitmap with the same
outline treatment as the characters.
"""

from gen.palette import Canvas

SIZE = 8
ANCHOR = (4, 4)                # centred: numbers are placed, not stood on a tile

DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


def digit(rows, key="FIL"):
    c = Canvas(SIZE, SIZE)
    for y, row in enumerate(rows):
        for x, bit in enumerate(row):
            if bit == "1":
                c.set(2 + x, 1 + y, key)
    return c.outline()


def spark():
    c = Canvas(SIZE, SIZE)
    c.col(3, 1, 5, "CL")                 # a four-pointed star, bright core
    c.row(1, 5, 3, "CL")
    c.set(3, 3, "FIL")
    return c


GLYPHS = {f"fx.{d}": (lambda r=rows: digit(r)) for d, rows in DIGITS.items()}
GLYPHS["fx.spark"] = spark
GLYPH_ORDER = list(GLYPHS)


def build_fx():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(gid, GLYPHS[gid]()) for gid in GLYPH_ORDER]

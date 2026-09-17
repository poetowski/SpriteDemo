"""16x16 effect glyphs, drawn at the 2x standard: the digits a hit floats up,
and the spark thrown out round them.

Drawn as sprites rather than rendered as text so they are pixels like
everything else - a font would blur when the canvas is scaled and would sit in
a different world from the sword that caused the number. At 16 a digit gets a
5x9 bitmap, which is wide enough for a proper 0 with a counter in it and a 4
with an open corner, where the old 3x5 had to fudge both.
"""

from gen.palette import Canvas

SIZE = 16
ANCHOR = (8, 8)                # centred: numbers are placed, not stood on a tile

# 5 wide, 9 tall. Drawn in the light metal so they read over grass and stone
# alike, with the usual outline doing the separating.
DIGITS = {
    "0": ("01110", "11011", "11011", "11011", "11011", "11011", "11011",
          "11011", "01110"),
    "1": ("00100", "01100", "11100", "00100", "00100", "00100", "00100",
          "00100", "11111"),
    "2": ("01110", "11011", "00011", "00011", "00110", "01100", "11000",
          "11000", "11111"),
    "3": ("11110", "00011", "00011", "01110", "00011", "00011", "00011",
          "11011", "01110"),
    "4": ("00110", "01110", "01110", "11010", "11010", "11111", "00010",
          "00010", "00010"),
    "5": ("11111", "11000", "11000", "11110", "00011", "00011", "00011",
          "11011", "01110"),
    "6": ("00110", "01100", "11000", "11110", "11011", "11011", "11011",
          "11011", "01110"),
    "7": ("11111", "00011", "00011", "00110", "00110", "01100", "01100",
          "11000", "11000"),
    "8": ("01110", "11011", "11011", "01110", "11011", "11011", "11011",
          "11011", "01110"),
    "9": ("01110", "11011", "11011", "11011", "01111", "00011", "00011",
          "00110", "01100"),
}


def digit(rows):
    c = Canvas(SIZE, SIZE)
    x0, y0 = 5, 3                               # centred in the frame
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "1":
                c.set(x0 + dx, y0 + dy, "MTL")
    for dx, ch in enumerate(rows[0]):           # a lit top edge, so it reads
        if ch == "1":                           # as struck metal not flat text
            c.set(x0 + dx, y0, "EW")
    return c.outline()


def spark():
    """Four arms and a bright core - thrown out where a blow lands."""
    c = Canvas(SIZE, SIZE)
    cx = cy = 7
    for i in range(2, 6):                       # the diagonal arms
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            key = "FIL" if i < 4 else "FI"
            c.set(cx + dx * i, cy + dy * i, key)
    for i in range(1, 4):                       # and the upright ones, shorter
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c.set(cx + dx * i, cy + dy * i, "FI" if i > 2 else "FIL")
    c.rect(cx - 1, cy - 1, cx + 2, cy + 2, "FIL")
    c.rect(cx, cy, cx + 1, cy + 1, "EW")        # a white heart
    return c.outline()


GLYPHS = {f"fx.{d}": (lambda r=rows: digit(r)) for d, rows in DIGITS.items()}
GLYPHS["fx.spark"] = spark
GLYPH_ORDER = list(GLYPHS)


def build_fx():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(gid, GLYPHS[gid]()) for gid in GLYPH_ORDER]

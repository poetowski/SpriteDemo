"""32x32 ground tiles.

Drawn at this size, not blown up from a smaller one: at 16px a tile could only
carry a handful of stray pixels, where 32 has room for real blades of grass,
pebbles with a lit edge, and courses of stone with staggered joints.

Detail is kept a little inside the edges so a tile repeats without a visible
seam - the pipeline checks the edges rather than trusting them (see
pipeline/validate). A tile's id and whether it blocks movement live in
content/tiles/; this module only draws pixels.
"""

from gen.palette import Canvas, scatter

SIZE = 32
EDGE = 2                       # keep detail this far in from every edge


def _blade(c, x, y, h, key):
    """An upright tuft: a stroke with a lean at the tip."""
    c.col(x, y, y + h - 1, key)
    c.set(x + (1 if (x + y) % 2 else -1), y, key)


def grass():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GR")
    rnd = scatter(0x6A55)
    for _ in range(26):                      # dark blades, the undergrowth
        _blade(c, EDGE + rnd(SIZE - EDGE * 2 - 2), EDGE + rnd(SIZE - EDGE * 2 - 3),
               2 + rnd(2), "GRD")
    for _ in range(18):                      # lit blades over the top
        _blade(c, EDGE + rnd(SIZE - EDGE * 2 - 2), EDGE + rnd(SIZE - EDGE * 2 - 3),
               2 + rnd(2), "GRL")
    for _ in range(5):                       # bare patches, so it is not uniform
        x, y = EDGE + rnd(SIZE - EDGE * 2 - 4), EDGE + rnd(SIZE - EDGE * 2 - 3)
        c.rect(x, y, x + 2 + rnd(2), y + 1, "GRD")
    return c


def grass_flower():
    c = grass()
    for x, y in ((7, 11), (21, 8), (13, 23), (25, 19)):
        c.col(x, y + 1, y + 3, "GRL")        # stem
        c.rect(x - 1, y - 1, x + 1, y, "FL")  # a four-petal head
        c.set(x, y - 2, "FL")
        c.set(x, y, "GRD")                   # a dark eye in the middle
    return c


def path():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "PT")
    rnd = scatter(0x9C31)
    for y in (9, 22):                        # two worn ruts, broken up
        x = EDGE
        while x < SIZE - EDGE:
            run = 3 + rnd(5)
            c.row(x, min(x + run, SIZE - EDGE - 1), y, "PTD")
            x += run + 2 + rnd(3)
    for _ in range(16):                      # pebbles: dark body, lit top-left
        x, y = EDGE + rnd(SIZE - EDGE * 2 - 3), EDGE + rnd(SIZE - EDGE * 2 - 2)
        c.rect(x, y, x + 1 + rnd(2), y + 1, "PTD")
        c.set(x, y, "PTL")
    for _ in range(22):                      # grit
        c.set(EDGE + rnd(SIZE - EDGE * 2), EDGE + rnd(SIZE - EDGE * 2), "PTL")
    return c


def water():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WA")
    # Ripples as shallow arcs rather than straight dashes: a lit crest with its
    # own shadow under it, which is what makes still water read as water.
    for cx, cy, w in ((9, 6, 5), (22, 11, 6), (6, 18, 4), (19, 24, 6), (27, 4, 3)):
        for i in range(-w, w + 1):
            y = cy + (abs(i) + 1) // 3
            c.set(cx + i, y, "WAL")
            c.set(cx + i, y + 1, "WAD")
    for x, y in ((14, 15), (25, 19), (4, 27), (17, 3)):
        c.set(x, y, "WAL")                   # glints
    return c


def stone():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "ST")
    rnd = scatter(0x51A7)
    courses = (7, 15, 23, 31)
    for i, y in enumerate(courses):          # the mortar between courses
        c.row(0, SIZE - 1, y, "STD")
        c.row(0, SIZE - 1, y - 1, "STL")     # each block lit along its top
        offset = 0 if i % 2 else 8           # stagger the vertical joints
        for x in range(offset, SIZE, 16):
            c.col(x, y - 6, y - 1, "STD")
    for _ in range(14):                      # pitting in the faces
        c.set(1 + rnd(SIZE - 2), 1 + rnd(SIZE - 2), "STD")
    for _ in range(8):
        c.set(1 + rnd(SIZE - 2), 1 + rnd(SIZE - 2), "STL")
    return c


TILES = {
    "tile.grass": grass,
    "tile.grass_flower": grass_flower,
    "tile.path": path,
    "tile.water": water,
    "tile.stone": stone,
}
TILE_ORDER = list(TILES)


def build_tiles():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(tid, TILES[tid]()) for tid in TILE_ORDER]

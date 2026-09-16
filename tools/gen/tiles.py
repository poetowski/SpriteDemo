"""16x16 ground tiles.

All detail is kept away from the tile edges so a tile repeats without a visible
seam - the pipeline checks this rather than trusting it (see pipeline/validate).
A tile's id and whether it blocks movement live in content/tiles/, not here;
this module only draws pixels.
"""

from gen.palette import Canvas

SIZE = 16


def _speckle(c, spots, key):
    for x, y in spots:
        c.set(x, y, key)


def grass():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GR")
    _speckle(c, ((3, 4), (4, 4), (10, 2), (13, 7), (6, 11), (12, 13)), "GRD")
    _speckle(c, ((7, 3), (2, 9), (11, 9), (5, 14), (14, 11)), "GRL")
    return c


def grass_flower():
    c = grass()
    for x, y in ((4, 6), (11, 5), (7, 12)):
        c.set(x, y, "FL")
        c.set(x, y - 1, "GRL")
    return c


def path():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "PT")
    _speckle(c, ((2, 3), (9, 2), (5, 8), (12, 6), (7, 13), (13, 12)), "PTD")
    _speckle(c, ((6, 5), (11, 9), (3, 11), (14, 3)), "PTL")
    return c


def water():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WA")
    # horizontal ripples, inset from the edges so tiling stays clean
    for x0, x1, y in ((3, 7, 3), (9, 13, 6), (2, 5, 9), (8, 12, 12)):
        c.row(x0, x1, y, "WAL")
        c.row(x0 + 1, x1 - 1, y + 1, "WAD")
    return c


def stone():
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "ST")
    # brick courses, offset every other row, edges left flat
    for y in (4, 10):
        c.row(1, SIZE - 2, y, "STD")
    for x, y0, y1 in ((8, 1, 3), (4, 5, 9), (12, 5, 9), (8, 11, 14)):
        c.col(x, y0, y1, "STD")
    _speckle(c, ((2, 2), (10, 7), (6, 12), (13, 13)), "STL")
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

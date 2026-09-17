"""32x32 ground tiles, and the transitions between them.

Two things separate ground that looks like a place from ground that looks like
wallpaper. The first is variation: a field is several grass drawings chosen by
position, not one stamp repeated. The second is edges: a path has a trodden
margin where it meets the turf, and water has a shore, instead of a hard pixel
seam between two textures.

Because the tiles are generated, both come cheap. Base textures take a seed and
wrap at the edges (detail is placed modulo the tile size), so every variant
tiles seamlessly. Transitions are the standard 47-tile blob set - one tile per
distinct neighbour arrangement - drawn by carving the terrain out of the grass
along a slightly wobbling boundary, with a treatment per terrain along that
boundary: sand and foam for water, a trodden strip for a path, a shadow at the
foot of stone. pipeline/autotile.py picks the tile for each map cell.

A tile's id, whether it blocks movement, and whether it blends at all live in
content/tiles/; this module only draws pixels.
"""

import math

from gen.palette import Canvas, scatter

SIZE = 32

# Neighbour bits, clockwise from north. Used by pipeline/autotile.py too.
N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128
FULL = 255


def canonical(mask):
    """A diagonal only matters when both cardinals beside it are set: a grass
    corner touching a path only at the corner does not change the path's
    shape. Folding those away leaves the 47 arrangements that look distinct."""
    if not (mask & N and mask & E):
        mask &= ~NE
    if not (mask & E and mask & S):
        mask &= ~SE
    if not (mask & S and mask & W):
        mask &= ~SW
    if not (mask & W and mask & N):
        mask &= ~NW
    return mask


ALL_MASKS = sorted({canonical(m) for m in range(256)})


# ----------------------------------------------------------------- helpers ---
def _put(c, x, y, key):
    """Set with wrap-around, so detail placed near an edge continues on the
    other side and the tile repeats without a seam."""
    c.set(x % SIZE, y % SIZE, key)


def _blade(c, x, y, h, key, lean=None):
    for i in range(h):
        _put(c, x, y - i, key)
    tip = lean if lean is not None else (1 if (x + y) % 2 else -1)
    _put(c, x + tip, y - h, key)


def _patch(c, rnd, x, y, w, h, key, n):
    """A soft blob of n pixels around (x, y), for patches of a second shade."""
    for _ in range(n):
        _put(c, x + rnd(w) - w // 2, y + rnd(h) - h // 2, key)


# ------------------------------------------------------------ base textures --
def grass(seed=0):
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GR")
    rnd = scatter(0x6A55 + seed * 977)
    for _ in range(5):                            # deep patches under the blades
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 9, 5, "GRX", 10 + rnd(8))
    for _ in range(3):                            # and a few worn, lighter ones
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 7, 4, "GRD", 6 + rnd(6))
    for _ in range(30):                           # blades in the shade
        _blade(c, rnd(SIZE), rnd(SIZE), 2 + rnd(2), "GRD")
    for _ in range(20):                           # blades catching the light
        _blade(c, rnd(SIZE), rnd(SIZE), 2 + rnd(2), "GRL")
    for _ in range(4):                            # clover
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "GRL")
        _put(c, x + 1, y, "GRL")
        _put(c, x, y + 1, "GRL")
    return c


def grass_tall(seed=0):
    """Rank, unmown grass: darker, with taller blades and lit tips."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GRD")
    rnd = scatter(0x7A11 + seed * 613)
    for _ in range(6):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 9, 6, "GRX", 12 + rnd(8))
    for _ in range(34):
        _blade(c, rnd(SIZE), rnd(SIZE), 3 + rnd(3), "GRX")
    for _ in range(26):
        x, y, h = rnd(SIZE), rnd(SIZE), 3 + rnd(3)
        _blade(c, x, y, h, "GR")
        _put(c, x, y - h + 1, "GRL")              # the tip catches the light
    return c


def grass_flower(seed=0):
    c = grass(seed)
    rnd = scatter(0xF10E + seed * 331)
    for i in range(5):
        x, y = rnd(SIZE), rnd(SIZE)
        head = "FL" if i % 3 else "EW"            # mostly yellow, some white
        _put(c, x, y + 1, "GRL")                  # stem
        _put(c, x, y + 2, "GRL")
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            _put(c, x + dx, y + dy, head)
        _put(c, x, y, "GRD" if head == "FL" else "FL")
    return c


def path(seed=0):
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "PT")
    rnd = scatter(0x9C31 + seed * 401)
    for _ in range(4):                            # worn darker patches
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 10, 5, "PTD", 10 + rnd(8))
    for _ in range(3):                            # dust, lighter
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 8, 4, "PTL", 8 + rnd(6))
    for _ in range(14):                           # pebbles: dark body, lit top
        x, y = rnd(SIZE), rnd(SIZE)
        w = 1 + rnd(2)
        for dx in range(w + 1):
            _put(c, x + dx, y, "PTD")
            _put(c, x + dx, y + 1, "PTD")
        _put(c, x, y, "PTL")
    for _ in range(3):                            # the odd real stone
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "STL")
        _put(c, x + 1, y, "ST")
        _put(c, x, y + 1, "ST")
        _put(c, x + 1, y + 1, "STD")
    for _ in range(18):
        _put(c, rnd(SIZE), rnd(SIZE), "PTL")      # grit
    return c


def dirt(seed=0):
    """Bare earth: clods, grit, the odd stone. Darker and redder than the path."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DR")
    rnd = scatter(0xD1A7 + seed * 173)
    for _ in range(12):                           # clods
        x, y = rnd(SIZE), rnd(SIZE)
        w = 1 + rnd(3)
        for dx in range(w + 1):
            _put(c, x + dx, y, "DRD")
        _put(c, x, y - 1, "DRL")
    for _ in range(4):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 8, 4, "DRD", 8 + rnd(6))
    for _ in range(16):
        _put(c, rnd(SIZE), rnd(SIZE), "DRL")
    for _ in range(2):
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "STL")
        _put(c, x + 1, y, "ST")
        _put(c, x + 1, y + 1, "STD")
    return c


def water(seed=0):
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WA")
    rnd = scatter(0x0A7E + seed * 809)
    for _ in range(4):                            # deeper patches
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 11, 6, "WAX", 14 + rnd(10))
    for _ in range(6):                            # ripples as shallow arcs
        cx, cy, w = rnd(SIZE), rnd(SIZE), 3 + rnd(4)
        for i in range(-w, w + 1):
            y = cy + (abs(i) + 1) // 3
            _put(c, cx + i, y, "WAL")
            _put(c, cx + i, y + 1, "WAD")
    for _ in range(3):
        _put(c, rnd(SIZE), rnd(SIZE), "EW")       # glints
    return c


def stone(seed=0):
    """Flagstones: a jittered partition of the tile, mortar between, each
    stone lit along its top and left."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "ST")
    rnd = scatter(0x51A7 + seed * 257)
    ys = [0, 10 + rnd(3), 21 + rnd(3), SIZE]
    for r in range(3):
        y0, y1 = ys[r], ys[r + 1]
        off = (r * 7 + rnd(4)) % 12
        xs = [off]
        while xs[-1] < SIZE + off:
            xs.append(xs[-1] + 9 + rnd(5))
        for x0, x1 in zip(xs, xs[1:]):
            for x in range(x0, x1):               # the face, lit at its edges
                for y in range(y0, y1):
                    key = "ST"
                    if y == y0 + 1 or x == x0 + 1:
                        key = "STL"
                    if y == y1 - 1 or x == x1 - 1:
                        key = "STD"
                    if y == y0 or x == x0:
                        key = "STD"               # mortar
                    _put(c, x, y, key)
    for _ in range(10):                           # pitting
        _put(c, rnd(SIZE), rnd(SIZE), "STD")
    return c


BASE = {
    "tile.grass": grass,
    "tile.grass_flower": grass_flower,
    "tile.grass_tall": grass_tall,
    "tile.path": path,
    "tile.dirt": dirt,
    "tile.water": water,
    "tile.stone": stone,
}
TILE_ORDER = list(BASE)

# How many seeded variants of each base to draw. A cell picks one by position,
# so the field changes without anyone having authored it.
VARIANTS = {"tile.grass": 3, "tile.grass_tall": 2, "tile.water": 2}


# ------------------------------------------------------------- transitions --
def _wobble(t, phase):
    """A gentle periodic wave along a 32px edge, quiet near the corners so it
    never fights the corner arcs. Periodic, so the line continues across the
    seam into the next tile."""
    w = math.sin(t / SIZE * 4 * math.pi + phase) * 1.5
    taper = min(1.0, min(t, SIZE - 1 - t) / 10.0)
    return w * taper


BAND = 6                       # how far the grass reaches into an open edge
ROUND = 6                      # radius of an outer corner's arc


def depth(x, y, mask):
    """How far inside the terrain a pixel is, in pixels; negative is grass.

    Each open edge pushes the boundary in by BAND (plus wobble). Two adjacent
    open edges meet in an arc rather than a square corner. An open diagonal
    with both cardinals closed takes a quarter-disc bite out of that corner,
    sized so it continues the neighbours' own edge bands exactly.
    """
    last = SIZE - 1
    d = 99.0
    if not mask & N:
        d = min(d, y - (BAND + _wobble(x, 0.3)))
    if not mask & S:
        d = min(d, (last - BAND - _wobble(x, 1.9)) - y)
    if not mask & W:
        d = min(d, x - (BAND + _wobble(y, 4.1)))
    if not mask & E:
        d = min(d, (last - BAND - _wobble(y, 2.7)) - x)

    c = BAND + ROUND
    corners = ((N, E, last - c, c, 1, -1), (N, W, c, c, -1, -1),
               (S, E, last - c, last - c, 1, 1), (S, W, c, last - c, -1, 1))
    for a, b, cx, cy, sx, sy in corners:
        if mask & a or mask & b:
            continue
        if (x - cx) * sx > 0 and (y - cy) * sy > 0:
            d = min(d, ROUND - math.hypot(x - cx, y - cy))

    bites = ((NE, N, E, last, 0), (SE, S, E, last, last),
             (SW, S, W, 0, last), (NW, N, W, 0, 0))
    for diag, a, b, cx, cy in bites:
        if mask & diag or not (mask & a and mask & b):
            continue
        d = min(d, math.hypot(x - cx, y - cy) - BAND)
    return d


def _edge_water(d, x, y, over, under, rnd):
    if d < 0:
        return under
    if d < 2.5:
        return "SAD" if rnd(6) == 0 else "SA"                # a strip of shore
    if d < 3.5:
        return "WAL" if rnd(4) else "WA"                     # foam, broken up
    if d < 5.5 and over == "WAX":
        return "WA"                                          # the shallows
    return over


def _edge_path(d, x, y, over, under, rnd, dark):
    if d < 0:
        return under
    if d < 1:
        return dark if (x + y) % 2 else under                # trodden edge
    if d < 2:
        return dark
    return over


def _edge_stone(d, x, y, over, under, rnd):
    if d < 0:
        return under
    if d < 1:
        return "GRX" if (x + y) % 2 else under               # shadow at the foot
    if d < 2:
        return "STD"
    return over


STYLE = {
    "tile.water": _edge_water,
    "tile.path": lambda d, x, y, o, u, r: _edge_path(d, x, y, o, u, r, "PTD"),
    "tile.dirt": lambda d, x, y, o, u, r: _edge_path(d, x, y, o, u, r, "DRD"),
    "tile.stone": _edge_stone,
}


def blend(tid, mask):
    """The tile for `tid` with this neighbour arrangement, carved out of grass."""
    over = BASE[tid](0)
    under = grass(sum(map(ord, tid)) % 3)
    rnd = scatter(0x5EED ^ (mask * 7919) ^ sum(map(ord, tid)))
    style = STYLE[tid]
    c = Canvas(SIZE, SIZE)
    for y in range(SIZE):
        for x in range(SIZE):
            d = depth(x, y, mask)
            c.set(x, y, style(d, x, y, over.px[y][x], under.px[y][x], rnd))
    return c


def build_tiles():
    """[(id, Canvas), ...] the plain base of every tile, in a stable order."""
    return [(tid, BASE[tid](0)) for tid in TILE_ORDER]

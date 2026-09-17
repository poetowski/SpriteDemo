"""16x16 ground tiles, the transitions between them, and the frames that move.

Two things separate ground that looks like a place from ground that looks like
wallpaper. The first is variation: a field is several grass drawings chosen by
position, not one stamp repeated. The second is edges: a path has a trodden
margin where it meets the turf, water has a shore, and a stone outcrop has a
lit lip with a shadow under it, instead of a hard seam.

None of that costs authoring effort, because it is generated. Base textures
take a seed and wrap at the edges (detail is placed modulo the tile size), so
every variant tiles seamlessly. Transitions are the standard 47-tile blob set -
one tile per distinct neighbour arrangement - carved out of the grass along a
slightly wobbling boundary, with a treatment per terrain along that boundary.
Water is drawn in phases and the engine cycles them, so a pond moves.
pipeline/autotile.py picks the tile for each map cell.

At 16 the treatments are one or two pixels wide rather than four or five, so
they read as an edge rather than as a border - which is the point.

A tile's id, whether it blocks movement, and whether it blends at all live in
content/tiles/; this module only draws pixels.
"""

import math

from gen.palette import Canvas, scatter

SIZE = 16

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


def _blade(c, x, y, h, key):
    for i in range(h):
        _put(c, x, y - i, key)
    _put(c, x + (1 if (x + y) % 2 else -1), y - h, key)


def _patch(c, rnd, x, y, w, h, key, n):
    for _ in range(n):
        _put(c, x + rnd(w) - w // 2, y + rnd(h) - h // 2, key)


def _pool(c, cx, cy, rx, ry, key):
    """A filled, soft-edged ellipse - one continuous mass, not a scatter."""
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            v = (dx / rx) ** 2 + (dy / ry) ** 2
            if v <= 0.7 or (v <= 1.0 and (dx + dy) % 2 == 0):
                _put(c, cx + dx, cy + dy, key)


# ------------------------------------------------------------ base textures --
def grass(seed=0, phase=0):
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GR")
    rnd = scatter(0x6A55 + seed * 977)
    for _ in range(2):                            # deep patches under the blades
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "GRX", 4 + rnd(3))
    for _ in range(8):                            # blades in the shade
        _blade(c, rnd(SIZE), rnd(SIZE), 1 + rnd(2), "GRD")
    for _ in range(6):                            # blades catching the light
        _blade(c, rnd(SIZE), rnd(SIZE), 1 + rnd(2), "GRL")
    return c


def grass_tall(seed=0, phase=0):
    """Rank, unmown grass: darker, with taller blades and lit tips."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GRD")
    rnd = scatter(0x7A11 + seed * 613)
    for _ in range(2):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 4, "GRX", 5 + rnd(4))
    for _ in range(10):
        _blade(c, rnd(SIZE), rnd(SIZE), 2 + rnd(2), "GRX")
    for _ in range(8):
        x, y, h = rnd(SIZE), rnd(SIZE), 2 + rnd(2)
        _blade(c, x, y, h, "GR")
        _put(c, x, y - h, "GRL")                  # the tip catches the light
    return c


def grass_flower(seed=0, phase=0):
    c = grass(seed)
    rnd = scatter(0xF10E + seed * 331)
    for i in range(3):
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y + 1, "GRL")                  # stem
        _put(c, x, y, "FL" if i % 2 else "EW")    # and the head
        _put(c, x - 1, y, "FL" if i % 2 else "EW")
    return c


def path(seed=0, phase=0):
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "PT")
    rnd = scatter(0x9C31 + seed * 401)
    for _ in range(2):                            # worn darker patches
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 6, 3, "PTD", 5 + rnd(4))
    for _ in range(5):                            # pebbles: dark body, lit top
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "PTD")
        _put(c, x + 1, y, "PTD")
        _put(c, x, y - 1, "PTL")
    for _ in range(8):
        _put(c, rnd(SIZE), rnd(SIZE), "PTL")      # grit
    return c


def dirt(seed=0, phase=0):
    """Bare earth: clods and grit. Darker and redder than the path."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DR")
    rnd = scatter(0xD1A7 + seed * 173)
    for _ in range(6):                            # clods
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "DRD")
        _put(c, x + 1, y, "DRD")
        _put(c, x, y - 1, "DRL")
    for _ in range(2):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "DRD", 4 + rnd(3))
    for _ in range(6):
        _put(c, rnd(SIZE), rnd(SIZE), "DRL")
    return c


def water(seed=0, phase=0):
    """Still water that is not quite still: the ripples drift a pixel with each
    phase and a different glint catches the light."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WA")
    rnd = scatter(0x0A7E + seed * 809)
    for _ in range(2):
        _pool(c, rnd(SIZE), rnd(SIZE), 3 + rnd(2), 2 + rnd(2), "WAX")
    arcs = [(rnd(SIZE), rnd(SIZE), 2 + rnd(2)) for _ in range(3)]
    for i, (ax, ay, w) in enumerate(arcs):
        ox = ax + phase * (1 if i % 2 else -1)    # alternate arcs drift apart
        for k in range(-w, w + 1):
            y = ay + (1 if abs(k) == w else 0)
            _put(c, ox + k, y, "WAL")
            _put(c, ox + k, y + 1, "WAD")
    glints = [(rnd(SIZE), rnd(SIZE)) for _ in range(3)]
    for i, (gx, gy) in enumerate(glints):
        if (i + phase) % 3 == 0:
            _put(c, gx, gy, "EW")
    return c


def stone(seed=0, phase=0):
    """Flagstones: courses with staggered joints, each stone lit along its top."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "ST")
    rnd = scatter(0x51A7 + seed * 257)
    for i, y in enumerate((5, 11, 15)):
        c.row(0, SIZE - 1, y, "STD")              # the mortar between courses
        if y > 0:
            c.row(0, SIZE - 1, y - 1, "STL")      # each block lit along its top
        for x in range((i % 2) * 5, SIZE, 9):
            for yy in range(max(0, y - 4), y):
                _put(c, x, yy, "STD")
    for _ in range(4):                            # pitting
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

# Tiles drawn in several phases. The art pipeline emits every phase as its own
# frame and the engine cycles them; the base frame is what the map resolves to.
ANIMATED = {"tile.water": 3}
ANIM_MS = 420


def frame(tid, variant=0, phase=0):
    return BASE[tid](variant, phase)


# ------------------------------------------------------------- transitions --
def _wobble(t, phase):
    """A gentle periodic wave along the edge, quiet near the corners so it
    never fights the corner arcs. Periodic, so the line continues across the
    seam into the next tile."""
    w = math.sin(t / SIZE * 4 * math.pi + phase) * 0.8
    return w * min(1.0, min(t, SIZE - 1 - t) / 5.0)


BAND = 3                       # how far the grass reaches into an open edge
ROUND = 3                      # radius of an outer corner's arc


def depth(x, y, mask):
    """(depth, which): how far inside the terrain a pixel is, and which open
    edge or corner put the boundary there. Negative is grass. `which` lets a
    style treat a downhill edge differently from an uphill one, which is what
    makes an outcrop read as raised."""
    last = SIZE - 1
    d, which = 99.0, "in"

    def take(v, tag):
        nonlocal d, which
        if v < d:
            d, which = v, tag

    if not mask & N:
        take(y - (BAND + _wobble(x, 0.3)), "N")
    if not mask & S:
        take((last - BAND - _wobble(x, 1.9)) - y, "S")
    if not mask & W:
        take(x - (BAND + _wobble(y, 4.1)), "W")
    if not mask & E:
        take((last - BAND - _wobble(y, 2.7)) - x, "E")

    c = BAND + ROUND
    corners = ((N, E, last - c, c, 1, -1, "cNE"), (N, W, c, c, -1, -1, "cNW"),
               (S, E, last - c, last - c, 1, 1, "cSE"), (S, W, c, last - c, -1, 1, "cSW"))
    for a, b, cx, cy, sx, sy, tag in corners:
        if mask & a or mask & b:
            continue
        if (x - cx) * sx > 0 and (y - cy) * sy > 0:
            take(ROUND - math.hypot(x - cx, y - cy), tag)

    bites = ((NE, N, E, last, 0, "bNE"), (SE, S, E, last, last, "bSE"),
             (SW, S, W, 0, last, "bSW"), (NW, N, W, 0, 0, "bNW"))
    for diag, a, b, cx, cy, tag in bites:
        if mask & diag or not (mask & a and mask & b):
            continue
        take(math.hypot(x - cx, y - cy) - BAND, tag)
    return d, which


def _edge_water(d, which, x, y, over, under, rnd, phase):
    if d < 0:
        return under
    if d < 1.2:
        return "SAD" if rnd(6) == 0 else "SA"                # a strip of shore
    if d < 2.0:
        return "WAL" if (x + y * 3 + phase * 2) % 4 else "WA"   # foam, creeping
    if d < 3.0 and over == "WAX":
        return "WA"                                          # the shallows
    return over


def _edge_trodden(d, which, x, y, over, under, rnd, dark, light):
    """A path or bare earth: worn hardest at the verge and on bends, lighter
    with dust down the middle."""
    if d < 0:
        return under
    if d < 1:
        return dark if (x + y) % 2 else under
    bend = which.startswith("c")
    if d < 2.2 and (rnd(3) == 0 or (bend and rnd(2) == 0)):
        return dark
    if d >= 5 and rnd(5) == 0:
        return light
    return over


def _edge_stone(d, which, x, y, over, under, rnd, phase):
    """An outcrop is raised ground: its downhill edge is a face with a lit lip
    and a shadow on the grass below; the other edges get a lit rim."""
    downhill = which in ("S", "cSE", "cSW")
    if d < 0:
        return "GRX" if downhill and d >= -1.5 else under
    if downhill:
        if d >= 3:
            return over
        if d >= 2:
            return "STL"                                     # the lip
        return "STX" if x % 5 == 0 else "STD"                # the face, cracked
    if d < 1:
        return "STL"                                         # rim
    return over


STYLE = {
    "tile.water": _edge_water,
    "tile.path": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "PTD", "PTL"),
    "tile.dirt": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "DRL"),
    "tile.stone": _edge_stone,
}


def blend(tid, mask, phase=0):
    """The tile for `tid` with this neighbour arrangement, carved out of grass."""
    over = frame(tid, 0, phase)
    under = grass(sum(map(ord, tid)) % 3)
    style = STYLE[tid]
    c = Canvas(SIZE, SIZE)
    for y in range(SIZE):
        # The rng restarts per row from the mask, so every phase of an animated
        # tile makes the same sand and wear decisions and only the water moves.
        rnd = scatter(0x5EED ^ (mask * 7919) ^ sum(map(ord, tid)) ^ (y * 331))
        for x in range(SIZE):
            d, which = depth(x, y, mask)
            c.set(x, y, style(d, which, x, y, over.px[y][x], under.px[y][x], rnd, phase))
    return c


def build_tiles():
    """[(id, Canvas), ...] the plain base of every tile, in a stable order."""
    return [(tid, BASE[tid](0)) for tid in TILE_ORDER]

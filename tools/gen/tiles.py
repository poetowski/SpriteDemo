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


def sand(seed=0, phase=0):
    """Dry sand: fine grain, the odd shell or pebble."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "SA")
    rnd = scatter(0x5A9D + seed * 331)
    for _ in range(2):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 6, 4, "SAD", 5 + rnd(4))
    for _ in range(14):
        _put(c, rnd(SIZE), rnd(SIZE), "SAL")
    for _ in range(8):
        _put(c, rnd(SIZE), rnd(SIZE), "SAD")
    for _ in range(2):                            # a shell, two pixels of it
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "EW")
        _put(c, x + 1, y, "SAD")
    return c


# --------------------------------------------------------------- the desert --
# The desert has its own base the way the meadow has grass: everything else in
# the biome is carved out of dune, so the two families never have to meet.
def dune(seed=0, phase=0):
    """Deep wind-blown sand. The ripples are the whole of it - sand without
    them is a flat wash, and sand with a scatter of dots on it is gravel. They
    run as long shallow arcs one way across the tile, drawn with _put so a
    ripple crossing the seam comes out of the far side and the desert reads as
    one surface rather than as a grid of squares."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DN")
    rnd = scatter(0xD0E5 + seed * 887)
    for k in range(3):                            # the crests
        y0 = rnd(SIZE)
        amp = 1 + rnd(2)
        for x in range(SIZE):
            y = y0 + round(math.sin((x + seed * 5 + k * 7) / SIZE * 2 * math.pi) * amp)
            _put(c, x, y, "DNL")
            _put(c, x, y + 1, "DND")              # the lee side, in shade
    for _ in range(3):                            # hollows between them
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "DND", 4 + rnd(3))
    for _ in range(6):
        _put(c, rnd(SIZE), rnd(SIZE), "DNL")
    return c


def salt(seed=0, phase=0):
    """A dry pan: white crust broken into plates. The cracks are the texture -
    crust with a few specks on it is just a pale square - so they run long,
    wander, and show the sand underneath where they open widest."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "SL")
    rnd = scatter(0x5A17 + seed * 439)
    for k in range(5):
        x, y = rnd(SIZE), rnd(SIZE)
        dx, dy = (1, 0) if k % 2 else (0, 1)      # each crack keeps a heading
        for i in range(7 + rnd(7)):
            _put(c, x, y, "SLD")
            if i % 3 == 2:                        # and opens here and there
                _put(c, x + dy, y + dx, "DND")
                _put(c, x, y, "DNX")
            x += dx + (0 if rnd(3) else (1 if rnd(2) else -1))
            y += dy + (0 if rnd(3) else (1 if rnd(2) else -1))
    for _ in range(12):
        _put(c, rnd(SIZE), rnd(SIZE), "SLL")      # crystals catching the sun
    for _ in range(4):
        _put(c, rnd(SIZE), rnd(SIZE), "SLD")
    return c


def sandstone(seed=0, phase=0):
    """A flagged court, seen from above. Four slabs to the tile, each its own
    shade, with a thin joint between them and sand lying in the corners.

    Two earlier versions were wrong in opposite directions. Lighting the top
    of every course gave each slab a lit upper edge - which is what a wall
    has and a floor does not - and it came out as brickwork standing up.
    Dashing the joints to fix that removed the slabs altogether and left
    noise. A floor needs its grid; what it must not have is the *same* grid in
    every tile, so the joints move with the variant."""
    c = Canvas(SIZE, SIZE)
    rnd = scatter(0x55A0 + seed * 691)
    row = (3 + seed * 5) % SIZE
    col = (2 + seed * 7) % SIZE
    # Barely apart on purpose. Cut stone from one quarry varies by a shade,
    # and four tones a step apart came out as a chessboard; the dark tone is
    # for the joints and the wear, never for a whole slab.
    tone = ("SS", "SS", "SSL", "SS")
    for y in range(SIZE):
        for x in range(SIZE):
            q = 2 * ((y - row) % SIZE < 8) + ((x - col) % SIZE < 8)
            c.set(x, y, tone[(q + seed) % 4])
    for i in range(SIZE):                         # the joints between them
        for j in (0, 8):
            _put(c, i, (row + j) % SIZE, "SSD")
            _put(c, (col + j) % SIZE, i, "SSD")
    _put(c, col, row, "DNX")                      # sand in the crossings
    _put(c, (col + 8) % SIZE, (row + 8) % SIZE, "DNX")
    for _ in range(5):                            # wear on the faces
        _put(c, rnd(SIZE), rnd(SIZE), "SSD")
    for _ in range(4):
        _put(c, rnd(SIZE), rnd(SIZE), "SSL")
    _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "DND", 4)   # and drifted sand
    return c


def scrub(seed=0, phase=0):
    """What grows here: thorn and dry stalk over the sand, sparse enough that
    the ground shows through it."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DN")
    rnd = scatter(0x5C30 + seed * 521)
    for _ in range(3):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "DND", 4)
    for _ in range(9):                            # stalks, most of them dead
        _blade(c, rnd(SIZE), rnd(SIZE), 2 + rnd(2), "SCD")
    for _ in range(6):
        x, y, h = rnd(SIZE), rnd(SIZE), 1 + rnd(2)
        _blade(c, x, y, h, "SC")
        _put(c, x, y - h, "SCL")
    return c


def oasis(seed=0, phase=0):
    """Still, deep and green: nothing moves it but the light on top, so the
    phases shift the glints rather than running a current.

    No pool shape in here. A base texture is laid down in every cell of the
    water, so anything centred in the tile repeats on a 16px grid - the first
    version put a dark ellipse in the middle of each one and the oasis came
    out as polka dots. Depth is scattered and wrapped like every other base."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "OA")
    rnd = scatter(0x0A51 + seed * 733)
    for _ in range(3):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 7, 5, "OAD", 8 + rnd(4))
    for _ in range(2):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 4, 3, "OAX", 4 + rnd(3))
    for _ in range(6):                            # light on the surface
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x + phase, y, "OAL")
        _put(c, x + 1 + phase, y, "OAL")
    return c


def gravel(seed=0, phase=0):
    """A made road: small stones rolled into the dirt."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "PTD")
    rnd = scatter(0x67A1 + seed * 457)
    for _ in range(22):                           # stones, lit on top
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "STL")
        _put(c, x + 1, y, "ST")
        _put(c, x, y + 1, "STD")
    for _ in range(10):
        _put(c, rnd(SIZE), rnd(SIZE), "PT")       # dust between them
    return c


def cobble(seed=0, phase=0):
    """Village paving: rounded setts in staggered courses."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "STD")
    rnd = scatter(0x3C0B + seed * 613)
    for row, y in enumerate((0, 4, 8, 12)):
        off = (row % 2) * 2
        for x in range(off, SIZE + off, 4):
            for dy in range(3):                   # a 3x3 sett, lit top-left
                for dx in range(3):
                    _put(c, x + dx, y + dy, "ST")
            _put(c, x, y, "STL")
            _put(c, x + 1, y, "STL")
            _put(c, x + 2, y + 2, "STD")
            if rnd(4) == 0:
                _put(c, x + 1, y + 1, "STD")      # a worn one
    return c


def field(seed=0, phase=0):
    """Ploughed earth: furrows with stubble left between them."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DR")
    rnd = scatter(0x11E7 + seed * 179)
    for y in range(0, SIZE, 4):                   # the furrows themselves
        c.row(0, SIZE - 1, y, "DRD")
        c.row(0, SIZE - 1, (y + 1) % SIZE, "DRL")
    for _ in range(10):                           # stubble on the ridges
        x, y = rnd(SIZE), rnd(SIZE)
        if y % 4 in (2, 3):
            _put(c, x, y, "TH")
    for _ in range(6):
        _put(c, rnd(SIZE), rnd(SIZE), "DRD")      # clods
    return c


def leaves(seed=0, phase=0):
    """Forest floor: leaf litter over dark earth, where a canopy shades it."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "LFD")
    rnd = scatter(0x9E11 + seed * 743)
    for _ in range(18):                           # fallen leaves, two pixels
        x, y = rnd(SIZE), rnd(SIZE)
        key = ("LF", "RFD", "GRX")[rnd(3)]
        _put(c, x, y, key)
        _put(c, x + 1, y, key)
    for _ in range(8):
        _put(c, rnd(SIZE), rnd(SIZE), "LF")
    for _ in range(4):                            # a twig
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "WDD")
        _put(c, x + 1, y + 1, "WDD")
    return c


def shallow(seed=0, phase=0):
    """Water you can wade: the bed shows through, and it moves."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WAL")
    rnd = scatter(0x2B4F + seed * 521)
    for _ in range(10):                           # sand and stones underneath
        _put(c, rnd(SIZE), rnd(SIZE), "SA")
    for _ in range(4):
        _put(c, rnd(SIZE), rnd(SIZE), "SAD")
    for i in range(3):                            # ripples travelling across
        ax, ay = rnd(SIZE), rnd(SIZE)
        for k in range(-2, 3):
            _put(c, ax + k + phase, ay + (1 if abs(k) == 2 else 0), "WA")
    for i in range(3):
        if (i + phase) % 2 == 0:
            _put(c, rnd(SIZE), rnd(SIZE), "EW")
    return c


def wood_floor(seed=0, phase=0):
    """Planks, for anywhere with a roof. No transitions: a floor has walls."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WD")
    rnd = scatter(0x7D00 + seed * 293)
    for y in range(0, SIZE, 5):                   # the boards
        c.row(0, SIZE - 1, y, "WDD")
        c.row(0, SIZE - 1, (y + 1) % SIZE, "WDL")
    for _ in range(4):                            # end joints, staggered
        x, y = rnd(SIZE), (rnd(3) * 5 + 2) % SIZE
        for dy in range(3):
            _put(c, x, y + dy, "WDD")
    for _ in range(8):                            # grain
        _put(c, rnd(SIZE), rnd(SIZE), "WDD")
    return c


def plank_wall(seed=0, phase=0):
    """A timber wall seen from inside: studs behind horizontal boards. Dark,
    because an interior wall is the thing light falls off rather than onto -
    and because a floor and a wall in the same wood at the same value would
    leave the room with no corners."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WDD")
    rnd = scatter(0x9A11 + seed * 379)
    # Darker than the floor by a clear margin, and it has to be measured
    # rather than eyeballed: the first version came out at luma 88 against a
    # floor of 95 and the room had no corners - the wall and the boards you
    # walk on were the same wood at the same brightness.
    for y in range(2, SIZE, 4):
        c.row(0, SIZE - 1, y - 1, "OL")           # the shadowed seam
        c.row(0, SIZE - 1, y, "WD")               # and the face of the board
    for x in (4, 12):                             # the studs behind them
        c.col(x, 0, SIZE - 1, "OL")
        c.col(x + 1, 0, SIZE - 1, "WDD")
    for _ in range(7):                            # knots and grain
        _put(c, rnd(SIZE), rnd(SIZE), "OL")
    return c


def straw(seed=0, phase=0):
    """Straw trodden over a floor: the cheapest thing to put down and the
    first thing in any shed that keeps animals or stores a harvest."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "TH")
    rnd = scatter(0x3C5E + seed * 421)
    for _ in range(26):                           # stalks, lying every way
        x, y = rnd(SIZE), rnd(SIZE)
        key = ("THD", "THL", "TH")[rnd(3)]
        if rnd(2):
            c.row(x, x + 2, y, key)
        else:
            c.col(x, y, y + 2, key)
    for _ in range(5):
        _put(c, rnd(SIZE), rnd(SIZE), "WDD")      # floor showing through
    return c


BASE = {
    "tile.grass": grass,
    "tile.grass_flower": grass_flower,
    "tile.grass_tall": grass_tall,
    "tile.leaves": leaves,
    "tile.path": path,
    "tile.gravel": gravel,
    "tile.dirt": dirt,
    "tile.field": field,
    "tile.sand": sand,
    "tile.dune": dune,
    "tile.salt": salt,
    "tile.sandstone": sandstone,
    "tile.scrub": scrub,
    "tile.oasis": oasis,
    "tile.cobble": cobble,
    "tile.stone": stone,
    "tile.wood_floor": wood_floor,
    "tile.plank_wall": plank_wall,
    "tile.straw": straw,
    "tile.shallow": shallow,
    "tile.water": water,
}
TILE_ORDER = list(BASE)

# How many seeded variants of each base to draw. A cell picks one by position,
# so the field changes without anyone having authored it.
VARIANTS = {"tile.grass": 3, "tile.grass_tall": 2, "tile.water": 2,
            "tile.sand": 2, "tile.leaves": 2, "tile.wood_floor": 2,
            "tile.straw": 2,
            # Dune needs the most of any base: it is the whole floor of the
            # biome, and one ripple pattern repeated across a map is a rug.
            "tile.dune": 4, "tile.salt": 2, "tile.scrub": 2,
            "tile.sandstone": 3, "tile.oasis": 2}

# Tiles drawn in several phases. The art pipeline emits every phase as its own
# frame and the engine cycles them; the base frame is what the map resolves to.
ANIMATED = {"tile.water": 3, "tile.shallow": 2, "tile.oasis": 3}
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


def _edge_soft(d, which, x, y, over, under, rnd, edge):
    """A boundary that crumbles rather than cuts: the outermost pixels are
    dithered between the two, which is what sand, leaf litter and gravel do
    where they meet turf."""
    if d < -0.8:
        return under
    if d < 0.8:
        return over if (x * 3 + y * 5) % 4 == 0 else under
    if d < 2:
        return edge if rnd(2) else over
    return over


def _edge_kerb(d, which, x, y, over, under, rnd, edge):
    """A laid surface: a hard line, because someone put a kerb there."""
    if d < 0:
        return under
    if d < 1:
        return edge
    return over


def _edge_shallow(d, which, x, y, over, under, rnd, phase):
    """A shoal, not a pond: the water thins into the bed it lies on rather
    than breaking against a shore, so there is no foam line and no sand strip -
    the strip would be sand drawn on sand and read as a painted border."""
    if d < 0:
        return under
    if d < 1.6:                                   # the bed showing through
        return under if (x * 3 + y * 5 + phase) % 3 else over
    if d < 2.6:
        return over if (x + y + phase) % 2 else "SA"
    return over


def _edge_oasis(d, which, x, y, over, under, rnd, phase):
    """A pool with no current: a wet margin where the sand darkens, then a
    thin bright rim, and no foam - foam is what a shore does to moving water,
    and there is nothing here to move it."""
    if d < 0:
        return under
    if d < 1.2:
        return "DNX" if rnd(4) == 0 else "DND"               # sand, damp
    if d < 2.0:
        return "OAL" if (x * 3 + y + phase) % 3 else "OA"    # the bright rim
    if d < 3.2 and over == "OAX":
        return "OAD"                                         # it shelves
    return over


def _edge_drift(d, which, x, y, over, under, rnd, edge):
    """Sand piled against something: it heaps on the lee side and thins to
    nothing on the other, so the boundary is a drift rather than a line. That
    is the one edge the meadow has no use for and the desert needs
    everywhere."""
    lee = which in ("S", "E", "cSE", "cSW", "cNE")
    if d < 0:
        return under
    if d < (2.2 if lee else 0.9):
        return edge if (x + y * 2) % 3 else under
    if d < (3.4 if lee else 1.8):
        return over if rnd(2) else edge
    return over


STYLE = {
    "tile.water": _edge_water,
    "tile.oasis": _edge_oasis,
    "tile.salt": lambda d, w, x, y, o, u, r, p: _edge_drift(d, w, x, y, o, u, r, "SLD"),
    "tile.scrub": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "SCD"),
    "tile.sandstone": lambda d, w, x, y, o, u, r, p: _edge_drift(d, w, x, y, o, u, r, "DND"),
    "tile.shallow": _edge_shallow,
    "tile.path": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "PTD", "PTL"),
    "tile.dirt": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "DRL"),
    "tile.gravel": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "STD"),
    "tile.sand": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "SAD"),
    "tile.leaves": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "LFD"),
    "tile.field": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "TH"),
    "tile.cobble": lambda d, w, x, y, o, u, r, p: _edge_kerb(d, w, x, y, o, u, r, "STD"),
    "tile.stone": _edge_stone,
}


BLEND_OVER = "tile.grass"      # what a terrain carves out of, unless it says


def blend(tid, mask, phase=0, under_tid=BLEND_OVER):
    """The tile for `tid` with this neighbour arrangement, carved out of the
    terrain it sits on - grass for most things, but a field is cut out of bare
    earth and a shoal out of sand, which is what those edges look like."""
    over = frame(tid, 0, phase)
    under = BASE[under_tid](sum(map(ord, tid)) % VARIANTS.get(under_tid, 1))
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

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
    """Turf, in three moods: even, damp and dry.

    Reseeding alone was not enough. Three variants drawn with the same counts
    differ only in where their blades landed, and a field of them reads as one
    texture repeating - which is what it was. So the counts change with the
    seed as well: 1 is damper, with more deep patches and more blades in
    shadow; 2 is drier, with fewer of both and more tips catching the light.
    The same grass over three kinds of ground, rather than one grass shuffled."""
    deep, shade, light = ((2, 8, 6), (4, 12, 3), (1, 5, 10))[seed % 3]
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GR")
    rnd = scatter(0x6A55 + seed * 977)
    for _ in range(deep):                         # deep patches under the blades
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 3, "GRX", 4 + rnd(3))
    for _ in range(shade):                        # blades in the shade
        _blade(c, rnd(SIZE), rnd(SIZE), 1 + rnd(2), "GRD")
    for _ in range(light):                        # blades catching the light
        _blade(c, rnd(SIZE), rnd(SIZE), 1 + rnd(2), "GRL")
    return c


def grass_tall(seed=0, phase=0):
    """Rank, unmown grass: darker, with taller blades and lit tips. Three
    moods, on the same rule as grass() - thicker, ranker, or going over."""
    deep, dark, lit = ((2, 10, 8), (3, 14, 5), (1, 7, 12))[seed % 3]
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "GRD")
    rnd = scatter(0x7A11 + seed * 613)
    for _ in range(deep):
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 5, 4, "GRX", 5 + rnd(4))
    for _ in range(dark):
        _blade(c, rnd(SIZE), rnd(SIZE), 2 + rnd(2), "GRX")
    for _ in range(lit):
        x, y, h = rnd(SIZE), rnd(SIZE), 2 + rnd(2)
        _blade(c, x, y, h, "GR")
        _put(c, x, y - h, "GRL")                  # the tip catches the light
    return c


def grass_flower(seed=0, phase=0):
    """Grass with flowers through it. The variants differ in how many and in
    which colour leads, so a meadow is not three blooms stamped over and over
    in the same two colours."""
    n, lead = ((3, "FL"), (5, "EW"), (2, "FL"))[seed % 3]
    c = grass(seed)
    rnd = scatter(0xF10E + seed * 331)
    other = "EW" if lead == "FL" else "FL"
    for i in range(n):
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y + 1, "GRL")                  # stem
        head = lead if i % 2 else other           # and the head
        _put(c, x, y, head)
        _put(c, x - 1, y, head)
    return c


def forest(seed=0, phase=0):
    """The floor under a canopy: turf in shade, not bare earth.

    tile.leaves is the other half of a wood - litter over dark ground - and for
    a long time it was doing both jobs on its own, which put a brown field at
    hue 37 beside a meadow at 101 and split every map into two countries. What
    changes under trees is not the material, it is the light: the ground is
    still green, it is darker, and its green leans blue where the meadow's
    leans yellow. Three moods on grass()'s rule - deep shade, even, and a
    thinner canopy letting more through."""
    deep, low, lit = ((3, 9, 3), (5, 13, 1), (2, 6, 7))[seed % 3]
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "FR")
    rnd = scatter(0x4E22 + seed * 857)
    for _ in range(deep):                         # where the canopy closes over
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 6, 4, "FRD", 5 + rnd(4))
    for _ in range(low):                          # low growth - clumps, not blades
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 3, 2, "FRD", 2 + rnd(2))
    for _ in range(lit):                          # sun through a gap in it
        _blade(c, rnd(SIZE), rnd(SIZE), 1 + rnd(2), "FRL")
    for _ in range(2):                            # and a little fallen litter
        x, y = rnd(SIZE), rnd(SIZE)               # dark: at map scale a bright
        _put(c, x, y, "LFD")                      # speck every few pixels over a
        _put(c, x + 1, y, "LFD")                  # whole wood reads as confetti
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


def tall_stone(seed=0, phase=0):
    """Stone that stands up, where tile.stone lies flat.

    Making the blocks taller inside the tile did not work: both textures were
    still patterns painted on the ground, so a wall of one read at exactly the
    height of a wall of the other. Height is not block size, it is a top you
    can see and a face under it.

    So the tile is a block in oblique: the top five rows are the cap, lit,
    because that surface faces the sky; below it the face drops through mid to
    dark as it goes away from the light; and the last two rows are the shadow
    the course throws on the one behind it. Stacked, that repeats as cap, face,
    shadow - a wall in courses rather than a floor with lines on it.

    The two variants carry their perpends at different offsets, so a run of
    them breaks up instead of ruling one line down every tile boundary."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, 4, "STL")              # the cap, facing the sky
    c.row(0, SIZE - 1, 5, "ST")                   # the arris it turns on
    c.rect(0, 6, SIZE - 1, 10, "ST")              # the face, dropping away
    c.rect(0, 11, SIZE - 1, 13, "STD")
    c.rect(0, 14, SIZE - 1, SIZE - 1, "STX")      # and the shadow at its foot
    rnd = scatter(0x7C3B + seed * 191)
    for x in ((0, 8), (4, 12))[seed % 2]:         # perpends, cap and face
        c.col(x, 0, 13, "STD")
        c.set(x, 4, "ST")                         # catching light on the cap
    for _ in range(5):                            # pitting, so neither surface
        _put(c, rnd(SIZE), rnd(5), "ST")          # is flat
    for _ in range(6):
        _put(c, rnd(SIZE), 6 + rnd(8), "STD")
    return c


# --------------------------------------------------------------- the desert --
# The desert has its own base the way the meadow has grass: everything else in
# the biome is carved out of dune, so the two families never have to meet.
# -------------------------------------------------------------- the wetland --
# The third biome starts where the meadow gets its feet wet, so unlike the
# desert it has to *meet* the country next to it: marsh is carved out of the
# wilderness's grass, which is what makes the fringe a transition rather than
# a join.
#
# The open water is the lily's problem over again, and it took the lily's
# answer. Drawn as its own family with its own shore, every marsh tile beside
# a pool saw a different ground next to it and drew *its* edge - against
# grass, the only thing it knows how to be cut out of - so each pool came out
# ringed in meadow in the middle of a fen. The pool's shore was never the
# problem; the marsh's was. One shared family and neither draws an edge
# against the other, which also means the bog never needs a transition and
# does not have to blend at all: three variants a phase instead of
# forty-seven. What keeps the bank from reading as tile grid is the shape it
# is laid in and the reeds standing along it, which is where a bank's
# raggedness belongs anyway.
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
    """Fallen leaves lying on the floor of a wood, where the canopy is thick
    enough that nothing much grows through them.

    This is a patch inside a wood now rather than the wood's whole floor -
    tile.forest is the ground and this is the worn heart of it - which changes
    what it is drawn on. It used to be a full tile of dry tan over brown earth,
    and two of its three leaf colours were the *roof* key, a brick red: a key
    borrowed from a building is a building's colour wherever you put it, so a
    stand of trees had an orange carpet under it at hue 37 against a meadow at
    101. What shows between leaves in a damp wood is the wood's own ground, so
    that is what it is laid over, and only the leaves themselves are brown.
    That keeps it a patch of litter rather than a hole of bare earth."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "FRD")
    rnd = scatter(0x9E11 + seed * 743)
    for _ in range(22):                           # fallen leaves, two pixels
        key = ("LFD", "LF", "DRD")[rnd(3)]        # gone over, dry, and wet
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, key)
        _put(c, x + 1, y, key)
    for _ in range(6):                            # a few still catching light
        _put(c, rnd(SIZE), rnd(SIZE), "LF")
    for _ in range(4):                            # a twig
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "WDD")
        _put(c, x + 1, y + 1, "WDD")
    return c


def shallow(seed=0, phase=0):
    """Water you can wade: the bed shows through, and it moves.

    The bed is silt and weed, not sand. It was sand, which is a bed for water
    in a desert - in a meadow it put a scatter of yellow grit through every
    shoal and none of it belonged to the grass the pool was cut out of."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "WAL")
    rnd = scatter(0x2B4F + seed * 521)
    for _ in range(10):                           # silt and weed underneath
        _put(c, rnd(SIZE), rnd(SIZE), "GRX")
    for _ in range(4):
        _put(c, rnd(SIZE), rnd(SIZE), "GRD")
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


def cave_floor(seed=0, phase=0):
    """The floor of a burrow: earth packed hard by something heavy going in
    and out, with grit and the odd stone trodden into it.

    Darker than tile.dirt on purpose. This is ground with a roof over it and
    one doorway of daylight at the far end, so earth at open-air brightness
    under a near-black wall would read as a hole cut in the world rather than
    as a room you are standing in."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DRD")
    rnd = scatter(0xC0DE + seed * 211)
    for _ in range(4):                            # where the traffic has worn it
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 6, 4, "DR", 5 + rnd(3))
    for _ in range(8):                            # grit
        _put(c, rnd(SIZE), rnd(SIZE), "OL")
    for _ in range(4):                            # small stones, lit along the top
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "STD")
        _put(c, x, y - 1, "ST")
    for _ in range(5):
        _put(c, rnd(SIZE), rnd(SIZE), "DRL")
    return c


def cave_wall(seed=0, phase=0):
    """Earth and rock seen from inside the burrow, with root threads through it.

    Measured against the floor rather than eyeballed, the way plank_wall is:
    this sits far enough below tile.cave_floor that the tunnel has corners.
    The roots are the one thing in here that says the hole is under a tree,
    which is the whole reason the map exists - so they run through the wall
    rather than being left to prop.roots alone."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "OL")
    rnd = scatter(0x8B0E + seed * 293)
    # _pool rather than _patch: a scatter of stone-coloured pixels reads as
    # grit on a black wall, not as rock in it. Rock has to be a continuous
    # mass with a lit top before it reads as something shouldering through.
    for _ in range(3):
        cx, cy = rnd(SIZE), rnd(SIZE)
        _pool(c, cx, cy, 3 + rnd(2), 2 + rnd(2), "STX")
        _pool(c, cx, cy - 1, 2, 1, "STD")         # caught by what light there is
    for _ in range(3):                            # root threads, running downward
        x, y = rnd(SIZE), rnd(SIZE)
        for i in range(6):
            _put(c, x + (i // 3), y + i, "WDD")
    for _ in range(4):
        _put(c, rnd(SIZE), rnd(SIZE), "STX")
    return c


# ------------------------------------------------------- the farmed valley --
def mud(seed=0, phase=0):
    """Trampled wet earth: what the ground turns to round a trough, a well or
    a gate, where feet and hooves have been at it all year.

    It sits on the ladder the wetland set - ground with water in it is darker
    than turf - one step below tile.dirt, so from across a map the yard in
    front of a byre reads as churned before any detail can be made out. The
    detail is what says *why*: a puddle holding a bit of sky, and hoof marks
    pressed into it in pairs."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DRD")
    rnd = scatter(0x3D0D + seed * 457)
    for _ in range(3):                            # wetter hollows
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 6, 3, "LFD", 5 + rnd(3))
    if seed % 3 == 1:
        # A puddle, in one variant of three. Put in every tile, the same small
        # pool came back on a grid and a yard of mud read as a sheet of blue
        # gems. Flat and wide, with the sky on its far edge.
        px, py = rnd(SIZE), rnd(SIZE)
        _pool(c, px, py, 4, 2, "WAD")
        for k in range(-2, 2):
            _put(c, px + k, py - 1, "WA")
        _put(c, px - 2, py - 1, "WAL")
    for _ in range(1 + seed % 2):                 # cloven prints, in pairs
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "OL")
        _put(c, x + 2, y, "OL")
        _put(c, x, y + 1, "DR")
        _put(c, x + 2, y + 1, "DR")
    for _ in range(5):                            # ridges catching the light
        x, y = rnd(SIZE), rnd(SIZE)
        _put(c, x, y, "DR")
        _put(c, x + 1, y, "DR")
    return c


def tilled(seed=0, phase=0):
    """A kitchen garden: dug beds with rows of something coming up in them.

    tile.field is the plough - furrows and stubble, a crop that has been cut.
    This is the spade, at the scale of a household, so the rows are short
    and what stands in them is green and round rather than gold and straight.
    The rows run across the tile at a 4px pitch so a bed of several tiles
    reads as one set of drills; the plants in them are placed on a pitch too,
    because a garden is the one thing here somebody lined up on purpose."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "DR")
    rnd = scatter(0x7111 + seed * 283)
    for y in range(0, SIZE, 4):                   # the drills
        c.row(0, SIZE - 1, y, "DRD")
        c.row(0, SIZE - 1, (y + 3) % SIZE, "DRL")
    kind = seed % 2
    for row, y in enumerate(range(1, SIZE, 4)):
        off = (row % 2) * 2
        for x in range(off, SIZE + off, 4):
            if rnd(6) == 0:
                continue                          # a gap where one failed
            if kind == 0:                         # cabbages: a lit round head
                _put(c, x, y, "BU")
                _put(c, x + 1, y, "BUL")
                _put(c, x, y + 1, "BUD")
                _put(c, x + 1, y + 1, "BU")
            else:                                 # onions: upright leaves
                _put(c, x, y + 1, "BU")
                _put(c, x, y, "GRL")
                _put(c, x + 1, y + 1, "BUD")
    return c


def flagstone(seed=0, phase=0):
    """A floor of stone flags, for a house that is better than the shed: the
    inn, a chapel, a cottage kitchen.

    Cobble is setts - small, round, all one size, laid for cartwheels. Flags
    are big and laid flat for feet, so there are only three or four to a tile,
    in two courses that break joint. The first version cut the tile into
    seven slabs in four tones with a lit rim on every one, and a floor of it
    read as a maze of glyphs; a floor is the thing in a room that should be
    quiet. So: one stone, a dark joint, a lit arris only along the top of each
    course, and grit."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "ST")
    rnd = scatter(0xF1A6 + seed * 541)
    off = (0, 3)[seed % 2]
    for y0, joints in ((0, (0, 9)), (8, (4, 12))):
        c.row(0, SIZE - 1, y0, "STD")             # the bed joint
        c.row(0, SIZE - 1, y0 + 1, "STL")         # and the arris under it
        for jx in joints:
            for dy in range(8):
                _put(c, jx + off, y0 + dy, "STD")
    for _ in range(3):                            # a flag worn hollow
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 4, 2, "STD", 2)
    for _ in range(7):                            # grit
        _put(c, rnd(SIZE), rnd(SIZE), "STL" if rnd(2) else "STD")
    return c


def plaster_wall(seed=0, phase=0):
    """A limewashed wall between timbers, seen from inside: the cottage's own
    outside turned in, so a room reads as being in the house you walked into.

    It is the cloth shade rather than the cloth: indoors a wall is where the
    light falls off, and at full white it would be the brightest thing in the
    room and the floor would sink. The timbers are the dark wood: a rail the
    length of the wall, and posts at uneven spacing, so a run comes out framed
    in bays the way the cottage is."""
    c = Canvas(SIZE, SIZE)
    c.rect(0, 0, SIZE - 1, SIZE - 1, "CLD")
    rnd = scatter(0x9A57 + seed * 199)
    for _ in range(6):                            # the limewash, uneven
        _patch(c, rnd, rnd(SIZE), rnd(SIZE), 4, 3, "CL", 3)
    for _ in range(3):
        _put(c, rnd(SIZE), rnd(SIZE), "HNS")      # a stain or two
    c.row(0, SIZE - 1, 11, "WDD")                 # the mid rail, the whole run
    c.row(0, SIZE - 1, 12, "WD")
    if seed % 2:
        # A post in one variant of two, so the bays come out uneven. On every
        # tile the frame was a grid of squares and a wall read as a window.
        c.col(7, 0, SIZE - 1, "WDD")
        c.col(8, 0, SIZE - 1, "WD")
    return c


BASE = {
    "tile.grass": grass,
    "tile.grass_flower": grass_flower,
    "tile.grass_tall": grass_tall,
    "tile.leaves": leaves,
    "tile.forest": forest,
    "tile.path": path,
    "tile.gravel": gravel,
    "tile.dirt": dirt,
    "tile.field": field,
    "tile.cobble": cobble,
    "tile.stone": stone,
    "tile.tall_stone": tall_stone,
    "tile.wood_floor": wood_floor,
    "tile.plank_wall": plank_wall,
    "tile.cave_floor": cave_floor,
    "tile.cave_wall": cave_wall,
    "tile.shallow": shallow,
    "tile.water": water,
    "tile.mud": mud,
    "tile.tilled": tilled,
    "tile.flagstone": flagstone,
    "tile.plaster_wall": plaster_wall,
}
TILE_ORDER = list(BASE)

# How many seeded variants of each base to draw. A cell picks one by position,
# so the field changes without anyone having authored it.
VARIANTS = {"tile.grass": 3, "tile.grass_flower": 3, "tile.grass_tall": 3,
            "tile.forest": 3,
            "tile.leaves": 2, "tile.water": 2, "tile.wood_floor": 2,
            "tile.cave_floor": 3, "tile.cave_wall": 2, "tile.tall_stone": 2,
            "tile.mud": 3, "tile.tilled": 2, "tile.flagstone": 2,
            "tile.plaster_wall": 2}

# Tiles drawn in several phases. The art pipeline emits every phase as its own
# frame and the engine cycles them; the base frame is what the map resolves to.
# One clock for everything that moves on the floor is what keeps the scene
# from twitching, so they all run at the same frame time.
ANIMATED = {"tile.water": 3, "tile.shallow": 2}
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
        # A damp bank, not a beach. This was a strip of sand, which is what a
        # pond in a desert has - dropped into a meadow it drew a yellow ring
        # round every pool and none of it met the grass it was cut out of.
        return "GRD" if rnd(5) == 0 else "GRX"
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


def _edge_plank(d, which, x, y, over, under, rnd, phase):
    """A timber wall standing on a floor. Same idea as _edge_stone - the side
    you can see is a face with a lit cap over it, the other edges get a lit
    arris - but in wood, and carved out of the boards rather than out of turf.
    A wall whose transitions were cut from grass would be a shed standing in a
    field, and this one is only ever indoors."""
    downhill = which in ("S", "cSE", "cSW")
    if d < 0:
        return "WDD" if downhill and d >= -1.5 else under    # shadow on the floor
    if downhill:
        if d >= 3:
            return over
        if d >= 2:
            return "WDL"                                     # the cap
        return "OL" if x % 5 == 0 else "WDD"                 # the face, jointed
    if d < 1:
        return "WDL"                                         # arris
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


def _edge_wood(d, which, x, y, over, under, rnd, phase):
    """A wood thins, it does not stop. Wind is what rubs out a desert's edge
    and water a shore's; here it is growth, so the outermost thing in the
    picture is bracken standing in the turf beyond the last tree.

    It has to be scattered by *position*. Keyed off the depth instead, the
    bracken came out as a dotted line a fixed distance outside the boundary -
    which is an outline, drawn in a second colour. Hashing x and y puts the
    clumps where they fall and lets the band thin out with distance without
    ever tracing the shape."""
    if d < -3.4:
        return under
    if d < 0:
        # How far a tuft reaches is decided per 4x4 cell, so the fringe is
        # ragged along its length: some of the boundary has bracken three
        # pixels out into the turf and some has none at all. Thinning a band
        # of fixed width by distance alone still leaves a band, and a band
        # that follows the shape is an outline drawn in a second colour.
        reach = 1 + ((x // 4) * 37 + (y // 4) * 23) % 4
        if -d > reach:
            return under
        return "FRD" if (x * 7 + y * 11) % 3 == 0 else under
    if d < 1.2:                                   # and the turf giving way
        return over if (x * 5 + y * 3) % 3 else under
    if d >= 4 and rnd(7) == 0:
        return "FRL"                              # a gap the sun comes through
    return over


def _edge_kerb(d, which, x, y, over, under, rnd, edge):
    """A laid surface: a hard line, because someone put a kerb there."""
    if d < 0:
        return under
    if d < 1:
        return edge
    return over


def _edge_shallow(d, which, x, y, over, under, rnd, phase):
    """A shoal, not a pond: the water thins into the bed it lies on rather than
    breaking against a shore, so there is no foam line and no bank - a bank
    would be the bed drawn on the bed and read as a painted border."""
    if d < 0:
        return under
    if d < 1.6:                                   # the bed showing through
        return under if (x * 3 + y * 5 + phase) % 3 else over
    if d < 2.6:
        return over if (x + y + phase) % 2 else "GRX"
    return over


def _edge_plaster(d, which, x, y, over, under, rnd, phase):
    """A plastered wall standing on a stone floor: _edge_plank's shape in
    the cottage's materials. The face you can see ends in a dark timber sole
    plate, because that is what a timber-framed wall stands on, and it throws
    its shadow on the flags."""
    downhill = which in ("S", "cSE", "cSW")
    if d < 0:
        return "STD" if downhill and d >= -1.5 else under    # shadow on the flags
    if downhill:
        if d >= 3:
            return over
        if d >= 2:
            return "CL"                                      # the lit face
        return "WDD"                                         # the sole plate
    if d < 1:
        return "WD"                                          # the frame's edge
    return over


STYLE = {
    "tile.water": _edge_water,
    "tile.shallow": _edge_shallow,
    "tile.path": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "PTD", "PTL"),
    "tile.dirt": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "DRL"),
    "tile.gravel": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "STD"),
    "tile.leaves": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "LFD"),
    "tile.forest": _edge_wood,
    "tile.field": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "TH"),
    "tile.cobble": lambda d, w, x, y, o, u, r, p: _edge_kerb(d, w, x, y, o, u, r, "STD"),
    "tile.plank_wall": _edge_plank,
    "tile.stone": _edge_stone,
    "tile.tall_stone": _edge_stone,
    "tile.mud": lambda d, w, x, y, o, u, r, p: _edge_soft(d, w, x, y, o, u, r, "DR"),
    "tile.tilled": lambda d, w, x, y, o, u, r, p: _edge_trodden(d, w, x, y, o, u, r, "DRD", "DRL"),
    "tile.plaster_wall": _edge_plaster,
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

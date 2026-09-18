"""Environment props.

Two frame sizes, one rule. Small props share the actor's 32x32 frame and ground
line, so a single anchor rule and a single depth-sort rule cover both:
everything is positioned by the point its base sits on, and drawn in order of
that point's y. Structures too big for that frame use a 48x48 frame with the
same convention - three tiles wide, base on the anchor row - and the few things
bigger still use 64x64, four tiles wide, or 128x128 for the one that stands on
four tiles by four. Same convention every time, which is why the engine needs
no special case for any of them.

How much of the world a prop *blocks* is not decided here: that is the
"footprint" field in content/props/, a list of tile offsets from the anchor
tile. Art and collision are authored separately on purpose, so a bush can have
a canopy wider than the tile it stands on.
"""

import math

from gen.actor import FRAME, GROUND_Y
from gen.palette import Canvas, scatter

BASE_Y = GROUND_Y - 1          # last opaque row, matching the actor's boots

# Structures: three tiles wide, same anchor convention as the 32x32 frame.
BIG_FRAME = 48
BIG_GROUND_Y = 45
BIG_ANCHOR = (24, BIG_GROUND_Y)
BIG_BASE_Y = BIG_GROUND_Y - 1

# Four tiles wide, for the one or two things that dwarf a building. An even
# tile count has no middle tile, so the anchor cannot sit at both the frame
# centre and a tile centre: it sits at a tile centre (x=24), because that is
# what keeps the sprite square on the grid, and the art is drawn centred in
# the frame. The sprite therefore covers tile offsets -1, 0, +1, +2.
HUGE_FRAME = 64
HUGE_GROUND_Y = 61
HUGE_ANCHOR = (24, HUGE_GROUND_Y)
HUGE_BASE_Y = HUGE_GROUND_Y - 1

# Four tiles wide and four deep, which is the only reason this frame exists: a
# mass standing on a 4x4 patch of ground eats 64px of the frame from the bottom
# before any of it is height, and there is nothing left of a 64px frame to be
# tall with. Same rule as above - anchor on a tile centre, art centred in the
# frame - so it covers tile offsets -1, 0, +1, +2 and rises most of four tiles
# over them.
VAST_FRAME = 128
VAST_GROUND_Y = 125
VAST_ANCHOR = (56, VAST_GROUND_Y)
VAST_BASE_Y = VAST_GROUND_Y - 1


# --------------------------------------------------------------- helpers ---
def _shade(c, key, light, dark):
    """Rim-light a mass: lit where it faces up-left, shaded where it faces
    down-right. Derived from the silhouette, like the outline, so a shape can
    be redrawn without re-deciding where the light falls."""
    for y in range(c.h):
        for x in range(c.w):
            if c.px[y][x] != key:
                continue
            if c.get(x - 1, y) is None or c.get(x, y - 1) is None:
                c.px[y][x] = light
            elif c.get(x + 1, y) is None or c.get(x, y + 1) is None:
                c.px[y][x] = dark


def _taper(c, y0, y1, w0, w1, key, cx=15):
    """Trapezoid centred on the cx/cx+1 boundary; w is the half-width."""
    span = max(1, y1 - y0)
    for y in range(y0, y1 + 1):
        w = w0 + (w1 - w0) * (y - y0) // span
        c.row(cx - w, cx + 1 + w, y, key)


def _blob(c, y0, widths, key, cx=15):
    """Stack of centred rows - a hand-shaped mass, one half-width per row."""
    for i, w in enumerate(widths):
        c.row(cx - w, cx + 1 + w, y0 + i, key)


def _lobe(c, cx, cy, r, key):
    """A filled disc. A crown built from several of these has a lumpy edge,
    where one big stack of centred rows only ever looks like a balloon."""
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                c.set(x, y, key)


def _plank(c, x0, y0, x1, y1, key="WD", light="WDL", dark="WDD"):
    """A board with a lit top edge and a shaded underside."""
    c.rect(x0, y0, x1, y1, key)
    c.row(x0, x1, y0, light)
    if y1 > y0:
        c.row(x0, x1, y1, dark)


def _post(c, x, y0, y1, key="WD", dark="WDD"):
    c.col(x, y0, y1, key)
    c.col(x + 1, y0, y1, dark)


ROCK = ("ST", "STL", "STD", "STX")


def _mass(c, lobes, base_y, key="ST"):
    """A solid lump: overlapping discs, then each column filled between its
    own topmost and bottommost pixel so the gaps where two discs meet close up
    without the silhouette being dragged anywhere. Filling down to the ground
    line instead would give every boulder vertical sides and a flat top - a
    mesa, not a rock.

    The lobes that carry the weight are placed *through* the ground line and
    cut off by it, which is what leaves a broad flat base: a boulder resting
    on the turf, rather than one balanced on the point it was drawn from."""
    for cx, cy, r in lobes:
        _lobe(c, cx, cy, r, key)
    for x in range(c.w):
        col = [y for y in range(base_y + 1) if c.px[y][x] is not None]
        if col:
            c.col(x, col[0], col[-1], key)
    c.rect(0, base_y + 1, c.w - 1, c.h - 1, None)


# The planes a rock is shaded in, as (du, dv, bias, key) scored over the mass's
# own bounds - u across, v down, both 0..1 - with the brightest score winning.
# A partition by straight lines, because that is what a facet is: light meets
# shade along an edge. The first thing tried here was a gradient quantised into
# bands, and a mass this size shaded that way reads as an airbrushed ball with
# contours on it however the bands are tuned. Light from the up-left, as
# everywhere else in the game.
PLANES = ((-1.00, -0.80, 1.05, "STL"),      # the face turned to the light
          (0.00, 0.00, 0.45, "ST"),         # the broad middle of the rock
          (0.90, 0.50, -0.30, "STD"),       # turned away, to the right
          (1.10, 1.10, -1.00, "STX"))       # and the corner in its own shadow


def _form(c, base="ST", seed=7, planes=PLANES, tilt=0.0, grit=0.8):
    """Volume by position within the mass's own bounds: every pixel goes to
    whichever plane claims it, so the tones meet along straight edges and the
    thing reads as faceted rock. `scatter` roughens those edges a pixel at a
    time, which is the difference between granite and a folded paper bag.

    Every pixel it touches is one that is already `base`, so the shading stays
    inside the silhouette - painting it by raw coordinate is what puts pixels
    outside the shape, and nothing asserts that away."""
    cells = [(x, y) for y in range(c.h) for x in range(c.w) if c.px[y][x] == base]
    if not cells:
        return
    x0 = min(x for x, _ in cells)
    x1 = max(x for x, _ in cells)
    y0 = min(y for _, y in cells)
    y1 = max(y for _, y in cells)
    grain = scatter(seed)
    # The jitter is measured against the mass, not the score: u and v are
    # normalised, so a fixed jitter frays a small rock by a pixel and a large
    # one across a quarter of its face. Divided by the span it is the same few
    # pixels of ragged edge whatever size the boulder is.
    span = max(4, x1 - x0, y1 - y0)
    for x, y in cells:
        u = (x - x0) / max(1, x1 - x0)
        v = (y - y0) / max(1, y1 - y0)
        # Bend the field the planes are scored over rather than the planes
        # themselves: added to every score alike, a wobble would cancel out of
        # the comparison and do nothing at all.
        u, v = u + tilt * math.sin(v * 4.1 + 0.7), v + tilt * math.sin(u * 3.3)
        best, key = None, base
        for du, dv, bias, k in planes:
            s = du * u + dv * v + bias + (grain(5) - 2) * (grit / span)
            if best is None or s > best:
                best, key = s, k
        c.px[y][x] = key


def _rim(c, keys, light, dark):
    """_shade for a mass that already has form inside it. The rim comes from
    the silhouette and the interior from _form, so running _shade after _form
    would only catch the pixels _form happened to leave alone."""
    for y in range(c.h):
        for x in range(c.w):
            if c.px[y][x] not in keys:
                continue
            if c.get(x - 1, y) is None or c.get(x, y - 1) is None:
                c.px[y][x] = light
            elif c.get(x + 1, y) is None or c.get(x, y + 1) is None:
                c.px[y][x] = dark


def _crack(c, pts, key="STX"):
    """A fissure: straight runs between points, drawn only where there is rock
    to crack. What keeps a big face from reading as a painted backdrop."""
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        steps = max(abs(bx - ax), abs(by - ay), 1)
        for i in range(steps + 1):
            x = ax + (bx - ax) * i // steps
            y = ay + (by - ay) * i // steps
            if c.get(x, y) is not None:
                c.set(x, y, key)


def _moss(c, patches, key="MS", seed=5):
    """Lichen low on the sheltered side. Thinned towards the rim of each patch
    rather than filled solid: a disc of one colour on a boulder reads as a
    sticker, where a patch that frays out at its edge reads as something
    growing. Only ever over rock, so it cannot eat the outline."""
    grain = scatter(seed)
    for cx, cy, r in patches:
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d > r * r or grain(r * r) < d:
                    continue
                if c.get(x, y) in ROCK:
                    c.set(x, y, key)


# ----------------------------------------------------------------- nature ---
def bush():
    c = Canvas(FRAME, FRAME)
    for y, x0, x1 in ((16, 11, 20), (17, 9, 22), (18, 8, 23), (19, 7, 24),
                      (20, 6, 25), (21, 6, 25), (22, 6, 25), (23, 6, 25),
                      (24, 6, 25), (25, 6, 25), (26, 6, 25),
                      (27, 7, 24), (28, 9, 22)):
        c.row(x0, x1, y, "BU")
    for y, x0, x1 in ((17, 12, 15), (18, 10, 16), (19, 9, 15),
                      (20, 8, 13), (21, 8, 11), (22, 9, 10)):
        c.row(x0, x1, y, "BUL")          # light crescent on the upper left
    for y, x0, x1 in ((22, 22, 25), (23, 21, 25), (24, 20, 25), (25, 18, 25),
                      (26, 16, 25), (27, 7, 24), (28, 9, 22)):
        c.row(x0, x1, y, "BUD")          # shade curves round the lower right
    for x, y in ((13, 16), (18, 16)):
        c.set(x, y, None)                # notch the crown so it reads as leaves
    for x, y in ((14, 21), (11, 25), (19, 19)):
        c.set(x, y, "BUD")
    return c.outline()


def rock():
    c = Canvas(FRAME, FRAME)
    for y, x0, x1 in ((20, 13, 18), (21, 11, 20), (22, 10, 21), (23, 9, 22),
                      (24, 9, 22), (25, 9, 22), (26, 10, 21), (27, 11, 20),
                      (28, 12, 19)):
        c.row(x0, x1, y, "ST")
    for y, x0, x1 in ((20, 14, 17), (21, 12, 17), (22, 11, 16), (23, 10, 14)):
        c.row(x0, x1, y, "STL")          # lit top-left facet
    for y, x0, x1 in ((25, 16, 22), (26, 15, 21), (27, 13, 20), (28, 12, 19)):
        c.row(x0, x1, y, "STD")
    c.set(15, 23, "STD")                 # a crack, so it is not a smooth blob
    c.set(16, 24, "STD")
    return c.outline()


def sign():
    c = Canvas(FRAME, FRAME)
    c.rect(15, 24, 16, BASE_Y, "WDD")    # post
    c.rect(10, 15, 21, 22, "WD")         # board
    c.row(10, 21, 15, "WD")
    c.row(10, 21, 22, "WDD")
    c.col(21, 15, 22, "WDD")
    for y in (17, 19):                   # carved lines, not readable text
        c.row(12, 19, y, "WDD")
    return c.outline()


def tree_pine():
    c = Canvas(FRAME, FRAME)
    c.rect(14, 22, 17, BASE_Y, "WD")
    _taper(c, 3, 11, 1, 5, "BU")         # three skirts, each overlapping the
    _taper(c, 10, 18, 2, 8, "BU")        # one below, so the silhouette reads
    _taper(c, 16, 24, 3, 11, "BU")       # as a conifer rather than a cone
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WD", "WDD")
    return c.outline()


def tree_oak():
    c = Canvas(FRAME, FRAME)
    c.rect(14, 13, 17, BASE_Y, "WD")
    c.row(12, 19, 27, "WD")              # roots flare into the ground
    c.row(11, 20, 28, "WD")
    _blob(c, 2, (3, 5, 7, 8, 9, 10, 10, 10, 10, 9, 8, 7, 5, 3), "BU")
    for x, y in ((9, 8), (22, 11), (13, 3), (18, 14)):
        c.set(x, y, None)                # gaps in the crown, for leaves
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WD", "WDD")
    return c.outline()


def tree_dead():
    c = Canvas(FRAME, FRAME)
    c.rect(14, 7, 17, BASE_Y, "WDD")
    for x, y in ((13, 14), (12, 13), (11, 12), (10, 11), (10, 10), (9, 9)):
        c.set(x, y, "WDD")               # branch reaching left
        c.set(x, y - 1, "WDD")
    for x, y in ((18, 12), (19, 11), (20, 10), (21, 10), (22, 9), (22, 8)):
        c.set(x, y, "WDD")               # and one right, at a different height
    c.row(12, 19, 27, "WDD")
    c.row(11, 20, 28, "WDD")
    _shade(c, "WDD", "WD", "WDD")
    return c.outline()


def stump():
    c = Canvas(FRAME, FRAME)
    c.rect(9, 19, 22, BASE_Y, "WD")
    c.rect(9, 19, 22, 22, "WDL")         # the cut face, seen at an angle
    c.rect(11, 20, 20, 21, "WD")
    c.rect(13, 20, 18, 21, "WDL")        # growth rings
    c.set(15, 20, "WDD")
    c.set(16, 21, "WDD")
    for x in (11, 15, 19):               # bark grooves down the sides
        c.col(x, 23, 27, "WDD")
    c.col(22, 19, BASE_Y, "WDD")
    c.row(9, 22, BASE_Y, "WDD")
    return c.outline()


def log():
    c = Canvas(FRAME, FRAME)
    c.rect(4, 21, 27, BASE_Y, "WD")
    c.row(4, 27, 21, "WDL")
    c.row(4, 27, BASE_Y, "WDD")
    for x in (12, 17, 22):               # bark grain
        c.set(x, 24, "WDD")
        c.set(x + 1, 25, "WDD")
    c.rect(4, 21, 9, BASE_Y, "WDD")      # the sawn end, rings facing us
    c.rect(5, 22, 8, 27, "WDL")
    c.rect(6, 23, 7, 26, "WD")
    return c.outline()


def boulder():
    c = Canvas(FRAME, FRAME)
    _blob(c, 13, (4, 7, 9, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10, 9, 8), "ST")
    for y, x0, x1 in ((15, 12, 19), (16, 10, 20), (17, 9, 19),
                      (18, 8, 17), (19, 7, 15), (20, 7, 12)):
        c.row(x0, x1, y, "STL")          # one broad facet catching the light
    for y, x0, x1 in ((23, 19, 26), (24, 18, 26), (25, 17, 26),
                      (26, 16, 25), (27, 15, 24)):
        c.row(x0, x1, y, "STD")          # and one turned away from it
    _shade(c, "ST", "STL", "STD")
    return c.outline()


# ------------------------------------------------------------- the ladder ---
# Boulders by how much ground they stand on. A rock field drawn from one rock
# at one size reads as a repeated stamp however it is scattered, so the sizes
# are the point: two tiles is something to walk round, sixteen is something the
# road stops at. Each is authored at the frame its footprint needs rather than
# drawn small and scaled up, and the tiles it actually blocks are the
# "footprint" in content/props/ - the art is free to overhang them.


def boulder_2():
    """Two tiles: a split rock, waist high, the smallest thing here you cannot
    step over. Drawn across the anchor tile and the one to its right, which is
    what an even-width footprint means - there is no middle tile to sit on."""
    c = Canvas(BIG_FRAME, BIG_FRAME)
    _mass(c, ((28, 37, 14), (38, 42, 8)), BIG_BASE_Y)
    _form(c, seed=21, tilt=0.10)
    _crack(c, ((31, 22), (29, 30), (33, 38), (32, 44)))
    _rim(c, ROCK, "STL", "STD")
    return c.outline()


def boulder_4():
    """Four tiles, two by two: shoulder height and square on, the first size
    that hides what is behind it."""
    c = Canvas(BIG_FRAME, BIG_FRAME)
    _mass(c, ((29, 33, 16), (38, 42, 9), (26, 22, 10)), BIG_BASE_Y)
    _form(c, seed=34, tilt=0.13)
    _crack(c, ((27, 12), (30, 22), (25, 32), (28, 44)))
    _crack(c, ((36, 26), (41, 35)))
    _moss(c, ((20, 40, 5), (31, 43, 4)))
    _rim(c, ROCK, "STL", "STD")
    return c.outline()


def boulder_6():
    """Six tiles, three by two: a crag rather than a rock, tall enough that the
    road has to bend round it. Same footprint as a cottage, which is the point
    of putting one at a bend - it reads as a building until you are close."""
    c = Canvas(BIG_FRAME, BIG_FRAME)
    _mass(c, ((23, 31, 20), (11, 42, 10), (37, 40, 9), (28, 17, 12)),
          BIG_BASE_Y)
    _form(c, seed=55, tilt=0.11)
    _crack(c, ((21, 8), (26, 20), (20, 29), (23, 44)))
    _crack(c, ((33, 24), (38, 33), (35, 44)))
    _moss(c, ((7, 41, 6), (18, 43, 4), (40, 41, 4)))
    _rim(c, ROCK, "STL", "STD")
    return c.outline()


def boulder_8():
    """Eight tiles, four by two: the boulder you see from the other end of the
    valley. Four tiles across, so it shares the 64x64 frame and the anchor
    convention with the burrow tree."""
    c = Canvas(HUGE_FRAME, HUGE_FRAME)
    _mass(c, ((29, 40, 27), (12, 55, 12), (50, 52, 12), (36, 22, 15)),
          HUGE_BASE_Y)
    _form(c, seed=71, tilt=0.12)
    _crack(c, ((28, 10), (34, 28), (27, 42), (31, 60)))
    _crack(c, ((44, 32), (52, 46), (48, 60)))
    _crack(c, ((9, 46), (17, 55)))
    _moss(c, ((8, 55, 7), (23, 58, 5), (54, 56, 5), (39, 59, 4)))
    _rim(c, ROCK, "STL", "STD")
    return c.outline()


def boulder_16():
    """Sixteen tiles, four by four: the erratic the pass is named for. Two
    storeys of rock standing on a square of ground the size of a barnyard,
    which is why it gets a frame of its own - see VAST_FRAME above.

    Built in two masses rather than one so it reads as a block that split and
    settled: a lower plinth spreading out to the ground, and a leaning cap sat
    on top of it with the fissure between them running the whole way across.
    One dome this size, however lumpy its edge, is a boulder-shaped hill."""
    c = Canvas(VAST_FRAME, VAST_FRAME)
    _mass(c, ((62, 100, 40), (48, 74, 24), (84, 80, 20),
              (62, 58, 22)), VAST_BASE_Y)
    _form(c, seed=93, tilt=0.14)
    # The split: one long fissure across the whole mass, with the cap's weight
    # carried on the left of it, plus the shorter cracks that run off it.
    _crack(c, ((27, 80), (46, 72), (64, 76), (82, 68), (102, 76)))
    _crack(c, ((46, 72), (50, 50), (45, 28)))
    _crack(c, ((64, 76), (68, 96), (62, 112), (65, 124)))
    _crack(c, ((82, 68), (90, 86), (86, 104), (90, 124)))
    _crack(c, ((33, 90), (39, 108), (34, 124)))
    _moss(c, ((32, 110, 9), (50, 119, 7), (97, 114, 8), (73, 121, 6),
              (24, 96, 5)))
    _rim(c, ROCK, "STL", "STD")
    return c.outline()


def cairn():
    c = Canvas(FRAME, FRAME)
    for y0, w in ((24, 8), (20, 6), (16, 4), (13, 2)):   # stacked, tapering up
        c.rect(15 - w, y0, 16 + w, y0 + 4, "ST")
        c.row(15 - w, 16 + w, y0, "STL")
        c.row(15 - w, 16 + w, y0 + 4, "STD")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    _shade(c, "ST", "STL", "STD")
    return c.outline()


def mushroom():
    c = Canvas(FRAME, FRAME)
    c.rect(14, 19, 17, BASE_Y, "CL")     # stem
    c.col(17, 19, BASE_Y, "CLD")
    c.row(13, 18, BASE_Y, "CL")          # flaring into the leaf litter
    _blob(c, 15, (2, 4, 6, 7, 7), "RF")  # cap - one tile across, no more
    _shade(c, "RF", "RFL", "RFD")
    for x, y in ((11, 18), (19, 17), (15, 16)):
        c.set(x, y, "CL")                # spots
        c.set(x + 1, y, "CL")
    return c.outline()


# ---------------------------------------------------------------- village ---
def well():
    c = Canvas(FRAME, FRAME)
    c.rect(8, 20, 23, BASE_Y, "ST")      # the ring wall
    c.row(9, 22, 19, "STL")
    c.rect(11, 20, 20, 22, "OL")         # the dark of the shaft
    _post(c, 9, 9, 20)
    _post(c, 21, 9, 20)
    _taper(c, 3, 9, 4, 11, "TH")         # a little thatched roof
    _shade(c, "TH", "THL", "THD")
    c.rect(13, 10, 18, 12, "WD")         # the winch drum
    c.col(18, 10, 12, "WDD")
    c.col(15, 13, 18, "MTD")             # rope into the dark
    _shade(c, "ST", "STL", "STD")
    return c.outline()


def crate():
    c = Canvas(FRAME, FRAME)
    _plank(c, 9, 16, 22, BASE_Y)
    c.col(22, 16, BASE_Y, "WDD")
    c.rect(9, 16, 22, 17, "WDL")         # lid
    for i in range(12):                  # the diagonal brace across the face
        c.set(10 + i, 18 + i, "WDD")
        c.set(21 - i, 18 + i, "WDD")
    c.col(9, 16, BASE_Y, "WDD")
    return c.outline()


def barrel():
    c = Canvas(FRAME, FRAME)
    _blob(c, 14, (4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4), "WD")
    _shade(c, "WD", "WDL", "WDD")
    for y in (17, 22, 26):
        for x in range(9, 23):
            if c.get(x, y) is not None:
                c.set(x, y, "MT")        # iron hoops
    c.row(12, 19, 14, "WDL")             # the lid, seen from above
    c.set(20, 18, "MTL")
    c.set(20, 23, "MTL")
    return c.outline()


def sack():
    c = Canvas(FRAME, FRAME)
    _blob(c, 15, (3, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5), "CL")
    _shade(c, "CL", "CL", "CLD")
    c.rect(14, 13, 17, 15, "CLD")        # the gathered neck
    c.row(13, 18, 16, "MTD")             # a cord round it
    for x, y in ((12, 22), (13, 25), (20, 20)):
        c.set(x, y, "CLD")               # creases
    return c.outline()


def woodpile():
    c = Canvas(FRAME, FRAME)
    for y0, xs in ((23, (3, 9, 15, 21)), (17, (6, 12, 18))):
        for x in xs:                     # each log is one end-on disc: bark
            c.rect(x, y0, x + 5, y0 + 5, "WDD")          # ring, sawn face,
            c.rect(x + 1, y0 + 1, x + 4, y0 + 4, "WDL")  # heartwood
            c.rect(x + 2, y0 + 2, x + 3, y0 + 3, "WD")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def anvil():
    c = Canvas(FRAME, FRAME)
    c.rect(11, 24, 20, BASE_Y, "WD")     # the stump it stands on
    c.col(20, 24, BASE_Y, "WDD")
    c.rect(10, 15, 21, 17, "MT")         # the face
    c.row(10, 21, 15, "MTL")
    c.rect(22, 15, 25, 17, "MT")         # the horn
    c.set(25, 16, "MT")
    c.rect(14, 18, 18, 20, "MTD")        # the waist
    c.rect(12, 21, 20, 23, "MT")         # the foot
    c.row(12, 20, 23, "MTD")
    return c.outline()


LAMP_WICK = [
    ((15, 8), (16, 8)),
    ((15, 7), (16, 8)),
    ((16, 7), (15, 8)),
    ((14, 8), (16, 8)),      # distinct: phases 2 and 3 were the same two pixels
]


def lamp_post(phase=0):
    c = Canvas(FRAME, FRAME)
    _post(c, 15, 10, BASE_Y)
    c.rect(13, BASE_Y - 1, 18, BASE_Y, "STD")   # a stone base
    c.rect(12, 4, 19, 5, "MTD")          # the cap
    c.rect(12, 10, 19, 11, "MTD")        # and the tray
    c.col(12, 5, 10, "MTD")
    c.col(19, 5, 10, "MTD")
    # The pane is lit the same every frame; it is the wick inside it that
    # moves, which is all a lantern needs - a lamp whose whole glass pulses
    # reads as a warning light.
    c.rect(13, 6, 18, 9, "FIL")          # the lit pane
    c.rect(14, 7, 17, 9, "FI")
    for x, y in LAMP_WICK[phase % len(LAMP_WICK)]:
        c.set(x, y, "FID")
    return c.outline()


def signpost():
    c = Canvas(FRAME, FRAME)
    _post(c, 15, 12, BASE_Y)
    c.rect(4, 7, 19, 11, "WD")           # arm pointing left
    c.row(5, 19, 7, "WDL")
    c.row(5, 19, 11, "WDD")
    for i in range(3):
        c.row(4 + i, 4 + i, 8 + i, "WD")
    c.rect(13, 14, 27, 18, "WD")         # and one pointing right
    c.row(13, 26, 14, "WDL")
    c.row(13, 26, 18, "WDD")
    for y in (9, 16):                    # carved lines, not readable text
        c.row(8, 16, y, "WDD")
    return c.outline()


def statue():
    c = Canvas(FRAME, FRAME)
    c.rect(8, 24, 23, BASE_Y, "ST")      # plinth
    c.row(8, 23, 24, "STL")
    c.rect(10, 21, 21, 23, "ST")
    c.rect(12, 12, 19, 21, "ST")         # robed body
    _blob(c, 6, (2, 3, 3, 3, 2), "ST")   # head
    c.rect(9, 13, 11, 15, "ST")          # arms held out
    c.rect(20, 13, 22, 15, "ST")
    _shade(c, "ST", "STL", "STD")
    c.set(14, 8, "STD")                  # eyes, worn almost flat
    c.set(17, 8, "STD")
    return c.outline()


def tombstone():
    c = Canvas(FRAME, FRAME)
    c.rect(11, 16, 20, BASE_Y, "ST")
    _blob(c, 12, (2, 3, 4, 4), "ST")     # rounded top
    c.rect(9, BASE_Y - 1, 22, BASE_Y, "STD")    # it has sunk into the turf
    _shade(c, "ST", "STL", "STD")
    for y in (19, 21, 23):               # an inscription, illegible at this size
        c.row(13, 18, y, "STD")
    return c.outline()


def bench():
    c = Canvas(FRAME, FRAME)
    _plank(c, 4, 20, 27, 22)             # seat
    _plank(c, 5, 12, 26, 14)             # backrest
    for x in (6, 23):
        _post(c, x, 14, 20)              # back uprights
        _post(c, x, 22, BASE_Y)          # legs
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def table():
    c = Canvas(FRAME, FRAME)
    _plank(c, 4, 17, 27, 20)
    c.row(4, 27, 21, "WDD")              # the edge of the top, in shadow
    for x in (7, 22):
        _post(c, x, 22, BASE_Y)
    c.rect(9, 25, 22, 25, "WDD")         # a stretcher between the legs
    return c.outline()


def chest():
    c = Canvas(FRAME, FRAME)
    c.rect(8, 19, 23, BASE_Y, "WD")      # body
    c.col(23, 19, BASE_Y, "WDD")
    c.row(8, 23, BASE_Y, "WDD")
    _blob(c, 13, (7, 7, 8, 8, 8, 8), "WD", cx=15)   # the domed lid
    c.row(8, 23, 13, "WDL")
    c.row(8, 23, 18, "WDD")
    for x in (11, 20):                   # iron bands over the lid and body
        c.col(x, 13, BASE_Y, "MT")
        c.col(x + 1, 13, BASE_Y, "MTD")
    c.rect(14, 18, 17, 21, "MTL")        # the lock plate
    c.set(15, 20, "OL")
    c.set(16, 20, "OL")
    return c.outline()


# Bees, two per frame, going round the skep. Drawn after the outline: a bee
# is one pixel, and the outline pass would wrap each into a three-by-three
# lump and turn the swarm into a set of dice.
BEES = [
    ((4, 12), (26, 17)),
    ((6, 8), (24, 21)),
    ((10, 5), (27, 13)),
    ((3, 16), (22, 7)),
]


def beehive(phase=0):
    c = Canvas(FRAME, FRAME)
    _blob(c, 13, (3, 5, 6, 7, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9), "TH")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    _shade(c, "TH", "THL", "THD")
    for y in (16, 20, 24):               # the coils of the skep
        c.row(7, 24, y, "THD")
    c.rect(14, 25, 17, BASE_Y, "OL")     # the entrance
    c.outline()
    for x, y in BEES[phase % len(BEES)]:
        c.set(x, y, "OL")
        c.set(x + 1, y, "FIL")           # a body and the light on its back
    return c


def scarecrow():
    c = Canvas(FRAME, FRAME)
    _post(c, 15, 14, BASE_Y)
    c.rect(6, 14, 25, 15, "WD")          # the crossbar
    c.rect(10, 14, 21, 24, "CL")         # a shirt hung on it
    _shade(c, "CL", "CL", "CLD")
    c.rect(11, 22, 20, 24, "TH")         # straw poking out at the hem
    for x in (7, 8, 23, 24):
        c.set(x, 16, "TH")
        c.set(x, 17, "TH")
    _blob(c, 7, (3, 4, 4, 4, 3), "TH")   # a straw head
    _shade(c, "TH", "THL", "THD")
    c.set(13, 9, "OL")                   # two buttons for eyes and a stitch
    c.set(18, 9, "OL")
    c.row(14, 17, 11, "OL")
    c.rect(10, 6, 21, 7, "WDD")          # hat brim
    _taper(c, 3, 5, 1, 3, "WDD")         # and crown
    return c.outline()


# A flame per phase: the stones and the logs do not move, so only the fire is
# written out four times. Uneven on purpose - a flame that breathes in and out
# on a regular count reads as a pulse rather than as burning.
CAMPFIRE_FLAME = [
    (12, (1, 2, 3, 4, 4, 5, 5, 5, 5, 4, 3), (14, 18, 17, 23), (15, 14)),
    (13, (1, 2, 3, 3, 4, 5, 5, 5, 4, 4), (14, 19, 17, 23), (17, 13)),
    (11, (1, 1, 2, 3, 4, 4, 5, 5, 5, 5, 4, 3), (13, 18, 16, 22), (13, 11)),
    (12, (1, 2, 2, 3, 4, 5, 5, 4, 5, 4, 3), (15, 18, 18, 23), (16, 15)),
]


def campfire(phase=0):
    def stone(x, y):
        c.rect(x, y, x + 3, y + 2, "ST")
        c.row(x, x + 3, y, "STL")
        c.row(x, x + 3, y + 2, "STD")

    c = Canvas(FRAME, FRAME)
    for x, y in ((10, 20), (17, 20)):    # the ring reads as an ellipse: these
        stone(x, y)                      # two sit behind the flame
    for i in range(10):                  # two logs, crossed over the ashes
        c.set(8 + i, 27 - i // 3, "WDD")
        c.set(9 + i, 26 - i // 3, "WD")
        c.set(23 - i, 27 - i // 3, "WDD")
        c.set(22 - i, 26 - i // 3, "WDL")
    top, widths, heart, spark = CAMPFIRE_FLAME[phase % len(CAMPFIRE_FLAME)]
    _blob(c, top, widths, "FI")
    _shade(c, "FI", "FIL", "FID")
    c.rect(*heart, "FIL")                # the hot heart of it
    for x, y in ((4, 23), (24, 23), (8, 26), (14, 27), (20, 26)):
        stone(x, y)                      # and these in front of it
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    c.outline()
    c.set(spark[0], spark[1], "FIL")     # a spark, after the outline so it
    return c                             # stays a speck instead of a blob


TROUGH_RIPPLE = [(8, 14), (13, 19), (17, 23)]


def trough(phase=0):
    c = Canvas(FRAME, FRAME)
    c.rect(4, 19, 27, BASE_Y, "WD")
    c.rect(6, 20, 25, 23, "WA")          # water, sitting below the rim
    c.row(6, 25, 20, "WAL")
    # One dark band drifting along the surface. Slow: standing water in a
    # trough should barely move, and a fast ripple makes it look like a stream.
    _r0, _r1 = TROUGH_RIPPLE[phase % len(TROUGH_RIPPLE)]
    c.row(_r0, _r1, 22, "WAD")
    c.row(4, 27, 19, "WDL")
    c.row(4, 27, BASE_Y, "WDD")
    c.col(27, 19, BASE_Y, "WDD")
    for x in (7, 24):                    # end bands
        c.col(x, 24, BASE_Y, "WDD")
    return c.outline()


def flowers():
    """A clump of wildflowers. Walkable, so unlike every other prop here the
    hero goes through it rather than round it - which is the whole reason it is
    drawn low and open, with the ground showing between the stems. Anything
    tall enough to hide a footfall reads as a bush, and a player who thinks a
    thing is solid will walk round it whatever the collision map says.

    No outline, for the same reason: the 1px rim that makes a prop sit *on* the
    grass is exactly what would stop these sitting *in* it.
    """
    c = Canvas(FRAME, FRAME)
    for x, h, head in ((10, 5, "FL"), (13, 7, "EW"), (16, 6, "FL"),
                       (19, 4, "EW"), (21, 6, "FL"), (12, 4, "FL")):
        top = BASE_Y - h
        c.col(x, top + 1, BASE_Y, "GRD")         # the stem, in the grass shade
        c.set(x, top, head)                      # and the head above it
        c.set(x - 1, top, head)
        c.set(x + 1, top, head)
        c.set(x, top - 1, head)
        c.set(x, top + 1, "GRX")                 # a shadow under each head
    for x in (9, 14, 18, 22):                    # leaves, sitting in the turf
        c.set(x, BASE_Y, "GRL")
        c.set(x + 1, BASE_Y - 1, "GRD")
        c.set(x - 1, BASE_Y - 1, "GRX")
    return c


def flower_pot():
    c = Canvas(FRAME, FRAME)
    _taper(c, 21, BASE_Y, 6, 4, "RFD")   # a terracotta pot, narrowing down
    c.rect(8, 19, 23, 21, "RF")          # with a lipped rim
    _shade(c, "RFD", "RF", "RFD")
    _blob(c, 12, (2, 4, 5, 6, 6, 6, 7), "BU")
    _shade(c, "BU", "BUL", "BUD")
    for x, y in ((11, 14), (16, 12), (20, 15)):         # three blooms
        c.rect(x, y - 1, x + 1, y, "FL")
        c.set(x - 1, y, "FL")
        c.set(x + 2, y, "FL")
    return c.outline()


# ------------------------------------------------------------- structures ---
def house():
    c = Canvas(BIG_FRAME, BIG_FRAME)
    c.rect(6, 24, 41, BIG_BASE_Y, "CL")                 # plastered walls
    _shade(c, "CL", "CL", "CLD")
    for x in (6, 23, 41):                               # exposed timber frame
        c.col(x, 24, BIG_BASE_Y, "WDD")
    c.row(6, 41, 24, "WDD")
    c.row(6, 41, 34, "WDD")
    _taper(c, 8, 25, 4, 21, "RF", cx=23)                # the roof
    _shade(c, "RF", "RFL", "RFD")
    for y in range(11, 26, 3):                          # courses of tile
        for x in range(BIG_FRAME):
            if c.get(x, y) == "RF":
                c.set(x, y, "RFD")
    c.rect(20, 32, 27, BIG_BASE_Y, "WD")                # door
    c.col(27, 32, BIG_BASE_Y, "WDD")
    c.row(20, 27, 32, "WDD")
    c.set(25, 39, "MTL")                                # handle
    for x0 in (11, 32):                                 # windows
        c.rect(x0, 28, x0 + 5, 33, "WDD")
        c.rect(x0 + 1, 29, x0 + 4, 32, "FIL")
        c.col(x0 + 2, 29, 32, "WDD")
        c.row(x0 + 1, x0 + 4, 30, "WDD")
    c.rect(32, 4, 37, 12, "ST")                         # chimney
    c.row(31, 38, 4, "STL")
    _shade(c, "ST", "STL", "STD")
    return c.outline()


def barn():
    c = Canvas(BIG_FRAME, BIG_FRAME)
    c.rect(5, 20, 42, BIG_BASE_Y, "RF")                 # red board walls
    _shade(c, "RF", "RFL", "RFD")
    for x in range(7, 42, 4):                           # vertical boards
        c.col(x, 20, BIG_BASE_Y, "RFD")
    _taper(c, 6, 21, 8, 22, "WDD", cx=23)               # gambrel roof, lower
    _taper(c, 2, 9, 3, 9, "WDD", cx=23)                 # and upper pitch
    _shade(c, "WDD", "WD", "WDD")
    c.rect(16, 28, 31, BIG_BASE_Y, "WD")                # the double doors
    _shade(c, "WD", "WDL", "WDD")
    c.col(23, 28, BIG_BASE_Y, "WDD")
    c.col(24, 28, BIG_BASE_Y, "WDD")
    c.row(16, 31, 28, "WDD")
    for i in range(9):                                  # cross braces on them
        c.set(17 + i, 30 + i, "WDL")
        c.set(30 - i, 30 + i, "WDL")
    c.rect(20, 12, 27, 18, "OL")                        # the hayloft opening
    c.rect(21, 13, 26, 17, "TH")
    _shade(c, "TH", "THL", "THD")
    return c.outline()


def tower():
    c = Canvas(BIG_FRAME, BIG_FRAME)
    c.rect(13, 12, 34, BIG_BASE_Y, "ST")
    for y in range(14, BIG_BASE_Y, 5):                  # courses of block
        c.row(13, 34, y, "STD")
    for y in range(14, BIG_BASE_Y, 10):                 # staggered joints
        for x in range(18, 35, 8):
            c.col(x, y + 1, y + 4, "STD")
    for y in range(19, BIG_BASE_Y, 10):
        for x in range(14, 35, 8):
            c.col(x, y + 1, y + 4, "STD")
    c.rect(11, 8, 36, 13, "ST")                         # the parapet, oversailing
    for x in range(12, 36, 5):                          # crenellations
        c.rect(x, 4, x + 2, 8, "ST")
    c.rect(21, 20, 26, 28, "OL")                        # an arched window
    c.rect(22, 21, 25, 27, "MTD")
    c.rect(20, 36, 27, BIG_BASE_Y, "WD")                # and a barred door
    _shade(c, "WD", "WDL", "WDD")
    for x in (22, 25):
        c.col(x, 36, BIG_BASE_Y, "MTD")
    _shade(c, "ST", "STL", "STD")
    return c.outline()


def windmill(phase=0):
    c = Canvas(BIG_FRAME, BIG_FRAME)
    _taper(c, 14, BIG_BASE_Y, 5, 11, "CL", cx=23)       # the tapered tower
    _shade(c, "CL", "CL", "CLD")
    for y in range(18, BIG_BASE_Y, 6):
        c.row(14, 33, y, "CLD")
    _taper(c, 8, 15, 2, 7, "WDD", cx=23)                # the cap
    _shade(c, "WDD", "WD", "WDD")
    c.rect(20, 34, 27, BIG_BASE_Y, "WD")                # door
    c.col(27, 34, BIG_BASE_Y, "WDD")
    c.row(20, 27, 34, "WDD")
    # Four sails on a turning hub. Four arms are 90 degrees apart, so a quarter
    # turn is a whole visual cycle and the frames step 22.5 degrees - any more
    # and it flicks between poses instead of turning.
    for k in range(4):
        a = math.radians(45 + k * 90 + phase * 22.5)
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux                                # across the spar
        # Stepped in halves, or a diagonal at 22.5 degrees comes out as a
        # dotted line with gaps in it; and the cloth hangs on one side of the
        # spar rather than both, which is what a sail does and what stops the
        # arm reading as a scribble when it turns.
        i = 2.0
        while i <= 11.0:
            c.set(round(23 + ux * i), round(12 + uy * i), "WD")
            i += 0.5
        i = 3.5
        while i <= 11.0:
            for w in (1, 2):
                c.set(round(23 + ux * i + px * w), round(12 + uy * i + py * w), "TH")
            i += 0.5
    c.rect(22, 11, 25, 14, "WDD")                       # the hub
    return c.outline()


def shed():
    """A shieling: the hut kept up on the high ground, built out of what was
    lying next to it. Drystone to head height, a steep plank roof above that,
    and stones laid along the boards - which is the detail that says weather,
    because nobody weights a roof anywhere the wind does not lift it."""
    c = Canvas(BIG_FRAME, BIG_FRAME)
    c.rect(7, 24, 40, BIG_BASE_Y, "ST")                 # drystone walls
    for i, y in enumerate(range(27, BIG_BASE_Y, 4)):    # rough courses, with
        c.row(7, 40, y, "STD")                          # the joints staggered
        for x in range(10 + (i % 2) * 4, 40, 8):        # so no two line up
            c.col(x, y - 3, y - 1, "STD")
    _shade(c, "ST", "STL", "STD")

    _taper(c, 8, 25, 1, 20, "WD", cx=23)                # a steep roof, laid
    _shade(c, "WD", "WDL", "WDD")                       # over the walls so the
    for y in range(11, 26, 3):                          # rain clears them
        for x in range(BIG_FRAME):
            if c.get(x, y) == "WD":
                c.set(x, y, "WDD")                      # the boards
    for y, x in ((13, 19), (13, 27), (17, 14), (17, 32), (21, 9), (21, 37)):
        c.set(x, y, "STL")                              # and the stones that
        c.set(x + 1, y, "ST")                           # hold them down
        c.set(x, y + 1, "STD")

    c.rect(19, 32, 28, BIG_BASE_Y, "STD")               # a dressed surround
    c.row(19, 28, 32, "STL")                            # under a lit lintel
    c.rect(20, 33, 27, BIG_BASE_Y, "WD")                # the door
    c.col(20, 33, BIG_BASE_Y, "WDL")
    c.col(27, 33, BIG_BASE_Y, "WDD")
    for x in range(22, 27, 2):
        c.col(x, 34, BIG_BASE_Y, "WDD")                 # its boards
    c.set(25, 39, "MTL")                                # and the latch

    c.rect(10, 28, 16, 34, "STD")                       # one small window,
    c.rect(11, 29, 15, 33, "FIL")                       # lit from inside
    c.col(13, 29, 33, "WDD")
    c.row(11, 15, 31, "WDD")

    c.rect(33, 11, 35, 21, "MT")                        # a stovepipe, standing
    c.col(35, 11, 21, "MTD")                            # clear of the ridge
    c.rect(32, 9, 36, 11, "MTL")
    return c.outline()


def burrow_tree():
    """An old tree with a burrow under its roots, four tiles across.

    Drawn in the order it would be seen: roots and trunk, the crown over them,
    then the hole cut into the trunk that gives the thing its name. The root
    flare reaches nearly the full width of the frame on purpose - it is what
    makes a four-tile footprint read as solid rather than as a canopy floating
    over walkable ground.

    The crown is built from lobes and then given its own light and shade
    inside, not just at the rim: a mass this size shaded only at the edge
    reads as one flat green balloon, whatever shape its silhouette is."""
    c = Canvas(HUGE_FRAME, HUGE_FRAME)
    CX = 31                      # rows span CX-w .. CX+1+w, so centred on x=32

    # Trunk, widening as it drops.
    _taper(c, 26, 52, 6, 10, "WD", cx=CX)
    # Roots, as separate humps along the ground rather than one trapezoid with
    # slices cut out of it - cutting gaps into a solid flare severs it and
    # leaves specks behind.
    for cx, cy, r in ((32, 56, 11), (19, 58, 7), (45, 58, 7),
                      (10, 60, 5), (54, 60, 5)):
        _lobe(c, cx, cy, r, "WD")
    for y in range(HUGE_GROUND_Y, HUGE_FRAME):      # nothing below the base
        for x in range(HUGE_FRAME):
            c.set(x, y, None)

    # A crown of overlapping lobes.
    for cx, cy, r in ((32, 22, 19), (16, 24, 12), (48, 24, 12), (32, 12, 11),
                      (21, 14, 8), (43, 14, 8), (11, 31, 7), (53, 31, 7),
                      (32, 32, 11)):
        _lobe(c, cx, cy, r, "BU")

    # Clumps: shadowed undersides low and to the right, lit tops high and to
    # the left. This is the internal form, and it does most of the work.
    # Each clump is a crescent, not a disc: the lobe, then a plain lobe laid
    # back over it offset towards the light. A full disc of the lighter green
    # reads as a pale spot stuck on the foliage; a crescent reads as light
    # catching the top of a clump, which is what it is.
    for cx, cy, r in ((25, 35, 7), (41, 34, 8), (52, 30, 5), (34, 39, 6),
                      (13, 30, 4), (44, 20, 5)):
        _lobe(c, cx, cy, r, "BUD")
        _lobe(c, cx - 2, cy - 2, r - 1, "BU")
    for cx, cy, r in ((24, 11, 6), (14, 20, 4), (38, 8, 5), (30, 19, 4),
                      (47, 15, 3)):
        _lobe(c, cx, cy, r, "BUL")
        _lobe(c, cx + 2, cy + 2, r - 1, "BU")

    # Sky through the leaves. Irregular on purpose: neat little diamonds read
    # as ornaments stuck on the tree rather than as gaps in it.
    for x, y in ((22, 19), (23, 19), (22, 20),
                 (40, 16), (41, 16), (41, 17), (42, 17),
                 (30, 9), (31, 10),
                 (36, 27), (37, 27), (36, 28),
                 (15, 26), (16, 27),
                 (49, 27), (50, 28), (50, 27),
                 (27, 30), (26, 31),
                 (33, 14), (34, 14),
                 (19, 33), (20, 33)):
        c.set(x, y, None)

    # Bark, on whatever trunk the crown left showing.
    for x in (CX - 7, CX - 3, CX + 4, CX + 8):
        for y in range(30, 58):
            if c.get(x, y) == "WD":
                c.set(x, y, "WDD")

    # The burrow: an arch cut into the base. OL, not a stone key - a hollow
    # under a tree is the darkest thing in the frame, and grey reads as rock.
    arch = (3, 4, 5, 6, 6, 7, 7, 7, 7, 7, 7, 7)
    for i, w in enumerate(arch):
        c.row(CX - w, CX + 1 + w, 49 + i, "OL")
    for y in (58, 59, 60):
        c.row(CX - 6, CX + 1 + 6, y, "DRD")
    c.row(CX - 5, CX + 1 + 5, 60, "DR")
    for x, y in ((CX - 4, 59), (CX + 5, 60), (CX + 1, 59)):
        c.set(x, y, "DRL")
    # A lip of shadow on the trunk around the mouth, so the hole is recessed
    # rather than painted on. _shade cannot do this: the arch is not
    # transparent, so it reads as interior and never gets an edge.
    for y in range(47, HUGE_GROUND_Y):
        for x in range(CX - 10, CX + 11):
            if c.get(x, y) != "WD":
                continue
            if any(c.get(x + dx, y + dy) in ("OL", "DRD", "DR")
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                c.set(x, y, "WDD")

    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")
    return c.outline()


def workbench():
    """A bench to work at: a thick top on trestles, with the tools that live
    on it. The vice at the near end is what says workbench rather than table."""
    c = Canvas(FRAME, FRAME)
    _plank(c, 2, 15, 29, 19)
    c.row(2, 29, 20, "WDD")                       # the edge of the top
    for x in (5, 24):
        _post(c, x, 21, BASE_Y)
    c.rect(7, 24, 24, 25, "WDD")                  # a shelf under it
    c.rect(2, 16, 6, 19, "MT")                    # the vice
    c.row(2, 6, 16, "MTL")
    c.col(4, 17, 19, "MTD")
    c.rect(11, 11, 13, 15, "WD")                  # a mallet standing on end
    c.rect(10, 9, 14, 12, "WDL")
    c.row(10, 14, 9, "WDD")
    for x in (18, 20, 22):                        # chisels in a row
        c.col(x, 11, 15, "MT")
        c.set(x, 11, "MTL")
        c.set(x, 14, "WD")
    return c.outline()


def shelf():
    """Shelving against a wall, with what a shed keeps on it: jars, a bowl,
    a folded sack. Two boards, because one reads as another table."""
    c = Canvas(FRAME, FRAME)
    for y in (14, 24):
        _plank(c, 3, y, 28, y + 2)
        c.row(3, 28, y + 3, "WDD")
    for x in (4, 27):                             # the uprights
        c.col(x, 11, BASE_Y, "WD")
        c.col(x + 1, 11, BASE_Y, "WDD")
    for x, key in ((8, "CL"), (12, "CLD"), (16, "CL")):
        c.rect(x, 10, x + 2, 13, key)             # jars on the top board
        c.row(x, x + 2, 10, "CL")
        c.set(x + 1, 9, "WDD")                    # and their stoppers
    _lobe(c, 23, 12, 3, "MT")                     # a bowl, upturned
    _lobe(c, 22, 11, 2, "MTL")
    c.rect(8, 20, 15, 23, "CLD")                  # a folded sack below
    c.row(8, 15, 20, "CL")
    c.rect(19, 19, 25, 23, "WD")                  # and a crate of something
    c.row(19, 25, 19, "WDL")
    c.col(22, 20, 23, "WDD")
    return c.outline()


HEARTH_EMBERS = [
    ((13, 16, 18), ((15, 23),)),
    ((12, 15, 19), ((16, 22), (14, 23))),
    ((14, 17), ((15, 22),)),
    ((13, 17, 19), ((16, 23),)),
]


def hearth(phase=0):
    """A stone hearth with the fire banked down in it. The only light source
    in the room, so the embers are the brightest thing on the sprite."""
    c = Canvas(FRAME, FRAME)
    c.rect(3, 8, 28, BASE_Y, "ST")                # the stack
    _shade(c, "ST", "STL", "STD")
    for i, y in enumerate(range(11, BASE_Y, 4)):  # courses
        c.row(4, 27, y, "STD")
        for x in range(6 + (i % 2) * 5, 27, 10):
            c.col(x, y - 3, y - 1, "STD")
    c.rect(9, 17, 22, BASE_Y, "OL")               # the opening, black inside
    c.row(9, 22, 16, "STL")                       # a lintel over it
    c.rect(11, 25, 20, 27, "FID")                 # embers on the hearthstone
    c.rect(12, 26, 19, 27, "FI")
    # Which embers are bright, and how far the flame licks up. Banked down, so
    # it glows and shifts rather than burning like the campfire outside.
    bright, lick = HEARTH_EMBERS[phase % len(HEARTH_EMBERS)]
    for x in bright:
        c.set(x, 25, "FIL")
        c.set(x, 24, "FID")
    for x, y in lick:
        c.set(x, y, "FI")
        c.set(x, y - 1, "FID")
    c.rect(10, 22, 12, 24, "WDD")                 # a log not yet burnt
    c.rect(19, 23, 21, 24, "WDD")
    return c.outline()


def weapon_rack():
    """A rack of hafts against the wall - the reason a shed near a road is
    worth going into."""
    c = Canvas(FRAME, FRAME)
    c.rect(2, 22, 29, 24, "WD")                   # the rail
    c.row(2, 29, 22, "WDL")
    c.row(2, 29, 25, "WDD")
    for x in (4, 27):
        c.col(x, 25, BASE_Y, "WD")
        c.col(x + 1, 25, BASE_Y, "WDD")
    for i, x in enumerate((8, 14, 20, 25)):       # hafts, leaning together
        lean = -1 if i % 2 else 1
        for j in range(16):
            c.set(x + (j * lean) // 6, 8 + j, "WD")
            c.set(x + (j * lean) // 6 + 1, 8 + j, "WDD")
    for x, lean in ((8, 1), (20, 1)):             # two of them shod in iron
        c.rect(x - 1, 6, x + 2, 9, "MT")
        c.row(x - 1, x + 2, 6, "MTL")
    return c.outline()


def bed_straw():
    """A pallet of straw under a blanket: where whoever works the shed sleeps
    when the weather shuts them in."""
    c = Canvas(FRAME, FRAME)
    c.rect(3, 16, 28, BASE_Y, "TH")               # the straw
    for x in range(4, 28, 3):
        c.col(x, 17, BASE_Y - 1, "THD")
    c.row(3, 28, 16, "THL")
    c.rect(3, 21, 28, 27, "TU")                   # a blanket thrown over it
    c.row(3, 28, 21, "TUL")
    c.row(3, 28, 27, "TUS")
    for x in range(5, 28, 6):                     # its folds
        c.col(x, 22, 26, "TUS")
    _lobe(c, 8, 18, 4, "CL")                      # a bolster at the head
    _lobe(c, 7, 17, 3, "CLD")
    return c.outline()


PROPS = {
    "prop.bush": bush,
    "prop.rock": rock,
    "prop.sign": sign,
    "prop.tree_pine": tree_pine,
    "prop.tree_oak": tree_oak,
    "prop.tree_dead": tree_dead,
    "prop.stump": stump,
    "prop.log": log,
    "prop.boulder": boulder,
    "prop.cairn": cairn,
    "prop.mushroom": mushroom,
    "prop.well": well,
    "prop.crate": crate,
    "prop.barrel": barrel,
    "prop.sack": sack,
    "prop.woodpile": woodpile,
    "prop.anvil": anvil,
    "prop.lamp_post": lamp_post,
    "prop.signpost": signpost,
    "prop.statue": statue,
    "prop.tombstone": tombstone,
    "prop.bench": bench,
    "prop.table": table,
    "prop.chest": chest,
    "prop.beehive": beehive,
    "prop.scarecrow": scarecrow,
    "prop.campfire": campfire,
    "prop.trough": trough,
    "prop.flower_pot": flower_pot,
    "prop.flowers": flowers,
    "prop.workbench": workbench,
    "prop.shelf": shelf,
    "prop.hearth": hearth,
    "prop.weapon_rack": weapon_rack,
    "prop.bed_straw": bed_straw,
}
PROP_ORDER = list(PROPS)

# Which props move, and how long a frame lasts. Everything else is still on
# purpose: the trees, bushes and flowers are the most numerous things in the
# game, so animating them multiplies the sheet and draws the eye to the
# background, and a table has no reason to move by itself.
ANIMATED = {
    "prop.campfire": (4, 130),      # flames, quick
    "prop.hearth": (4, 260),        # banked down, so slower
    "prop.lamp_post": (4, 210),
    "prop.beehive": (4, 170),
    "prop.trough": (3, 430),        # standing water barely moves
}
ANIMATED_BIG = {
    "prop.windmill": (4, 150),
}


def prop_frames(pid, table=None):
    """Every frame of a prop, first frame first. One frame for most of them."""
    fns = table if table is not None else PROPS
    n = (ANIMATED.get(pid) or ANIMATED_BIG.get(pid) or (1, 0))[0]
    return [fns[pid](phase=p) if n > 1 else fns[pid]() for p in range(n)]

BIG_PROPS = {
    "prop.house": house,
    "prop.barn": barn,
    "prop.tower": tower,
    "prop.windmill": windmill,
    "prop.shed": shed,
    "prop.boulder_2": boulder_2,
    "prop.boulder_4": boulder_4,
    "prop.boulder_6": boulder_6,
}
BIG_PROP_ORDER = list(BIG_PROPS)

HUGE_PROPS = {
    "prop.burrow_tree": burrow_tree,
    "prop.boulder_8": boulder_8,
}
HUGE_PROP_ORDER = list(HUGE_PROPS)

VAST_PROPS = {
    "prop.boulder_16": boulder_16,
}
VAST_PROP_ORDER = list(VAST_PROPS)


def build_props():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(pid, PROPS[pid]()) for pid in PROP_ORDER]


def build_big_props():
    """The 48x48 structures, same contract, their own atlas."""
    return [(pid, BIG_PROPS[pid]()) for pid in BIG_PROP_ORDER]


def build_huge_props():
    """The 64x64 giants, same contract again, their own atlas."""
    return [(pid, HUGE_PROPS[pid]()) for pid in HUGE_PROP_ORDER]


def build_vast_props():
    """The 128x128 class: four tiles across and four deep, their own atlas."""
    return [(pid, VAST_PROPS[pid]()) for pid in VAST_PROP_ORDER]

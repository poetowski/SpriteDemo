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


def _twig(c, x0, y0, x1, y1, w=0, key="WDD"):
    """A branch stroke from the trunk outward, thinning to nothing."""
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i // steps
        y = y0 + (y1 - y0) * i // steps
        ww = max(0, w - (w * i) // steps)
        c.rect(x - ww, y - ww, x + ww, y + ww, key)


def _crown(c, lobes, shade, light, holes):
    """A canopy built from overlapping discs, then given its own internal
    light and shade. A mass this size shaded only at its rim reads as one flat
    balloon whatever its outline does, which is what both of these trees were
    before: a single stack of centred rows with four pixels punched out."""
    for cx, cy, r in lobes:
        _lobe(c, cx, cy, r, "BU")
    for cx, cy, r in shade:                       # crescents, not discs - a full
        _lobe(c, cx, cy, r, "BUD")                # disc of the paler green reads
        _lobe(c, cx - 2, cy - 2, r - 1, "BU")     # as a spot stuck on the leaves
    for cx, cy, r in light:
        _lobe(c, cx, cy, r, "BUL")
        _lobe(c, cx + 1, cy + 2, r - 1, "BU")
    for x, y in holes:
        c.set(x, y, None)                         # sky through it


def tree_oak():
    """A broad oak: a short trunk that flares straight into the crown, which is
    what an oak grown in the open does.

    The trunk tapers rather than standing as a rectangle, and the roots are
    three humps rather than two rows - the old one read as a post driven into
    the grass because nothing about its base said it had grown there."""
    c = Canvas(FRAME, FRAME)
    _taper(c, 13, BASE_Y, 1, 3, "WD")
    for cx, cy, r in ((15, 27, 4), (10, 28, 3), (21, 28, 3)):
        _lobe(c, cx, cy, r, "WD")
    for x0, y0, x1, y1 in ((14, 15, 9, 10), (17, 14, 22, 10), (15, 13, 15, 8)):
        _twig(c, x0, y0, x1, y1, 1, "WD")
    _crown(c,
           [(15, 9, 8), (7, 12, 5), (24, 12, 5), (15, 4, 6),
            (9, 6, 4), (22, 6, 4), (15, 15, 6)],
           [(11, 14, 4), (20, 13, 4), (15, 17, 3)],
           [(12, 5, 3), (20, 8, 3)],
           [(10, 9), (21, 11), (15, 2), (17, 16), (6, 12), (25, 13)])
    _twig(c, 13, 16, 10, 13)                      # limb ends, over the leaves
    _twig(c, 18, 15, 21, 12)
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")
    return c.outline()


def tree_oak_forked():
    """The same species grown crowded: the trunk forks low and carries two
    crowns that have merged into one lopsided mass.

    A second oak is only worth having if it is a different silhouette - a
    recoloured or slightly wider copy of the first reads as the first one at a
    glance, which is the whole failure mode of a variant."""
    c = Canvas(FRAME, FRAME)
    _taper(c, 20, BASE_Y, 1, 3, "WD")             # one trunk to the fork
    for cx, cy, r in ((15, 27, 4), (10, 28, 3), (21, 28, 3)):
        _lobe(c, cx, cy, r, "WD")
    _twig(c, 15, 21, 10, 12, 1, "WD")             # then two limbs, not one
    _twig(c, 16, 21, 21, 13, 1, "WD")
    _crown(c,
           [(9, 10, 7), (21, 11, 6), (14, 7, 5), (6, 15, 4),
            (24, 15, 4), (15, 13, 5)],
           [(8, 14, 4), (22, 14, 3), (14, 11, 3)],
           [(8, 6, 3), (19, 8, 3)],
           [(9, 12), (20, 10), (12, 5), (5, 14), (24, 17)])
    _twig(c, 12, 15, 8, 12, 0)
    _twig(c, 18, 15, 22, 13, 0)
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")
    return c.outline()


def _conifer(c, rows, top, seed, trunk_from):
    """A conifer from a per-row pair of half-widths.

    The first cut at these drew each whorl as its own centred trapezoid with a
    black row under it, and what came out was a stack of plates: every bough
    the same shape, every gap the same height, both sides the same width. A
    real one steps - each whorl reaches a little past the one above it and then
    the next starts narrower again - and it is never symmetrical, because half
    of it grew towards the light and half did not.

    So the silhouette is authored as two lists, left and right, that step
    independently. _shade then lights the steps for free: a stepped edge gives
    it something to catch, where a smooth trapezoid gives it nothing."""
    rnd = scatter(seed)
    # The trunk first, so the boughs close over it and only the foot shows.
    c.rect(14, trunk_from, 17, BASE_Y, "WD")
    c.col(14, trunk_from, BASE_Y, "WDL")
    c.col(17, trunk_from, BASE_Y, "WDD")
    c.row(13, 18, BASE_Y, "WDD")

    prev_l = prev_r = 0
    for i, (l, r) in enumerate(rows):
        y = top + i
        c.row(15 - l, 16 + r, y, "BU")
        # Where a whorl reaches past the row above it, that overhang is the
        # underside of a bough and is in shadow. The shadow runs a few pixels
        # further in than the overhang itself: stopped at the step, all the
        # depth sat on the outline and the middle of the tree stayed flat.
        if l > prev_l:
            c.row(15 - l, 15 - prev_l + 3, y, "BUD")
        if r > prev_r:
            c.row(16 + prev_r - 3, 16 + r, y, "BUD")
        # and a drooping tip on the wider side, every few rows
        if i and i % 4 == 3:
            if l >= r:
                c.set(15 - l - 1, y, "BUD")
                c.set(15 - l, y + 1, "BUD")
            else:
                c.set(16 + r + 1, y, "BUD")
                c.set(16 + r, y + 1, "BUD")
        prev_l, prev_r = l, r

    # Needle texture through the body, or the inside of it is one flat green
    # however ragged the outline is.
    for _ in range(26):
        i = rnd(len(rows))
        l, r = rows[i]
        span = l + r + 2
        x = 15 - l + rnd(max(1, span))
        y = top + i
        if c.get(x, y) == "BU":
            c.set(x, y, "BUD" if rnd(3) else "BUL")
    # Needles: single pixels bitten out of the edge, so the outline is not a
    # clean staircase. Four or five is enough - more and it reads as damage.
    for _ in range(5):
        i = 4 + rnd(len(rows) - 5)
        l, r = rows[i]
        c.set(15 - l if rnd(2) else 16 + r, top + i, None)
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")
    return c


def tree_pine():
    """A mature pine: six whorls, none of them the same width as its
    neighbours and none of them symmetrical."""
    c = Canvas(FRAME, FRAME)
    rows = [(0, 1), (1, 1), (2, 2), (3, 3),
            (1, 2), (2, 3), (3, 4), (4, 4),
            (2, 3), (3, 4), (4, 5), (5, 6),
            (4, 4), (5, 6), (6, 7), (7, 7),
            (5, 6), (6, 7), (7, 8), (8, 9),
            (7, 8), (8, 9), (9, 10), (10, 10),
            (9, 9)]
    _conifer(c, rows, 2, 0x2B71, 22)
    return c.outline()


def tree_pine_slim():
    """A pine grown in company: bare for half its height, then four narrow
    whorls where it finally reached the light.

    The bare trunk is the point of it - placed beside the broad one it reads as
    the same species at a different age, which is what a second version is for.
    Two trees that differ only in width read as one tree drawn twice."""
    c = Canvas(FRAME, FRAME)
    rows = [(0, 1), (1, 1), (2, 2),
            (1, 2), (2, 2), (3, 3),
            (2, 3), (3, 3), (4, 4),
            (3, 4), (4, 5), (5, 5),
            (4, 5), (5, 6), (6, 6)]
    _conifer(c, rows, 2, 0x6D34, 14)
    for y in range(20, BASE_Y, 4):               # branch scars down the bare
        c.set(13, y, "WDD")                      # half of it
        c.set(18, y + 1, "WDD")
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


def _eave(c, x, y, step, key, dark, n=7):
    """The upturned tip of an Asian eave. It lifts faster the further out it
    goes - a tip that rises in a straight line is a ramp, and the whole look of
    the roof is in that curve."""
    for i in range(n):
        lift = (i * i) // 5
        c.col(x + step * i, y - lift, y + 2 - lift // 2, key)
        c.set(x + step * i, y - lift, dark)


TEMPLE_DUST = ((46, 96), (58, 90), (68, 94), (80, 88), (52, 102),
               (74, 104), (44, 86), (84, 98), (63, 82), (88, 92))

# ------------------------------------------------------------- the desert --
# A second biome needs its own scenery or it is the same country recoloured.
# These all lean on the same two ideas as the rest: the shape carries it, and
# the palette says which world it belongs to.
def _frond(c, x, y, dx, dy, n, key, dark):
    """A palm leaf: a rib out from the crown that droops further the further
    it goes, with leaflets hung off both sides of it. Drawn as a walk rather
    than a line, because a straight frond reads as a feather duster."""
    fx, fy = float(x), float(y)
    for i in range(n):
        fx += dx
        fy += dy + i * 0.18                       # the droop, gathering
        px, py = round(fx), round(fy)
        c.set(px, py, key)
        if i:
            c.set(px, py - 1, key if i % 2 else dark)
            c.set(px, py + 1, dark)


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


def table():
    c = Canvas(FRAME, FRAME)
    _plank(c, 4, 17, 27, 20)
    c.row(4, 27, 21, "WDD")              # the edge of the top, in shadow
    for x in (7, 22):
        _post(c, x, 22, BASE_Y)
    c.rect(9, 25, 22, 25, "WDD")         # a stretcher between the legs
    return c.outline()


def _chest_body(c, wood, light, dark, lid=True):
    """The shared carcass: a box on the ground line and a lid over it."""
    c.rect(8, 19, 23, BASE_Y, wood)      # body
    c.col(23, 19, BASE_Y, dark)
    c.row(8, 23, BASE_Y, dark)
    if lid:
        _blob(c, 13, (7, 7, 8, 8, 8, 8), wood, cx=15)   # the domed lid
        c.row(8, 23, 13, light)
    c.row(8, 23, 18, dark)


def _lock(c, plate="MTL"):
    c.rect(14, 18, 17, 21, plate)        # the lock plate
    c.set(15, 20, "OL")
    c.set(16, 20, "OL")


def chest():
    c = Canvas(FRAME, FRAME)
    _chest_body(c, "WD", "WDL", "WDD")
    for x in (11, 20):                   # iron bands over the lid and body
        c.col(x, 13, BASE_Y, "MT")
        c.col(x + 1, 13, BASE_Y, "MTD")
    _lock(c)
    return c.outline()


# Four more chests on the same carcass. They differ in what they are made of
# first and in one small thing second, because a chest is read by its colour
# from across a room and by its detail only once you are standing at it.

def chest_gilded():
    """Red lacquer and gold: the one worth robbing, and it says so."""
    c = Canvas(FRAME, FRAME)
    _chest_body(c, "RF", "RFL", "RFD")
    for x in (11, 20):
        c.col(x, 13, BASE_Y, "TH")
        c.col(x + 1, 13, BASE_Y, "THD")
    c.row(8, 23, 19, "TH")               # a gold rim where the lid shuts
    _lock(c, "THL")
    return c.outline()


def chest_iron():
    """A strongbox: flat lid, riveted plate, and no wood anywhere."""
    c = Canvas(FRAME, FRAME)
    _chest_body(c, "MT", "MTL", "MTD", lid=False)
    c.rect(8, 15, 23, 17, "MT")          # a flat lid, not a dome
    c.row(8, 23, 15, "MTL")
    c.col(23, 15, 17, "MTD")
    for x in (9, 22):                    # rivets down each corner
        for y in (20, 23, 26):
            c.set(x, y, "MTL")
    c.rect(14, 18, 17, 21, "MTD")        # the lock is a dark hasp on steel
    c.set(15, 20, "OL")
    c.set(16, 20, "OL")
    c.row(14, 17, 18, "TH")              # one brass edge to find it by
    return c.outline()


def chest_stone():
    """A coffer cut from one block, lichen on the lid where the rain sits."""
    c = Canvas(FRAME, FRAME)
    _chest_body(c, "ST", "STL", "STD", lid=False)
    c.rect(7, 15, 24, 18, "ST")          # a slab lid, proud of the body
    c.row(7, 24, 15, "STL")
    c.row(7, 24, 18, "STX")
    c.col(24, 15, 18, "STD")
    c.rect(11, 21, 20, 25, "STD")        # a sunk panel on the face
    c.rect(12, 22, 19, 24, "ST")
    c.rect(9, 15, 12, 16, "MS")          # lichen
    c.set(20, 15, "MS")
    c.set(10, 17, "MS")
    return c.outline()


def chest_old():
    """The first chest left out for years: bleached, rusted, a band gone."""
    c = Canvas(FRAME, FRAME)
    _chest_body(c, "PTD", "PT", "DRD")
    c.col(11, 13, BASE_Y, "MTD")         # one band left, rusted through
    c.col(12, 13, BASE_Y, "DRD")
    for y in (16, 23):
        c.set(11, y, "FID")
    for y in (14, 21, 25):               # where the other one was nailed
        c.set(20, y, "DRD")
    c.col(18, 22, BASE_Y - 1, "DRD")     # a split plank
    c.rect(14, 18, 17, 21, "MTD")
    c.set(17, 21, "FID")
    c.set(15, 20, "OL")
    c.set(16, 20, "OL")
    c.rect(18, 13, 21, 14, "MS")         # moss on the lid
    c.set(22, 15, "MS")
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


# ----------------------------------------------------------- the burrow ---
# Four props that only make sense underground. They share a constraint the
# outdoor set does not have: the floor they stand on is dark, so anything drawn
# in a mid tone sinks into it. Each of these is either paler than the floor or
# outlined hard against it.
def roots():
    """Tree roots broken through the roof of the burrow and left hanging.

    The one prop here drawn from the top of the frame downward instead of up
    from the base line: a hanging thing is placed by where it is fixed, not by
    where it ends. The gauges and lengths all differ on purpose - four strands
    of one width read as rope, which is the failure this shape falls into most
    easily."""
    c = Canvas(FRAME, FRAME)
    # Three pixels across, not one. A single-pixel strand plus the outline
    # this returns is two parts dark to one part wood, and what comes out is
    # a crack in the wall rather than a root hanging in front of it.
    for x0, length, lean in ((6, 20, 1), (12, 14, 0), (18, 24, -1), (25, 11, 1)):
        x = x0
        for y in range(length):
            c.set(x, y, "WD")
            c.set(x + 1, y, "WD")
            if y < length - 4:
                c.set(x + 2, y, "WDD")       # the shaded side of the strand
            if y % 5 == 0:
                c.set(x, y, "WDL")           # and a lit one, in patches
            if y and y % 7 == 0:
                x += lean                    # a kink, not a curve
        c.set(x, min(length, FRAME - 1), "WDD")      # a blunt tip, not a point
    return c.outline()


# ---------------------------------------------------------------- wetland ---

def fence(mask=0):
    """One piece of a split-rail run, drawn for the neighbours it has.

    A fence is a *line*, and a line has to know which way it goes. Drawn as a
    single east-west piece it was fine along the top of a paddock and absurd
    down the side: sixteen pixels apart, each tile repeated the same run of
    horizontal rail, so a north-south fence came out as a stack of little
    ladders lying on the grass with nothing joining them.

    `mask` is which cardinal neighbours are fence too - N=1, E=2, W=4. South is
    deliberately not in it: the piece *below* draws its own north connector
    upwards into this one's foot, so a southward join needs nothing drawn here
    and the family is eight pieces rather than sixteen.

    The geometry is all arithmetic about the 16px grid:

    - Rails run to the frame edge on a connected side. outline() borders a
      pixel only where there is transparency beside it, so a rail that touches
      the edge grows no end cap and butts onto its neighbour; stopping short
      put a black bar between every pair of tiles.
    - Three pixels thick, six apart. Thinner and the border eats the rail;
      closer and it eats the daylight between the two.
    - The post is seven wide and stops at y16, and the north connector is four
      wide. A post tall enough to meet its neighbour's would make a vertical
      run one unbroken bar - a pole, not a fence. The narrow waist between two
      wide posts is the whole of what says "these are separate posts in a row"
      when the run is coming towards you."""
    N, E, W = mask & 1, mask & 2, mask & 4
    c = Canvas(FRAME, FRAME)

    # --- the rails, laid first so the post stands in front of them ----------
    for y0 in (15, 24):
        if W:
            c.rect(0, y0, 16, y0 + 2, "WD")
            c.row(0, 16, y0, "WDL")
            c.row(0, 16, y0 + 2, "WDD")
        if E:
            c.rect(15, y0, FRAME - 1, y0 + 2, "WD")
            c.row(15, FRAME - 1, y0, "WDL")
            c.row(15, FRAME - 1, y0 + 2, "WDD")

    # --- the run coming towards you -----------------------------------------
    if N:
        # Two rails going away from you, up to the foot of the post in the tile
        # above - the same pair as the east-west piece, turned. A single
        # connector down the middle was tried first and a run of it read as a
        # chain: one bar between two posts says "joint", and what has to be
        # said is "rail". They sit a pixel proud of the post on each side,
        # which is where a split rail actually runs - past the post, not
        # flush into it.
        for x0 in (10, 18):          # symmetric about the post centre, x15
            c.rect(x0, 11, x0 + 2, 18, "WD")
            c.col(x0, 11, 18, "WDL")
            c.col(x0 + 2, 11, 18, "WDD")

    # --- the post ------------------------------------------------------------
    c.rect(12, 16, 18, BASE_Y, "WD")
    c.col(12, 16, BASE_Y, "WDL")
    c.col(18, 16, BASE_Y, "WDD")
    c.row(12, 18, 16, "WDL")                     # a weathered top
    c.set(15, 19, "WDD")
    return c.outline()



# Hedge and wall are the fence's idea carried over to things that are solid
# rather than open: a run is one continuous mass, so where the fence's rails
# butt together these have to *be* one body across the join. Two rules make
# that work, and both come from the frame being 32 wide on a 16px grid:
#
# - Neighbouring pieces overlap by half a frame, so every texture here is a
#   function of x % 16 (and y % 16 down a run). Anything else puts a seam
#   every tile where the next piece's pattern lands over this one's.
# - Light is worked out with the frame edge counted as *more of the same*,
#   not as air. _shade treats the edge as open and lights it, which drew a
#   pale stripe down every join; a run is only lit where it really ends.
def _run(mask, top, body, arm, fill):
    """The mass of one linked piece: the tile's own body, arms out east and
    west to the frame edge, and a spine north to meet the piece above. Returns
    the canvas filled with whatever `fill(x, y, edge)` says, where edge is
    "top", "left", "right", "foot" or None for the inside."""
    N, E, W = mask & 1, mask & 2, mask & 4
    c = Canvas(FRAME, FRAME)
    if N and not (E or W) and not callable(arm):
        # The foot of a north-south run is the end of it seen head on, so it
        # is only as wide as the spine. Drawn at full width, every piece down
        # the run stuck its front face out either side and a straight wall
        # came out notched like a caterpillar.
        body = arm
    x0 = 0 if W else body[0]
    x1 = FRAME - 1 if E else body[1]
    solid = set()
    for x in range(x0, x1 + 1):
        t = top(x)
        # a free end is rounded off rather than cut square
        if not W and x < body[0] + 3:
            t += body[0] + 3 - x
        if not E and x > body[1] - 3:
            t += x - (body[1] - 3)
        for y in range(t, BASE_Y + 1):
            solid.add((x, y))
    if N:
        for y in range(0, BASE_Y + 1):
            lo, hi = arm(y) if callable(arm) else arm
            for x in range(lo, hi + 1):
                solid.add((x, y))

    def filled(x, y):
        if not (0 <= x < FRAME) or y < 0:
            return True                           # the next piece carries on
        return (x, y) in solid
    for x, y in solid:
        if not filled(x, y - 1):
            edge = "top"
        elif not filled(x - 1, y):
            edge = "left"
        elif not filled(x + 1, y) or y == BASE_Y:
            edge = "right" if not filled(x + 1, y) else "foot"
        else:
            edge = None
        c.set(x, y, fill(x, y, edge))
    return c


def hedge(mask=0):
    """A hawthorn hedgerow, one piece of a run, drawn for its neighbours.

    The thing a fence cannot do: say that a field boundary is old. A hedge is
    a green wall with a ragged top, so the top is a sum of two ripples at the
    16px period and every tile of a run lifts and dips in the same place -
    which, repeated, reads as growth rather than as a stamp only because it
    is broken up by the texture inside it. A few sprays of blossom say
    hawthorn, and they are the cloth white, which is the only white thing in
    the meadow and so reads from across a field."""
    def top(x):
        u = x % 16
        return 12 + round(1.4 * math.sin(u / 16 * 2 * math.pi)
                          + 0.8 * math.sin(u / 16 * 6 * math.pi + 1.0))

    def leafy(x, y):
        """Leaf clumps on a 4px lattice, staggered each band: a lit pixel with
        a crescent of shade under it, which is the bush's own trick at a
        smaller scale. One-pixel speckle was tried first and a run of it read
        as carpet."""
        u, v = x % 16, y % 16
        band = v // 4
        a, b = (u + (2 if band % 2 else 0)) % 4, v % 4
        if (a, b) == (1, 0):
            return "light"
        if (a, b) in ((2, 1), (1, 2), (2, 2)):
            return "shade"
        return None

    def fill(x, y, edge):
        leaf = leafy(x, y)
        if edge == "top":
            return "BUL"
        if edge == "right" or y >= BASE_Y - 1:
            return "BUD"
        if edge == "left":
            return "BUL" if leaf != "shade" else "BU"
        if leaf == "light":
            return "BUL" if y < 24 else "BU"
        if leaf == "shade":
            return "BUD"
        return "BU" if y < 25 else ("BUD" if (x + y) % 3 == 0 else "BU")

    def spine(y):
        v = y % 16                                # a hedge's sides are not ruled
        wob = (0, 1, 1, 0, -1, 0, 1, 0, 0, -1, -1, 0, 1, 1, 0, 0)
        return 8 + wob[v], 23 + wob[(v + 5) % 16]
    c = _run(mask, top, (8, 23), spine, fill)
    # Blossom, and only a little of it. Every piece repeats on a 16px period,
    # so whatever is drawn here comes back every tile; in the bright white it
    # was a string of lights along the top. In the cloth's shade it is a
    # sprinkle that says hawthorn only once you look.
    for x, y in ((12, 16), (5, 22)):
        for bx in (x, x + 16):
            for dx, dy, k in ((0, 0, "CL"), (1, 1, "CLD")):
                if c.get(bx + dx, y + dy) in ("BU", "BUL", "BUD"):
                    c.set(bx + dx, y + dy, k)
    return c.outline()


def wall(mask=0):
    """A dry-stone field wall, one piece of a run, drawn for its neighbours.

    Uncoursed stone read at 16px is a grey band with a crack in it, so the
    two things that say "dry-stone" are exaggerated: the joints are deep and
    dark, because nothing fills them, and the top is a row of stones set on
    edge, because that coping is the one part of the wall with a silhouette.
    Knee high - lower than the hedge, so the two read as different things
    when a field has one on each side."""
    def top(x):
        u = x % 16
        return 16 + (0, 1, 0, 0, 1, 2, 1, 0, 0, 1, 0, 1, 2, 1, 0, 0)[u]

    # Courses of stones as (row start, height, joint offsets); a joint is a
    # dark column, and staggering them course to course is what makes stone.
    courses = ((19, 3, (0, 7, 12)), (22, 3, (3, 10)), (25, 4, (1, 6, 13)))

    def fill(x, y, edge):
        u, v = x % 16, y % 16
        if y < 19:                                # the coping, stones on edge
            if u % 3 == 0:
                return "STX"
            return "STL" if edge == "top" or y == top(x) else "ST"
        for y0, h, joints in courses:
            if y0 <= y < y0 + h:
                if y == y0:
                    return "STX"                  # the bed joint
                if u in joints:
                    return "STX"
                if y == y0 + 1:
                    return "STL" if edge != "right" else "ST"
                return "STD" if edge == "right" or y == y0 + h - 1 else "ST"
        return "STD"

    def fill_run(x, y, edge):
        # Down the northward spine the wall is seen from above: coping along
        # its length, one stone every four rows, lit on the west side.
        if (mask & 1) and 11 <= x <= 20 and y < 19:
            if y % 4 == 0:
                return "STX"
            if x == 11:
                return "STL"
            if x == 20:
                return "STD"
            return "ST" if (x + y // 4) % 3 else "STL"
        return fill(x, y, edge)
    c = _run(mask, top, (8, 23), (11, 20), fill_run)
    for x, y in ((4, 27), (5, 27), (19, 26)):     # lichen low on the stones
        if c.get(x, y) in ("ST", "STD"):
            c.set(x, y, "MS")
    return c.outline()



def haystack():
    """Cut grass built round a pole and left to dry.

    Drawn with straight sides off _taper it came out a perfect triangle, which
    is a tent, not a rick - the silhouette of a heap is convex and it sags.
    So the sides are built from lobes that bulge past the cone and the top is
    rounded off, and the thatch keys carry it because what this has to do is
    read as gold against green from across a field."""
    c = Canvas(FRAME, FRAME)
    _taper(c, 10, BASE_Y, 2, 10, "TH")
    for cx, cy, r in ((15, 14, 5), (10, 20, 6), (21, 20, 6),
                      (15, 24, 8), (7, 26, 4), (24, 26, 4)):
        _lobe(c, cx, cy, r, "TH")                # the heap bulging past the cone
    rnd = scatter(0x8A17)
    for _ in range(34):                          # loose ends all over it
        x, y = 4 + rnd(24), 11 + rnd(17)
        if c.get(x, y) == "TH":
            c.set(x, y, "THD" if rnd(2) else "THL")
    for y in range(15, BASE_Y, 6):               # and the courses it was built in
        for x in range(FRAME):
            if c.get(x, y) == "TH" and c.get(x, y + 1) == "TH":
                c.set(x, y, "THD")
    c.rect(14, 5, 16, 11, "WD")                  # the pole out of the top
    c.col(14, 5, 11, "WDL")
    _shade(c, "TH", "THL", "THD")
    return c.outline()

def cart():
    """A two-wheeled farm cart, tipped forward on its shafts.

    The wheel is the whole object at this size and it has to break the body's
    silhouette to be seen at all: drawn tucked under the bed it was a dark
    smudge and the cart read as a crate somebody had left out. It stands
    proud of the boards now, and it is drawn as a lit rim with spokes across
    a gap rather than as a disc - a disc is a barrel lying down."""
    c = Canvas(FRAME, FRAME)
    c.rect(7, 10, 27, 12, "WD")                  # the top rail of the body
    c.rect(7, 12, 27, 20, "WD")                  # and its boards
    for x in range(9, 27, 4):
        c.col(x, 13, 19, "WDD")
    c.row(7, 27, 10, "WDL")
    c.row(7, 27, 20, "WDD")
    c.rect(5, 9, 8, 21, "WD")                    # the end boards, standing proud
    c.rect(26, 9, 29, 21, "WD")
    c.col(5, 9, 21, "WDL")
    for i in range(7):                           # a shaft down to the ground
        c.set(4 - i // 2, 21 + i, "WDD")
        c.set(5 - i // 2, 21 + i, "WD")

    # The wheel, hanging below the bed where it can be seen.
    cx, cy, r = 19, 22, 6
    for a in range(0, 360, 7):
        x = round(cx + math.cos(math.radians(a)) * r)
        y = round(cy + math.sin(math.radians(a)) * r * 0.85)
        c.set(x, y, "WDL")
        c.set(x, y + 1, "WDD")
    for a in (20, 80, 140):                      # three spokes is enough to say
        dx = math.cos(math.radians(a)) * (r - 1)
        dy = math.sin(math.radians(a)) * (r - 1) * 0.85
        _twig(c, round(cx - dx), round(cy - dy),
              round(cx + dx), round(cy + dy), 0, "WDD")
    _lobe(c, cx, cy, 2, "MTD")
    c.set(cx - 1, cy - 1, "MTL")                 # the hub, catching the light
    _shade(c, "WD", "WDL", "WDD")
    return c.outline()

def tree_birch():
    """A third deciduous tree, so a wood can be one species with others through
    it rather than one of each standing in a row.

    A birch is its bark, and the whole difficulty is that saying so at 32px
    nearly costs you the tree. The first one used the cloth key straight, with
    the oak's flared root base under it, and came back a white column with a
    bush balanced on top - a pillar, not a trunk. It is the *shade* of the
    cloth that carries the bark, with the light only down the lit side, and
    the base barely flares at all: a birch does not buttress. The crown stays
    small and high to keep out of the trunk's way."""
    c = Canvas(FRAME, FRAME)
    _taper(c, 7, BASE_Y, 1, 2, "CLD")
    _lobe(c, 15, 27, 2, "CLD")                   # barely a flare - not an oak
    for y in range(8, BASE_Y):                   # the lit side of the bole
        for x in range(FRAME):
            if c.get(x, y) == "CLD" and c.get(x - 1, y) is None:
                c.set(x + 1, y, "CL")
                c.set(x + 2, y, "CL")
    for y in (10, 13, 17, 20, 24, 27):           # the bars, which are the tree
        c.row(13, 16, y, "OL")
        c.set(12 if y % 2 else 17, y, "OL")      # each one running off one side
    for x0, y0, x1, y1 in ((15, 13, 10, 8), (15, 11, 21, 7)):
        _twig(c, x0, y0, x1, y1, 0, "CLD")
    _crown(c,
           [(15, 6, 6), (9, 8, 4), (22, 8, 4), (15, 11, 4)],
           [(11, 10, 3), (20, 10, 3)],
           [(13, 3, 3), (19, 5, 2)],
           [(9, 5), (21, 4), (15, 1), (7, 9), (24, 9), (12, 12), (19, 12)])
    _shade(c, "BU", "BUL", "BUD")
    return c.outline()

def _deck(c):
    """The boards of a bridge, edge to edge so a span joins into one crossing.

    outline() borders a pixel only where there is transparency beside it, so a
    deck that reaches the frame edge grows no end cap and butts straight onto
    its neighbour. Drawn a little short instead, every tile of the span came
    back ringed in black and the bridge read as a row of crates."""
    c.rect(0, 14, FRAME - 1, 27, "WDL")          # pale, to carry against water
    for x in range(1, FRAME, 3):                 # planks, across the crossing
        c.col(x, 14, 27, "WD")
    c.row(0, FRAME - 1, 14, "WD")                # a kerb along each long edge
    c.row(0, FRAME - 1, 15, "WDD")
    c.row(0, FRAME - 1, 27, "WDD")


def bridge():
    """Planks over water, with a rail along the far side.

    A bridge is seen from much the same angle as everything else here - a
    little above - so what you mostly see is the deck, and the first version
    forgot that and drew a side elevation: a solid slab with a rail on it,
    which read as a fence lying down. The deck is the object. It is pale,
    because it has to separate from the water under it, and its planks run
    *across* the way you walk so the eye is carried over rather than along.

    It is laid on tile.shallow, not on deep water: a bridge does not make the
    ground under it walkable - the tile decides that, and a walkable shoal is
    what this is drawn to sit on."""
    c = Canvas(FRAME, FRAME)
    _deck(c)
    for x in (3, 15, 27):                        # handrail posts, on the far side
        c.rect(x, 7, x + 2, 14, "WD")
        c.col(x, 7, 14, "WDL")
        c.col(x + 2, 7, 14, "WDD")
    c.rect(0, 8, FRAME - 1, 10, "WD")            # the rail: three rows, or the
    c.row(0, FRAME - 1, 8, "WDL")                # outline hands it back as a hair
    c.row(0, FRAME - 1, 10, "WDD")
    return c.outline()


def bridge_deck():
    """The same boards with no rail, for the rows of a crossing in front of the
    railed one.

    A road here is two tiles wide, so a bridge over it is two rows of prop -
    and giving both a rail put a fence down the middle of the crossing, which
    read as a pen rather than a bridge. A rail belongs on the far side only,
    which is the one side you can see from this angle."""
    c = Canvas(FRAME, FRAME)
    _deck(c)
    return c.outline()



# ------------------------------------------------------------ the country ---
# What a farmed valley grows and builds that the first set did not: the plants
# the items come from, and the few fixtures a village hangs its life on. Every
# one is in the palette the meadow already uses, because the point of them is
# to make one country denser rather than to start a second.

def _leaf(c, base, ctrl, tip, width, key, light, dark, serrate=True):
    """A leaf or frond on a curve: from `base` through `ctrl` to `tip`, as wide
    as `width` at the foot and tapering to a point, with leaflets across it.

    It is swept rather than walked: at each step along the curve a short
    line is laid *across* the direction of growth, sampled finely enough that
    a diagonal leaf comes out solid rather than as a chequerboard. The palm's
    _frond was tried first and set its leaflets above and below a rib that
    was meant to lie flat; stood upright, those leaflets ran along the rib and
    outline() handed every fern back as a tuft of black hairs.

    The side facing up-left is lit and the rib is dark, which is all the
    modelling a thing three to five pixels wide can carry."""
    (ax, ay), (bx, by), (ex, ey) = base, ctrl, tip
    steps = 48
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * bx + t * t * ex
        y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * by + t * t * ey
        tx = 2 * (1 - t) * (bx - ax) + 2 * t * (ex - bx)
        ty = 2 * (1 - t) * (by - ay) + 2 * t * (ey - by)
        m = math.hypot(tx, ty) or 1
        nx, ny = -ty / m, tx / m
        w = width * (1 - t) ** 0.7
        if serrate and int(t * 14) % 2:
            w *= 0.55                             # the gaps between leaflets
        k = -w
        while k <= w:
            px, py = round(x + nx * k), round(y + ny * k)
            lit = (nx * k + ny * k) < 0           # the half turned up-left
            c.set(px, py, light if lit else key)
            k += 0.5
        c.set(round(x), round(y), dark)           # the rib


def bramble():
    """A blackberry thicket: low, wider than it is tall, arching canes, and
    fruit on it - because item.berries has to come off something.

    A bush with dots on it is a bush with dots on it. What makes a bramble is
    the canes: they arch *out* of the mound and come back down to root, so the
    silhouette is a heap with loops standing off it. The canes are the roof's
    dark red, the one warm note, which is also the colour a bramble stem is.
    The fruit is the berry item's own blue-black, so what you pick is visibly
    what was growing."""
    c = Canvas(FRAME, FRAME)
    for cx, cy, r in ((15, 22, 7), (8, 24, 5), (23, 24, 5), (12, 18, 4),
                      (20, 19, 4), (4, 26, 3), (27, 26, 3)):
        _lobe(c, cx, cy, r, "BU")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    rnd = scatter(0xB4A3)
    for _ in range(22):                          # leaf texture through the mass
        x, y = 2 + rnd(28), 14 + rnd(14)
        if c.get(x, y) == "BU":
            c.set(x, y, "BUD")
    _shade(c, "BU", "BUL", "BUD")
    # Canes sprayed out of the mound and falling back to root beyond it, two
    # pixels thick: one pixel of cane plus its outline is a hair. Drawn as
    # three matching arches over the top they read as horseshoes - a bramble
    # is untidy, so these leave from different heights and land at different
    # distances, and only on the sides.
    for (ax, ay), (bx, by), (ex, ey) in (((11, 17), (3, 10), (0, BASE_Y - 2)),
                                         ((20, 18), (28, 12), (31, BASE_Y - 4)),
                                         ((17, 16), (22, 9), (26, 15))):
        for i in range(25):
            t = i / 24
            x = round((1 - t) ** 2 * ax + 2 * (1 - t) * t * bx + t * t * ex)
            y = round((1 - t) ** 2 * ay + 2 * (1 - t) * t * by + t * t * ey)
            c.set(x, y, "WDD")
            c.set(x, y + 1, "WDD")
            if c.get(x, y - 1) is None:
                c.set(x, y, "RFD")                # lit along its top
    # Fruit in clusters of three, each with a glint: a single dark pixel on dark
    # leaves is a hole, three with one lit is a berry.
    for x, y in ((9, 21), (18, 17), (22, 23), (13, 25), (5, 25), (26, 20)):
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            c.set(x + dx, y + dy, "WAD")
        c.set(x, y, "WAL")
        c.set(x + 2, y + 1, "WAX")
    for x, y in ((15, 20), (11, 17)):            # a flower or two still out
        c.set(x, y, "CLL")
        c.set(x + 1, y, "CL")
    return c.outline()


def tree_apple():
    """An orchard tree: short, crooked, wider than it is tall, and hung with
    fruit - the other half of item.apple.

    It has to read apart from the oak at a glance, which is the rule for any
    second tree: same palette, different silhouette. An apple is pruned, so
    the crown is low and broad and starts barely a tile off the ground, and
    the trunk leans and kinks where the oak's rises straight and flares. The
    apples are the item's own red with a lit side, and a couple lie in the
    grass under it, because an apple tree in autumn always has windfalls."""
    c = Canvas(FRAME, FRAME)
    for y in range(17, BASE_Y + 1):              # a leaning, kinked bole
        x = 15 + (1 if y < 23 else 0) + (1 if y < 19 else 0)
        c.row(x - 1, x + 1, y, "WD")
    for cx, cy, r in ((15, 28, 3), (11, 29, 2), (19, 29, 2)):
        _lobe(c, cx, cy, r, "WD")                # a root flare, not a stake
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    _twig(c, 16, 18, 9, 12, 1, "WD")
    _twig(c, 17, 17, 23, 13, 1, "WD")
    _crown(c,
           [(15, 11, 7), (7, 13, 5), (24, 13, 5), (11, 7, 4), (20, 7, 4),
            (15, 15, 5), (3, 15, 3), (28, 15, 3)],
           [(10, 15, 4), (21, 15, 4)],
           [(11, 6, 3), (19, 7, 2)],
           [(8, 9), (22, 10), (15, 4), (4, 12), (27, 12), (13, 18)])
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")
    for x, y in ((7, 11), (13, 8), (20, 11), (25, 14), (10, 15), (17, 14),
                 (4, 15), (22, 7)):
        c.rect(x, y, x + 1, y + 1, "RF")         # fruit, two by two
        c.set(x, y, "RFL")
        c.set(x + 1, y + 1, "RFD")
    c.rect(22, BASE_Y - 1, 23, BASE_Y, "RF")     # a windfall
    c.set(22, BASE_Y - 1, "RFL")
    return c.outline()


def bracken():
    """A clump of fern for the wood floor: something green and low between
    the trunks, so a wood can be dense without being more trees.

    Each frond is a _leaf: a rib that climbs and arches over, with leaflets
    set across it so it is several pixels wide the whole way up. The palm's
    _frond was tried first and set its leaflets along an upright rib, which
    outline() handed back as a tuft of black hairs. One of the six has
    turned, because bracken browns from the tips in autumn and a
    clump of one green reads as a bush."""
    c = Canvas(FRAME, FRAME)
    B = (15, BASE_Y - 1)
    for ctrl, tip, w, key, light in (
            ((6, 14), (1, 21), 3.2, "LF", "DRL"),      # turned, lying lowest
            ((25, 15), (30, 22), 3.0, "BU", "BUL"),
            ((8, 7), (4, 13), 3.4, "BU", "BUL"),
            ((22, 6), (27, 12), 3.4, "BU", "BUL"),
            ((12, 3), (10, 9), 3.0, "BUL", "GRL"),
            ((19, 4), (22, 8), 2.8, "BU", "BUL")):
        _leaf(c, B, ctrl, tip, w, key, light, "BUD" if key != "LF" else "LFD")
    _lobe(c, 15, BASE_Y, 2, "BUD")               # the crown they spring from
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def reeds():
    """A clump of bulrush for the edge of the water.

    The last reed bed here was six parallel stalks, and outline() turned it
    into a dark comb. So: three stalks, not six, each two pixels wide, and at
    least six apart where they rise from the clump - the first gap that shows
    daylight between two bordered stalks. What says bulrush is the brown head,
    and it is the one thing drawn fat. Leaf blades arch off the base in the
    light green, standing clear of the stems."""
    c = Canvas(FRAME, FRAME)
    for x, top, lean in ((9, 6, -1), (16, 3, 0), (23, 8, 1)):
        for y in range(top, BASE_Y + 1):
            dx = lean * max(0, (20 - y)) // 8
            c.set(x + dx, y, "THD")
            c.set(x + dx + 1, y, "TH")
        hx = x + lean * max(0, (20 - top - 3)) // 8
        c.rect(hx - 1, top + 2, hx + 2, top + 7, "WD")      # the head
        c.col(hx - 1, top + 2, top + 7, "WDL")
        c.col(hx + 2, top + 3, top + 7, "WDD")
        c.set(hx, top, "THD")                              # the spike above it
        c.set(hx, top + 1, "THD")
    for base, ctrl, tip in (((13, BASE_Y - 2), (8, 12), (3, 16)),
                            ((19, BASE_Y - 2), (26, 13), (30, 18)),
                            ((15, BASE_Y - 2), (12, 10), (12, 5))):
        _leaf(c, base, ctrl, tip, 1.6, "BU", "GRL", "BUD", serrate=False)
    for cx, r in ((11, 3), (16, 3), (21, 3)):    # the clump the stems stand in
        _lobe(c, cx, BASE_Y, r, "BU")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    _shade(c, "BU", "BUL", "BUD")
    return c.outline()


def inn_sign():
    """The sign that says a cottage is an inn: a post, a bracket, and a board
    hung off it on two chains, painted with a tankard.

    Hanging is what says "inn" rather than "notice": a board on a post is the
    signpost. The emblem is drawn big and simple - a mug is a pale box with a
    handle and a head of foam - because it is read from across a green."""
    c = Canvas(FRAME, FRAME)
    _post(c, 6, 4, BASE_Y)
    c.rect(5, 4, 8, BASE_Y, "WD")
    c.col(5, 4, BASE_Y, "WDL")
    c.col(8, 4, BASE_Y, "WDD")
    c.rect(4, BASE_Y - 1, 9, BASE_Y, "WDD")        # its foot
    c.rect(8, 5, 29, 7, "WD")                    # the bracket arm
    c.row(8, 29, 5, "WDL")
    c.row(8, 29, 7, "WDD")
    for i in range(5):                           # a brace under it, three wide
        c.rect(9 + i, 12 - i, 10 + i, 12 - i, "WDD")
    for x in (15, 26):                           # chains
        c.col(x, 8, 11, "MT")
        c.col(x + 1, 8, 11, "MTD")
    X = 2                                        # the board hangs clear of the post
    c.rect(11 + X, 12, 27 + X, 25, "WD")         # the board
    c.row(11 + X, 27 + X, 12, "WDL")
    c.col(27 + X, 12, 25, "WDD")
    c.row(11 + X, 27 + X, 25, "WDD")
    c.rect(12 + X, 13, 26 + X, 24, "RFD")        # painted field
    c.rect(15 + X, 16, 21 + X, 23, "TH")         # the tankard
    c.col(15 + X, 16, 23, "THL")
    c.col(21 + X, 16, 23, "THD")
    c.row(16 + X, 20 + X, 19, "THD")             # a hoop round it
    c.rect(22 + X, 17, 24 + X, 21, "TH")         # the handle
    c.rect(22 + X, 18, 23 + X, 20, "RFD")
    c.rect(14 + X, 14, 22 + X, 15, "CLL")        # the head, spilling over
    c.set(22 + X, 16, "CLL")
    return c.outline()


def notice_board():
    """Two posts and a little roof over a board with notices pinned to it -
    the place a village puts up what it wants done.

    The papers are what make it a notice board and not a sign, so there are
    several, of different sizes, each pinned a little crooked. The roof is
    shingle, not tile: roof red is kept for houses, so that a warm mass on
    the map always means somebody lives there."""
    c = Canvas(FRAME, FRAME)
    for x in (7, 23):
        c.rect(x, 12, x + 2, BASE_Y, "WD")
        c.col(x, 12, BASE_Y, "WDL")
        c.col(x + 2, 12, BASE_Y, "WDD")
    c.rect(9, 13, 23, 25, "WDD")                 # the board, in the shade
    c.row(9, 23, 13, "WD")
    for y0, x0, x1 in ((6, 13, 18), (7, 10, 21), (8, 7, 24), (9, 5, 26), (10, 4, 27)):
        c.row(x0, x1, y0, "WD")                  # a shingle roof
    for x in range(5, 27, 3):
        c.set(x, 10, "WDD")
    c.row(4, 27, 11, "WDD")
    c.row(13, 18, 6, "WDL")
    for x0, y0, x1, y1, key in ((10, 15, 14, 21, "CL"), (16, 14, 21, 18, "CLL"),
                                (16, 20, 22, 24, "CL"), (11, 22, 14, 24, "CLL")):
        c.rect(x0, y0, x1, y1, key)
        c.row(x0, x1, y1, "CLD")
        for y in range(y0 + 2, y1, 2):           # lines of writing, not text
            c.row(x0 + 1, x1 - 1, y, "CLD")
    c.set(10, 15, "CLD")                         # a curled corner
    for x, y in ((12, 15), (18, 14), (19, 20)):
        c.set(x, y, "RF")                        # pins, and a seal
    c.rect(12, 23, 13, 24, "RF")
    return c.outline()


PROPS = {
    "prop.bush": bush,
    "prop.bridge": bridge,
    "prop.bridge_deck": bridge_deck,
    "prop.tree_birch": tree_birch,
    "prop.cart": cart,
    "prop.haystack": haystack,
    "prop.fence": fence,
    "prop.hedge": hedge,
    "prop.wall": wall,
    "prop.rock": rock,
    "prop.sign": sign,
    "prop.tree_pine": tree_pine,
    "prop.tree_pine_slim": tree_pine_slim,
    "prop.tree_oak": tree_oak,
    "prop.tree_oak_forked": tree_oak_forked,
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
    "prop.table": table,
    "prop.chest": chest,
    "prop.chest_gilded": chest_gilded,
    "prop.chest_iron": chest_iron,
    "prop.chest_stone": chest_stone,
    "prop.chest_old": chest_old,
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
    "prop.roots": roots,
    "prop.bramble": bramble,
    "prop.tree_apple": tree_apple,
    "prop.bracken": bracken,
    "prop.reeds": reeds,
    "prop.inn_sign": inn_sign,
    "prop.notice_board": notice_board,
}
PROP_ORDER = list(PROPS)

# Which props move, and how long a frame lasts. Everything else is still on
# purpose: the trees, bushes and flowers are the most numerous things in the
# game, so animating them multiplies the sheet and draws the eye to the
# background, and a table has no reason to move by itself.
# Props that draw themselves differently depending on which of their cardinal
# neighbours are the same prop. A fence is a *line*, and a line has to know
# which way it runs; nothing else here does. Mask 0 keeps the plain id as its
# atlas key, exactly as the first frame of an animated prop does, so the
# editor palette and the sprite-exists gate are unaffected - the other seven
# pieces are added beside it and the build picks one per placement.
# This is not an animation: nothing cycles them.
LINKED = {"prop.fence": fence, "prop.hedge": hedge, "prop.wall": wall}
LINK_MASKS = range(8)          # N=1, E=2, W=4; south needs no art of its own


ANIMATED = {
    "prop.campfire": (4, 130),      # flames, quick
    "prop.hearth": (4, 260),        # banked down, so slower
    "prop.lamp_post": (4, 210),
    "prop.beehive": (4, 170),
    "prop.trough": (3, 430),        # standing water barely moves
}
ANIMATED_HUGE = {}                  # nothing this size moves yet
ANIMATED_VAST = {
}
# One table per frame size, because that is how the sheets are built - but the
# lookup is over all of them, so nothing has to know which class a prop is in
# to ask whether it moves.
ANIMATED_ALL = (ANIMATED, ANIMATED_HUGE, ANIMATED_VAST)


def prop_frames(pid, table=None):
    """Every frame of a prop, first frame first. One frame for most of them."""
    fns = table if table is not None else PROPS
    n = next((t[pid][0] for t in ANIMATED_ALL if pid in t), 1)
    return [fns[pid](phase=p) if n > 1 else fns[pid]() for p in range(n)]


def shed():
    """A shieling: drystone to head height, a steep plank roof weighted with
    stones, and a boarded terrace along its left side.

    Four tiles of frame is not four tiles of building. The hut is under three
    of them and the leftmost is the terrace, which is why the footprint leaves
    that tile walkable - a porch you cannot stand on is a painting of a porch.

    Two things had to be redrawn after the first cut at this size. The terrace
    came out a solid brown block: rails and posts and decking all touching,
    and once outline() had been round it there was no daylight left anywhere
    to say it was a frame rather than a crate. It is drawn open now, with real
    gaps between the rails. The chimney rose from the right-hand wall straight
    up past the eaves, so the top two thirds of it stood in the sky beside the
    roof with a gap behind; it comes out of the slope now, near the ridge,
    where a chimney on a hut this size would actually be."""
    c = Canvas(HUGE_FRAME, HUGE_FRAME)
    Y = HUGE_BASE_Y                              # 60
    WALL_T, WALL_L, WALL_R = 30, 18, 61

    # --- the terrace, drawn first so the hut stands in front of it -----------
    # Open, not solid: posts and two rails with daylight between them.
    # The decking runs right up to the wall. Stopped short of it the whole
    # thing read as a bench standing near the hut rather than a porch on it.
    for x in range(1, 20):
        c.col(x, 54, Y - 1, "WD" if x % 3 else "WDD")
    c.row(1, 19, 54, "WDL")                      # its lit leading edge
    c.row(1, 19, Y - 1, "WDD")
    for x in (3, 16):
        c.rect(x, 44, x + 1, 54, "WD")           # posts, up from the boards
        c.col(x, 44, 54, "WDL")
    c.rect(2, 44, 17, 45, "WD")                  # the top rail
    c.row(2, 17, 44, "WDL")
    c.rect(2, 50, 17, 51, "WDD")                 # and a lower one, with real
    c.rect(7, 50, 11, 53, "WD")                  # daylight between the two
    c.row(7, 11, 50, "WDL")                      # a pail left on the boards
    c.set(9, 49, "MTL")                          # and its handle

    # --- walls ---------------------------------------------------------------
    c.rect(WALL_L, WALL_T, WALL_R, Y, "ST")
    for i, y in enumerate(range(WALL_T + 4, Y, 5)):     # courses, joints
        c.row(WALL_L, WALL_R, y, "STD")                 # staggered so no two
        for x in range(WALL_L + 4 + (i % 2) * 6, WALL_R, 12):
            c.col(x, y - 4, y - 1, "STD")
    for x, y in ((21, 34), (57, 39), (30, 56), (52, 55)):
        c.set(x, y, "STL")                              # a few lit faces, so
        c.set(x + 1, y + 1, "STD")                      # the wall is not flat
    for x, y in ((19, 57), (20, 58), (60, 52), (59, 53), (61, 58)):
        c.set(x, y, "MS")                               # moss at the footings
    _shade(c, "ST", "STL", "STD")

    # --- roof ----------------------------------------------------------------
    _taper(c, 7, 31, 1, 25, "WD", cx=39)         # steep, and over the terrace
    _shade(c, "WD", "WDL", "WDD")
    for y in range(10, 32, 4):                   # the boards
        for x in range(HUGE_FRAME):
            if c.get(x, y) == "WD":
                c.set(x, y, "WDD")
    c.rect(36, 4, 43, 7, "WDD")                  # a ridge cap along the top
    c.row(36, 43, 4, "WDL")
    for y, x in ((14, 33), (19, 27), (19, 50), (24, 21),
                 (24, 56), (29, 16), (29, 60)):
        c.set(x, y, "STL")                       # stones holding the boards
        c.set(x + 1, y, "ST")
        c.set(x, y + 1, "STD")
    for x in range(15, 64, 6):                   # rafter ends under the eaves
        c.set(x, 31, "WDD")

    # --- the chimney, out of the slope rather than beside it ----------------
    c.rect(41, 12, 47, 29, "ST")
    for y in range(15, 29, 4):
        c.row(41, 47, y, "STD")
    c.rect(39, 8, 49, 12, "STL")                 # the cap
    c.row(39, 49, 8, "ST")
    c.row(41, 47, 9, "OL")                       # the flue, and the soot in it
    _shade(c, "ST", "STL", "STD")

    # --- the door, centred on the tile the footprint leaves open -------------
    c.rect(33, 38, 47, Y, "STD")                 # a dressed surround
    c.row(33, 47, 38, "STL")                     # under a lit lintel
    c.rect(35, 40, 45, Y, "WD")                  # the door
    c.col(35, 40, Y, "WDL")
    c.col(45, 40, Y, "WDD")
    for x in (38, 41, 44):
        c.col(x, 41, Y - 1, "WDD")               # its boards
    for y in (43, 54):                           # strap hinges across them
        c.row(35, 42, y, "MTD")
        c.set(36, y, "MTL")
    c.set(43, 49, "MTL")                         # the latch
    c.rect(32, Y - 1, 48, Y, "STL")              # a worn step at the foot
    c.row(32, 48, Y - 1, "ST")
    c.rect(48, 40, 50, 42, "MTD")                # a lantern on a bracket
    c.set(49, 41, "FIL")
    c.set(49, 39, "MTL")

    # --- windows -------------------------------------------------------------
    # A lit rectangle reads as a hole with a lamp behind it. What says window
    # is the frame round it and the bars across it.
    for x0 in (21, 50):
        c.rect(x0, 35, x0 + 8, 36, "STL")        # a dressed head
        c.rect(x0, 46, x0 + 8, 47, "STL")        # and a sill, standing proud
        c.rect(x0 + 1, 37, x0 + 7, 45, "WDD")    # the frame
        c.rect(x0 + 2, 38, x0 + 6, 44, "FIL")    # lit from inside
        c.col(x0 + 4, 38, 44, "WDD")             # mullion
        c.row(x0 + 2, x0 + 6, 41, "WDD")         # and transom - four panes
        c.set(x0 + 2, 38, "FI")                  # the glass is not one flat
        c.set(x0 + 6, 44, "FI")                  # tone across all four
        for sx in (x0 - 3, x0 + 9):              # shutters, folded back
            c.rect(sx, 36, sx + 2, 46, "WD")
            c.col(sx + 1, 36, 46, "WDD")
            c.set(sx + 1, 41, "MTD")

    for y in range(Y + 1, HUGE_FRAME):           # nothing below the base line
        for x in range(HUGE_FRAME):
            c.set(x, y, None)
    return c.outline()



def cottage():
    """A timber-framed house with a tiled roof: the thing this world had no
    word for. Every building in it was prop.shed, a drystone shieling, and the
    one roof key in the palette was spent on a temple from another continent -
    so a settlement could only ever be huts and a smithy.

    Terracotta over plaster between dark timbers is the whole colour idea, and
    it is chosen against the ground rather than for itself: the roof is the
    only large warm mass in a green country, which is what makes a hamlet
    visible across a map of meadow and wood. The frame has to stay *dark* for
    it - drawn a shade off the plaster the timbers vanished at map scale and
    the house came out a white box with a red lid.

    Four tiles wide, like the shed, and solid on all four: there is no inside
    yet, and a door you can walk into that opens on nothing is worse than a
    painted one."""
    Y = HUGE_BASE_Y
    CX = 31
    c = Canvas(HUGE_FRAME, HUGE_FRAME)

    # --- walls: plaster panels between a dark frame -------------------------
    c.rect(9, 30, 54, Y, "CL")
    _shade(c, "CL", "CLL", "CLD")
    for x in (9, 21, 42, 54):                    # posts, framing three bays
        c.rect(x - 1, 30, x, Y, "WDD")
        c.col(x - 1, 30, Y, "WD")
    c.rect(9, 42, 54, 43, "WDD")                 # the mid rail
    c.row(9, 54, 42, "WD")
    c.rect(9, 29, 54, 30, "WDD")                 # a sill plate under the eaves
    for cx in (15, 48):                          # a cross brace per outer bay
        for i in range(-5, 6):
            for dx in (0, 1):
                c.set(cx + i + dx, 36 + i, "WDD")
                c.set(cx - i + dx, 36 + i, "WDD")

    # --- roof: steep, tiled, and oversailing the walls ----------------------
    _taper(c, 6, 28, 2, 27, "RF", cx=CX)
    _shade(c, "RF", "RFL", "RFD")
    for y in range(9, 29, 3):                    # courses of tile
        for x in range(HUGE_FRAME):
            if c.get(x, y) == "RF":
                c.set(x, y, "RFD")
    for y in range(10, 29, 3):                   # and the lit lip of each
        for x in range(HUGE_FRAME):
            if c.get(x, y) == "RF" and c.get(x, y - 1) == "RFD":
                c.set(x, y, "RFL")
    c.rect(CX - 3, 4, CX + 3, 6, "RFD")          # the ridge
    c.row(CX - 3, CX + 3, 4, "RFL")
    c.rect(4, 28, 59, 29, "RFD")                 # eaves, standing proud
    c.row(4, 59, 28, "RFL")

    # --- the chimney, out of the slope like the shed's ----------------------
    c.rect(45, 10, 51, 27, "ST")
    for y in range(13, 27, 4):
        c.row(45, 51, y, "STD")
    c.rect(43, 6, 53, 10, "STL")                 # the cap
    c.row(43, 53, 6, "ST")
    c.row(45, 51, 7, "OL")                       # the flue
    _shade(c, "ST", "STL", "STD")

    # --- door, centred, with a stone step -----------------------------------
    c.rect(27, 44, 36, Y, "WD")
    c.col(27, 44, Y, "WDL")
    c.col(36, 44, Y, "WDD")
    for x in (30, 33):
        c.col(x, 45, Y - 1, "WDD")               # its boards
    c.rect(26, 43, 37, 44, "WDD")                # the head
    for y in (47, 56):
        c.row(27, 33, y, "MTD")                  # strap hinges
        c.set(28, y, "MTL")
    c.set(34, 52, "MTL")                         # the latch
    c.rect(24, Y - 1, 39, Y, "STL")              # a worn step
    c.row(24, 39, Y - 1, "ST")

    # --- windows: a frame and bars, never a lit rectangle -------------------
    for x0 in (11, 45):
        c.rect(x0, 44, x0 + 7, 45, "WDD")        # head
        c.rect(x0, 55, x0 + 7, 56, "WDD")        # and sill
        c.rect(x0 + 1, 46, x0 + 6, 54, "FIL")    # lit from inside
        c.col(x0 + 3, 46, 54, "WDD")             # mullion
        c.row(x0 + 1, x0 + 6, 50, "WDD")         # transom
        c.set(x0 + 1, 46, "FI")                  # not one flat tone
        c.set(x0 + 6, 54, "FI")
    # A window in the gable, which is what says the roof has a room under it.
    c.rect(CX - 3, 18, CX + 4, 19, "WDD")
    c.rect(CX - 2, 20, CX + 3, 25, "FIL")
    c.col(CX, 20, 25, "WDD")
    c.col(CX + 1, 20, 25, "WDD")
    c.rect(CX - 3, 26, CX + 4, 26, "WDD")

    for y in range(Y + 1, HUGE_FRAME):
        for x in range(HUGE_FRAME):
            c.set(x, y, None)
    return c.outline()


def market_stall():
    """A trestle stall under a striped awning, with the valley's produce laid
    out on it: apples, cabbages, loaves and a basket of eggs.

    The awning is the stall, the way the wheel is the cart: at map scale a
    table with things on it is a table, and a striped roof on poles is a
    market. The stripes are roof red and cloth, the cottage's two colours, so
    the stall reads as belonging to the same village. Two tiles wide and
    solid only along the counter - the awning overhangs ground you can walk
    under, which is where you would stand to buy."""
    Y = HUGE_BASE_Y
    c = Canvas(HUGE_FRAME, HUGE_FRAME)
    for x in (15, 46):                           # the poles
        c.rect(x, 20, x + 2, Y, "WD")
        c.col(x, 20, Y, "WDL")
        c.col(x + 2, 20, Y, "WDD")
    c.rect(16, 42, 47, Y, "WD")                  # the counter front
    for x in range(19, 47, 5):
        c.col(x, 44, Y, "WDD")
    c.rect(14, 38, 49, 41, "WDL")                # its top
    c.row(14, 49, 41, "WDD")
    # Produce, each lot in its own basket or crate along the counter top. Heaped
    # straight on the boards the apples ran into one red lump and the cabbages
    # into one green one - inside a silhouette nothing draws an edge for you,
    # so every lot brings its own container and a dark line under its rim.
    def basket(x0, x1):
        c.rect(x0, 35, x1, 37, "THD")
        c.row(x0, x1, 35, "TH")
        c.row(x0, x1, 38, "OL")
        c.col(x0 - 1, 35, 37, "OL")
        c.col(x1 + 1, 35, 37, "OL")
    for cx, cy in ((19, 33), (23, 33), (21, 31)):          # apples
        _lobe(c, cx, cy, 2, "RF")
        c.set(cx - 1, cy - 1, "RFL")
        c.set(cx + 1, cy + 1, "RFD")
    basket(16, 25)
    for cx in (30, 35):                                    # cabbages
        _lobe(c, cx, 33, 3, "BUL")
        c.set(cx, 33, "BU")
        c.set(cx + 1, 34, "BU")
        c.set(cx - 1, 32, "GRL")
    c.col(32, 30, 34, "BUD")                               # the gap between them
    basket(27, 37)
    c.rect(40, 32, 48, 37, "WD")                           # a crate of loaves
    for x0 in (41, 45):
        c.rect(x0, 30, x0 + 2, 33, "TH")
        c.row(x0, x0 + 2, 30, "THL")
        c.set(x0 + 1, 32, "THD")
    c.row(40, 48, 34, "WDL")
    c.row(40, 48, 38, "OL")
    c.col(39, 32, 37, "OL")
    # The awning: a sloped cloth roof in stripes, with a scalloped valance.
    for i, y in enumerate(range(12, 22)):
        c.row(13 - i // 3, 50 + i // 3, y, "CL")
    for x in range(10, 54):
        if (x // 5) % 2 == 0:
            for y in range(12, 25):
                if c.get(x, y) == "CL":
                    c.set(x, y, "RF")
    c.row(13, 50, 12, "CLL")
    for x in range(10, 54):                      # the valance, scalloped
        k = "RF" if (x // 5) % 2 == 0 else "CL"
        depth = 2 if x % 5 in (1, 2, 3) else 1
        c.col(x, 22, 22 + depth, k)
    for y in range(12, 25):                      # the underside, in shadow
        for x in range(10, 54):
            if c.get(x, y) == "RF" and c.get(x, y + 1) is None:
                c.set(x, y, "RFD")
            elif c.get(x, y) == "CL" and c.get(x, y + 1) is None:
                c.set(x, y, "CLD")
    c.rect(24, 8, 39, 11, "WD")                  # a ridge board, and the name
    c.row(24, 39, 8, "WDL")
    c.row(26, 37, 10, "WDD")
    return c.outline()


HUGE_PROPS = {
    "prop.cottage": cottage,
    "prop.shed": shed,
    "prop.burrow_tree": burrow_tree,
    "prop.market_stall": market_stall,
}
HUGE_PROP_ORDER = list(HUGE_PROPS)


def great_oak():
    """The tree a road bends round. The size ladder the boulders make - a thing
    you step over up to a thing a road stops at - had no equivalent in anything
    that grows, so every wood was built from one size of tree and read as a
    pattern however carefully it was scattered.

    Two things went wrong drawing it and both are worth keeping. The lower
    boughs were drawn over the crown to put them in front of it, from the
    trunk straight out to either side - which at this width is a horizontal
    line, and a horizontal brown line across a canopy is a plank through the
    tree. They angle down and out now, the way a bough that has carried its
    own weight for a century does. And the crown was one mass: the sky holes
    punched in it were filled again by the next lobe, so it came out a green
    cloud with shading on it. The gaps go in last, and they are gaps in the
    *outline* - the lobes are pulled apart so the silhouette itself is broken
    into masses. Punching discs of sky into the middle instead is worse than
    doing nothing: outline() borders anything with transparency beside it, so
    every hole came back as a neat black-rimmed circle and the canopy read as
    a colander. Depth here is carried by the crescents inside the mass and by
    the shape of its edge, which is all it ever was."""
    Y = VAST_BASE_Y
    CX = 56
    c = Canvas(VAST_FRAME, VAST_FRAME)

    # --- trunk and root flare ----------------------------------------------
    _taper(c, 44, Y, 9, 15, "WD", cx=CX)
    for dx, r in ((-22, 9), (-11, 11), (0, 12), (12, 11), (23, 9)):
        _lobe(c, CX + dx, Y - 4, r, "WD")        # roots, most of the frame wide
    _shade(c, "WD", "WDL", "WDD")
    # Bark. A bole this wide drawn in one tone is a column, so the grain runs
    # the full height in deep fissures with a lit edge on one side of each -
    # the same trick that separates the crystal ring from the shafts behind it.
    for dx in (-26, -19, -12, -4, 3, 11, 19, 26):
        wob = 0
        for y in range(45, Y - 1):
            if (y + dx) % 11 == 0:
                wob += 1 if (dx + y) % 2 else -1
            x = CX + dx + wob
            if c.get(x, y) in ("WD", "WDL", "WDD"):
                c.set(x, y, "WDD")
                if c.get(x + 1, y) == "WD":
                    c.set(x + 1, y, "WDL")

    # --- boughs, out before the leaves go on --------------------------------
    for x1, y1 in ((22, 40), (90, 40), (34, 26), (78, 26), (56, 20)):
        _twig(c, CX, 52, x1, y1, 2, "WD")
    _shade(c, "WD", "WDL", "WDD")

    # --- crown, in tiers ----------------------------------------------------
    _crown(c,
           [(56, 26, 20), (26, 40, 14), (86, 40, 14), (56, 52, 16),
            (34, 22, 12), (78, 22, 12), (56, 8, 14),
            (18, 30, 9), (94, 30, 9), (40, 46, 11), (72, 46, 11)],
           [(30, 48, 9), (82, 48, 9), (56, 60, 10), (22, 36, 7), (90, 36, 7)],
           [(42, 12, 9), (70, 16, 8), (56, 30, 8), (30, 26, 6)],
           [])
    # A bough out over the leaves on each side, angled down and away, and
    # stopping well inside the canopy: run out to the edge they cleared the
    # leaves on both sides and the tree grew a pair of antlers.
    for x1, y1 in ((38, 60), (74, 60)):
        _twig(c, CX, 48, x1, y1, 1, "WD")
    _shade(c, "BU", "BUL", "BUD")
    _shade(c, "WD", "WDL", "WDD")

    for y in range(Y + 1, VAST_FRAME):
        for x in range(VAST_FRAME):
            c.set(x, y, None)
    return c.outline()

VAST_PROPS = {
    "prop.great_oak": great_oak,
}
VAST_PROP_ORDER = list(VAST_PROPS)

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


def _rune(c, x, y, key="CYL", dim="CY"):
    """A mark cut into stone with light in it.

    The socket is the whole of why it reads. Drawn as bright strokes laid on
    the face, a rune this size is a speck of dirt; sunk in a near-black cut
    the same strokes read as something carved that light is coming out of,
    which is the difference between a mark and a smudge. At this size it must
    not try to be a letter - what has to say "written" is that the same
    angular shape repeats round the band, the way real carved work does."""
    for dy in range(-3, 4):
        for dx in range(-2, 3):
            c.set(x + dx, y + dy, "STX")               # the cut it sits in
    for dx, dy in ((0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
                   (-1, -2), (1, 2), (-1, 1), (1, -1)):
        c.set(x + dx, y + dy, key)
    c.set(x + 1, y - 2, dim)
    c.set(x - 1, y + 2, dim)


def _shard(c, x, y, r):
    """A crystal turning in the gate: a faceted diamond, *blue* with one lit
    corner rather than white with a blue edge. Built the other way round, a
    ring of them reads as ice cubes floating in a bowl - the light has to be
    a glint off one facet, not the body of the thing."""
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if abs(dx) + abs(dy) > r:
                continue
            c.set(x + dx, y + dy, "CY")
    for i in range(r):                                 # the facet facing the
        c.set(x - i, y - (r - 1 - i), "CYL")           # light, along one edge
    c.set(x, y - r + 1, "CYL")
    for i in range(r):                                 # and the one away from it
        c.set(x + i, y + (r - 1 - i), "CYD")


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
def bush(variant=0):
    """Five bushes. The light crescent stays on the upper left and the shade on
    the lower right throughout - what changes is the mass under them, because a
    bush is a silhouette and nothing else at this size: round, sprawling,
    double, leggy, and upright."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # low and sprawling, wider than tall
        for y, x0, x1 in ((20, 9, 22), (21, 6, 25), (22, 4, 27), (23, 3, 28),
                          (24, 3, 28), (25, 3, 28), (26, 4, 27), (27, 5, 26),
                          (28, 8, 23)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((21, 8, 14), (22, 6, 13), (23, 5, 12), (24, 5, 10)):
            c.row(x0, x1, y, "BUL")
        for y, x0, x1 in ((25, 20, 28), (26, 18, 27), (27, 14, 26), (28, 12, 23)):
            c.row(x0, x1, y, "BUD")
        for x, y in ((11, 20), (19, 20), (24, 22)):
            c.set(x, y, None)
    elif variant == 2:                   # two crowns from one root
        for y, x0, x1 in ((17, 6, 12), (18, 4, 14), (19, 3, 15), (20, 3, 16),
                          (21, 3, 16), (22, 4, 17), (23, 5, 18)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((20, 17, 25), (21, 16, 27), (22, 15, 28), (23, 15, 28),
                          (24, 14, 28), (25, 14, 27)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((24, 5, 26), (25, 5, 26), (26, 6, 25),
                          (27, 7, 24), (28, 9, 22)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((18, 5, 9), (19, 4, 8), (20, 4, 7), (21, 16, 20),
                          (22, 15, 19)):
            c.row(x0, x1, y, "BUL")
        for y, x0, x1 in ((24, 20, 28), (25, 19, 27), (26, 17, 25),
                          (27, 14, 24), (28, 11, 22)):
            c.row(x0, x1, y, "BUD")
        for x, y in ((9, 17), (13, 21), (22, 20), (17, 24)):
            c.set(x, y, None)
    elif variant == 3:                   # leggy, with its stems showing
        # Three tufts on their own stems rather than one disc over all of them:
        # a single mass sitting on legs is an umbrella, and no amount of
        # notching the rim talks it out of that.
        for x0, y0, x1, y1 in ((15, 22, 11, 28), (16, 21, 20, 28), (15, 20, 15, 28)):
            _twig(c, x0, y0, x1, y1, 0, "WDD")
        for cx, cy, r in ((11, 19, 4), (20, 18, 4), (15, 15, 5)):
            _lobe(c, cx, cy, r, "BU")
        for cx, cy, r in ((10, 17, 2), (13, 13, 2), (18, 16, 2)):
            _lobe(c, cx, cy, r, "BUL")
        for cx, cy, r in ((22, 20, 2), (13, 21, 2), (17, 18, 2)):
            _lobe(c, cx, cy, r, "BUD")
        for x, y in ((8, 19), (23, 18), (15, 11), (14, 19)):
            c.set(x, y, None)
    elif variant == 4:                   # upright, taller than it is wide
        for y, x0, x1 in ((12, 13, 18), (13, 11, 20), (14, 10, 21), (15, 9, 22),
                          (16, 9, 22), (17, 9, 22), (18, 9, 22), (19, 8, 23),
                          (20, 8, 23), (21, 8, 23), (22, 9, 22), (23, 9, 22),
                          (24, 10, 21), (25, 10, 21), (26, 11, 20),
                          (27, 12, 19), (28, 13, 18)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((13, 13, 17), (14, 11, 16), (15, 10, 15),
                          (16, 10, 14), (17, 10, 13), (18, 10, 12)):
            c.row(x0, x1, y, "BUL")
        for y, x0, x1 in ((21, 18, 23), (22, 17, 22), (23, 16, 22),
                          (24, 15, 21), (25, 14, 21), (26, 13, 20)):
            c.row(x0, x1, y, "BUD")
        for x, y in ((15, 12), (19, 15), (12, 22)):
            c.set(x, y, None)
    else:                                # round, the one everything else is not
        for y, x0, x1 in ((16, 11, 20), (17, 9, 22), (18, 8, 23), (19, 7, 24),
                          (20, 6, 25), (21, 6, 25), (22, 6, 25), (23, 6, 25),
                          (24, 6, 25), (25, 6, 25), (26, 6, 25),
                          (27, 7, 24), (28, 9, 22)):
            c.row(x0, x1, y, "BU")
        for y, x0, x1 in ((17, 12, 15), (18, 10, 16), (19, 9, 15),
                          (20, 8, 13), (21, 8, 11), (22, 9, 10)):
            c.row(x0, x1, y, "BUL")      # light crescent on the upper left
        for y, x0, x1 in ((22, 22, 25), (23, 21, 25), (24, 20, 25), (25, 18, 25),
                          (26, 16, 25), (27, 7, 24), (28, 9, 22)):
            c.row(x0, x1, y, "BUD")      # shade curves round the lower right
        for x, y in ((13, 16), (18, 16)):
            c.set(x, y, None)            # notch the crown so it reads as leaves
        for x, y in ((14, 21), (11, 25), (19, 19)):
            c.set(x, y, "BUD")
    return c.outline()


def rock(variant=0):
    """Five small stones. The first is the original drawing; the rest are built
    from _mass and _form, which is the vocabulary the big boulders use - one
    stone, a flat one, two together, a split shard, and a scatter of three.

    A rock field drawn from one rock reads as a repeated stamp however it is
    scattered, and at this size the fix is the number and arrangement of lumps
    rather than any amount of detail inside one."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # flat, half sunk in the turf
        _mass(c, [(15, 27, 6), (10, 28, 4), (21, 28, 4)], BASE_Y)
        _form(c, "ST", 0x31, tilt=0.10)
        _rim(c, ROCK, "STL", "STD")
    elif variant == 2:                   # two, one leaning on the other
        _mass(c, [(11, 25, 5), (20, 27, 4)], BASE_Y)
        _form(c, "ST", 0x5D, tilt=0.16)
        _rim(c, ROCK, "STL", "STD")
        _crack(c, [(16, 21), (16, 28)])
    elif variant == 3:                   # a shard, standing on its point
        # Pointed, which none of the other four are. Drawn as rows rather than
        # lobes because _mass rounds everything it touches, and the whole of
        # this one is that it has corners.
        for y, x0, x1 in ((17, 15, 16), (18, 14, 17), (19, 13, 18), (20, 13, 19),
                          (21, 12, 19), (22, 11, 20), (23, 11, 20), (24, 10, 21),
                          (25, 10, 21), (26, 11, 21), (27, 12, 20), (28, 13, 19)):
            c.row(x0, x1, y, "ST")
        _form(c, "ST", 0x7B, tilt=0.02, grit=0.2)
        _rim(c, ROCK, "STL", "STD")
        _crack(c, [(15, 18), (17, 23), (15, 28)])
    elif variant == 4:                   # three pebbles, none of them the same
        _mass(c, [(9, 27, 3), (16, 26, 4), (23, 28, 3)], BASE_Y)
        _form(c, "ST", 0x2F, tilt=0.20)
        _rim(c, ROCK, "STL", "STD")
    else:
        for y, x0, x1 in ((20, 13, 18), (21, 11, 20), (22, 10, 21), (23, 9, 22),
                          (24, 9, 22), (25, 9, 22), (26, 10, 21), (27, 11, 20),
                          (28, 12, 19)):
            c.row(x0, x1, y, "ST")
        for y, x0, x1 in ((20, 14, 17), (21, 12, 17), (22, 11, 16), (23, 10, 14)):
            c.row(x0, x1, y, "STL")      # lit top-left facet
        for y, x0, x1 in ((25, 16, 22), (26, 15, 21), (27, 13, 20), (28, 12, 19)):
            c.row(x0, x1, y, "STD")
        c.set(15, 23, "STD")             # a crack, so it is not a smooth blob
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


def tree_oak(variant=0):
    """Five oaks, told apart by what shape they grew into.

    A second oak is only worth having if it is a different silhouette - a
    recoloured or slightly wider copy of the first reads as the first one at a
    glance, which is the whole failure mode of a variant. So these are five
    histories rather than five sizes: grown in the open, grown crowded and
    forked, grown against the wind, drawn up thin in a wood, and grown old.
    """
    c = Canvas(FRAME, FRAME)
    if variant == 1:                              # grown crowded: forks low
        _taper(c, 20, BASE_Y, 1, 3, "WD")
        for cx, cy, r in ((15, 27, 4), (10, 28, 3), (21, 28, 3)):
            _lobe(c, cx, cy, r, "WD")
        _twig(c, 15, 21, 10, 12, 1, "WD")         # then two limbs, not one
        _twig(c, 16, 21, 21, 13, 1, "WD")
        _crown(c,
               [(9, 10, 7), (21, 11, 6), (14, 7, 5), (6, 15, 4),
                (24, 15, 4), (15, 13, 5)],
               [(8, 14, 4), (22, 14, 3), (14, 11, 3)],
               [(8, 6, 3), (19, 8, 3)],
               [(9, 12), (20, 10), (12, 5), (5, 14), (24, 17)])
        _twig(c, 12, 15, 8, 12, 0)
        _twig(c, 18, 15, 22, 13, 0)
    elif variant == 2:                            # grown against the wind
        # The trunk leans and the crown is streamed off to one side, with the
        # windward face cut back almost to the limbs. A tree bent by weather is
        # the one silhouette here that is not symmetrical about anything.
        _twig(c, 14, BASE_Y, 19, 15, 1, "WD")
        for cx, cy, r in ((14, 27, 4), (9, 28, 3), (19, 28, 3)):
            _lobe(c, cx, cy, r, "WD")
        _twig(c, 18, 17, 24, 13, 1, "WD")
        _twig(c, 18, 18, 13, 16, 0, "WD")
        _crown(c,
               [(22, 11, 7), (27, 14, 4), (17, 13, 5), (24, 6, 5), (13, 10, 4)],
               [(19, 15, 4), (26, 16, 3)],
               [(24, 7, 3), (20, 9, 3)],
               [(23, 13), (27, 12), (16, 11), (12, 9)])
        _twig(c, 20, 14, 26, 11, 0)
    elif variant == 3:                            # drawn up thin in a wood
        # Bare for most of its height, because in company an oak throws
        # everything at the light and keeps nothing below it. The crown is
        # small, high and nearly round - the opposite of the open-grown one.
        _taper(c, 11, BASE_Y, 1, 2, "WD")
        for cx, cy, r in ((15, 28, 3), (11, 29, 2), (19, 29, 2)):
            _lobe(c, cx, cy, r, "WD")
        for y in range(16, 26, 4):                # branch scars down the bole
            c.set(13, y, "WDD")
            c.set(18, y + 2, "WDD")
        _twig(c, 15, 13, 10, 9, 1, "WD")
        _twig(c, 16, 13, 21, 9, 1, "WD")
        _crown(c,
               [(15, 7, 6), (9, 10, 4), (22, 10, 4), (15, 3, 4)],
               [(11, 12, 3), (20, 12, 3)],
               [(13, 3, 3)],
               [(10, 8), (21, 8), (15, 11)])
    elif variant == 4:                            # grown old and spreading
        # Heavy in the bole, low and wide in the crown, and carrying one limb
        # that has died and been left - which is what tells an old tree from a
        # merely big one at this size.
        _taper(c, 17, BASE_Y, 2, 4, "WD")
        for cx, cy, r in ((15, 27, 5), (8, 28, 3), (23, 28, 3)):
            _lobe(c, cx, cy, r, "WD")
        _twig(c, 14, 19, 7, 15, 1, "WD")
        _twig(c, 17, 19, 25, 16, 1, "WD")
        _crown(c,
               [(15, 14, 7), (6, 16, 5), (25, 17, 5), (10, 10, 5),
                (21, 10, 5), (15, 8, 5)],
               [(9, 19, 4), (22, 20, 4), (15, 18, 4)],
               [(11, 8, 3), (20, 8, 3), (15, 12, 3)],
               [(8, 14), (23, 15), (15, 6), (12, 18), (19, 17), (3, 17)])
        _twig(c, 18, 13, 27, 8, 0, "WDD")         # the dead limb, out of the
        _twig(c, 24, 10, 26, 6, 0, "WDD")         # leaves and bare
    else:                                         # grown in the open
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
        _twig(c, 13, 16, 10, 13)                  # limb ends, over the leaves
        _twig(c, 18, 15, 21, 12)
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


def tree_pine(variant=0):
    """Five pines from five whorl profiles, because at this size the profile is
    the whole of what a conifer silhouette is.

    Mature, drawn up in company, a sapling, a spire, and one broad and flat
    topped with age. Two trees that differ only in width read as one tree drawn
    twice, so what changes between these is where the crown starts and how fast
    it widens - not how big it is."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                              # grown in company
        rows = [(0, 1), (1, 1), (2, 2),
                (1, 2), (2, 2), (3, 3),
                (2, 3), (3, 3), (4, 4),
                (3, 4), (4, 5), (5, 5),
                (4, 5), (5, 6), (6, 6)]
        _conifer(c, rows, 2, 0x6D34, 14)
        for y in range(20, BASE_Y, 4):            # branch scars down the bare
            c.set(13, y, "WDD")                   # half of it
            c.set(18, y + 1, "WDD")
    elif variant == 2:                            # a sapling
        # Short, and skirted to the ground with no bare trunk at all, which is
        # what keeps it from reading as the mature one scaled down.
        rows = [(0, 1), (1, 1), (2, 2),
                (1, 2), (2, 3), (3, 3),
                (2, 3), (3, 4), (4, 5),
                (3, 4), (4, 5), (5, 6)]
        _conifer(c, rows, 16, 0x41C9, 29)
    elif variant == 3:                            # a spire
        # Tall, and widening so slowly it is nearly a column - a pine grown
        # where there was nothing to reach for sideways.
        rows = [(0, 1), (1, 1), (1, 2), (2, 2),
                (1, 2), (2, 2), (2, 3), (3, 3),
                (2, 3), (3, 3), (3, 4), (4, 4),
                (3, 4), (4, 4), (4, 5), (5, 5),
                (4, 5), (5, 5), (5, 6), (6, 6),
                (5, 6), (6, 6), (6, 7), (7, 7),
                (6, 7), (7, 7)]
        _conifer(c, rows, 1, 0x1F53, 27)
    elif variant == 4:                            # old, broad, flat topped
        # The leader has stopped and gone flat while the lower whorls kept
        # spreading - the one profile here that is wider than it is tall.
        rows = [(3, 3), (4, 4), (4, 4),
                (3, 4), (4, 5), (5, 6),
                (5, 6), (6, 7), (7, 8),
                (7, 8), (8, 9), (9, 10),
                (9, 10), (10, 11), (11, 11),
                (10, 11), (11, 12)]
        _conifer(c, rows, 9, 0x8E22, 26)
    else:                                         # mature
        rows = [(0, 1), (1, 1), (2, 2), (3, 3),
                (1, 2), (2, 3), (3, 4), (4, 4),
                (2, 3), (3, 4), (4, 5), (5, 6),
                (4, 4), (5, 6), (6, 7), (7, 7),
                (5, 6), (6, 7), (7, 8), (8, 9),
                (7, 8), (8, 9), (9, 10), (10, 10),
                (9, 9)]
        _conifer(c, rows, 2, 0x2B71, 22)
    return c.outline()


def tree_dead(variant=0):
    """Five dead trees: standing, snapped off, leaning, a bare skeleton, and a
    hollow shell.

    All bark and no leaves, so the silhouette is doing all of the work and
    there is nothing else to tell one from another - which makes the shape of
    what is left the whole design of each."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # snapped off, splintered at the break
        c.rect(13, 16, 18, BASE_Y, "WDD")
        for x, y in ((13, 15), (15, 14), (16, 15), (18, 13), (14, 16), (17, 14)):
            c.set(x, y, "WDD")           # the splinters, at no two heights
        c.row(11, 20, 27, "WDD")
        c.row(10, 21, 28, "WDD")
        c.rect(14, 17, 17, 19, "WD")     # the open grain of the break
    elif variant == 2:                   # leaning, its roots half out
        # Drawn as rows that step sideways and narrow as they rise, not as one
        # stroke of constant width: a bar at the same thickness end to end is
        # a log lying across the frame, whichever angle it is drawn at.
        for i, y in enumerate(range(BASE_Y, 8, -1)):
            x = 12 + (i * 9) // 18
            w = 3 - (i * 2) // 18
            c.row(x - w, x + w, y, "WDD")
        for x0, y0, x1, y1 in ((17, 16, 23, 13), (16, 19, 10, 15), (19, 11, 24, 9)):
            _twig(c, x0, y0, x1, y1, 0, "WDD")
        c.row(8, 17, 27, "WDD")          # the root plate, lifting on one side
        c.row(7, 15, 28, "WDD")
        for x, y in ((7, 26), (9, 25)):  # roots torn out of the ground with it
            c.set(x, y, "WDD")
    elif variant == 3:                   # a bare skeleton, still full of branches
        c.rect(14, 5, 17, BASE_Y, "WDD")
        for x0, y0, x1, y1 in ((14, 11, 6, 6), (17, 10, 25, 5), (14, 17, 7, 13),
                               (17, 15, 24, 11), (15, 7, 11, 2), (16, 7, 21, 3)):
            _twig(c, x0, y0, x1, y1, 0, "WDD")
        for x0, y0, x1, y1 in ((9, 8, 6, 4), (23, 7, 26, 3), (9, 15, 5, 12)):
            _twig(c, x0, y0, x1, y1, 0, "WDD")
        c.row(11, 20, 27, "WDD")
        c.row(10, 21, 28, "WDD")
    elif variant == 4:                   # a hollow shell, broken open
        for y, x0, x1 in ((12, 13, 18), (13, 12, 19), (14, 12, 19), (15, 11, 20),
                          (16, 11, 20), (17, 11, 20), (18, 11, 21), (19, 11, 21),
                          (20, 10, 21), (21, 10, 21), (22, 10, 22), (23, 10, 22),
                          (24, 9, 22), (25, 9, 23), (26, 9, 23)):
            c.row(x0, x1, y, "WDD")      # the shell, widening to the root
        for y, x0, x1 in ((16, 14, 17), (17, 13, 18), (18, 13, 18), (19, 13, 18),
                          (20, 14, 18), (21, 14, 17)):
            c.row(x0, x1, y, None)       # the cavity: an opening, not a window
        c.set(13, 15, None)
        c.set(18, 22, None)
        for x, y in ((13, 11), (16, 11), (19, 12), (15, 12)):
            c.set(x, y, "WD")            # the broken rim, seen into from above
        c.set(14, 12, None)              # and chewed away at no two heights
        c.set(17, 11, None)
        _twig(c, 20, 15, 25, 10, 0, "WDD")
        c.row(8, 23, 27, "WDD")
        c.row(7, 24, 28, "WDD")
    else:                                # still standing, two branches
        c.rect(14, 7, 17, BASE_Y, "WDD")
        for x, y in ((13, 14), (12, 13), (11, 12), (10, 11), (10, 10), (9, 9)):
            c.set(x, y, "WDD")           # branch reaching left
            c.set(x, y - 1, "WDD")
        for x, y in ((18, 12), (19, 11), (20, 10), (21, 10), (22, 9), (22, 8)):
            c.set(x, y, "WDD")           # and one right, at a different height
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


def boulder(variant=0):
    """Five boulders: the original round one, a flat slab, one split in two, a
    tall angular block, and a low one gone over to lichen.

    What separates them is the number of lumps and how they sit, because a
    boulder is a silhouette with facets in it - a second one differing only in
    its shading reads as the first with the light moved."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # a flat slab, wider than it is tall
        _mass(c, [(15, 26, 9), (7, 27, 6), (24, 27, 6)], BASE_Y)
        _form(c, "ST", 0x13, tilt=0.08, grit=0.5)
        _rim(c, ROCK, "STL", "STD")
        _crack(c, [(8, 24), (16, 22), (23, 25)])
    elif variant == 2:                   # split, with daylight down the cleft
        _mass(c, [(9, 22, 7), (10, 27, 6)], BASE_Y)
        _mass(c, [(22, 24, 6), (22, 28, 5)], BASE_Y)
        _form(c, "ST", 0x47, tilt=0.14)
        _rim(c, ROCK, "STL", "STD")
    elif variant == 3:                   # tall and angular, standing on a corner
        _mass(c, [(15, 13, 5), (14, 19, 7), (16, 26, 8)], BASE_Y)
        _form(c, "ST", 0x6B, tilt=0.03, grit=0.25)
        _rim(c, ROCK, "STL", "STD")
        _crack(c, [(12, 10), (17, 17), (13, 24)])
    elif variant == 4:                   # low, and gone over to lichen
        _mass(c, [(15, 24, 8), (8, 27, 5), (23, 27, 5)], BASE_Y)
        _form(c, "ST", 0x29, tilt=0.18)
        _rim(c, ROCK, "STL", "STD")
        _moss(c, [(11, 25, 4), (20, 27, 3), (16, 21, 3)], seed=11)
    else:
        _blob(c, 13, (4, 7, 9, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10, 9, 8), "ST")
        for y, x0, x1 in ((15, 12, 19), (16, 10, 20), (17, 9, 19),
                          (18, 8, 17), (19, 7, 15), (20, 7, 12)):
            c.row(x0, x1, y, "STL")      # one broad facet catching the light
        for y, x0, x1 in ((23, 19, 26), (24, 18, 26), (25, 17, 26),
                          (26, 16, 25), (27, 15, 24)):
            c.row(x0, x1, y, "STD")      # and one turned away from it
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


# The flame on a lamp column, one entry per phase: where it starts and how wide
# it is at each row up. Written out rather than generated because a flame that
# is only noise reads as static - these four are shapes, and they lean.
TEMPLE_FLAME = (                              # every one of them ends at y 83,
    (70, (0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 3, 3, 2, 2)),               # in the bowl
    (68, (0, 0, 1, 2, 2, 3, 4, 4, 4, 4, 3, 3, 3, 2, 2, 1)),
    (72, (0, 1, 2, 2, 3, 3, 4, 4, 4, 3, 2, 2)),
    (69, (0, 1, 1, 2, 3, 3, 4, 4, 4, 4, 3, 2, 2, 2, 1)),
)
# Where the dust hangs: over the steps and in the dark of the hall, which is
# where anything this faint can be seen at all. Each mote drifts up and out
# over the four frames, and they start at staggered phases so the air moves
# instead of pulsing.

# Where the dust hangs: over the steps and in the dark of the hall, which is
# where anything this faint can be seen at all. Each mote drifts up and out
# over the four frames, and they start at staggered phases so the air moves
# instead of pulsing.
TEMPLE_DUST = ((46, 96), (58, 90), (68, 94), (80, 88), (52, 102),
               (74, 104), (44, 86), (84, 98), (63, 82), (88, 92))

def temple(phase=0):
    """A temple on a square of ground four tiles by four: stone podium, a
    vermilion colonnade, two tiers of upswept tile roof, a pair of lamp columns
    burning at the front, and dust hanging in the air over the steps.

    It is the second thing in the 128 class and the first that moves, which is
    what made animation worth generalising to every frame size - see
    ANIMATED_VAST. Grey-blue tile against vermilion post is the whole colour
    idea: the roof reads as one mass and the columns as another, which is what
    stops a facade this size turning into texture."""
    c = Canvas(VAST_FRAME, VAST_FRAME)
    mid = 63                                  # centred on the 63/64 boundary

    # --- the podium: three courses, each stepping out over the one above ----
    c.rect(30, 96, 97, 103, "ST")             # the top surface the columns
    c.row(30, 97, 96, "STL")                  # stand on
    c.rect(28, 102, 99, 113, "ST")            # the body
    c.row(28, 99, 102, "STL")
    c.rect(24, 112, 103, VAST_BASE_Y, "ST")   # and the plinth it rests on
    c.row(24, 103, 112, "STL")
    for y in range(106, VAST_BASE_Y, 5):      # courses, joints staggered
        c.row(25, 102, y, "STD")
        for x in range(28 + (y % 10), 102, 9):
            c.col(x, y - 4, y - 1, "STD")
    _shade(c, "ST", "STL", "STD")

    # --- the steps, cut into the front of it -------------------------------
    for i, (y0, y1, w) in enumerate(((106, 111, 4), (112, 117, 6), (118, 124, 8))):
        c.rect(mid - w, y0, mid + 1 + w, y1, "ST")
        c.row(mid - w, mid + 1 + w, y0, "STL")
        c.row(mid - w, mid + 1 + w, y1, "STD")

    # --- behind the columns: the dark of the hall, and the doorway ----------
    c.rect(36, 68, 91, 97, "STX")
    c.rect(54, 74, 73, 97, "OL")              # the way in, darker still
    c.row(54, 73, 74, "RFD")                  # under a painted lintel
    c.row(54, 73, 73, "RF")

    # --- four vermilion columns, and the beam they carry --------------------
    for cx in (44, 56, 71, 83):
        c.rect(cx, 66, cx + 4, 99, "RF")
        c.col(cx, 66, 99, "RFL")              # lit edge
        c.col(cx + 4, 66, 99, "RFD")
        c.rect(cx - 1, 64, cx + 5, 67, "RFD")  # the capital
        c.row(cx - 1, cx + 5, 64, "RFL")
        c.rect(cx - 1, 96, cx + 5, 99, "STD")  # and a stone base
    c.rect(30, 58, 97, 65, "RF")              # the architrave
    c.row(30, 97, 58, "RFL")
    c.row(30, 97, 65, "RFD")
    for x in range(34, 96, 8):                # painted brackets under it
        c.rect(x, 60, x + 3, 63, "THD")
        c.row(x, x + 3, 60, "TH")

    # --- the lower roof: the widest thing here, so it is drawn as one mass --
    _taper(c, 42, 57, 17, 41, "MT", cx=mid)
    _shade(c, "MT", "MTL", "MTD")
    for y in range(45, 58, 3):                # tile courses
        for x in range(VAST_FRAME):
            if c.get(x, y) == "MT":
                c.set(x, y, "MTD")
    for x in range(26, 102, 6):               # and the ridges running down it
        if c.get(x, 56) == "MT" or c.get(x, 56) == "MTD":
            c.col(x, 50, 57, "MTL")
    _eave(c, 22, 57, -1, "MT", "MTL")         # the tips, lifting as they go out
    _eave(c, 105, 57, 1, "MT", "MTL")
    c.row(21, 106, 57, "MTD")                 # the shadowed line of the eaves

    # --- the upper storey and its roof --------------------------------------
    c.rect(46, 34, 81, 45, "RF")              # a short wall between the tiers
    c.row(46, 81, 34, "RFL")
    c.row(46, 81, 45, "RFD")
    c.rect(56, 37, 71, 43, "THD")             # one window, shuttered in gold
    c.row(56, 71, 37, "TH")
    for x in range(58, 71, 4):
        c.col(x, 38, 42, "TH")
    _taper(c, 20, 33, 8, 29, "MT", cx=mid)
    _shade(c, "MT", "MTL", "MTD")
    for y in range(22, 34, 3):
        for x in range(VAST_FRAME):
            if c.get(x, y) == "MT":
                c.set(x, y, "MTD")
    _eave(c, 34, 33, -1, "MT", "MTL", n=6)
    _eave(c, 93, 33, 1, "MT", "MTL", n=6)
    c.row(33, 94, 33, "MTD")

    # --- the finial ---------------------------------------------------------
    c.rect(61, 14, 66, 21, "THD")
    c.row(61, 66, 14, "TH")
    c.col(61, 14, 21, "TH")
    _lobe(c, 63, 11, 3, "TH")
    _shade(c, "TH", "TH", "THD")

    # --- two guardians flanking the steps -----------------------------------
    # Dark stone on pale, because a stone lion the colour of the stone it sits
    # on is not a lion, it is a lump - the first version of these disappeared
    # into the podium entirely.
    for sx, face in ((40, 1), (76, -1)):      # they look in at the stair
        hx = sx + 5 + face                                 # where the head sits
        c.rect(sx, 116, sx + 11, VAST_BASE_Y, "STD")       # its own plinth
        c.row(sx, sx + 11, 116, "ST")
        c.rect(sx + 2, 104, sx + 9, 117, "STX")            # chest and haunches
        c.col(sx + 2, 104, 117, "STD")                     # lit down one side
        for a, r in ((-4, 3), (0, 4), (4, 3)):             # a mane of lobes, so
            _lobe(c, hx + a, 101 + abs(a) // 2, r, "STX")  # the head is a shape
        _lobe(c, hx, 101, 3, "STD")                        # the face inside it
        c.set(hx + face * 3, 98, "STX")                    # ears
        c.set(hx - face * 2, 98, "STX")
        c.rect(sx + 3, 113, sx + 8, 116, "STD")            # forepaws out front
        c.col(sx + 4, 113, 116, "STX")
        c.col(sx + 7, 113, 116, "STX")
        c.set(hx + face, 101, "FIL")                       # eyes catching the
        c.set(hx - face * 2, 101, "FIL")                   # light off the bowls
        c.set(hx + face, 103, "STX")                       # and an open mouth

    # --- the lamp columns, and the fire on them -----------------------------
    top, widths = TEMPLE_FLAME[phase % len(TEMPLE_FLAME)]
    for lx in (34, 92):
        c.rect(lx - 3, 92, lx + 4, 116, "RF")              # a painted shaft, so
        c.col(lx - 3, 92, 116, "RFL")                      # it is not one more
        c.col(lx + 4, 92, 116, "RFD")                      # grey thing on grey
        c.rect(lx - 4, 90, lx + 5, 93, "RFD")
        c.rect(lx - 5, 84, lx + 6, 90, "MT")               # the bowl
        c.row(lx - 5, lx + 6, 84, "MTL")
        c.row(lx - 5, lx + 6, 90, "MTD")
        c.rect(lx - 4, 82, lx + 5, 84, "FID")              # coals banked in it
        _blob(c, top, widths, "FI", cx=lx)
    _shade(c, "FI", "FIL", "FID")
    for lx in (34, 92):                                    # the hot heart
        c.rect(lx - 1, 79, lx + 2, 83, "FIL")

    c.rect(0, VAST_BASE_Y + 1, VAST_FRAME - 1, VAST_FRAME - 1, None)
    c.outline()

    # Dust, after the outline: a translucent mote with a hard line round it is
    # a pebble in the air, not dust. Same reason the campfire's spark is last.
    for i, (dx, dy) in enumerate(TEMPLE_DUST):
        t = (phase + i) % 4
        x, y = dx + t, dy - t * 3
        c.set(x, y, "DUL" if (i + phase) % 2 else "DU")
        if t % 2:
            c.set(x + 1, y, "DUL")
    return c


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


def dry_bush(phase=0):
    """Thorn: a few long stems and a lot of gaps. Twenty short ones packed
    round a root came out as a solid green lump - what says dead scrub is the
    sand showing through it."""
    c = Canvas(FRAME, FRAME)
    for i in range(9):
        a = -math.pi / 2 + (i - 4) * 0.34
        x, y = 16.0, float(BASE_Y - 1)
        for k in range(6 + (i % 3)):
            x += math.cos(a) * 1.5
            y += math.sin(a) * 1.15 + 0.12        # straightening as it rises
            c.set(round(x), round(y), "SC" if k % 3 else "SCD")
            if k == 3:                            # one side shoot each
                c.set(round(x + math.cos(a + 1.1) * 2),
                      round(y + math.sin(a + 1.1) * 2), "SCD")
        c.set(round(x), round(y), "SCL")          # a lit tip
    c.row(14, 18, BASE_Y, "SCD")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def bones(phase=0, variant=0):
    """Three lots of bones: a horned skull sunk in a drift, a scattered pile,
    and a ribcage still standing out of the ground.

    What actually reads as bone at 32px is a skull - a pale mass with two black
    sockets in it - which is why two of the three are built round one. The
    third is the exception and had to earn it: a ribcage drawn side on with a
    solid spine and ribs hanging off it is a comb, so this one buries the spine
    and draws the ribs as separate arcs with daylight between them, which is
    what a ribcage looks like from outside anyway.
    """
    c = Canvas(FRAME, FRAME)
    if variant == 1:                                  # scattered, on bare ground
        # Was prop.bone_pile: what a den leaves behind, gnawed at the ends and
        # left where it dropped. No drift under it - on a cave floor a mound of
        # pale sand reads as something carried in from outside.
        for x0, x1, y in ((5, 16, BASE_Y - 1), (9, 21, BASE_Y - 4), (14, 25, BASE_Y)):
            c.row(x0, x1, y, "CL")
            c.row(x0, x1, y + 1, "CLD")
            for x in (x0, x1):                        # knuckled ends
                c.set(x, y - 1, "CL")
                c.set(x, y + 1, "CLD")
        _lobe(c, 20, BASE_Y - 9, 4, "CL")
        c.rect(15, BASE_Y - 10, 19, BASE_Y - 7, "CL")  # the muzzle
        _shade(c, "CL", "SLL", "CLD")
        for x in (17, 21):
            c.set(x, BASE_Y - 10, "OL")               # sockets
            c.set(x, BASE_Y - 9, "OL")
        return c.outline()
    if variant == 2:                                  # a ribcage, still standing
        rnd = scatter(0x5C19)
        for x in range(7, 25):                        # the ground it is sunk in
            h = round(2 * math.sin((x - 7) / 17 * math.pi))
            if h <= 0:
                continue
            c.col(x, BASE_Y - h, BASE_Y, "DND")
            c.set(x, BASE_Y - h, "DNX")
        # The animal is on its side and the spine is under the mound, so the
        # ribs rise out of the ground and lean in towards each other - a dome
        # of separate arcs with daylight between them. Curved all the same way
        # and run together at the foot they came out as a palm frond.
        for bx, rise in ((8, 11), (12, 14), (16, 15), (20, 13), (24, 10)):
            for k in range(rise):
                y = 26 - k
                t = k / max(1, rise - 1)
                x = bx + round((15.5 - bx) * t * t * 0.55)
                c.set(x, y, "CL")
                c.set(x + 1, y, "CLD")
            c.set(bx + round((15.5 - bx) * 0.55), 26 - rise, "CL")
        for x, y in ((11, 26), (17, 27), (22, 26)):
            c.set(x, y, "CLD")                        # vertebrae showing through
        c.set(9 + rnd(2), 27, "CL")
        c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
        return c.outline()
    # A mound, not a slab: drawn as a rectangle the drift read as a plank the
    # skull had been laid on.
    rnd = scatter(0x3B21)
    for x in range(3, 29):
        h = round(3 * math.sin((x - 3) / 25 * math.pi)) + (rnd(2) if 5 < x < 26 else 0)
        if h <= 0:
            continue
        c.col(x, BASE_Y - h, BASE_Y, "DND")
        c.set(x, BASE_Y - h, "DNX")

    # One long bone beside it rather than a ribcage. Three ribs drawn as arcs
    # at this size ran together into a white crate, and a rib on its own says
    # nothing: a femur with a knob at each end is the one bone that is legible
    # lying down.
    for k in range(8):
        c.set(21 + k, 24 - k // 3, "CL")
        c.set(21 + k, 25 - k // 3, "CLD")
    for kx, ky in ((20, 24), (20, 25), (21, 23), (28, 21), (28, 22), (27, 20)):
        c.set(kx, ky, "CL")

    # The horns first, so the skull is drawn over where they meet it and they
    # never look stuck on the front of its face.
    for side, hx in ((-1, 10), (1, 19)):
        for k in range(7):
            x = hx + side * k
            y = 17 - (k * 3) // 4 - (k > 4)
            c.set(x, y, "HN")
            c.set(x, y + 1, "HNS")

    c.rect(10, 16, 19, 22, "CL")                  # the cranium
    c.row(11, 18, 15, "CL")
    c.row(12, 17, 15, "CLD")                      # a brow over the sockets
    c.rect(13, 22, 16, 26, "CL")                  # and the long face under it
    c.row(13, 16, 26, "CLD")
    c.col(14, 23, 25, "CLD")                      # the nasal groove
    c.rect(11, 18, 12, 20, "OL")                  # two sockets, which is the
    c.rect(17, 18, 18, 20, "OL")                  # whole of why it reads
    c.set(10, 16, "CLD")
    c.set(19, 16, "CLD")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def cairn(variant=0):
    """Five cairns: the plain taper, a tall one, a squat one, one that has
    settled out of true, and one that has come down altogether.

    A cairn is stones somebody stacked, so the variants are five states of that
    stack rather than five sizes of the same pile - the toppled one especially,
    which is the only way this prop can say that time passed."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # tall and narrow, five courses
        courses = ((25, 6), (21, 5), (17, 4), (13, 3), (9, 2))
        step = 3
    elif variant == 2:                   # squat, three heavy courses
        courses = ((24, 10), (19, 8), (15, 5))
        step = 4
    elif variant == 3:                   # settled out of true
        # The offsets alternate and stay small. Climbing in one direction - the
        # first thing tried here - is not a leaning cairn, it is a staircase,
        # and at four courses there is no reading it any other way.
        for (y0, w, off) in ((24, 8, 0), (20, 6, 2), (16, 4, -1), (13, 2, 1)):
            c.rect(15 - w + off, y0, 16 + w + off, y0 + 4, "ST")
            c.row(15 - w + off, 16 + w + off, y0, "STL")
            c.row(15 - w + off, 16 + w + off, y0 + 4, "STD")
        c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
        _shade(c, "ST", "STL", "STD")
        return c.outline()
    elif variant == 4:                   # come down: a low heap and its strays
        _mass(c, [(14, 26, 5), (19, 27, 4), (9, 28, 3)], BASE_Y)
        _form(c, "ST", 0x9C, tilt=0.15)
        _rim(c, ROCK, "STL", "STD")
        for x, y, w in ((24, 27, 2), (5, 26, 1)):     # stones that rolled clear
            c.rect(x - w, y, x + w, y + 1, "ST")
            c.row(x - w, x + w, y, "STL")
            c.row(x - w, x + w, y + 1, "STD")
        return c.outline()
    else:                                # stacked, tapering up
        courses = ((24, 8), (20, 6), (16, 4), (13, 2))
        step = 4
    for y0, w in courses:
        c.rect(15 - w, y0, 16 + w, y0 + step, "ST")
        c.row(15 - w, 16 + w, y0, "STL")
        c.row(15 - w, 16 + w, y0 + step, "STD")
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


def crate(variant=0):
    """Five crates: nailed shut, a tall chest, one open with straw coming out
    of it, two stacked, and one that has been staved in.

    A box is the hardest thing here to vary, because a box is a rectangle and
    a slightly different rectangle is the same rectangle. So four of the five
    break the outline somewhere - a lid standing off it, a second box on top,
    a corner gone - and only the first is the plain square it started as."""
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # a tall chest, banded rather than braced
        _plank(c, 11, 10, 20, BASE_Y)
        c.col(20, 10, BASE_Y, "WDD")
        c.col(11, 10, BASE_Y, "WDD")
        c.rect(11, 10, 20, 11, "WDL")    # the lid
        for y in (16, 22, 27):           # iron bands down its height
            c.row(11, 20, y, "MT")
            c.set(11, y, "MTL")
        c.set(20, 19, "MTD")
    elif variant == 2:                   # open, with the packing coming out
        _plank(c, 9, 18, 22, BASE_Y)
        c.col(22, 18, BASE_Y, "WDD")
        c.col(9, 18, BASE_Y, "WDD")
        c.rect(10, 18, 21, 20, "WDD")    # down into it, past the near boards
        for i in range(12):
            c.set(10 + i, 22 + i, "WDD")
        # Straw over the edge, which is what says open rather than lidless -
        # an empty box with its top row darkened is just a box in shadow.
        for x, y, h in ((11, 16, 3), (14, 15, 4), (18, 16, 3), (21, 17, 2)):
            for i in range(h):
                c.set(x + (i % 2), y + i, "TH")
            c.set(x, y, "THL")
        # The lid leans against the near side. Drawn as a level board above
        # the box it floated, because nothing in the picture said what was
        # holding it up - so it slants, and its foot is on the ground.
        for i in range(11):
            y = 28 - i
            x = 23 + i // 3
            c.set(x, y, "WDL")
            c.set(x + 1, y, "WD")
            c.set(x + 2, y, "WDD")
    elif variant == 3:                   # two, the smaller one on top
        _plank(c, 8, 20, 23, BASE_Y)
        c.col(23, 20, BASE_Y, "WDD")
        c.col(8, 20, BASE_Y, "WDD")
        c.rect(8, 20, 23, 21, "WDL")
        for i in range(8):
            c.set(9 + i, 22 + i, "WDD")
            c.set(22 - i, 22 + i, "WDD")
        _plank(c, 12, 11, 22, 19)        # the second one, set back and over
        c.col(22, 11, 19, "WDD")
        c.col(12, 11, 19, "WDD")
        c.rect(12, 11, 22, 12, "WDL")
        for i in range(7):
            c.set(13 + i, 13 + i, "WDD")
    elif variant == 4:                   # staved in, one corner gone
        _plank(c, 9, 16, 22, BASE_Y)
        c.col(22, 16, BASE_Y, "WDD")
        c.col(9, 16, BASE_Y, "WDD")
        c.rect(9, 16, 22, 17, "WDL")
        for i in range(12):
            c.set(21 - i, 18 + i, "WDD")
        # A hole through the face, ragged, with the corners of the box left
        # standing - a clean diagonal off one corner is a wedge, not damage.
        for y, x0, x1 in ((20, 13, 18), (21, 12, 19), (22, 11, 19),
                          (23, 12, 20), (24, 13, 19), (25, 14, 18)):
            c.row(x0, x1, y, None)
        c.set(11, 21, None)
        c.set(20, 22, None)
        c.set(15, 19, None)
        for x, y in ((12, 19), (17, 19), (19, 21), (13, 26), (18, 26), (11, 23)):
            c.set(x, y, "WDD")           # splinters left round the break
        for x, y in ((14, 20), (16, 25)):
            c.set(x, y, "WDL")           # and the lit edge of a snapped board
        for x, y in ((24, 27), (25, 27), (26, 28), (27, 28)):
            c.set(x, y, "WDD")           # a board that ended up on the floor
        c.set(24, 26, "WDL")
    else:                                # nailed shut, braced across the face
        _plank(c, 9, 16, 22, BASE_Y)
        c.col(22, 16, BASE_Y, "WDD")
        c.rect(9, 16, 22, 17, "WDL")     # lid
        for i in range(12):              # the diagonal brace across the face
            c.set(10 + i, 18 + i, "WDD")
            c.set(21 - i, 18 + i, "WDD")
        c.col(9, 16, BASE_Y, "WDD")
    return c.outline()


def barrel(variant=0):
    """Three barrels, all of them standing on end: headed up, open, and a tall
    cask with a tap in it.

    They differ in proportion and in state rather than in dimensions, because a
    barrel one pixel wider is the first barrel drawn twice. A fourth was drawn
    lying on its side, which is the easiest way to make a barrel look like a
    different object and the wrong one here - a barrel on the floor reads as
    something knocked over, and stock standing in a store room should not.
    """
    c = Canvas(FRAME, FRAME)
    if variant == 1:                     # the head off, and you can see in
        _blob(c, 12, (5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4, 3), "WD")
        _shade(c, "WD", "WDL", "WDD")
        for y in (17, 22, 26):
            for x in range(8, 24):
                if c.get(x, y) is not None:
                    c.set(x, y, "MT")    # three hoops, as on the closed one
        for y, x0, x1 in ((12, 11, 19), (13, 10, 20), (14, 11, 19)):
            c.row(x0, x1, y, "WDD")      # the far wall inside it, in shadow -
        c.row(10, 20, 12, "MTD")         # dark enough to read as a hole and
        c.set(9, 13, "MTL")              # not as a lid
        c.set(21, 13, "MTD")
    elif variant == 2:                   # a tall cask, and it has been tapped
        _blob(c, 9, (3, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 3, 3, 2), "WD")
        _shade(c, "WD", "WDL", "WDD")
        for y in (13, 18, 23, 27):       # four hoops, because it is taller
            for x in range(9, 22):
                if c.get(x, y) is not None:
                    c.set(x, y, "MT")
        c.row(12, 18, 9, "WDL")          # the head, seen from above
        c.set(19, 13, "MTL")             # light on a hoop, where there is one
        # The tap is the whole of what tells this one from the first at a
        # glance, so it breaks the silhouette instead of being painted on the
        # face. Drawn down the middle of the near side first, it was three
        # dark pixels inside the outline and read as a knot in the wood.
        c.set(10, 22, "MTD")
        c.set(9, 22, "MT")
        c.set(8, 22, "MT")
        c.set(8, 23, "MTL")              # the spout turning down
        c.set(8, 24, "MTD")
        c.set(9, 21, "MTL")              # and the key on top of it
    else:                                # headed up, the plain one
        _blob(c, 14, (4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4), "WD")
        _shade(c, "WD", "WDL", "WDD")
        for y in (17, 22, 26):
            for x in range(9, 23):
                if c.get(x, y) is not None:
                    c.set(x, y, "MT")    # iron hoops
        c.row(12, 19, 14, "WDL")         # the lid, seen from above
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


def cave_shroom():
    """A cluster of pale fungus on the burrow floor - three caps, no two the
    same height.

    prop.mushroom is a red forest toadstool and reads as woodland at a glance.
    Down here the cap is salt rather than roof-red: the only thing a hole in
    the ground gives you to see by is whatever is paler than the dirt."""
    c = Canvas(FRAME, FRAME)
    for cx, top, w in ((10, 22, 3), (17, 17, 4), (24, 24, 2)):
        c.rect(cx - 1, top + 3, cx, BASE_Y, "CLD")           # stem
        c.col(cx - 1, top + 3, BASE_Y, "CL")
        _blob(c, top, (w - 2, w, w), "SL", cx=cx - 1)        # cap
        c.row(cx - 1 - w, cx + w, top + 3, "SLD")            # gills under the rim
    _shade(c, "SL", "SLL", "SLD")
    return c.outline()


# ---------------------------------------------------------------- wetland ---
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
    "prop.tombstone": tombstone,
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
    "prop.dry_bush": dry_bush,
    "prop.bones": bones,
    "prop.roots": roots,
    "prop.cave_shroom": cave_shroom,
}
PROP_ORDER = list(PROPS)

# How many drawings of a prop exist. Unlike a tile's variants - picked by where
# the cell is, so a map looks the same every time it loads - a prop's is rolled
# once when it is placed and written into the map, because a prop is a thing
# somebody put there and which one it is deserves to be part of the map rather
# than a function of the square it stands on. Variant 0 keeps the plain id as
# its sprite key, so everything that only wants a picture of the thing is
# unaffected.
#
# A variant earns its frame by being a different object at a glance. A barrel
# one pixel wider is the first barrel drawn twice, and a tree one shade
# greener is the first tree drawn twice - see tree_oak, whose five are five
# histories rather than five sizes.
VARIANTS = {
    "prop.barrel": 3,
    "prop.bones": 3,
    "prop.crate": 5,
    "prop.tree_oak": 5,
    "prop.tree_pine": 5,
    "prop.tree_dead": 5,
    "prop.cairn": 5,
    "prop.bush": 5,
    "prop.boulder": 5,
    "prop.rock": 5,
}

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
ANIMATED_HUGE = {}                  # nothing this size moves yet
ANIMATED_VAST = {
    "prop.temple": (4, 180),        # two fires and the dust off the steps
    "prop.crystal_gate": (4, 150),  # the crystal turning, and two more fires
}
# One table per frame size, because that is how the sheets are built - but the
# lookup is over all of them, so nothing has to know which class a prop is in
# to ask whether it moves.
ANIMATED_ALL = (ANIMATED, ANIMATED_HUGE, ANIMATED_VAST)


def prop_frames(pid, table=None, variant=0):
    """Every frame of one variant of a prop, first frame first. One frame for
    most of them, and variant 0 for most of them."""
    fns = table if table is not None else PROPS
    n = next((t[pid][0] for t in ANIMATED_ALL if pid in t), 1)
    kw = {"variant": variant} if pid in VARIANTS else {}
    if n == 1:
        return [fns[pid](**kw)]
    return [fns[pid](phase=p, **kw) for p in range(n)]


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


HUGE_PROPS = {
    "prop.shed": shed,
    "prop.burrow_tree": burrow_tree,
}
HUGE_PROP_ORDER = list(HUGE_PROPS)

# The flame on each of the gate's columns, one entry per phase: where it
# starts and its half-width at each row down. The same idea as TEMPLE_FLAME -
# shapes that lean, rather than noise, which is what stops a four-frame fire
# reading as static - and every one of them ends at y 30, in the bowl.
GATE_FLAME = (
    (16, (0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 3, 3, 2, 2, 2)),
    (14, (0, 0, 1, 2, 2, 3, 4, 4, 4, 4, 3, 3, 3, 2, 2, 1, 1)),
    (18, (0, 1, 2, 2, 3, 3, 4, 4, 4, 3, 2, 2, 2)),
    (15, (0, 1, 1, 2, 3, 3, 4, 4, 4, 4, 3, 2, 2, 2, 1, 1)),
)
# The crystals turning inside the ring: (radius, how many, which way round).
# Each one advances a *quarter of its own spacing* per frame, so after four
# frames every shard has arrived exactly where its neighbour started and the
# loop closes with nothing jumping. Turning each a quarter of the way round
# the ring instead - the obvious thing to do with four frames - is four
# separate pictures shown in sequence, and reads as a stutter.
# (radius, how many, which way round, how big each shard is)
GATE_RINGS = ((14, 6, 1, 3), (7, 4, -1, 2))


def crystal_gate(phase=0):
    """A gate four tiles by four: a stone ring on a plinth between two burning
    columns, with crystal turning inside it.

    The colour idea is the whole of it, and it has only three parts: the stone
    is grey and unpainted, the light in the ring is blue-white, and the one
    warm thing anywhere near it is the fire on the columns - which is also why
    the thing standing guard in front of it is red. Nothing here borrows a
    biome's palette, on purpose: a gateway painted in the local greens is a
    wall somebody built.

    **The ring needs an edge of its own.** It is drawn over the columns, and
    the first version gave it the same grey as the shafts behind it - so the
    whole upper half came out as one grey slab with a blue hole in it and
    there was no ring at all. A band a shade lighter with a near-black rim on
    both its edges is what separates it, the same trick the giant rig uses for
    an arm lying over a belly: the outline pass only wraps the silhouette, so
    anything drawn *inside* one has to bring its own."""
    c = Canvas(VAST_FRAME, VAST_FRAME)
    cx, cy = 63, 66

    # --- the plinth, two steps of it ---------------------------------------
    for x0, x1, y0, y1 in ((30, 97, 114, VAST_BASE_Y), (35, 92, 106, 114)):
        c.rect(x0, y0, x1, y1, "ST")
        c.row(x0, x1, y0, "STL")                       # lit along each tread
        c.row(x0, x1, y1, "STD")
        for x in range(x0 + 5, x1 - 2, 11):            # the joints between slabs
            c.col(x, y0 + 1, y1, "STD")

    # --- the two columns ----------------------------------------------------
    for lx in (39, 88):
        c.rect(lx - 6, 44, lx + 6, 108, "ST")          # the shaft
        c.col(lx - 6, 44, 108, "STL")                  # lit down one side and
        c.col(lx + 6, 44, 108, "STD")                  # shaded down the other
        for y0, y1 in ((38, 44), (102, 108)):          # capital and base
            c.rect(lx - 9, y0, lx + 9, y1, "ST")
            c.row(lx - 9, lx + 9, y0, "STL")
            c.row(lx - 9, lx + 9, y1, "STD")
        _rune(c, lx, 99)                               # the only stretch of
        _rune(c, lx, 41)                               # shaft the ring leaves

    # The ring stands on a block between the columns. Without it the gap under
    # the ring and between the two bases reads as a doorway of its own, which
    # is one doorway too many on a thing that is already a way through.
    c.rect(45, 92, 82, 108, "ST")
    c.row(45, 82, 92, "STL")
    c.rect(48, 96, 79, 108, "STD")
    c.rect(50, 98, 77, 108, "ST")

    # --- the ring -----------------------------------------------------------
    for y in range(cy - 28, cy + 29):
        for x in range(cx - 28, cx + 29):
            d = math.hypot(x - cx, y - cy)
            if d > 26.6 or d < 18.4:
                continue
            if d > 25.4 or d < 19.6:
                c.set(x, y, "STX")                     # the rim, both edges
            elif x - cx + (y - cy) < -6:
                c.set(x, y, "STL")                     # lit round the top left
            elif x - cx + (y - cy) > 8:
                c.set(x, y, "STD")
            else:
                c.set(x, y, "ST")
    for i in range(8):                                 # runes carved round it
        a = i * math.pi / 4 + math.pi / 8
        _rune(c, round(cx + math.cos(a) * 22.5), round(cy + math.sin(a) * 22.5))

    # --- what is inside it --------------------------------------------------
    # Deep in the middle and lighter at the rim, because the far side is a long
    # way off. Built up from the mid blue rather than the dark one: started
    # from the deep end it comes out a hole rather than a light.
    for y in range(cy - 20, cy + 21):
        for x in range(cx - 20, cx + 21):
            d = math.hypot(x - cx, y - cy)
            if d > 19.4:
                continue
            c.set(x, y, "CYD" if d > 13 else "CYX")
    for i in range(2):                                 # currents turning in it
        a0 = i * 3.1 + phase * 0.22
        for k in range(16):
            a = a0 + k * 0.17
            r = 5 + k * 0.85
            c.set(round(cx + math.cos(a) * r), round(cy + math.sin(a) * r), "CY")

    for radius, count, way, size in GATE_RINGS:
        step = 2 * math.pi / count
        for i in range(count):
            a = i * step + way * phase * step / 4
            _shard(c, round(cx + math.cos(a) * radius),
                   round(cy + math.sin(a) * radius), size)

    # --- the bowls, and the fire in them ------------------------------------
    top, widths = GATE_FLAME[phase % len(GATE_FLAME)]
    for lx in (39, 88):
        c.rect(lx - 7, 30, lx + 7, 38, "MT")           # the bowl
        c.row(lx - 7, lx + 7, 30, "MTL")
        c.row(lx - 7, lx + 7, 38, "MTD")
        c.rect(lx - 6, 28, lx + 6, 30, "FID")          # coals banked in it
        _blob(c, top, widths, "FI", cx=lx - 1)
    _shade(c, "FI", "FIL", "FID")
    for lx in (39, 88):
        c.rect(lx - 2, top + 6, lx + 1, 29, "FIL")     # the hot heart

    c.rect(0, VAST_BASE_Y + 1, VAST_FRAME - 1, VAST_FRAME - 1, None)
    return c.outline()



VAST_PROPS = {
    "prop.temple": temple,
    "prop.crystal_gate": crystal_gate,
}
VAST_PROP_ORDER = list(VAST_PROPS)

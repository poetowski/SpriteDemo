"""Environment props.

Two frame sizes, one rule. Small props share the actor's 32x32 frame and ground
line, so a single anchor rule and a single depth-sort rule cover both:
everything is positioned by the point its base sits on, and drawn in order of
that point's y. Structures too big for that frame use a 48x48 frame with the
same convention - three tiles wide, base on the anchor row - which is why the
engine needs no special case for them.

How much of the world a prop *blocks* is not decided here: that is the
"footprint" field in content/props/, a list of tile offsets from the anchor
tile. Art and collision are authored separately on purpose, so a bush can have
a canopy wider than the tile it stands on.
"""

from gen.palette import Canvas, scatter

# Props are still drawn at the old scale and blown up in tools/build.py on the
# way into the atlas. They are next in line to be redrawn natively at 64x64;
# until then these stay pinned here rather than following actor.FRAME.
FRAME = 32
GROUND_Y = 29

BASE_Y = GROUND_Y - 1          # last opaque row, matching the actor's boots

# Structures: three tiles wide, same anchor convention as the 32x32 frame.
BIG_FRAME = 48
BIG_GROUND_Y = 45
BIG_ANCHOR = (24, BIG_GROUND_Y)
BIG_BASE_Y = BIG_GROUND_Y - 1


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


def _plank(c, x0, y0, x1, y1, key="WD", light="WDL", dark="WDD"):
    """A board with a lit top edge and a shaded underside."""
    c.rect(x0, y0, x1, y1, key)
    c.row(x0, x1, y0, light)
    if y1 > y0:
        c.row(x0, x1, y1, dark)


def _post(c, x, y0, y1, key="WD", dark="WDD"):
    c.col(x, y0, y1, key)
    c.col(x + 1, y0, y1, dark)


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


def lamp_post():
    c = Canvas(FRAME, FRAME)
    _post(c, 15, 10, BASE_Y)
    c.rect(13, BASE_Y - 1, 18, BASE_Y, "STD")   # a stone base
    c.rect(12, 4, 19, 5, "MTD")          # the cap
    c.rect(12, 10, 19, 11, "MTD")        # and the tray
    c.col(12, 5, 10, "MTD")
    c.col(19, 5, 10, "MTD")
    c.rect(13, 6, 18, 9, "FIL")          # the lit pane
    c.rect(14, 7, 17, 9, "FI")
    c.set(15, 8, "FID")
    c.set(16, 8, "FID")
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


def beehive():
    c = Canvas(FRAME, FRAME)
    _blob(c, 13, (3, 5, 6, 7, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9), "TH")
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    _shade(c, "TH", "THL", "THD")
    for y in (16, 20, 24):               # the coils of the skep
        c.row(7, 24, y, "THD")
    c.rect(14, 25, 17, BASE_Y, "OL")     # the entrance
    return c.outline()


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


def campfire():
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
    _blob(c, 12, (1, 2, 3, 4, 4, 5, 5, 5, 5, 4, 3), "FI")
    _shade(c, "FI", "FIL", "FID")
    c.rect(14, 18, 17, 23, "FIL")        # the hot heart of it
    c.set(15, 15, "FIL")
    for x, y in ((4, 23), (24, 23), (8, 26), (14, 27), (20, 26)):
        stone(x, y)                      # and these in front of it
    c.rect(0, BASE_Y + 1, FRAME - 1, FRAME - 1, None)
    return c.outline()


def trough():
    c = Canvas(FRAME, FRAME)
    c.rect(4, 19, 27, BASE_Y, "WD")
    c.rect(6, 20, 25, 23, "WA")          # water, sitting below the rim
    c.row(6, 25, 20, "WAL")
    c.row(8, 14, 22, "WAD")
    c.row(4, 27, 19, "WDL")
    c.row(4, 27, BASE_Y, "WDD")
    c.col(27, 19, BASE_Y, "WDD")
    for x in (7, 24):                    # end bands
        c.col(x, 24, BASE_Y, "WDD")
    return c.outline()


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


def windmill():
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
    for i in range(11):                                 # four sails, as a saltire
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x = 23 + dx * (i + 2)
            y = 12 + dy * (i + 2)
            c.set(x, y, "WD")
            c.set(x + dx, y, "TH")
            c.set(x, y + dy, "TH")
    c.rect(22, 11, 25, 14, "WDD")                       # the hub
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
}
PROP_ORDER = list(PROPS)

BIG_PROPS = {
    "prop.house": house,
    "prop.barn": barn,
    "prop.tower": tower,
    "prop.windmill": windmill,
}
BIG_PROP_ORDER = list(BIG_PROPS)




# ============================================================================
# Redrawn at the 2x standard.
#
# Drawn on a 64x64 canvas with the base on NEW_BASE, the same ground line the
# actors stand on. Everything in PROPS not listed in NATIVE is still at the old
# 32x32 drawing scale and is blown up in build_props() on the way out, so
# NATIVE is the honest record of what has actually been redrawn.
# ============================================================================
NEW = 64
NEW_BASE = 57                  # last opaque row, matching the actor's boots


def _form(c, key, light, dark):
    """Give a flat mass volume.

    _shade only recolours the 1px rim, which leaves a big shape reading as a
    flat sticker. This judges each pixel by where it sits inside the shape's
    own bounds and lights the upper-left of the mass, shading the lower-right,
    so a canopy or a boulder turns instead of just being outlined.
    """
    pts = [(x, y) for y in range(c.h) for x in range(c.w) if c.px[y][x] == key]
    if not pts:
        return
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    w = max(1, max(xs) - min(xs))
    h = max(1, max(ys) - min(ys))
    for x, y in pts:
        d = (x - min(xs)) / w + (y - min(ys)) / h
        if d < 0.62:
            c.set(x, y, light)
        elif d > 1.34:
            c.set(x, y, dark)


def _leaves(c, x0, y0, x1, y1, seed, key, light, dark):
    """Clumps of foliage over a mass: pairs of pixels, fixed per prop so the
    canopy never shimmers between frames."""
    rnd = scatter(seed)
    for _ in range(90):
        x = x0 + rnd(max(1, x1 - x0 - 1))
        y = y0 + rnd(max(1, y1 - y0 - 1))
        if c.get(x, y) != key:
            continue
        k = light if rnd(2) else dark
        c.set(x, y, k)
        c.set(x + 1, y, k)


def bush64():
    c = Canvas(NEW, NEW)
    _blob(c, 33, (5, 9, 12, 15, 17, 18, 19, 19, 20, 20, 20, 20, 19, 19,
                  18, 17, 15, 13, 10), "BU", cx=31)
    _form(c, "BU", "BUL", "BUD")                  # volume first
    _leaves(c, 12, 34, 50, 51, 0x81B3, "BU", "BUL", "BUD")   # then the texture
    _shade(c, "BU", "BUL", "BUD")                 # then the rim
    for x in (18, 25, 33, 41):                    # notch the crown into leaves
        c.set(x, 33, None)
        c.set(x + 1, 33, None)
    return c.outline()


def tree_oak64():
    c = Canvas(NEW, NEW)
    c.rect(27, 18, 36, NEW_BASE, "WD")            # runs up behind the crown
    c.row(24, 39, 54, "WD")                       # roots flare into the ground
    c.row(21, 42, NEW_BASE, "WD")
    for y in range(34, 54, 5):                    # bark
        c.rect(30, y, 31, y + 2, "WDD")
    _shade(c, "WD", "WDL", "WDD")
    _blob(c, 3, (4, 8, 12, 15, 18, 20, 21, 22, 23, 23, 24, 24, 23, 23,
                 22, 21, 19, 17, 14, 10, 6), "BU", cx=31)
    _form(c, "BU", "BUL", "BUD")
    _leaves(c, 9, 4, 54, 23, 0x4F21, "BU", "BUL", "BUD")
    _shade(c, "BU", "BUL", "BUD")
    for x, y in ((17, 14), (46, 17), (25, 5), (39, 21), (30, 10)):
        c.set(x, y, None)                         # sky through the leaves
        c.set(x + 1, y, None)
    return c.outline()


def tree_pine64():
    c = Canvas(NEW, NEW)
    c.rect(29, 44, 34, NEW_BASE, "WD")
    _shade(c, "WD", "WDL", "WDD")
    for y0, y1, w0, w1 in ((4, 20, 2, 11), (16, 34, 4, 16), (30, 48, 6, 21)):
        _taper(c, y0, y1, w0, w1, "BU", cx=31)    # three overlapping skirts
    _form(c, "BU", "BUL", "BUD")
    _leaves(c, 12, 6, 50, 47, 0x2D77, "BU", "BUL", "BUD")
    for y, w in ((20, 11), (34, 16), (48, 21)):   # a dark line under each skirt
        c.row(31 - w, 32 + w, y, "BUD")
    _shade(c, "BU", "BUL", "BUD")
    return c.outline()


def tree_dead64():
    c = Canvas(NEW, NEW)
    c.rect(27, 14, 36, NEW_BASE, "WDD")
    c.row(24, 39, 54, "WDD")
    c.row(21, 42, NEW_BASE, "WDD")
    for i in range(12):                           # a branch reaching left
        c.rect(26 - i, 28 - i, 27 - i, 29 - i, "WDD")
    for i in range(9):                            # and one right, higher up
        c.rect(36 + i, 24 - i, 37 + i, 25 - i, "WDD")
    for i in range(6):
        c.rect(36 + i, 40 - i, 37 + i, 41 - i, "WDD")
    _shade(c, "WDD", "WD", "WDD")
    for y in range(18, 54, 7):                    # splits in the dead wood
        c.col(31, y, y + 2, "WDD")
    return c.outline()


def stump64():
    c = Canvas(NEW, NEW)
    c.rect(20, 40, 43, NEW_BASE, "WD")            # the bole
    for x in range(22, 44, 5):                    # bark grooves down the sides
        c.col(x, 44, 56, "WDD")
    _shade(c, "WD", "WDL", "WDD")
    _blob(c, 34, (8, 10, 11, 12, 12, 11, 10, 8), "WDL", cx=31)   # the cut face
    _blob(c, 36, (6, 7, 8, 8, 7, 5), "WD", cx=31)                # growth rings
    _blob(c, 38, (3, 4, 4, 3), "WDL", cx=31)
    c.set(31, 39, "WDD")
    c.set(32, 40, "WDD")
    return c.outline()


def log64():
    c = Canvas(NEW, NEW)
    c.rect(9, 41, 55, 55, "WD")                   # the barrel of the trunk
    c.row(11, 53, 40, "WD")                       # rounded top and bottom
    c.row(11, 53, 56, "WD")
    c.row(10, 54, 41, "WDL")                      # lit along the upper curve
    c.row(11, 53, 40, "WDL")
    c.row(10, 54, 55, "WDD")                      # shaded underneath
    c.row(11, 53, 56, "WDD")
    for x in range(22, 50, 9):                    # bark grain follows the curve
        c.rect(x, 46, x + 4, 47, "WDD")
        c.rect(x + 3, 50, x + 7, 51, "WDD")
    _blob(c, 40, (8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8), "WDD",
          cx=13)                                  # the sawn end, facing us
    _blob(c, 42, (6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6), "WDL", cx=13)
    _blob(c, 45, (3, 3, 3, 3, 3, 3, 3), "WD", cx=13)
    c.set(13, 48, "WDD")
    return c.outline()


def boulder64():
    c = Canvas(NEW, NEW)
    _blob(c, 22, (7, 13, 17, 20, 21, 22, 22, 23, 23, 23, 23, 23, 23,
                  22, 22, 21, 20, 18, 16), "ST", cx=31)
    _form(c, "ST", "STL", "STD")
    _shade(c, "ST", "STL", "STD")
    for x, y in ((30, 33), (34, 38), (25, 42), (41, 31)):
        c.rect(x, y, x + 3, y + 1, "STD")         # cracks, inside the mass
    for x, y in ((22, 30), (27, 27), (36, 29)):
        c.rect(x, y, x + 4, y + 1, "STL")         # a lit facet up top
    return c.outline()


def rock64():
    c = Canvas(NEW, NEW)
    _blob(c, 38, (5, 9, 12, 13, 14, 14, 14, 13, 12, 10), "ST", cx=31)
    _form(c, "ST", "STL", "STD")
    _shade(c, "ST", "STL", "STD")
    c.rect(29, 44, 32, 45, "STD")                 # one crack
    c.rect(25, 41, 28, 42, "STL")
    return c.outline()


def cairn64():
    c = Canvas(NEW, NEW)
    for y0, widths in ((46, (14, 16, 16, 15, 13)),
                       (37, (10, 12, 12, 11, 9)),
                       (29, (7, 9, 9, 8, 6)),
                       (22, (4, 6, 6, 5, 4))):
        _blob(c, y0, widths, "ST", cx=31)         # rounded stones, not blocks
    _form(c, "ST", "STL", "STD")
    _shade(c, "ST", "STL", "STD")
    return c.outline()


def mushroom64():
    c = Canvas(NEW, NEW)
    c.rect(28, 38, 35, NEW_BASE, "CL")            # stem
    c.row(25, 38, NEW_BASE, "CL")                 # flaring into the leaf litter
    c.row(24, 39, 56, "CL")
    _shade(c, "CL", "CL", "CLD")
    _blob(c, 28, (4, 8, 11, 13, 14, 14, 14, 13, 11, 8), "RF", cx=31)
    _form(c, "RF", "RFL", "RFD")
    _shade(c, "RF", "RFL", "RFD")
    for x, y in ((22, 34), (39, 32), (31, 29), (26, 31), (36, 36)):
        c.rect(x, y, x + 2, y + 1, "CL")          # spots
    c.row(21, 42, 38, "CLD")                      # the gills under the cap
    return c.outline()


NATIVE = {
    "prop.bush": bush64,
    "prop.tree_oak": tree_oak64,
    "prop.tree_pine": tree_pine64,
    "prop.tree_dead": tree_dead64,
    "prop.stump": stump64,
    "prop.log": log64,
    "prop.boulder": boulder64,
    "prop.rock": rock64,
    "prop.cairn": cairn64,
    "prop.mushroom": mushroom64,
}


# --- the village set, redrawn at the 2x standard -----------------------------
def _staves(c, x0, y0, x1, y1, key, dark, light):
    """Vertical boards with a lit and a shaded edge - barrels, crates, doors."""
    c.rect(x0, y0, x1, y1, key)
    for x in range(x0, x1 + 1, 5):
        c.col(x, y0, y1, dark)
    c.col(x0, y0, y1, light)
    c.row(x0, x1, y0, light)
    c.row(x0, x1, y1, dark)


def barrel64():
    c = Canvas(NEW, NEW)
    for i, y in enumerate(range(24, NEW_BASE + 1)):
        bulge = 2 if 8 < i < 26 else (1 if 4 < i < 30 else 0)
        c.row(18 - bulge, 45 + bulge, y, "WD")
    for x in range(19, 46, 5):
        c.col(x, 24, NEW_BASE, "WDD")           # staves
    _form(c, "WD", "WDL", "WDD")
    for y in (30, 46):                          # iron hoops
        c.rect(16, y, 47, y + 2, "MT")
        c.row(16, 47, y, "MTL")
        c.row(16, 47, y + 2, "MTD")
    c.rect(20, 22, 43, 25, "WDL")               # the lid, seen at an angle
    c.row(20, 43, 22, "WD")
    return c.outline()


def crate64():
    c = Canvas(NEW, NEW)
    _staves(c, 14, 26, 49, NEW_BASE, "WD", "WDD", "WDL")
    c.rect(14, 26, 49, 29, "WDL")               # a lid board
    c.rect(14, 52, 49, 55, "WDD")               # and one at the foot
    for i in range(24):                         # a diagonal brace
        c.set(16 + i, 54 - i, "WDL")
        c.set(17 + i, 54 - i, "WDD")
    return c.outline()


def chest64():
    c = Canvas(NEW, NEW)
    _staves(c, 13, 34, 50, NEW_BASE, "WD", "WDD", "WDL")
    _blob(c, 22, (17, 18, 18, 19, 19, 19, 19, 19, 19, 19, 19, 19), "WD", cx=31)
    _form(c, "WD", "WDL", "WDD")
    for x in (20, 43):                          # iron bands over the lid
        c.rect(x, 22, x + 3, NEW_BASE, "MT")
        c.col(x, 22, NEW_BASE, "MTL")
        c.col(x + 3, 22, NEW_BASE, "MTD")
    c.rect(28, 32, 35, 42, "MT")                # the lock plate
    c.row(28, 35, 32, "MTL")
    c.rect(30, 36, 33, 39, "MTD")
    return c.outline()


def sack64():
    c = Canvas(NEW, NEW)
    # Taller than it is wide, or it reads as a cushion. Folds are painted only
    # where cloth already is - drawing them by coordinate put lines below the
    # body and gave it legs.
    _blob(c, 24, (8, 12, 15, 17, 18, 19, 19, 20, 20, 20, 20, 20, 20,
                  19, 19, 18, 17, 16, 14, 12, 9), "CLD", cx=31)
    _form(c, "CLD", "CL", "CLD")
    for x in (24, 31, 38):
        for y in range(24, NEW_BASE):
            if c.get(x, y) is not None:
                c.set(x, y, "CLD")
    for i, y in enumerate(range(14, 25)):       # the neck, pinched in
        w = 7 - i // 2
        c.row(31 - w, 32 + w, y, "CLD")
        c.set(31 - w, y, "CL")
    c.rect(22, 21, 41, 25, "WDD")               # the cord tying it shut
    c.row(22, 41, 21, "WD")
    c.rect(28, 10, 35, 15, "CL")                # the gathered top above it
    return c.outline()

def table64():
    c = Canvas(NEW, NEW)
    _plank(c, 8, 28, 55, 34)                    # the top
    c.row(8, 55, 28, "WDL")
    for x in (12, 48):                          # legs
        _post(c, x, 35, NEW_BASE)
        c.rect(x, 35, x + 3, NEW_BASE, "WD")
        c.col(x + 3, 35, NEW_BASE, "WDD")
    c.rect(14, 44, 49, 47, "WD")                # a stretcher between them
    c.row(14, 49, 44, "WDL")
    return c.outline()


def bench64():
    c = Canvas(NEW, NEW)
    _plank(c, 10, 38, 53, 43)
    for x in (14, 46):
        c.rect(x, 44, x + 3, NEW_BASE, "WD")
        c.col(x + 3, 44, NEW_BASE, "WDD")
    c.rect(12, 24, 51, 28, "WD")                # a back rail
    c.row(12, 51, 24, "WDL")
    for x in (14, 46):
        c.rect(x, 25, x + 3, 40, "WD")
        c.col(x + 3, 25, 40, "WDD")
    return c.outline()


def anvil64():
    c = Canvas(NEW, NEW)
    c.rect(18, 44, 45, NEW_BASE, "WD")          # the block it stands on
    for x in range(20, 46, 6):
        c.col(x, 44, NEW_BASE, "WDD")
    _form(c, "WD", "WDL", "WDD")
    c.rect(16, 28, 47, 35, "MT")                # the face
    c.rect(22, 35, 41, 40, "MT")                # the waist
    c.rect(18, 40, 45, 44, "MT")                # and the foot
    c.rect(6, 29, 17, 33, "MT")                 # the horn
    c.rect(6, 30, 12, 32, "MT")
    _form(c, "MT", "MTL", "MTD")
    c.row(16, 47, 28, "MTL")
    return c.outline()


def woodpile64():
    c = Canvas(NEW, NEW)
    for row, y in enumerate((46, 36, 26)):
        n = 5 - row
        for i in range(n):
            x = 8 + row * 6 + i * 10
            c.rect(x, y, x + 9, y + 9, "WD")
            _blob(c, y + 1, (3, 4, 4, 4, 4, 3), "WDD", cx=x + 4)
            _blob(c, y + 3, (2, 2, 2), "WDL", cx=x + 4)
            c.set(x + 4, y + 4, "WDD")
    _shade(c, "WD", "WDL", "WDD")
    c.rect(0, NEW_BASE + 1, NEW - 1, NEW - 1, None)
    return c.outline()


def campfire64():
    c = Canvas(NEW, NEW)
    # Three logs crossing, drawn first so the flame sits down among them.
    for x0, y0, x1, y1 in ((8, 47, 38, 53), (26, 49, 56, 55), (12, 52, 44, 57)):
        c.rect(x0, y0, x1, y1, "WD")
        c.row(x0, x1, y0, "WDL")
        c.row(x0, x1, y1, "WDD")
        c.rect(x0, y0, x0 + 4, y1, "WDD")       # a sawn end on each
    # A tongue of flame: narrow at the tip, widest at the base, with licks.
    for i, y in enumerate(range(16, 50)):
        w = 1 + i * 11 // 34
        c.row(31 - w, 32 + w, y, "FI")
    for i, y in enumerate(range(26, 50)):
        w = i * 7 // 24
        c.row(30 - w, 31 + w, y, "FIL")
    for i, y in enumerate(range(38, 50)):
        w = i * 4 // 12
        c.row(30 - w, 31 + w, y, "EW")          # the white heart of it
    for x, y, h in ((22, 30, 8), (41, 34, 7), (25, 40, 6)):
        for k in range(h):                      # licks curling off the sides
            c.set(x + k // 3, y + k, "FI")
            c.set(x + k // 3 + 1, y + k, "FID")
    for x, y in ((16, 24), (46, 20), (20, 14), (44, 30)):
        c.rect(x, y, x + 1, y + 2, "FID")       # embers drifting up
    return c.outline()

def beehive64():
    c = Canvas(NEW, NEW)
    for i, (y, w) in enumerate(((20, 9), (27, 13), (35, 17), (44, 20),
                                (51, 21))):
        c.rect(31 - w, y, 32 + w, min(y + 8, NEW_BASE), "TH")
        c.row(31 - w, 32 + w, y, "THL")         # coils of straw, each lit
        c.row(31 - w, 32 + w, min(y + 7, NEW_BASE), "THD")
    _form(c, "TH", "THL", "THD")
    c.rect(26, 50, 37, NEW_BASE, "WDD")         # the entrance
    c.rect(28, 53, 35, NEW_BASE, "OL")
    for x, y in ((14, 30), (48, 40), (20, 18)):
        c.rect(x, y, x + 2, y + 1, "FL")        # bees
    return c.outline()


def flower_pot64():
    c = Canvas(NEW, NEW)
    for i, y in enumerate(range(36, NEW_BASE + 1)):
        taper = i // 4
        c.row(20 + taper, 43 - taper, y, "RF")
    c.rect(17, 32, 46, 38, "RF")                # the rim
    _form(c, "RF", "RFL", "RFD")
    c.row(17, 46, 32, "RFL")
    c.rect(22, 34, 41, 37, "WDD")               # soil
    c.rect(29, 18, 32, 36, "BU")                # stem
    c.rect(33, 24, 40, 28, "BU")                # leaves
    c.rect(21, 28, 28, 32, "BU")
    _blob(c, 10, (3, 5, 6, 6, 5, 3), "FL", cx=30)
    c.rect(28, 13, 31, 16, "RF")
    return c.outline()


def lamp_post64():
    c = Canvas(NEW, NEW)
    c.rect(28, 26, 35, NEW_BASE, "MT")          # the post
    c.col(28, 26, NEW_BASE, "MTL")
    c.col(35, 26, NEW_BASE, "MTD")
    c.rect(24, 54, 39, NEW_BASE, "MTD")         # its foot
    c.rect(22, 12, 41, 28, "MT")                # the lantern housing
    c.rect(25, 15, 38, 25, "FL")                # the light inside
    c.rect(27, 17, 36, 23, "EW")
    c.row(22, 41, 12, "MTL")
    c.rect(19, 6, 44, 12, "MTD")                # a little cap over it
    c.row(19, 44, 6, "MT")
    c.rect(30, 2, 33, 6, "MTD")
    return c.outline()


def scarecrow64():
    c = Canvas(NEW, NEW)
    c.rect(29, 26, 34, NEW_BASE, "WD")          # the post
    c.col(34, 26, NEW_BASE, "WDD")
    c.rect(10, 30, 53, 35, "WD")                # the crossbar
    c.row(10, 53, 30, "WDL")
    c.row(10, 53, 35, "WDD")
    # Straw stuffed into a sack, sitting on the post - taller than wide, with
    # the neck of it going down into the collar.
    _blob(c, 4, (3, 5, 7, 8, 8, 9, 9, 9, 8, 8, 7, 6, 5), "TH", cx=31)
    c.rect(28, 17, 35, 26, "TH")
    _form(c, "TH", "THL", "THD")
    c.rect(18, 24, 45, 50, "CL")                # the shirt, over the crossbar
    c.rect(18, 24, 45, 29, "CLD")               # its collar
    for x in range(21, 46, 6):
        c.col(x, 30, 49, "CLD")
    c.row(18, 45, 50, "CLD")
    c.rect(11, 36, 21, 44, "TH")                # straw out of the cuffs
    c.rect(42, 36, 52, 44, "TH")
    c.rect(25, 50, 38, NEW_BASE, "TH")          # and out of the hem
    c.rect(26, 8, 28, 11, "OL")                 # two stitched eyes
    c.rect(35, 8, 37, 11, "OL")
    for x in range(28, 36, 3):
        c.set(x, 14, "OL")                      # a stitched mouth
    return c.outline()

def sign64():
    c = Canvas(NEW, NEW)
    c.rect(29, 36, 34, NEW_BASE, "WD")
    c.col(34, 36, NEW_BASE, "WDD")
    _plank(c, 14, 20, 49, 38)
    c.rect(14, 20, 49, 23, "WDL")
    c.rect(14, 35, 49, 38, "WDD")
    for y in (26, 30):                          # carved lines, not readable text
        c.rect(19, y, 44, y + 2, "WDD")
    return c.outline()


def signpost64():
    c = Canvas(NEW, NEW)
    c.rect(29, 12, 34, NEW_BASE, "WD")
    c.col(34, 12, NEW_BASE, "WDD")
    c.rect(26, 8, 37, 13, "WDL")                # a cap on the post
    for y, x0, x1, point in ((18, 4, 33, "left"), (32, 30, 59, "right")):
        c.rect(x0, y, x1, y + 9, "WD")          # two arms, pointing opposite
        c.row(x0, x1, y, "WDL")
        c.row(x0, x1, y + 9, "WDD")
        for i in range(5):                      # the pointed end
            if point == "left":
                c.col(x0 - 1 + i, y + i, y + 9 - i, "WD")
                c.set(x0 - 1 + i, y + i, "WDL")
            else:
                c.col(x1 + 1 - i, y + i, y + 9 - i, "WD")
                c.set(x1 + 1 - i, y + i, "WDL")
        c.rect(x0 + 6, y + 3, x1 - 6, y + 5, "WDD")
    return c.outline()


def statue64():
    c = Canvas(NEW, NEW)
    c.rect(12, 50, 51, NEW_BASE, "ST")          # the plinth
    c.row(12, 51, 50, "STL")
    c.row(12, 51, NEW_BASE, "STD")
    c.rect(16, 44, 47, 51, "ST")
    c.row(16, 47, 44, "STL")

    for i, y in enumerate(range(26, 45)):       # a robe flaring to the base
        w = 8 + i // 2
        c.row(31 - w, 32 + w, y, "ST")
    c.rect(24, 20, 39, 28, "ST")                # shoulders
    _blob(c, 8, (4, 6, 7, 7, 7, 6, 5), "ST", cx=31)          # head
    c.rect(29, 15, 34, 21, "ST")                # neck
    for x0 in (17, 41):                         # arms, with a gap either side
        c.rect(x0, 23, x0 + 5, 40, "ST")
    _form(c, "ST", "STL", "STD")
    _shade(c, "ST", "STL", "STD")
    c.rect(26, 11, 28, 13, "STD")               # features, worn almost away
    c.rect(35, 11, 37, 13, "STD")
    c.row(29, 34, 28, "STD")                    # a fold at the collar
    for y in range(32, 44, 4):                  # and down the robe
        c.rect(26, y, 37, y + 1, "STD")
    return c.outline()

def tombstone64():
    c = Canvas(NEW, NEW)
    c.rect(16, 24, 47, NEW_BASE, "ST")
    _blob(c, 14, (9, 12, 14, 15, 15, 16), "ST", cx=31)      # the rounded top
    c.rect(12, 52, 51, NEW_BASE, "ST")                      # a base in the turf
    _form(c, "ST", "STL", "STD")
    _shade(c, "ST", "STL", "STD")
    for y in (30, 36, 42):                      # weathered inscription
        c.rect(22, y, 41, y + 2, "STD")
    c.rect(26, 46, 37, 48, "STD")
    return c.outline()


def trough64():
    c = Canvas(NEW, NEW)
    c.rect(6, 30, 57, NEW_BASE, "WD")
    c.rect(10, 34, 53, 50, "WA")                # water in it
    c.rect(10, 34, 53, 37, "WAL")
    for x in range(14, 52, 9):
        c.rect(x, 40, x + 4, 41, "WAL")         # ripples
    c.rect(6, 30, 57, 34, "WDL")                # the rim
    c.rect(6, 50, 57, NEW_BASE, "WD")
    c.row(6, 57, NEW_BASE, "WDD")
    for x in (9, 52):                           # end boards
        c.rect(x - 3, 30, x + 3, NEW_BASE, "WD")
        c.col(x + 3, 30, NEW_BASE, "WDD")
    return c.outline()


def well64():
    c = Canvas(NEW, NEW)
    c.rect(12, 36, 51, NEW_BASE, "ST")          # the ring wall
    for y in (42, 50):
        c.row(12, 51, y, "STD")
    for x in range(16, 52, 10):
        c.col(x, 36, 42, "STD")
        c.col(x + 5, 42, 50, "STD")
    _form(c, "ST", "STL", "STD")
    c.rect(18, 36, 45, 44, "OL")                # the dark of the shaft
    c.rect(20, 38, 43, 43, "OL")
    for x in (14, 47):                          # posts holding the roof
        c.rect(x, 12, x + 4, 38, "WD")
        c.col(x + 4, 12, 38, "WDD")
    _taper(c, 2, 14, 6, 24, "TH", cx=31)        # a thatched roof
    _form(c, "TH", "THL", "THD")
    c.rect(26, 16, 37, 22, "WD")                # the winch drum
    c.col(37, 16, 22, "WDD")
    c.col(31, 23, 36, "MTD")                    # rope down into the dark
    return c.outline()


NATIVE.update({
    "prop.barrel": barrel64,
    "prop.crate": crate64,
    "prop.chest": chest64,
    "prop.sack": sack64,
    "prop.table": table64,
    "prop.bench": bench64,
    "prop.anvil": anvil64,
    "prop.woodpile": woodpile64,
    "prop.campfire": campfire64,
    "prop.beehive": beehive64,
    "prop.flower_pot": flower_pot64,
    "prop.lamp_post": lamp_post64,
    "prop.scarecrow": scarecrow64,
    "prop.sign": sign64,
    "prop.signpost": signpost64,
    "prop.statue": statue64,
    "prop.tombstone": tombstone64,
    "prop.trough": trough64,
    "prop.well": well64,
})


# --- the structures, redrawn at 96x96 ---------------------------------------
BIG_NEW = 96
BIG_NEW_BASE = 89


def _wall(c, x0, y0, x1, y1, key, light, dark):
    c.rect(x0, y0, x1, y1, key)
    c.row(x0, x1, y0, light)
    c.row(x0, x1, y1, dark)
    c.col(x0, y0, y1, light)
    c.col(x1, y0, y1, dark)


def _roof(c, y0, y1, w0, w1, cx, key, light, dark):
    span = max(1, y1 - y0)
    for y in range(y0, y1 + 1):
        w = w0 + (w1 - w0) * (y - y0) // span
        c.row(cx - w, cx + w, y, key)
        c.set(cx - w, y, light)
        c.set(cx + w, y, dark)
    c.row(cx - w1, cx + w1, y1, dark)


def house64():
    c = Canvas(BIG_NEW, BIG_NEW)
    _wall(c, 14, 44, 81, BIG_NEW_BASE, "CL", "CL", "CLD")
    for x in range(18, 82, 12):                 # timbers in the plaster
        c.col(x, 46, BIG_NEW_BASE - 1, "WDD")
    c.rect(14, 44, 81, 47, "WDD")
    _roof(c, 12, 46, 6, 44, 47, "RF", "RFL", "RFD")
    for y in range(14, 46, 4):                  # courses of tile
        c.row(47 - (y - 12), 47 + (y - 12), y, "RFD")
    c.rect(40, 62, 55, BIG_NEW_BASE, "WD")      # the door
    c.rect(42, 64, 53, BIG_NEW_BASE, "WDD")
    c.set(51, 76, "MTL")
    for x in (22, 66):                          # two shuttered windows
        c.rect(x, 56, x + 13, 70, "WDD")
        c.rect(x + 2, 58, x + 11, 68, "FL")
        c.col(x + 6, 58, 68, "WDD")
        c.row(x + 2, x + 11, 63, "WDD")
    c.rect(60, 4, 71, 22, "ST")                 # a chimney
    _form(c, "ST", "STL", "STD")
    return c.outline()


def barn64():
    c = Canvas(BIG_NEW, BIG_NEW)
    _wall(c, 8, 38, 87, BIG_NEW_BASE, "RF", "RFL", "RFD")
    for x in range(12, 88, 9):                  # board and batten
        c.col(x, 40, BIG_NEW_BASE - 1, "RFD")
    _roof(c, 8, 40, 8, 46, 47, "WD", "WDL", "WDD")
    for y in range(10, 40, 5):
        c.row(47 - (y - 6), 47 + (y - 6), y, "WDD")
    c.rect(30, 52, 65, BIG_NEW_BASE, "WD")      # the big doors
    c.col(47, 52, BIG_NEW_BASE, "WDD")
    c.rect(30, 52, 65, 55, "WDD")
    for i in range(18):                         # cross braces on each leaf
        c.set(32 + i, 86 - i, "WDD")
        c.set(63 - i, 86 - i, "WDD")
    c.rect(41, 22, 54, 34, "WDD")               # the hay door up in the gable
    c.rect(43, 24, 52, 32, "OL")
    return c.outline()


def tower64():
    c = Canvas(BIG_NEW, BIG_NEW)
    _wall(c, 26, 22, 69, BIG_NEW_BASE, "ST", "STL", "STD")
    for i, y in enumerate(range(24, BIG_NEW_BASE, 8)):   # courses, staggered
        c.row(26, 69, y, "STD")
        for x in range(30 + (i % 2) * 10, 70, 20):
            c.col(x, y + 1, y + 7, "STD")
    _form(c, "ST", "STL", "STD")
    c.rect(20, 14, 75, 24, "ST")                # the parapet oversails
    for x in range(20, 76, 11):                 # battlements
        c.rect(x, 6, x + 6, 15, "ST")
    _shade(c, "ST", "STL", "STD")
    for y in (40, 58):                          # arrow slits
        c.rect(45, y, 50, y + 12, "OL")
        c.rect(46, y + 1, 49, y + 11, "OL")
    c.rect(38, 72, 57, BIG_NEW_BASE, "WD")      # a studded door
    c.rect(40, 74, 55, BIG_NEW_BASE, "WDD")
    for x in (43, 52):
        c.col(x, 76, 86, "MTD")
    return c.outline()


def windmill64():
    c = Canvas(BIG_NEW, BIG_NEW)
    for i, y in enumerate(range(36, BIG_NEW_BASE + 1)):  # a tapering tower
        t = (BIG_NEW_BASE - y) // 6
        c.row(26 + t, 69 - t, y, "CL")
    for y in range(40, BIG_NEW_BASE, 7):
        c.row(27, 68, y, "CLD")
    _form(c, "CL", "CL", "CLD")
    _roof(c, 22, 40, 10, 24, 47, "WD", "WDL", "WDD")     # the cap
    c.rect(40, 70, 55, BIG_NEW_BASE, "WD")               # door
    c.rect(42, 72, 53, BIG_NEW_BASE, "WDD")
    c.rect(43, 50, 52, 60, "WDD")                        # a window
    c.rect(45, 52, 50, 58, "FL")
    for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):  # four sails
        for i in range(4, 34):
            c.set(47 + dx * i, 30 + dy * i, "WD")
            c.set(47 + dx * i + dx, 30 + dy * i, "WDD")
            if i % 4:                                    # the lattice of slats
                c.set(47 + dx * i - dy * 3, 30 + dy * i + dx * 3, "WDL")
                c.set(47 + dx * i - dy * 5, 30 + dy * i + dx * 5, "WDL")
    c.rect(43, 26, 51, 34, "WDD")                        # the hub
    c.rect(45, 28, 49, 32, "MTD")
    return c.outline()


BIG_NATIVE = {
    "prop.house": house64,
    "prop.barn": barn64,
    "prop.tower": tower64,
    "prop.windmill": windmill64,
}


def build_props():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index.

    Every prop is drawn at the 2x standard; NATIVE is the whole set. PROPS
    below still holds the original 32x32 drawings, kept as the reference the
    redraws were made from rather than as anything the build ships.
    """
    return [(pid, NATIVE[pid]()) for pid in PROP_ORDER]


def build_big_props():
    """The structures, same contract, their own atlas - redrawn at 96x96."""
    return [(pid, BIG_NATIVE[pid]()) for pid in BIG_PROP_ORDER]

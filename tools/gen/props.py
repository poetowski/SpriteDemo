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

from gen.actor import FRAME, GROUND_Y
from gen.palette import Canvas

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


def build_props():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(pid, PROPS[pid]()) for pid in PROP_ORDER]


def build_big_props():
    """The 48x48 structures, same contract, their own atlas."""
    return [(pid, BIG_PROPS[pid]()) for pid in BIG_PROP_ORDER]

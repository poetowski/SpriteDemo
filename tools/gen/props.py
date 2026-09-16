"""Environment props.

Props share the actor's 32x32 frame and ground line, so one anchor rule and one
depth-sort rule cover both: everything is positioned by the point its base sits
on, and drawn in order of that point's y.
"""

from gen.actor import FRAME, GROUND_Y
from gen.palette import Canvas

BASE_Y = GROUND_Y - 1          # last opaque row, matching the actor's boots


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


PROPS = {"prop.bush": bush, "prop.rock": rock, "prop.sign": sign}
PROP_ORDER = list(PROPS)


def build_props():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(pid, PROPS[pid]()) for pid in PROP_ORDER]

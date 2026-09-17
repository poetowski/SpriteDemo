"""32x32 item icons, drawn at the 2x standard.

One drawing serves two places: lying on the ground in the world, where it is
placed by its anchor like any other sprite, and in the bag, where the HUD cuts
the same cell out of the same atlas. What an item *is* - whether it stacks,
whether it goes in the weapon hand - lives in content/items/, not here; this
module only draws pixels.

At 32 there is room for a blade to have an edge and a fuller, a coin to carry a
face, and a fish to have a fin - none of which fitted in 16.
"""

from gen.palette import Canvas

SIZE = 32
ANCHOR = (16, 28)              # bottom centre: an item lies on its tile


def _disc(c, cx, cy, r, key):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r // 2:
                c.set(x, y, key)


def _diag(c, x0, y0, n, key, dx=1, dy=-1, w=1):
    """A line from (x0, y0), n pixels, up and to the right by default."""
    for i in range(n):
        for k in range(w):
            c.set(x0 + dx * i + k, y0 + dy * i, key)


def _blade(c, x0, y0, n, dx, dy, edge, core, back):
    """A three-wide blade: a lit edge, a fuller down the middle, a dark back."""
    px, py = -dy, dx
    for i in range(n):
        x, y = x0 + dx * i, y0 + dy * i
        c.set(x, y, core)
        c.set(x + px, y + py, edge)
        c.set(x - px, y - py, back)


# --------------------------------------------------------------- materials --
def apple():
    c = Canvas(SIZE, SIZE)
    _disc(c, 15, 18, 8, "RF")
    _disc(c, 12, 15, 3, "RFL")                  # the shine
    c.row(11, 19, 26, "RFD")
    c.row(13, 17, 27, "RFD")
    c.rect(15, 7, 16, 11, "WDD")                # stem
    c.rect(17, 5, 23, 9, "BU")                  # one leaf
    c.rect(19, 6, 22, 7, "BUL")
    return c.outline()


def berries():
    c = Canvas(SIZE, SIZE)
    for x, y in ((10, 19), (19, 17), (14, 25), (23, 24), (16, 13)):
        _disc(c, x, y, 4, "WAD")
        _disc(c, x - 1, y - 1, 2, "WA")
        c.rect(x - 2, y - 3, x - 1, y - 2, "WAL")
    c.rect(5, 6, 13, 8, "BU")                   # the sprig they came on
    c.rect(12, 8, 14, 13, "BU")
    c.rect(6, 4, 10, 6, "BUL")
    return c.outline()


def wheat():
    c = Canvas(SIZE, SIZE)
    for x in (9, 15, 21):                       # three stalks
        c.rect(x, 10, x + 1, 27, "TH")
        c.col(x + 1, 10, 27, "THD")
        for y in range(3, 11, 2):               # grains up the ear
            c.rect(x - 2, y, x + 3, y + 1, "THL")
            c.set(x - 2, y + 1, "THD")
            c.set(x + 3, y + 1, "THD")
    c.rect(6, 20, 25, 22, "WDD")                # tied into a sheaf
    c.row(6, 25, 20, "WD")
    return c.outline()


def wool():
    c = Canvas(SIZE, SIZE)
    _disc(c, 15, 18, 10, "AB")
    for x, y in ((8, 13), (18, 11), (22, 19), (11, 24), (19, 25), (14, 17)):
        _disc(c, x, y, 3, "ABL")                # curls catching the light
    for x, y in ((10, 22), (21, 23), (16, 26)):
        _disc(c, x, y, 2, "ABS")
    return c.outline()


def fish():
    c = Canvas(SIZE, SIZE)
    _disc(c, 15, 17, 8, "WA")
    c.rect(7, 15, 23, 19, "WA")
    c.rect(9, 12, 20, 15, "WAL")                # the lit flank
    c.rect(8, 20, 21, 22, "WAD")
    c.rect(24, 12, 27, 23, "WAD")               # tail
    c.rect(25, 14, 27, 21, "WA")
    c.rect(12, 8, 18, 12, "WAD")                # dorsal fin
    c.rect(9, 15, 11, 17, "EW")                 # eye
    c.rect(10, 16, 11, 17, "EY")
    c.rect(13, 20, 17, 23, "WAD")               # belly fin
    return c.outline()


def honey():
    c = Canvas(SIZE, SIZE)
    c.rect(8, 11, 23, 27, "CL")                 # the pot
    c.rect(8, 11, 23, 14, "CLD")
    c.rect(10, 15, 21, 26, "FL")                # honey inside
    c.rect(11, 16, 15, 20, "THL")               # a highlight on the glass
    c.rect(7, 8, 24, 11, "WD")                  # a cloth tied over the top
    c.row(7, 24, 8, "WDL")
    c.rect(12, 5, 19, 8, "CL")
    return c.outline()


def ore():
    c = Canvas(SIZE, SIZE)
    _disc(c, 15, 19, 9, "ST")
    c.rect(7, 16, 24, 26, "ST")
    for y, x0, x1 in ((12, 12, 20), (14, 9, 22), (16, 8, 23)):
        c.row(x0, x1, y, "STL")                 # the lit top facet
    c.rect(8, 24, 23, 26, "STD")
    for x, y in ((11, 18), (17, 16), (20, 22), (13, 23)):
        c.rect(x, y, x + 2, y + 1, "MTL")       # veins of metal
        c.set(x + 3, y + 1, "MT")
    return c.outline()


def firewood():
    c = Canvas(SIZE, SIZE)
    for i, (x, y) in enumerate(((6, 12), (16, 10), (11, 21))):
        c.rect(x, y, x + 12, y + 6, "WD")
        c.row(x, x + 12, y, "WDL")
        c.row(x, x + 12, y + 6, "WDD")
        c.rect(x, y, x + 3, y + 6, "WDD")       # the sawn end
        c.rect(x + 1, y + 1, x + 2, y + 5, "WDL")
    c.rect(13, 8, 16, 27, "CLD")                # the cord binding them
    c.col(14, 8, 27, "CL")
    return c.outline()


def coin():
    c = Canvas(SIZE, SIZE)
    _disc(c, 15, 17, 9, "THD")
    _disc(c, 15, 17, 8, "FL")
    _disc(c, 12, 14, 3, "THL")                  # the shine
    c.rect(12, 13, 19, 21, "THD")               # a face stamped on it
    c.rect(13, 14, 18, 20, "FL")
    c.rect(14, 16, 17, 18, "THD")
    return c.outline()


def key():
    c = Canvas(SIZE, SIZE)
    _disc(c, 11, 10, 6, "MT")
    _disc(c, 11, 10, 3, None)                   # the bow, with its eye
    _disc(c, 11, 10, 3, "MTD")
    _disc(c, 11, 10, 2, None)
    c.rect(10, 15, 13, 27, "MT")                # the shaft
    c.col(10, 15, 27, "MTL")
    c.col(13, 15, 27, "MTD")
    c.rect(14, 22, 20, 24, "MT")                # wards
    c.rect(14, 25, 18, 27, "MT")
    c.row(14, 20, 22, "MTL")
    return c.outline()


def flower():
    c = Canvas(SIZE, SIZE)
    c.rect(15, 14, 16, 28, "BU")                # stem
    c.col(16, 14, 28, "BUD")
    c.rect(18, 18, 24, 21, "BU")                # leaves
    c.rect(7, 22, 14, 25, "BU")
    c.rect(19, 19, 23, 20, "BUL")
    for dx, dy in ((0, -7), (-6, -3), (6, -3), (-4, 3), (4, 3)):
        _disc(c, 15 + dx, 10 + dy + 2, 3, "FL")   # five petals
    _disc(c, 15, 12, 3, "RF")                   # and a heart
    c.set(14, 11, "RFL")
    return c.outline()


# ----------------------------------------------------------------- weapons --
def sword():
    c = Canvas(SIZE, SIZE)
    _blade(c, 16, 22, 17, 0, -1, "MTL", "MT", "MTD")
    c.rect(14, 3, 18, 5, "MTL")                 # the point
    c.rect(11, 22, 21, 24, "MT")                # crossguard
    c.row(11, 21, 22, "MTL")
    c.row(11, 21, 24, "MTD")
    c.rect(15, 25, 17, 29, "WDD")               # grip
    c.col(15, 25, 29, "WD")
    c.rect(14, 29, 18, 31, "MTD")               # pommel
    return c.outline()


def axe():
    c = Canvas(SIZE, SIZE)
    c.rect(14, 6, 17, 30, "WD")                 # haft
    c.col(14, 6, 30, "WDL")
    c.col(17, 6, 30, "WDD")
    for y, x0, x1 in ((6, 18, 24), (7, 18, 26), (8, 18, 27), (9, 18, 27),
                      (10, 18, 27), (11, 18, 26), (12, 18, 24)):
        c.row(x0, x1, y, "MT")                  # the bit, hung on one side
    c.rect(24, 7, 27, 11, "MTL")                # its edge
    c.rect(18, 5, 21, 13, "MTD")                # and the eye round the haft
    return c.outline()


def spear():
    c = Canvas(SIZE, SIZE)
    c.rect(15, 9, 17, 31, "WD")                 # shaft
    c.col(15, 9, 31, "WDL")
    c.col(17, 9, 31, "WDD")
    c.rect(14, 8, 18, 10, "WDD")                # the collar
    for y, w in ((7, 3), (6, 3), (5, 2), (4, 2), (3, 1), (2, 1), (1, 0)):
        c.row(16 - w, 16 + w, y, "MT")          # a leaf-shaped head
    c.col(16, 1, 7, "MTL")
    c.col(18, 4, 7, "MTD")
    return c.outline()


def mail():
    c = Canvas(SIZE, SIZE)
    c.rect(7, 9, 24, 27, "MT")                  # the body of the shirt
    c.rect(3, 10, 8, 19, "MT")                  # sleeves
    c.rect(23, 10, 28, 19, "MT")
    for y in range(10, 27):                     # rings, as a fine mesh
        for x in range(3, 29):
            if c.get(x, y) == "MT" and (x + y) % 2:
                c.set(x, y, "MTD")
    c.row(7, 24, 9, "MTL")                      # a lit collar
    c.rect(12, 7, 19, 10, "MTD")                # the neck opening
    c.rect(13, 8, 18, 10, None)
    c.row(3, 28, 10, "MTL")                     # and lit shoulders
    c.row(7, 24, 27, "MTD")                     # the skirt
    return c.outline()


ITEMS = {
    "item.apple": apple,
    "item.berries": berries,
    "item.wheat": wheat,
    "item.wool": wool,
    "item.fish": fish,
    "item.honey": honey,
    "item.ore": ore,
    "item.firewood": firewood,
    "item.coin": coin,
    "item.key": key,
    "item.flower": flower,
    "item.sword": sword,
    "item.axe": axe,
    "item.spear": spear,
    "item.mail": mail,
}
ITEM_ORDER = list(ITEMS)


def build_items():
    """[(id, Canvas), ...] in a stable order - the order is the atlas index."""
    return [(iid, ITEMS[iid]()) for iid in ITEM_ORDER]

"""16x16 item icons.

One drawing serves two places: lying on the ground in the world, where it is
placed by its anchor like any other sprite, and in the inventory strip, where
the HUD cuts the same cell out of the same atlas. What an item *is* - whether
it stacks, whether it goes in the weapon hand - lives in content/items/, not
here; this module only draws pixels.
"""

from gen.palette import Canvas

SIZE = 16
ANCHOR = (8, 14)               # bottom centre: an item lies on its tile


def _disc(c, cx, cy, r, key):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r // 2:
                c.set(x, y, key)


def _diag(c, x0, y0, n, key, dx=1, dy=-1):
    """A 1px line from (x0, y0), n pixels, up and to the right by default."""
    for i in range(n):
        c.set(x0 + dx * i, y0 + dy * i, key)


# --------------------------------------------------------------- materials --
def apple():
    c = Canvas(SIZE, SIZE)
    _disc(c, 7, 9, 4, "RF")
    c.rect(5, 6, 6, 7, "RFL")                   # the shine
    c.row(6, 9, 13, "RFD")
    c.col(8, 3, 5, "WDD")                       # stem
    c.row(9, 11, 4, "BU")                       # one leaf
    c.set(10, 3, "BU")
    return c.outline()


def berries():
    c = Canvas(SIZE, SIZE)
    for x, y in ((5, 9), (9, 8), (7, 12), (11, 11)):
        _disc(c, x, y, 2, "WAD")
        c.set(x - 1, y - 1, "WAL")
    c.row(3, 6, 4, "BU")                        # a sprig they came on
    c.col(6, 4, 6, "BU")
    return c.outline()


def wheat():
    c = Canvas(SIZE, SIZE)
    for x in (5, 8, 11):                        # three stalks
        c.col(x, 5, 13, "TH")
        c.rect(x - 1, 2, x + 1, 5, "THL")       # the ear
        c.set(x, 3, "THD")
    c.rect(4, 10, 12, 11, "WDD")                # tied into a sheaf
    return c.outline()


def honey():
    c = Canvas(SIZE, SIZE)
    c.rect(4, 5, 11, 13, "FI")                  # the jar
    c.rect(5, 6, 6, 11, "FIL")                  # amber catching the light
    c.rect(3, 3, 12, 5, "CL")                   # lid
    c.row(3, 12, 5, "CLD")
    c.rect(6, 9, 9, 11, "CL")                   # a label
    return c.outline()


def wool():
    c = Canvas(SIZE, SIZE)
    _disc(c, 7, 8, 4, "AB")
    for x, y in ((4, 6), (10, 5), (11, 10), (5, 11)):
        _disc(c, x, y, 2, "AB")                 # lumpy, as a fleece is
    c.rect(5, 5, 7, 6, "ABL")
    c.row(6, 10, 12, "ABS")
    c.set(11, 11, "ABS")
    return c.outline()


def ore():
    c = Canvas(SIZE, SIZE)
    for y, x0, x1 in ((5, 6, 9), (6, 5, 11), (7, 4, 12), (8, 3, 12), (9, 3, 12),
                      (10, 4, 12), (11, 4, 11), (12, 5, 10)):
        c.row(x0, x1, y, "ST")
    c.rect(5, 6, 7, 7, "STL")
    c.row(5, 10, 12, "STD")
    for x, y in ((8, 8), (6, 10), (10, 9), (9, 11)):
        c.set(x, y, "FI")                       # the vein that makes it ore
    return c.outline()


def firewood():
    c = Canvas(SIZE, SIZE)
    for i, (x0, y0) in enumerate(((2, 6), (2, 9), (2, 12))):
        c.rect(x0, y0, x0 + 11, y0 + 2, "WD")
        c.row(x0, x0 + 11, y0, "WDL")
        c.rect(x0, y0, x0 + 1, y0 + 2, "WDD")   # sawn ends
        c.rect(x0 + 10, y0, x0 + 11, y0 + 2, "WDL")
    c.col(7, 5, 14, "MTD")                      # the cord round the bundle
    c.col(8, 5, 14, "MTD")
    return c.outline()


def fish():
    c = Canvas(SIZE, SIZE)
    for y, x0, x1 in ((7, 5, 10), (8, 3, 11), (9, 2, 11), (10, 3, 11), (11, 5, 10)):
        c.row(x0, x1, y, "WAL")
    c.row(4, 10, 10, "MTL")                     # the pale belly
    c.rect(12, 7, 13, 11, "WAL")                # tail
    c.set(13, 6, "WAL")
    c.set(13, 12, "WAL")
    c.set(4, 8, "EY")
    return c.outline()


def coin():
    c = Canvas(SIZE, SIZE)
    _disc(c, 8, 9, 4, "FIL")
    _disc(c, 8, 9, 2, "TH")                     # struck in the middle
    c.set(6, 7, "CL")                           # a glint
    c.row(6, 10, 13, "THD")
    return c.outline()


def flower():
    c = Canvas(SIZE, SIZE)
    c.col(8, 7, 13, "BU")                       # stem
    c.row(9, 10, 10, "BU")                      # leaf
    for x, y in ((6, 5), (10, 5), (8, 3), (8, 7)):
        c.rect(x - 1, y - 1, x, y, "RFL")       # four petals
    c.rect(7, 4, 8, 5, "FL")                    # and the eye
    return c.outline()


# ----------------------------------------------------------------- weapons --
def sword():
    c = Canvas(SIZE, SIZE)
    _diag(c, 6, 9, 7, "MTL")                    # the blade, on the diagonal
    _diag(c, 7, 9, 6, "MT")
    _diag(c, 3, 12, 3, "WD")                    # grip
    c.set(5, 11, "WDD")                         # guard
    c.set(4, 10, "WDD")
    c.set(6, 12, "WDD")
    c.set(7, 13, "WDD")
    return c.outline()


def axe():
    c = Canvas(SIZE, SIZE)
    _diag(c, 3, 13, 9, "WD")                    # haft
    _diag(c, 4, 13, 8, "WDD")
    c.rect(9, 3, 12, 6, "MT")                   # the head, hung to one side
    c.rect(10, 2, 13, 4, "MTL")
    c.set(12, 7, "MT")
    return c.outline()


def spear():
    c = Canvas(SIZE, SIZE)
    _diag(c, 2, 14, 10, "WD")                   # shaft
    _diag(c, 3, 14, 9, "WDD")
    c.set(11, 5, "WDD")                         # collar
    _diag(c, 12, 4, 3, "MTL")                   # the point
    c.set(13, 4, "MTL")
    c.set(12, 3, "MTL")
    return c.outline()


# ------------------------------------------------------------------ armour --
def mail():
    c = Canvas(SIZE, SIZE)
    c.rect(4, 4, 11, 13, "MT")                  # the shirt
    c.rect(2, 4, 4, 7, "MT")                    # short sleeves
    c.rect(11, 4, 13, 7, "MT")
    for y in range(5, 13):                      # rings, as a checker
        for x in range(4, 12):
            if (x + y) % 2:
                c.set(x, y, "MTD")
    c.row(6, 9, 4, "MTL")                       # collar
    c.set(5, 3, "MTL")
    c.set(10, 3, "MTL")
    return c.outline()


ITEMS = {
    "item.apple": apple,
    "item.berries": berries,
    "item.wheat": wheat,
    "item.honey": honey,
    "item.wool": wool,
    "item.ore": ore,
    "item.firewood": firewood,
    "item.fish": fish,
    "item.coin": coin,
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

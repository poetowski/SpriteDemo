"""Shared palette and pixel canvas for every generator.

One palette for the whole project. Sprites store palette *keys*, not colours,
which is what makes a variant (a second NPC, a recoloured tileset) a remap
rather than a redraw.

**Five colours, and nothing else.** Every key below resolves to one of the five
in RAMP, and the assertion at the bottom of this module holds the line - a new
key mixed by eye would fail on import rather than after three hundred sprites
had quietly drifted off the palette.

Four of the five are one green ramp, so *value* carries every read: what is
near, what is raised, what is in shade. The fifth, ROSE, is the only warm
colour in the world and sits at the same value as MINT, so it is a hue step
rather than a lighter one - spending it on a surface buys nothing but warmth.
That makes it precious, and it is rationed by a rule:

    a cool material lights to MINT; a warm one lights to ROSE.

Grass, water, stone, metal and the hero's tunic are cool. Skin, sand, thatch,
fire, flowers and the wool on a sheep's back are warm. The warm ones are the
things meant to be looked at, which is why the meadow flowers, the shoreline
and everyone's face are the only pink in a green world.
"""

# https://coolors.co/e5c2c0-8fd5a6-329f5b-0c8346-0d5d56
INK = (0x0d, 0x5d, 0x56, 255)    # darkest: outlines, hollows, the deep water
DEEP = (0x0c, 0x83, 0x46, 255)   # the shade step under almost everything
MID = (0x32, 0x9f, 0x5b, 255)    # the workhorse: grass, and most mass
MINT = (0x8f, 0xd5, 0xa6, 255)   # the cool light
ROSE = (0xe5, 0xc2, 0xc0, 255)   # the warm light - the only warm colour there is

RAMP = (INK, DEEP, MID, MINT, ROSE)

# Key -> (RGBA, human name).
PALETTE = {
    "OL":  (INK,  "outline"),
    "SK":  (ROSE, "skin"),
    "SKS": (MID,  "skin shade"),
    "HR":  (DEEP, "hair"),
    "HRL": (MID,  "hair light"),
    "TU":  (MINT, "tunic"),
    "TUS": (MID,  "tunic shade"),
    "TUL": (ROSE, "tunic light"),
    "PN":  (DEEP, "pants"),
    "PNS": (INK,  "pants shade"),
    "BT":  (DEEP, "boots"),
    "BTS": (INK,  "boots shade"),
    "EY":  (INK,  "eye"),
    "EW":  (MINT, "eye white"),
    "SH":  ((*INK[:3], 90), "ground shadow"),
    # scenery. The hero wears the pale end of the ramp and walks on the middle
    # of it, so he reads against the ground from any distance.
    "GR":  (MID,  "grass"),
    "GRD": (DEEP, "grass dark"),
    "GRL": (MINT, "grass light"),
    "FL":  (ROSE, "flower"),
    "PT":  (MINT, "path"),
    "PTD": (MID,  "path dark"),
    "PTL": (ROSE, "path light"),
    # Water lights all the way to MINT, two steps above its own body. A shoal
    # is drawn in that light alone, and at MID it read as a pale-edged lawn
    # rather than as water; at MINT it is the brightest ground there is, which
    # is what water does when the sun is on it.
    "WA":  (DEEP, "water"),
    "WAD": (INK,  "water dark"),
    "WAL": (MINT, "water light"),
    "WAX": (INK,  "water deep"),
    "GRX": (INK,  "grass deep"),
    # Sand is warm and the path is cool, though both are pale: the same three
    # colours inverted, which is what keeps a beach and a road apart when they
    # cannot be told apart by value.
    "SA":  (ROSE, "sand"),
    "SAD": (MID,  "sand dark"),
    "SAL": (MINT, "sand light"),
    "LF":  (MID,  "leaf litter"),
    "LFD": (DEEP, "leaf litter dark"),
    "DR":  (DEEP, "dirt"),
    "DRD": (INK,  "dirt dark"),
    "DRL": (MID,  "dirt light"),
    "ST":  (MINT, "stone"),
    "STD": (MID,  "stone dark"),
    "STL": (ROSE, "stone light"),
    "STX": (DEEP, "stone deep"),
    "BU":  (DEEP, "bush"),
    "BUD": (INK,  "bush dark"),
    "BUL": (MID,  "bush light"),
    "WD":  (DEEP, "wood"),
    "WDD": (INK,  "wood dark"),
    "WDL": (MID,  "wood light"),
    # built scenery - roofs, thatch, iron, fire, cloth
    "RF":  (DEEP, "roof"),
    "RFD": (INK,  "roof dark"),
    "RFL": (MID,  "roof light"),
    "TH":  (MINT, "thatch"),
    "THD": (MID,  "thatch dark"),
    "THL": (ROSE, "thatch light"),
    "MT":  (MID,  "metal"),
    "MTD": (DEEP, "metal dark"),
    "MTL": (MINT, "metal light"),
    "FI":  (MID,  "fire"),
    "FID": (DEEP, "fire dark"),
    "FIL": (ROSE, "fire light"),
    "CL":  (MINT, "cloth"),
    "CLD": (MID,  "cloth dark"),
    # animals - generic keys so a species is a palette swap of one rig
    "AB":  (MINT, "animal body"),
    "ABS": (MID,  "animal body shade"),
    "ABL": (ROSE, "animal body light"),
    "AF":  (DEEP, "animal face"),
    "AFS": (INK,  "animal face shade"),
    "AH":  (INK,  "animal hoof"),
    "HN":  (ROSE, "horn"),
    "HNS": (MID,  "horn shade"),
}

# Palette swaps. The frames are identical pixels; only the lookup changes, so a
# second character costs nothing to draw and stays in perfect sync with the rig.
# With five colours a swap can only move a character along the ramp, so each one
# takes a different rung: the hero is pale-chested, the smith is dark.
VARIANTS = {
    "hero": {},
    "smith": {
        "TU":  DEEP,                      # a soot-dark apron, not the hero's mint
        "TUS": INK,
        "TUL": MID,
        "HR":  MINT,                      # grey hair, which on this ramp is pale
        "HRL": ROSE,
        "PN":  MID,
        "PNS": DEEP,
    },
    "sheep": {},                          # the base animal palette is the sheep
    "goat": {
        # A mid coat where the sheep's fleece is the pale end. The face and
        # hooves need no override any more: the two species are told apart by
        # the coat, the horns and the beard, which is the silhouette doing the
        # work rather than a second brown.
        "AB":  MID,
        "ABS": DEEP,
        "ABL": MINT,
    },
}

_FIVE = {c[:3] for c in RAMP}
assert all(rgba[:3] in _FIVE for rgba, _n in PALETTE.values()), "off-palette key"
assert all(rgba[:3] in _FIVE for v in VARIANTS.values()
           for rgba in v.values()), "off-palette variant"


def resolve(variant="hero"):
    """Return a key -> RGBA map with the variant's overrides applied."""
    out = {k: rgba for k, (rgba, _n) in PALETTE.items()}
    out.update(VARIANTS[variant])
    return out


def scatter(seed):
    """A tiny deterministic generator, so texture can be dense without being
    typed out pixel by pixel - and identical on every machine, every run."""
    state = seed & 0x7fffffff

    def nxt(n):
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7fffffff
        # The high bits, not the low ones: this generator's bottom bits cycle
        # with a period as short as n, so `% 16` laid tufts out in diagonal
        # stripes and the grass read as hatching instead of texture.
        return (state >> 15) % n
    return nxt


class Canvas:
    """Indexed pixel buffer. Stores palette keys; None = transparent."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, key):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = key

    def rect(self, x0, y0, x1, y1, key):
        """Inclusive rectangle."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, key)

    def row(self, x0, x1, y, key):
        self.rect(x0, y, x1, y, key)

    def col(self, x, y0, y1, key):
        self.rect(x, y0, x, y1, key)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def mirrored(self):
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                out.px[y][x] = self.px[y][self.w - 1 - x]
        return out

    def outline(self, key="OL"):
        """Wrap the silhouette in a 1px outline (4-neighbourhood)."""
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if self.get(x + dx, y + dy) is not None:
                        add.append((x, y))
                        break
        for x, y in add:
            self.set(x, y, key)
        return self

    def rgba_bytes(self, pal=None):
        pal = pal or resolve()
        out = bytearray()
        for y in range(self.h):
            for x in range(self.w):
                k = self.px[y][x]
                out += bytes(pal[k]) if k else b"\x00\x00\x00\x00"
        return bytes(out)

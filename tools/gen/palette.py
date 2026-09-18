"""Shared palette and pixel canvas for every generator.

One palette for the whole project. Sprites store palette *keys*, not colours,
which is what makes a variant (a second NPC, a recoloured tileset) a remap
rather than a redraw.
"""

# Key -> (RGBA, human name).
PALETTE = {
    "OL":  ((0x24, 0x1a, 0x2e, 255), "outline"),
    "SK":  ((0xf2, 0xc2, 0x92, 255), "skin"),
    "SKS": ((0xcc, 0x94, 0x64, 255), "skin shade"),
    "SKL": ((0xff, 0xdd, 0xb4, 255), "skin light"),
    "HR":  ((0x5c, 0x3a, 0x24, 255), "hair"),
    "HRL": ((0x82, 0x55, 0x35, 255), "hair light"),
    "TU":  ((0x4f, 0xa5, 0x55, 255), "tunic"),
    "TUS": ((0x2f, 0x71, 0x3c, 255), "tunic shade"),
    "TUL": ((0x74, 0xc4, 0x6b, 255), "tunic light"),
    "PN":  ((0x3d, 0x5d, 0x94, 255), "pants"),
    "PNS": ((0x28, 0x41, 0x6d, 255), "pants shade"),
    "BT":  ((0x7d, 0x51, 0x2f, 255), "boots"),
    "BTS": ((0x55, 0x34, 0x1d, 255), "boots shade"),
    "EY":  ((0x24, 0x1a, 0x2e, 255), "eye"),
    "EW":  ((0xf4, 0xef, 0xe4, 255), "eye white"),
    "SH":  ((0x24, 0x1a, 0x2e, 90),  "ground shadow"),
    # scenery
    "GR":  ((0x4e, 0x7a, 0x3a, 255), "grass"),
    "GRD": ((0x42, 0x6b, 0x31, 255), "grass dark"),
    "GRL": ((0x5e, 0x8c, 0x45, 255), "grass light"),
    "FL":  ((0xd8, 0xc0, 0x5c, 255), "flower"),
    "PT":  ((0xa8, 0x8a, 0x5e, 255), "path"),
    "PTD": ((0x8c, 0x71, 0x49, 255), "path dark"),
    "PTL": ((0xc0, 0xa3, 0x76, 255), "path light"),
    "WA":  ((0x36, 0x6d, 0xa8, 255), "water"),
    "WAD": ((0x27, 0x53, 0x84, 255), "water dark"),
    "WAL": ((0x52, 0x92, 0xc4, 255), "water light"),
    "WAX": ((0x1f, 0x42, 0x6b, 255), "water deep"),
    "GRX": ((0x38, 0x5a, 0x29, 255), "grass deep"),
    "SA":  ((0xd8, 0xc5, 0x8e, 255), "sand"),
    "SAD": ((0xb9, 0xa5, 0x70, 255), "sand dark"),
    "SAL": ((0xee, 0xdf, 0xb0, 255), "sand light"),
    "LF":  ((0x8c, 0x6a, 0x30, 255), "leaf litter"),
    "LFD": ((0x6a, 0x4e, 0x22, 255), "leaf litter dark"),
    "DR":  ((0x7f, 0x5b, 0x3d, 255), "dirt"),
    "DRD": ((0x64, 0x46, 0x2e, 255), "dirt dark"),
    "DRL": ((0x9a, 0x75, 0x53, 255), "dirt light"),
    "ST":  ((0x82, 0x84, 0x8e, 255), "stone"),
    "STD": ((0x5e, 0x60, 0x6c, 255), "stone dark"),
    "STL": ((0xa2, 0xa4, 0xae, 255), "stone light"),
    "STX": ((0x44, 0x46, 0x50, 255), "stone deep"),
    "BU":  ((0x35, 0x72, 0x3a, 255), "bush"),
    "BUD": ((0x23, 0x4f, 0x2b, 255), "bush dark"),
    "BUL": ((0x45, 0x89, 0x4a, 255), "bush light"),
    "WD":  ((0x7a, 0x5a, 0x38, 255), "wood"),
    "WDD": ((0x55, 0x3d, 0x25, 255), "wood dark"),
    "WDL": ((0x9c, 0x78, 0x4e, 255), "wood light"),
    # built scenery - roofs, thatch, iron, fire, cloth
    "RF":  ((0xa8, 0x4b, 0x3c, 255), "roof"),
    "RFD": ((0x7c, 0x33, 0x2a, 255), "roof dark"),
    "RFL": ((0xc9, 0x6a, 0x54, 255), "roof light"),
    "TH":  ((0xc4, 0xa0, 0x52, 255), "thatch"),
    "THD": ((0x96, 0x77, 0x39, 255), "thatch dark"),
    "THL": ((0xdc, 0xc0, 0x78, 255), "thatch light"),
    "MT":  ((0x6e, 0x76, 0x84, 255), "metal"),
    "MTD": ((0x4a, 0x51, 0x5c, 255), "metal dark"),
    "MTL": ((0x99, 0xa2, 0xb0, 255), "metal light"),
    "FI":  ((0xe0, 0x7a, 0x2c, 255), "fire"),
    "FID": ((0xb0, 0x42, 0x20, 255), "fire dark"),
    "FIL": ((0xf5, 0xcc, 0x55, 255), "fire light"),
    "CL":  ((0xd8, 0xd2, 0xc0, 255), "cloth"),
    "CLD": ((0xab, 0xa4, 0x90, 255), "cloth dark"),
    # animals - generic keys so a species is a palette swap of one rig
    "AB":  ((0xe4, 0xde, 0xcd, 255), "animal body"),
    "ABS": ((0xc0, 0xb8, 0xa4, 255), "animal body shade"),
    "ABL": ((0xf5, 0xf1, 0xe6, 255), "animal body light"),
    "AF":  ((0x5b, 0x52, 0x4b, 255), "animal face"),
    "AFS": ((0x3e, 0x37, 0x32, 255), "animal face shade"),
    "AH":  ((0x4a, 0x41, 0x3a, 255), "animal hoof"),
    "HN":  ((0xcd, 0xbb, 0x96, 255), "horn"),
    "HNS": ((0xa3, 0x90, 0x6d, 255), "horn shade"),
    # Gas, and the only translucent colours besides the ground shadow: a cloud
    # you cannot see the grass through is a balloon, not a smell.
    "GS":  ((0xc8, 0xbe, 0x3a, 165), "gas"),
    "GSL": ((0xe9, 0xe1, 0x7c, 120), "gas light"),
}

# Palette swaps. The frames are identical pixels; only the lookup changes, so a
# second character costs nothing to draw and stays in perfect sync with the rig.
VARIANTS = {
    "hero": {},
    "smith": {
        "TU":  (0x9c, 0x4f, 0x3a, 255),   # rust apron
        "TUS": (0x6e, 0x33, 0x25, 255),
        "TUL": (0xc0, 0x6e, 0x50, 255),
        "HR":  (0x54, 0x51, 0x4d, 255),   # grey hair
        "HRL": (0x77, 0x74, 0x6f, 255),
        "PN":  (0x4a, 0x44, 0x3c, 255),
        "PNS": (0x33, 0x2e, 0x29, 255),
    },
    "sheep": {},                          # the base animal palette is the sheep
    "goat": {
        "AB":  (0xa8, 0x82, 0x52, 255),   # tan coat instead of wool
        "ABS": (0x83, 0x62, 0x3c, 255),
        "ABL": (0xc4, 0xa0, 0x6e, 255),
        "AF":  (0x6d, 0x51, 0x32, 255),
        "AFS": (0x4c, 0x38, 0x22, 255),
        "AH":  (0x39, 0x2c, 0x22, 255),
    },
    "boar": {
        # Dark all through, so it reads as a shape coming at you through trees
        # rather than as livestock. The tusks keep the default ivory: they are
        # the one bright thing on it, and the only warning you get.
        "AB":  (0x4a, 0x3a, 0x2e, 255),
        "ABS": (0x33, 0x27, 0x1f, 255),
        "ABL": (0x63, 0x4f, 0x3e, 255),
        "AF":  (0x2e, 0x24, 0x1d, 255),
        "AFS": (0x20, 0x19, 0x14, 255),
        "AH":  (0x1d, 0x17, 0x12, 255),
    },
    "troll": {
        # Woodland colours: moss and bark, so a troll standing still among the
        # trees is nearly one of them until it moves. The gas keys are left
        # alone - the yellow is the only thing on him that is not the wood.
        "SK":  (0x5a, 0x73, 0x38, 255),   # mossy hide
        "SKS": (0x3c, 0x51, 0x25, 255),
        "SKL": (0x7a, 0x93, 0x4e, 255),
        "TU":  (0x66, 0x47, 0x29, 255),   # a hide slung round the waist
        "TUS": (0x46, 0x2f, 0x1a, 255),
        "TUL": (0x8a, 0x64, 0x3c, 255),
        "BT":  (0x2b, 0x23, 0x1a, 255),   # near-black: straps, nails, the maw
        "BTS": (0x1a, 0x15, 0x10, 255),
        "HN":  (0xb5, 0xa6, 0x7c, 255),   # tusks, grubbier than a goat's horn
        "HNS": (0x8d, 0x7f, 0x5c, 255),
    },
}


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

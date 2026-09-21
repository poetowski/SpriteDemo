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
    # A fourth tone and some detail keys, for the giant rig: three tones over a
    # mass that size leaves it flat, and a monster wants things on it that a
    # person does not.
    "MS":  ((0x86, 0x96, 0x6a, 255), "lichen"),
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
    # The pale patch a deer shows you as it leaves. Defaults to the body's own
    # light tone, so it costs the species that do not have one nothing at all.
    "AR":  ((0xf5, 0xf1, 0xe6, 255), "animal rump"),
    "HN":  ((0xcd, 0xbb, 0x96, 255), "horn"),
    "HNS": ((0xa3, 0x90, 0x6d, 255), "horn shade"),
    # Gas, and the only translucent colours besides the ground shadow: a cloud
    # you cannot see the grass through is a balloon, not a smell.
    # Dust hanging in the air. Warmer and fainter than the gas, because it is
    # lit by something rather than coming off something.
    "DU":  ((0xe8, 0xdc, 0xbe, 150), "dust"),
    "DUL": ((0xff, 0xf2, 0xd4, 110), "dust light"),
    # --- the desert -------------------------------------------------------
    # A second biome wants its own family of keys, not a remap of the first.
    # Nothing in the grass palette reads as sun-bleached: the greens are all
    # cool and the browns are all damp, and a desert drawn out of them comes
    # out looking like a dead meadow.
    "DND": ((0xbd, 0x9a, 0x5c, 255), "dune shade"),
    "DNX": ((0x9a, 0x7a, 0x45, 255), "dune deep"),
    "SL":  ((0xe8, 0xe4, 0xd8, 255), "salt"),
    "SLD": ((0xc2, 0xbd, 0xae, 255), "salt shade"),
    "SLL": ((0xfb, 0xf8, 0xef, 255), "salt light"),
    "SS":  ((0xc9, 0x8f, 0x5a, 255), "sandstone"),
    "SSD": ((0x9c, 0x6a, 0x3e, 255), "sandstone shade"),
    "SSL": ((0xe3, 0xad, 0x74, 255), "sandstone light"),
    "SC":  ((0x9a, 0x8a, 0x52, 255), "scrub"),
    "SCD": ((0x6f, 0x63, 0x38, 255), "scrub shade"),
    "SCL": ((0xb9, 0xa8, 0x6c, 255), "scrub light"),
    # An oasis is not the river: still, green-blue and much darker in the
    # middle, because it is deep and there is nothing moving it.
    "OA":  ((0x2f, 0x8f, 0x8a, 255), "oasis"),
    "OAD": ((0x1d, 0x63, 0x60, 255), "oasis dark"),
    "OAL": ((0x57, 0xb9, 0xb0, 255), "oasis light"),
    "OAX": ((0x14, 0x46, 0x4a, 255), "oasis deep"),
    # What the old kingdom put on the things it meant to outlast it.
    "GD":  ((0xd9, 0xb2, 0x4c, 255), "gold"),
    "GDL": ((0xf0, 0xd5, 0x82, 255), "gold light"),
    "LP":  ((0x2f, 0x4e, 0x9c, 255), "lapis"),
    "LPD": ((0x1d, 0x31, 0x68, 255), "lapis shade"),

    # --- the wetland ------------------------------------------------------
    # The country between the meadow and whatever grows south of it. Its own
    # family again, for the desert's reason: the grass keys are a dry, yellow
    # green and there is nothing in them that reads as ground with water
    # standing in it.
    #
    # The one colour idea here is worth saying out loud, because the whole
    # biome is built on it: **the wetland's green leans blue where the
    # meadow's leans yellow.** That is what says a different country begins
    # at the fringe, before a single new prop is placed - and it is the note
    # the jungle south of here carries on.
    # Ground with water standing in it is *darker* than turf, and that is the
    # whole of why this is not a tint of the grass keys: an olive drawn a step
    # brighter than the meadow reads as a dry field, whatever its hue. Grass
    # is luma 105, marsh 86, bog 65 - a ladder you can see from across the
    # map, which is what tells you the ground has changed before you notice
    # the sedge.
    "MAD": ((0x3a, 0x4d, 0x33, 255), "marsh shade"),
    # Peat water, not river water: what stains it is the ground it stands in,
    # so it is brown-green and much darker than anything the wilderness has.
    # Rush and sedge: paler and more golden than anything growing on dry
    # ground here, which is what makes a reed bed read as a reed bed from a
    # screen away.
    # And the blue-green the leaves take when they never dry out. Measured
    # against the ground rather than picked for hue: the first pass was a
    # deep teal at luma 69 standing on marsh at 86, so a bush in the fen was
    # a hole in it. A plant has to sit *above* the ground it grows out of.

    # --- crystal ----------------------------------------------------------
    # Two families, and they are a pair on purpose: the blue burns in the gate
    # and the red grows on the thing standing in front of it, so the only two
    # saturated colours in that corner of the world are the two sides of one
    # argument. Neither is in any biome's palette, on purpose: a crystal
    # painted in the local greens is a rock somebody polished.
    "CY":  ((0x6c, 0xc8, 0xf4, 255), "crystal"),
    "CYD": ((0x27, 0x6a, 0xa8, 255), "crystal shade"),
    "CYL": ((0xea, 0xf8, 0xff, 255), "crystal light"),
    "CYX": ((0x14, 0x3a, 0x6e, 255), "crystal deep"),

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
    "monk": {
        # Bald is a remap like everything else: the rig draws a crown of hair
        # over the skull, so pointing the hair keys at the skin ones leaves a
        # shaved head with the light still on the dome. Nothing in the rig
        # knows there is a bald character.
        "HR":  (0xf2, 0xc2, 0x92, 255),
        "HRL": (0xff, 0xdd, 0xb4, 255),
        "TU":  (0xd9, 0x7d, 0x2b, 255),   # saffron robe over one shoulder
        "TUS": (0xa4, 0x52, 0x18, 255),
        "TUL": (0xf0, 0xa3, 0x4c, 255),
        "PN":  (0xb9, 0x63, 0x22, 255),   # and down to the ankle, so the legs
        "PNS": (0x8c, 0x47, 0x17, 255),   # are robe rather than trousers
        "BT":  (0x6b, 0x4c, 0x2c, 255),   # sandals
        "BTS": (0x49, 0x33, 0x1d, 255),
    },
    "nomad": {
        # A headcloth is a remap too, the same trick as the monk's bald head
        # run the other way: the rig draws a crown of hair over the skull, so
        # pointing the hair keys at indigo puts a wrapped head on a character
        # nothing in the rig knows about. Indigo on undyed linen is the whole
        # of the look, and it is the one colour scheme in the game that is not
        # in either biome's palette - which is the point of a man who crosses
        # both.
        "HR":  (0x2f, 0x3e, 0x7a, 255),
        "HRL": (0x49, 0x5d, 0xa8, 255),
        "TU":  (0xd8, 0xcd, 0xb4, 255),   # undyed robe
        "TUS": (0xab, 0xa0, 0x88, 255),
        "TUL": (0xf0, 0xe8, 0xd2, 255),
        "PN":  (0xc6, 0xba, 0x9e, 255),   # and down to the ankle, like the
        "PNS": (0x9c, 0x90, 0x77, 255),   # monk's, so the legs are robe
        "BT":  (0x7d, 0x5f, 0x3a, 255),   # sandals
        "BTS": (0x55, 0x3f, 0x25, 255),
        "SK":  (0xd9, 0xa4, 0x6e, 255),   # and weathered by the sun he lives in
        "SKS": (0xad, 0x7c, 0x4e, 255),
        "SKL": (0xf0, 0xc4, 0x92, 255),
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

"""Pick the drawn tile for every map cell.

The map is authored as plain terrain - a path cell is a path cell - and this
turns that into the transition tile that matches its neighbours, so the author
never places an edge by hand. Two tiles are neighbours of a kind when their
`family` matches (grass, flowered grass and tall grass are all grass, so a path
edges against all of them the same way). Off the edge of the world counts as
"same", so the map's border never grows a rim of transitions.

For tiles without transitions the cell picks one of the base's seeded variants
by position, which is what stops a field from reading as one repeated stamp.
"""

from gen.tiles import canonical

# (bit, dx, dy), clockwise from north - the order the bits are numbered in.
NEIGHBOURS = ((1, 0, -1), (2, 1, -1), (4, 1, 0), (8, 1, 1),
              (16, 0, 1), (32, -1, 1), (64, -1, 0), (128, -1, -1))


def family_of(tile_defs, tid):
    return tile_defs[tid].get("family", tid)


def resolve(m, tile_defs, lookup):
    """A grid of atlas indices for map `m`.

    lookup(tid, x, y, mask) returns the index for that tile with that
    canonical neighbour mask; the caller decides how variants are chosen.
    """
    w, h = m["size"]
    rows, legend = m["ground"], m["legend"]

    def at(x, y):
        if 0 <= x < w and 0 <= y < h:
            return legend[rows[y][x]]
        return None

    grid = []
    for y in range(h):
        row = []
        for x in range(w):
            tid = at(x, y)
            fam = family_of(tile_defs, tid)
            mask = 0
            for bit, dx, dy in NEIGHBOURS:
                n = at(x + dx, y + dy)
                if n is None or family_of(tile_defs, n) == fam:
                    mask |= bit
            row.append(lookup(tid, x, y, canonical(mask)))
        grid.append(row)
    return grid


def pick_variant(x, y, n):
    """A stable, well-mixed choice of one of n variants for a cell."""
    return ((x * 73856093) ^ (y * 19349663) ^ 0x2F6B) % n

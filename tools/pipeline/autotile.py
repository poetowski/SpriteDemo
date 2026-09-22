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


# --- linked props ------------------------------------------------------------
# Ground is not the only thing that has to know what is next to it. A fence is
# a line, and a line drawn without regard to its neighbours is a row of
# disconnected pieces - a north-south run came out as a stack of little
# east-west ladders lying on the grass. So a prop may declare a `links` group,
# and the build picks its drawing from which cardinal neighbours carry the same
# group, exactly as resolve() picks a tile from its eight.
#
# The mask is N=1, E=2, W=4 and deliberately has no south bit: the piece below
# draws its own north connector up into this one's foot, so a southward join
# needs nothing drawn here. Eight pieces instead of sixteen, and one fewer
# thing to keep in step.
LINK_BITS = ((1, 0, -1), (2, 1, 0), (4, -1, 0))


def link_group(defs, def_id):
    d = defs.get(def_id)
    return d.get("links") if d else None


def resolve_links(m, defs):
    """{index in m["entities"]: sprite key} for every placement that links.

    Keyed by position in the entity list rather than by tile, because two
    things may legitimately stand on one tile and only one of them is a fence.
    """
    groups = {}
    for e in m.get("entities", []):
        g = link_group(defs, e["def"])
        if g:
            groups.setdefault(g, set()).add(tuple(e["tile"]))
    out = {}
    for i, e in enumerate(m.get("entities", [])):
        g = link_group(defs, e["def"])
        if not g:
            continue
        x, y = e["tile"]
        mask = 0
        for bit, dx, dy in LINK_BITS:
            if (x + dx, y + dy) in groups[g]:
                mask |= bit
        if mask:
            out[i] = f"{defs[e['def']]['sprite']}/link/{mask}"
    return out

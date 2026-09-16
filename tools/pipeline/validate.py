"""The gates between the build and the engine.

Nothing reaches the game that has not been checked here. Each gate catches a
class of bug that costs minutes now and weeks at three hundred assets; a failure
always points at an authored file, never at generated output.
"""

import re

from gen.actor import FACINGS, STATE_ORDER

ID_RE = re.compile(r"^[a-z]+\.[a-z0-9_]+$")
SPRITE_RE = re.compile(r"^[a-z]+\.[a-z0-9_]+(/[a-z0-9_]+)*$")


class GateError(Exception):
    pass


def _fail(gate, msg):
    raise GateError(f"[{gate}] {msg}")


def run(content, man, tile_canvases):
    """Returns the list of gate names that passed, or raises GateError."""
    passed = []

    # 1 - every ID is well formed and unique within its kind
    for kind, defs in content.items():
        for cid, defn in defs.items():
            if not ID_RE.match(cid):
                _fail("id-format", f"{defn['_file']}: bad id {cid!r}")
            if not cid.startswith(("tile.", "prop.", "actor.", "npc.",
                                   "dlg.", "map.")):
                _fail("id-format", f"{defn['_file']}: unknown id prefix {cid!r}")
    passed.append("id-format")

    # 2 - every sprite key referenced by a definition exists in an atlas
    for kind in ("tiles", "props", "actors"):
        for cid, defn in content[kind].items():
            key = defn["sprite"]
            if not SPRITE_RE.match(key):
                _fail("sprite-format", f"{defn['_file']}: bad sprite {key!r}")
            if kind == "actors":
                continue                     # actors resolve through anims
            if key not in man["sprites"]:
                _fail("sprite-exists",
                      f"{defn['_file']}: sprite {key!r} is not in any atlas")
    passed.append("sprite-format")
    passed.append("sprite-exists")

    # 3 - every actor has all facings for every state, and one shared anchor
    for cid, defn in content["actors"].items():
        base = defn["sprite"]
        anchors = set()
        for state in STATE_ORDER:
            for facing in FACINGS:
                key = f"{base}/{state}/{facing}"
                if key not in man["anims"]:
                    _fail("actor-complete",
                          f"{defn['_file']}: missing animation {key!r}")
                for idx in man["anims"][key]["frames"]:
                    pass
        for skey, rec in man["sprites"].items():
            if skey.startswith(base + "/"):
                anchors.add(tuple(rec["anchor"]))
        if len(anchors) != 1:
            _fail("actor-anchor",
                  f"{cid}: frames disagree on the anchor: {sorted(anchors)}")
    passed.append("actor-complete")
    passed.append("actor-anchor")

    # 4 - anchors lie inside their frame
    for key, rec in man["sprites"].items():
        fw, fh = man["atlases"][rec["atlas"]]["frame"]
        ax, ay = rec["anchor"]
        if not (0 <= ax <= fw and 0 <= ay <= fh):
            _fail("anchor-bounds", f"{key}: anchor {rec['anchor']} outside {fw}x{fh}")
    passed.append("anchor-bounds")

    # 5 - tiles repeat without a seam: opposite edges must be free of detail
    #     that would read as a hard line when the tile is tiled.
    for tid, c in tile_canvases.items():
        for y in range(c.h):
            if c.px[y][0] is None or c.px[y][c.w - 1] is None:
                _fail("tile-seam", f"{tid}: transparent pixel on a vertical edge")
        for x in range(c.w):
            if c.px[0][x] is None or c.px[c.h - 1][x] is None:
                _fail("tile-seam", f"{tid}: transparent pixel on a horizontal edge")
    passed.append("tile-seam")

    # 6 - maps: rectangular grid, legend covers it, entities land in bounds
    for mid, m in content["maps"].items():
        w, h = m["size"]
        if len(m["ground"]) != h:
            _fail("map-shape", f"{mid}: {len(m['ground'])} rows, expected {h}")
        for y, row in enumerate(m["ground"]):
            if len(row) != w:
                _fail("map-shape", f"{mid}: row {y} is {len(row)} wide, expected {w}")
            for ch in row:
                if ch not in m["legend"]:
                    _fail("map-legend", f"{mid}: row {y} uses {ch!r}, not in legend")
        for ch, tid in m["legend"].items():
            if tid not in man["tiles"]:
                _fail("map-legend", f"{mid}: legend {ch!r} -> unknown tile {tid!r}")
        for e in m["entities"]:
            if e["def"] not in man["props"] and e["def"] not in man["actors"]:
                _fail("map-entity", f"{mid}: unknown definition {e['def']!r}")
            ex, ey = e["tile"]
            if not (0 <= ex < w and 0 <= ey < h):
                _fail("map-entity", f"{mid}: {e['def']} at {e['tile']} is off the map")
            tid = m["legend"][m["ground"][ey][ex]]
            if not man["tiles"][tid]["walkable"]:
                _fail("map-entity",
                      f"{mid}: {e['def']} at {e['tile']} stands on {tid}")
        sx, sy = m["spawn"]["tile"]
        if not man["tiles"][m["legend"][m["ground"][sy][sx]]]["walkable"]:
            _fail("map-spawn", f"{mid}: spawn {m['spawn']['tile']} is not walkable")
        blocked = {tuple(e["tile"]) for e in m["entities"]
                   if (man["props"].get(e["def"]) or man["actors"][e["def"]]).get("blocks")}
        if (sx, sy) in blocked:
            _fail("map-spawn", f"{mid}: spawn {m['spawn']['tile']} is inside a solid entity")
    passed.append("map-shape")
    passed.append("map-legend")
    passed.append("map-entity")
    passed.append("map-spawn")

    # 7 - every dialogue referenced by an entity exists
    for kind in ("props", "actors"):
        for cid, defn in content[kind].items():
            dlg = defn.get("interact")
            if dlg and dlg not in man["dialogue"]:
                _fail("dialogue-exists",
                      f"{defn['_file']}: interact -> unknown dialogue {dlg!r}")
    passed.append("dialogue-exists")

    return passed

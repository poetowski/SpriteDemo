"""The gates between the build and the engine.

Nothing reaches the game that has not been checked here. Each gate catches a
class of bug that costs minutes now and weeks at three hundred assets; a failure
always points at an authored file, never at generated output.
"""

import re

from gen.actor import FACINGS

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
                                   "item.", "dlg.", "map.")):
                _fail("id-format", f"{defn['_file']}: unknown id prefix {cid!r}")
    passed.append("id-format")

    # 2 - every sprite key referenced by a definition exists in an atlas
    for kind in ("tiles", "props", "actors", "items"):
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
        states = defn.get("states")
        if not states:
            _fail("actor-states", f"{defn['_file']}: no \"states\" declared")
        for state in states:
            for facing in FACINGS:
                key = f"{base}/{state}/{facing}"
                if key not in man["anims"]:
                    _fail("actor-complete",
                          f"{defn['_file']}: declares state {state!r} but the rig "
                          f"generated no animation {key!r}")
        for skey, rec in man["sprites"].items():
            if skey.startswith(base + "/"):
                anchors.add(tuple(rec["anchor"]))
        if len(anchors) != 1:
            _fail("actor-anchor",
                  f"{cid}: frames disagree on the anchor: {sorted(anchors)}")
    passed.append("actor-states")
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
        # A definition's footprint is the tiles it actually stands on, as
        # offsets from its anchor tile. Every one of them has to be real ground,
        # and no two solid things may claim the same tile - otherwise a cottage
        # ends up half in the river, or two props fight over one collision box.
        claimed = {}
        placed = []
        for e in m["entities"]:
            defn = (man["props"].get(e["def"]) or man["actors"].get(e["def"])
                    or man["items"].get(e["def"]))
            if defn is None:
                _fail("map-entity", f"{mid}: unknown definition {e['def']!r}")
            ex, ey = e["tile"]
            if not (0 <= ex < w and 0 <= ey < h):
                _fail("map-entity", f"{mid}: {e['def']} at {e['tile']} is off the map")
            for dx, dy in defn.get("footprint") or [[0, 0]]:
                fx, fy = ex + dx, ey + dy
                where = f"{e['def']} at {e['tile']}"
                if not (0 <= fx < w and 0 <= fy < h):
                    _fail("map-footprint",
                          f"{mid}: {where} covers [{fx}, {fy}], off the map")
                tid = m["legend"][m["ground"][fy][fx]]
                if not man["tiles"][tid]["walkable"]:
                    _fail("map-footprint",
                          f"{mid}: {where} covers [{fx}, {fy}], which is {tid}")
                if not defn.get("blocks"):
                    continue
                if (fx, fy) in claimed:
                    _fail("map-overlap", f"{mid}: {where} and {claimed[(fx, fy)]} "
                                         f"both claim tile [{fx}, {fy}]")
                claimed[(fx, fy)] = where
            placed.append((e, defn))
        # Nothing that does not block may stand inside something that does: an
        # item under a boulder cannot be picked up, a sheep inside a wall
        # cannot leave, and neither would ever be seen.
        for e, defn in placed:
            ex, ey = e["tile"]
            if not defn.get("blocks") and (ex, ey) in claimed:
                _fail("map-overlap", f"{mid}: {e['def']} at {e['tile']} is inside "
                                     f"{claimed[(ex, ey)]}")
        sx, sy = m["spawn"]["tile"]
        if not man["tiles"][m["legend"][m["ground"][sy][sx]]]["walkable"]:
            _fail("map-spawn", f"{mid}: spawn {m['spawn']['tile']} is not walkable")
        if (sx, sy) in claimed:
            _fail("map-spawn", f"{mid}: spawn {m['spawn']['tile']} is inside "
                               f"{claimed[(sx, sy)]}")
    passed.append("map-shape")
    passed.append("map-legend")
    passed.append("map-entity")
    passed.append("map-footprint")
    passed.append("map-overlap")
    passed.append("map-spawn")

    # 7 - every dialogue referenced by an entity exists
    for kind in ("props", "actors"):
        for cid, defn in content[kind].items():
            dlg = defn.get("interact")
            if dlg and dlg not in man["dialogue"]:
                _fail("dialogue-exists",
                      f"{defn['_file']}: interact -> unknown dialogue {dlg!r}")
    passed.append("dialogue-exists")

    # 7b - dialogue graphs. A conversation is nodes joined by choices, so the
    # ways it can break are structural: a goto that points nowhere leaves the
    # player stuck mid-sentence, an unreachable node is writing nobody will
    # ever see, and a condition on a flag no choice sets is a branch that can
    # never be taken. All three are invisible until someone plays that path.
    def _entry_rules(d):
        start = d.get("start")
        if isinstance(start, str):
            return [{"goto": start}]
        return start or []

    def _conds(c):
        """Every condition in a when-clause, flattened."""
        w = c.get("when")
        if not w:
            return []
        return w.get("all") if "all" in w else [w]

    for did, d in content["dialogue"].items():
        where = d["_file"]
        nodes = d.get("nodes")
        if not isinstance(nodes, dict) or not nodes:
            _fail("dialogue-shape", f"{where}: no \"nodes\"")
        if not _entry_rules(d):
            _fail("dialogue-shape", f"{where}: no \"start\"")
        for nid, node in nodes.items():
            if not node.get("text"):
                _fail("dialogue-shape", f"{where}: node {nid!r} says nothing")
            for ch in node.get("choices") or []:
                if not ch.get("text"):
                    _fail("dialogue-shape",
                          f"{where}: a choice in {nid!r} has no text")
    passed.append("dialogue-shape")

    for did, d in content["dialogue"].items():
        where, nodes = d["_file"], d["nodes"]
        seen, queue = set(), []
        for rule in _entry_rules(d):
            if rule["goto"] not in nodes:
                _fail("dialogue-links",
                      f"{where}: start -> unknown node {rule['goto']!r}")
            queue.append(rule["goto"])
        while queue:                             # walk it the way a player would
            nid = queue.pop()
            if nid in seen:
                continue
            seen.add(nid)
            for ch in nodes[nid].get("choices") or []:
                goto = ch.get("goto")
                if goto is None:
                    continue                     # a choice with no goto ends it
                if goto not in nodes:
                    _fail("dialogue-links", f"{where}: {nid!r} -> unknown node "
                                            f"{goto!r}")
                queue.append(goto)
        orphans = sorted(set(nodes) - seen)
        if orphans:
            _fail("dialogue-links", f"{where}: unreachable node(s) "
                                    f"{', '.join(orphans)}")
    passed.append("dialogue-links")

    set_flags = set()
    read_flags = {}
    for did, d in content["dialogue"].items():
        for nid, node in d["nodes"].items():
            for ch in node.get("choices") or []:
                for key in ("set",):
                    if ch.get(key):
                        set_flags.add(ch[key])
                for key in ("give", "take"):
                    if ch.get(key) and ch[key] not in man["items"]:
                        _fail("dialogue-effects", f"{d['_file']}: {nid!r} {key}s "
                                                  f"unknown item {ch[key]!r}")
                for cond in _conds(ch):
                    for key in ("has", "nothas"):
                        if cond.get(key) and cond[key] not in man["items"]:
                            _fail("dialogue-effects",
                                  f"{d['_file']}: {nid!r} tests unknown item "
                                  f"{cond[key]!r}")
                    for key in ("flag", "noflag"):
                        if cond.get(key):
                            read_flags.setdefault(cond[key], f"{d['_file']}: {nid!r}")
            for rule in _entry_rules(d):
                for key in ("flag", "noflag"):
                    if (rule.get("when") or {}).get(key):
                        read_flags.setdefault(rule["when"][key], f"{d['_file']}: start")
    for flag, where in sorted(read_flags.items()):
        if flag not in set_flags:
            _fail("dialogue-effects", f"{where} waits on flag {flag!r}, which no "
                                      f"choice ever sets")
    passed.append("dialogue-effects")

    # 8 - items: a kind the engine knows; a weapon names what the hand holds;
    #     and every actor that wields has a complete frame set per weapon,
    #     slash included, or the engine would switch to a sprite with holes.
    for iid, defn in content["items"].items():
        kind = defn.get("kind")
        if kind not in ("material", "weapon", "armor"):
            _fail("item-kind", f"{defn['_file']}: kind must be material, weapon or "
                               f"armor, not {kind!r}")
        if kind == "weapon" and not defn.get("held"):
            _fail("item-kind", f"{defn['_file']}: a weapon needs a \"held\" drawing")
        if kind == "armor" and not defn.get("worn"):
            _fail("item-kind", f"{defn['_file']}: armor needs a \"worn\" drawing")
        if kind == "weapon" and not (isinstance(defn.get("damage"), int)
                                     and defn["damage"] > 0):
            _fail("item-kind", f"{defn['_file']}: a weapon needs a positive "
                               f"integer \"damage\"")
    passed.append("item-kind")
    # looks: "<weapon item>|<armor item>" -> sprite base, every combination the
    # actor can be seen in. Armed looks must also carry the slash.
    for cid, defn in content["actors"].items():
        for combo, base in (defn.get("looks") or {}).items():
            weapon, _armor = combo.split("|")
            states = list(defn["states"]) + (["slash"] if weapon else [])
            for state in states:
                for facing in FACINGS:
                    key = f"{base}/{state}/{facing}"
                    if key not in man["anims"]:
                        _fail("item-held",
                              f"{cid} as {combo!r}: no animation {key!r}")
    passed.append("item-held")

    return passed

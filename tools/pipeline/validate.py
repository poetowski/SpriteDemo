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


def run(content, man, tile_canvases=None):
    """Returns the list of gate names that passed, or raises GateError."""
    passed = []

    # 0 - the art scale standard. Every atlas is drawn at 2x; a rig that drifts
    #     back to the old size, or a new atlas added at the wrong one, fails
    #     here rather than looking subtly chunky in the game.
    STANDARD = {"actors": 32, "actors_huge": 64, "tiles": 16, "props": 32,
                "props_big": 48, "props_huge": 64, "items": 16, "fx": 8}
    for name, meta in man["atlases"].items():
        w, h = meta["frame"]
        if w != h:
            _fail("art-scale", f"atlas {name!r} frame {w}x{h} is not square")
        want = STANDARD.get(name)
        if want is None:
            if w % 16:
                _fail("art-scale", f"new atlas {name!r} is {w}px; the standard is "
                                   f"a multiple of the 16px tile")
        elif w != want:
            _fail("art-scale", f"atlas {name!r} is {w}px, the standard is {want}px")
    passed.append("art-scale")

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
    # A hostile actor runs at the player and hurts them, so every number that
    # decides how it feels is required and has to be sane. A "sight" larger
    # than "lose" would make it give up the instant it noticed you, and a
    # "reach" it cannot close would make it harmless while looking dangerous -
    # both read as the boar being broken rather than as tuning.
    for cid, defn in content["actors"].items():
        h = defn.get("hostile")
        if not h:
            continue
        for field in ("sight", "lose", "charge_speed", "damage", "reach",
                      "cooldown_ms", "leash"):
            v = h.get(field)
            if not isinstance(v, (int, float)) or v <= 0:
                _fail("actor-hostile", f"{defn['_file']}: hostile.{field} must "
                                       f"be a positive number, not {v!r}")
        if h["lose"] < h["sight"]:
            _fail("actor-hostile", f"{defn['_file']}: hostile.lose ({h['lose']}) "
                                   f"is inside hostile.sight ({h['sight']}), so "
                                   f"it would drop the chase as it started it")
        if not defn.get("wander"):
            _fail("actor-hostile", f"{defn['_file']}: a hostile actor needs "
                                   f"\"wander\" too - chasing is a mode it "
                                   f"drops into, and it has to have something "
                                   f"to drop back to")
    passed.append("actor-hostile")
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

    # 5 - tiles repeat without a seam. The art pipeline runs this on the
    #     canvases it draws; the game build has no canvases and skips it.
    for tid, c in (tile_canvases or {}).items():
        for y in range(c.h):
            if c.px[y][0] is None or c.px[y][c.w - 1] is None:
                _fail("tile-seam", f"{tid}: transparent pixel on a vertical edge")
        for x in range(c.w):
            if c.px[0][x] is None or c.px[c.h - 1][x] is None:
                _fail("tile-seam", f"{tid}: transparent pixel on a horizontal edge")
    passed.append("tile-seam")

    # 6 - maps: rectangular grid, legend covers it, entities land in bounds
    all_claimed = {}                     # per map, the tiles solid things hold
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
        all_claimed[mid] = claimed
    passed.append("map-shape")
    passed.append("map-legend")
    passed.append("map-entity")
    passed.append("map-footprint")
    passed.append("map-overlap")
    passed.append("map-spawn")

    # 6bis - exits. A way off one map has to be standable at both ends, and it
    #        must not put you down on the way back: arriving on the return exit
    #        bounces the player through it again the moment they move, which
    #        looks like the two maps flickering rather than like a bug.
    # An edge-wide doorway is a seam between two maps, and the direction you
    # walk to reach it is the direction you are still walking when you arrive.
    # A doorway inland - a cave mouth, a stair - is exempt: there is no edge to
    # infer a direction from, so whatever it says goes.
    edge_facing = {"west": "left", "east": "right", "north": "up", "south": "down"}

    def _edge_of(mm, tiles_):
        w_, h_ = mm["size"]
        if all(t[0] == 0 for t in tiles_):
            return "west"
        if all(t[0] == w_ - 1 for t in tiles_):
            return "east"
        if all(t[1] == 0 for t in tiles_):
            return "north"
        if all(t[1] == h_ - 1 for t in tiles_):
            return "south"
        return None

    def _standable(mm, mid_, tx, ty):
        w_, h_ = mm["size"]
        if not (0 <= tx < w_ and 0 <= ty < h_):
            return "off the map"
        tid = mm["legend"][mm["ground"][ty][tx]]
        if not man["tiles"][tid]["walkable"]:
            return f"on {tid}"
        if (tx, ty) in all_claimed.get(mid_, {}):
            return f"inside {all_claimed[mid_][(tx, ty)]}"
        return None

    for mid, m in content["maps"].items():
        for i, ex in enumerate(m.get("exits") or []):
            where = f"{m['_file']}: exit {i}"
            tiles = ex.get("tiles")
            if not tiles:
                _fail("map-exit", f"{where} has no \"tiles\"")
            dest_id = ex.get("to")
            if dest_id not in content["maps"]:
                _fail("map-exit", f"{where} leads to unknown map {dest_id!r}")
            dest = content["maps"][dest_id]
            for tx, ty in tiles:
                why = _standable(m, mid, tx, ty)
                if why:
                    _fail("map-exit", f"{where}: doorway tile [{tx}, {ty}] is {why}")
            # One arrival for the whole doorway, or one per tile. An edge-wide
            # crossing uses the second so the player keeps their place along
            # the edge, and then every one of those arrivals has to be checked:
            # it is the row nobody walks through in testing that is off the map.
            spawns = ex.get("spawns")
            if spawns is None:
                if not ex.get("spawn"):
                    _fail("map-exit", f"{where} says where it goes but not "
                                      f"where you come in (\"spawn\")")
                spawns = [ex["spawn"]] * len(tiles)
            elif len(spawns) != len(tiles):
                _fail("map-exit", f"{where} has {len(tiles)} doorway tiles but "
                                  f"{len(spawns)} arrivals; they pair up by "
                                  f"position, so there must be one each")
            edge = _edge_of(m, tiles)
            if edge and ex.get("facing") and ex["facing"] != edge_facing[edge]:
                _fail("map-exit", f"{where} leaves by the {edge} edge, so the "
                                  f"player is walking {edge_facing[edge]} - but "
                                  f"arrives on {dest_id} facing {ex['facing']!r}, "
                                  f"spun round on the spot")
            back = {tuple(t) for b in (dest.get("exits") or []) for t in b["tiles"]}
            for door, spawn in zip(tiles, spawns):
                why = _standable(dest, dest_id, spawn[0], spawn[1])
                if why:
                    _fail("map-exit", f"{where}: {door} arrives at {spawn} on "
                                      f"{dest_id}, which is {why}")
                if tuple(spawn) in back:
                    _fail("map-exit", f"{where}: {door} arrives at {spawn} on "
                                      f"{dest_id}, which is itself an exit - "
                                      f"the player would be sent straight back")
    passed.append("map-exit")

    # 6a - the resolved grid: rectangular, and every index a real tile
    count = man["atlases"]["tiles"]["count"]
    for mid, m in man["maps"].items():
        grid = m.get("grid")
        if grid is None:
            _fail("map-grid", f"{mid}: no resolved grid")
        w, h = m["size"]
        if len(grid) != h or any(len(r) != w for r in grid):
            _fail("map-grid", f"{mid}: grid is not {w}x{h}")
        for row in grid:
            for i in row:
                if not (0 <= i < count):
                    _fail("map-grid", f"{mid}: tile index {i} outside the atlas")
    passed.append("map-grid")

    # 6b - a playable actor carries a whole stat block, or the sheet shows
    #      blanks that only surface when someone presses C.
    for cid, defn in content["actors"].items():
        if "display_name" not in defn:
            continue
        for field in ("level", "hp_max", "hp_per_level", "base_damage",
                      "xp_curve", "gear_slots"):
            if field not in defn:
                _fail("hero-stats", f"{defn['_file']}: {cid} has a display_name "
                                    f"but no {field!r}")
        curve = defn["xp_curve"]
        for k in ("base", "growth"):
            if not isinstance(curve.get(k), (int, float)) or curve[k] <= 0:
                _fail("hero-stats", f"{defn['_file']}: xp_curve.{k} must be a "
                                    f"positive number")
        for slot in defn["gear_slots"]:
            if not any(i.get("slot") == slot for i in content["items"].values()):
                _fail("hero-stats", f"{defn['_file']}: gear slot {slot!r} has no "
                                    f"item that fits it")
    passed.append("hero-stats")

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

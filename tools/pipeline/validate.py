"""The gates between the build and the engine.

Nothing reaches the game that has not been checked here. Each gate catches a
class of bug that costs minutes now and weeks at three hundred assets; a failure
always points at an authored file, never at generated output.
"""

import ast
import pathlib
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
    # (width, height). Everything here is square, and for a while that was the
    # rule rather than an observation. It is not enforced any more: a thing can
    # be taller than it is wide without being a mistake, so what is checked is
    # that both sides are whole 16px tiles.
    STANDARD = {"actors": (32, 32), "tiles": (16, 16), "props": (32, 32),
                "props_huge": (64, 64),
                "props_vast": (128, 128), "items": (16, 16), "fx": (8, 8)}
    for name, meta in man["atlases"].items():
        w, h = meta["frame"]
        want = STANDARD.get(name)
        if want is None:
            if w % 16 or h % 16:
                _fail("art-scale", f"new atlas {name!r} is {w}x{h}; the standard "
                                   f"is a whole number of 16px tiles each way")
        elif (w, h) != want:
            _fail("art-scale", f"atlas {name!r} is {w}x{h}, the standard is "
                               f"{want[0]}x{want[1]}")
    passed.append("art-scale")

    # 0a - the palette has one entry per key. A dict literal takes the last of
    #      a repeated key without a word, so a new colour that reuses a name
    #      silently repaints whatever had it - and the drawing that loses its
    #      colour is somewhere else entirely, which is the worst kind of bug to
    #      go looking for. "AR" was added for an arcane violet while it already
    #      meant the elk's rump patch, and nothing anywhere would have said so.
    #      Read from the source rather than the dict, because by then it is too
    #      late to tell.
    src = pathlib.Path(__file__).resolve().parents[1] / "gen" / "palette.py"
    for node in ast.walk(ast.parse(src.read_text())):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        if not any(getattr(t, "id", None) == "PALETTE" for t in node.targets):
            continue
        seen = set()
        for k in node.value.keys:
            if not isinstance(k, ast.Constant):
                continue
            if k.value in seen:
                _fail("palette-keys", f"gen/palette.py line {k.lineno}: "
                                      f"{k.value!r} is already a key; the later "
                                      f"colour would silently replace the first")
            seen.add(k.value)
    passed.append("palette-keys")

    # 1 - every ID is well formed and unique within its kind
    for kind, defs in content.items():
        for cid, defn in defs.items():
            if not ID_RE.match(cid):
                _fail("id-format", f"{defn['_file']}: bad id {cid!r}")
            if not cid.startswith(("tile.", "prop.", "actor.", "npc.",
                                   "item.", "dlg.", "quest.", "map.")):
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
        # "damage" used to live here. It is defn["attack"] now, because a
        # creature hits just as hard whether it is chasing you or standing
        # still, and having it under "hostile" meant nothing peaceful could
        # own a number at all.
        for field in ("sight", "lose", "charge_speed", "reach",
                      "cooldown_ms", "leash"):
            v = h.get(field)
            if not isinstance(v, (int, float)) or v <= 0:
                _fail("actor-hostile", f"{defn['_file']}: hostile.{field} must "
                                       f"be a positive number, not {v!r}")
        # "provoked" used to live here as a flag. It is defn["behaviour"] now,
        # which says the same thing in one word and leaves room for a third
        # answer - a creature that walks up and starts it.
        if "provoked" in h:
            _fail("actor-hostile", f"{defn['_file']}: hostile.provoked is gone - "
                                   f"say behaviour: \"defensive\" instead")
        if h["lose"] < h["sight"]:
            _fail("actor-hostile", f"{defn['_file']}: hostile.lose ({h['lose']}) "
                                   f"is inside hostile.sight ({h['sight']}), so "
                                   f"it would drop the chase as it started it")
        if not defn.get("walking"):
            _fail("actor-hostile", f"{defn['_file']}: a fighting actor has to "
                                   f"walk - chasing is a mode it drops into, "
                                   f"and it has to have something to drop "
                                   f"back to")
    passed.append("actor-hostile")
    # A creature dies only if its definition says how much it can take, so "hp"
    # is the one field that decides whether something is a hazard or a target.
    # Half an hp would leave a boar that survives every possible blow.
    for cid, defn in content["actors"].items():
        if "hp" not in defn:
            continue
        if not isinstance(defn["hp"], int) or isinstance(defn["hp"], bool) or defn["hp"] <= 0:
            _fail("actor-hp", f"{defn['_file']}: hp must be a positive whole "
                              f"number, not {defn['hp']!r}")
        if not defn.get("walking"):
            _fail("actor-hp", f"{defn['_file']}: {cid} has hp but does not walk "
                              f"- only a walking thing can be struck")
    passed.append("actor-hp")
    # Every actor carries the four numbers the editor shows, because a sheet
    # with blanks in it is worse than one with zeroes: zero attack says "does
    # not fight", a missing attack says nobody has decided yet.
    for cid, defn in content["actors"].items():
        d = defn.get("description")
        if not isinstance(d, str) or not d.strip():
            _fail("actor-stats", f"{defn['_file']}: needs a description")
        for field, low in (("level", 1), ("attack", 0), ("armor", 0)):
            v = defn.get(field)
            if not isinstance(v, int) or isinstance(v, bool) or v < low:
                _fail("actor-stats", f"{defn['_file']}: {field} must be a whole "
                                     f"number >= {low}, not {v!r}")
        # Armour is subtracted from every blow, so armour at or above what the
        # hero can swing would make a creature literally unkillable.
        if defn.get("armor", 0) >= 12:
            _fail("actor-stats", f"{defn['_file']}: armor {defn['armor']} is at "
                                 f"or above the heaviest blow in the game")
        # behaviour and the hostile block are two halves of one fact: the word
        # says whether it fights, the block says how far it sees and how hard
        # it presses. One without the other is a creature that cannot act.
        b = defn.get("behaviour")
        if b not in ("passive", "defensive", "offensive"):
            _fail("actor-stats", f"{defn['_file']}: behaviour must be passive, "
                                 f"defensive or offensive, not {b!r}")
        if b != "passive" and not defn.get("hostile"):
            _fail("actor-stats", f"{defn['_file']}: {b} but carries no "
                                 f"\"hostile\" block to chase with")
        if b == "passive" and defn.get("hostile"):
            _fail("actor-stats", f"{defn['_file']}: passive but carries a "
                                 f"\"hostile\" block that can never be used")
        if not isinstance(defn.get("walking"), bool):
            _fail("actor-stats", f"{defn['_file']}: walking is a flag - true or "
                                 f"false, not {defn.get('walking')!r}")
        r = defn.get("walk_radius")
        if not isinstance(r, int) or isinstance(r, bool) or r < 0:
            _fail("actor-stats", f"{defn['_file']}: walk_radius must be a whole "
                                 f"number >= 0, not {r!r}")
        if defn.get("walking") and r < 1:
            _fail("actor-stats", f"{defn['_file']}: it walks, so walk_radius has "
                                 f"to be at least 1 - at 0 it stands still")
        if not defn.get("walking") and r:
            _fail("actor-stats", f"{defn['_file']}: walk_radius {r} on something "
                                 f"that does not walk says nothing")
        if defn.get("walking") and not defn.get("wander"):
            _fail("actor-stats", f"{defn['_file']}: it walks but has no "
                                 f"\"wander\" timings to walk by")
        if defn.get("behaviour") != "passive" and defn.get("attack", 0) <= 0:
            _fail("actor-stats", f"{defn['_file']}: it is hostile but its attack "
                                 f"is {defn.get('attack')!r} - it would chase "
                                 f"the hero and never hurt them")
    passed.append("actor-stats")
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

    # 6c - tags. A zone is a tag its maps share, and the editor groups by it -
    # so a stray capital, a space, or a bare string where a list belongs
    # quietly splits one zone into two that read identically in the panel.
    for mid, m in content["maps"].items():
        tags = m.get("tags")
        if tags is None:
            continue
        if not isinstance(tags, list) or not tags:
            _fail("map-tags", f"{m['_file']}: \"tags\" is a list of names, "
                              f"not {tags!r}")
        for t in tags:
            if not isinstance(t, str) or not t or t != t.lower() or " " in t:
                _fail("map-tags", f"{m['_file']}: tag {t!r} should be one "
                                  f"lowercase word with no spaces")
        if len(set(tags)) != len(tags):
            _fail("map-tags", f"{m['_file']}: {tags} repeats a tag")
    passed.append("map-tags")

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
        # base_damage was this list's name for the hero's own contribution to
        # a blow; every actor carries "attack" now and the hero is an actor.
        for field in ("level", "hp_max", "hp_per_level", "attack",
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

    # A quest is the other thing a conversation can be waiting on, so the same
    # walk collects where each one is offered, handed in and asked about. What
    # it finds is checked by the quest gates below.
    QUEST_STATES = ("none", "active", "ready", "done")
    started, finished, quest_reads = {}, {}, {}

    def _quest_cond(cond, where):
        """The quest id a condition waits on, checking its shape as it goes."""
        q = cond.get("quest")
        if q is None:
            return None
        if not isinstance(q, dict) or not q.get("id"):
            _fail("dialogue-effects", f"{where}: a quest condition is "
                                      f"{{\"id\": ..., \"is\": ...}}, not {q!r}")
        want = q.get("is", "active")
        for state in ([want] if isinstance(want, str) else want):
            if state not in QUEST_STATES:
                _fail("dialogue-effects", f"{where}: quest state {state!r} is not "
                                          f"one of {', '.join(QUEST_STATES)}")
        return q["id"]

    set_flags = set()
    read_flags = {}
    for did, d in content["dialogue"].items():
        for nid, node in d["nodes"].items():
            for ch in node.get("choices") or []:
                where = f"{d['_file']}: {nid!r}"
                for key in ("set",):
                    if ch.get(key):
                        set_flags.add(ch[key])
                for key in ("give", "take"):
                    if ch.get(key) and ch[key] not in man["items"]:
                        _fail("dialogue-effects", f"{d['_file']}: {nid!r} {key}s "
                                                  f"unknown item {ch[key]!r}")
                for key, table in (("start", started), ("finish", finished)):
                    if ch.get(key):
                        table.setdefault(ch[key], []).append(where)
                for cond in _conds(ch):
                    for key in ("has", "nothas"):
                        if cond.get(key) and cond[key] not in man["items"]:
                            _fail("dialogue-effects",
                                  f"{d['_file']}: {nid!r} tests unknown item "
                                  f"{cond[key]!r}")
                    for key in ("flag", "noflag"):
                        if cond.get(key):
                            read_flags.setdefault(cond[key], where)
                    qid = _quest_cond(cond, where)
                    if qid:
                        quest_reads.setdefault(qid, where)
            for rule in _entry_rules(d):
                for cond in _conds(rule):
                    for key in ("flag", "noflag"):
                        if cond.get(key):
                            read_flags.setdefault(cond[key], f"{d['_file']}: start")
                    qid = _quest_cond(cond, f"{d['_file']}: start")
                    if qid:
                        quest_reads.setdefault(qid, f"{d['_file']}: start")
    # Finishing a quest sets its reward flag, so a conversation may wait on one
    # no choice mentions. Without this a reward flag reads as a dead branch.
    for q in content["quests"].values():
        if (q.get("reward") or {}).get("set"):
            set_flags.add(q["reward"]["set"])
    for flag, where in sorted(read_flags.items()):
        if flag not in set_flags:
            _fail("dialogue-effects", f"{where} waits on flag {flag!r}, which no "
                                      f"choice ever sets")
    passed.append("dialogue-effects")

    # 7c - quests. A quest is a contract between a conversation and the world:
    # something to do, somewhere it can be done, and someone to tell. Every way
    # it breaks is silent in game - a quest nobody can start, an errand for an
    # item that exists nowhere, a bounty on something that cannot die - so each
    # of those is a gate rather than something to find by playing it through.
    OBJ_KINDS = ("collect", "kill", "talk", "visit")
    for qid, q in content["quests"].items():
        where = q["_file"]
        for field in ("name", "summary", "objectives"):
            if not q.get(field):
                _fail("quest-shape", f"{where}: no {field!r}")
        if "auto" in q and not isinstance(q["auto"], bool):
            _fail("quest-shape", f"{where}: \"auto\" is a flag - true or false, "
                                 f"not {q['auto']!r}")
        if q.get("giver") and q["giver"] not in content["actors"]:
            _fail("quest-shape", f"{where}: giver {q['giver']!r} is not an actor")
        seen = set()
        for ob in q["objectives"]:
            oid = ob.get("id")
            if not oid or not isinstance(oid, str):
                _fail("quest-shape", f"{where}: an objective has no \"id\"")
            if oid in seen:
                _fail("quest-shape", f"{where}: two objectives are both {oid!r}; "
                                     f"progress is kept against that id")
            seen.add(oid)
            if not ob.get("text"):
                _fail("quest-shape", f"{where}: objective {oid!r} has no \"text\" "
                                     f"- the log would show a blank line")
            if ob.get("kind") not in OBJ_KINDS:
                _fail("quest-shape", f"{where}: objective {oid!r} is a "
                                     f"{ob.get('kind')!r}; the kinds are "
                                     f"{', '.join(OBJ_KINDS)}")
    passed.append("quest-shape")

    for qid, q in content["quests"].items():
        where = q["_file"]
        for ob in q["objectives"]:
            kind, target = ob["kind"], ob.get("target")
            table = {"collect": content["items"], "kill": content["actors"],
                     "talk": {**content["actors"], **content["props"]},
                     "visit": content["maps"]}[kind]
            if target not in table:
                _fail("quest-target", f"{where}: objective {ob['id']!r} is a "
                                      f"{kind} of {target!r}, which is not a "
                                      f"known {'definition' if kind != 'visit' else 'map'}")
            if kind in ("collect", "kill"):
                n = ob.get("count", 1)
                if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                    _fail("quest-target", f"{where}: objective {ob['id']!r} asks "
                                          f"for {n!r} of {target!r}")
            # Something the player is told to speak to has to have something to
            # say, and something they are told to kill has to be able to die.
            if kind == "talk" and not table[target].get("interact"):
                _fail("quest-target", f"{where}: objective {ob['id']!r} sends the "
                                      f"player to talk to {target!r}, which has "
                                      f"no \"interact\" and cannot be talked to")
            if kind == "kill" and not table[target].get("hp"):
                _fail("quest-target", f"{where}: objective {ob['id']!r} is a bounty "
                                      f"on {target!r}, which has no \"hp\" and so "
                                      f"can never be killed")
            if kind == "visit" and ob.get("tile"):
                tw, th = content["maps"][target]["size"]
                tx, ty = ob["tile"]
                if not (0 <= tx < tw and 0 <= ty < th):
                    _fail("quest-target", f"{where}: objective {ob['id']!r} points "
                                          f"at tile {ob['tile']} on {target}, "
                                          f"which is {tw}x{th}")
        r = q.get("reward") or {}
        if r.get("give") and r["give"] not in content["items"]:
            _fail("quest-reward", f"{where}: reward gives unknown item "
                                  f"{r['give']!r}")
        if "xp" in r and (not isinstance(r["xp"], int) or isinstance(r["xp"], bool)
                          or r["xp"] <= 0):
            _fail("quest-reward", f"{where}: reward xp must be a positive whole "
                                  f"number, not {r['xp']!r}")
        if "set" in r and not isinstance(r["set"], str):
            _fail("quest-reward", f"{where}: reward set must be a flag name, "
                                  f"not {r['set']!r}")
    passed.append("quest-target")
    passed.append("quest-reward")

    # The world has to be able to pay out what the quest asks for. "Fetch three
    # berries" where two exist is a quest that reads perfectly and cannot be
    # finished, and nothing else in the build would ever say so.
    placed = {}
    for m in content["maps"].values():
        for e in m["entities"]:
            placed[e["def"]] = placed.get(e["def"], 0) + 1
    handed = {ch["give"] for d in content["dialogue"].values()
              for node in d["nodes"].values()
              for ch in node.get("choices") or [] if ch.get("give")}
    handed |= {q["reward"]["give"] for q in content["quests"].values()
               if (q.get("reward") or {}).get("give")}
    for qid, q in content["quests"].items():
        where = q["_file"]
        for ob in q["objectives"]:
            if ob["kind"] == "visit":
                continue
            have = placed.get(ob["target"], 0)
            want = ob.get("count", 1)
            if ob["kind"] == "collect" and ob["target"] in handed:
                continue                       # a conversation hands it over
            if have < want:
                _fail("quest-supply", f"{where}: objective {ob['id']!r} needs "
                                      f"{want} x {ob['target']}, but the maps "
                                      f"place {have}")
    passed.append("quest-supply")

    # And someone has to be able to offer it, and - unless it finishes itself -
    # someone has to be able to take it back.
    for qid, where in sorted(quest_reads.items()):
        if qid not in content["quests"]:
            _fail("quest-reach", f"{where} waits on unknown quest {qid!r}")
    for table, verb in ((started, "start"), (finished, "finish")):
        for qid, wheres in sorted(table.items()):
            if qid not in content["quests"]:
                _fail("quest-reach", f"{wheres[0]} tries to {verb} unknown quest "
                                     f"{qid!r}")
    for qid, q in content["quests"].items():
        if qid not in started:
            _fail("quest-reach", f"{q['_file']}: no conversation ever starts "
                                 f"{qid} - it would sit in content and never "
                                 f"appear in the game")
        if not q.get("auto") and qid not in finished:
            _fail("quest-reach", f"{q['_file']}: no conversation ever finishes "
                                 f"{qid}, and it is not \"auto\" - the player "
                                 f"would complete every objective and never be "
                                 f"paid")
    passed.append("quest-reach")

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
    # What the editor lets you type, the build has to police.
    for iid, defn in content["items"].items():
        if not isinstance(defn.get("description"), str) or not defn["description"].strip():
            _fail("item-trade", f"{defn['_file']}: needs a description")
        price = defn.get("price")
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            _fail("item-trade", f"{defn['_file']}: price must be a whole number "
                                f">= 0, not {price!r}")
        for flag in ("stack", "consumable", "equippable"):
            if not isinstance(defn.get(flag), bool):
                _fail("item-trade", f"{defn['_file']}: {flag} is a flag - true or "
                                    f"false, not {defn.get(flag)!r}")
        # stack_max is only meaningful beside stack, and a cap of one is a
        # thing that does not stack wearing the wrong flag.
        if defn["stack"]:
            m = defn.get("stack_max")
            if not isinstance(m, int) or isinstance(m, bool) or m < 2:
                _fail("item-trade", f"{defn['_file']}: it stacks, so stack_max "
                                    f"must be a whole number >= 2, not {m!r}")
        elif "stack_max" in defn:
            _fail("item-trade", f"{defn['_file']}: stack_max beside stack:false "
                                f"says nothing - drop one of them")
        # Equippable and slot are two halves of one fact.
        if defn["equippable"] and not defn.get("slot"):
            _fail("item-trade", f"{defn['_file']}: equippable but has no slot to "
                                f"go in")
        if defn.get("slot") and not defn["equippable"]:
            _fail("item-trade", f"{defn['_file']}: it has a {defn['slot']!r} slot "
                                f"but is not marked equippable")
        if "note" in defn and (not isinstance(defn["note"], str) or not defn["note"].strip()):
            _fail("item-trade", f"{defn['_file']}: note is there but empty - "
                                f"leave it out instead")
    passed.append("item-trade")
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

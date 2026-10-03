"""Load authored content/ and merge it with the generated atlases.

The manifest is the single file the game loads. Definitions stay engine-neutral
JSON on disk; this turns them into one registry keyed by stable string IDs, so
nothing downstream ever refers to a sprite or a definition by position.
"""

import json
import os

KINDS = ("tiles", "props", "actors", "items", "dialogue", "quests", "maps")


def load_content(root):
    """{kind: {id: definition}} from content/<kind>/*.json."""
    out = {k: {} for k in KINDS}
    for kind in KINDS:
        d = os.path.join(root, "content", kind)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(d, fn), encoding="utf-8") as fh:
                defn = json.load(fh)
            defn["_file"] = f"content/{kind}/{fn}"
            out[kind][defn["id"]] = defn
    return out


def _prop(defn, sprites):
    """A prop record, plus how many drawings of it the art library holds.

    Counted off the sprite keys rather than declared in the content, because
    the drawings are what a variant actually is - a number in a JSON file that
    the art does not back would have the editor roll a variant nothing can
    draw."""
    out = _strip(defn)
    n = 1
    while f"{defn['sprite']}/v{n}" in sprites:
        n += 1
    out["variants"] = n
    return out


def build(content, atlases, sprites, anims, tileset=None, grids=None):
    """Assemble the manifest dict the engine consumes."""
    tiles = {}
    for i, (tid, defn) in enumerate(sorted(content["tiles"].items())):
        rec = sprites[defn["sprite"]]
        tiles[tid] = {
            "index": rec["index"],
            "walkable": bool(defn.get("walkable", True)),
            "material": defn.get("material", "none"),
            "family": defn.get("family", tid),
            "variants": (tileset or {}).get("variants", {}).get(tid, [rec["index"]]),
        }
    maps = {}
    for mid, defn in content["maps"].items():
        entry = _strip(defn)
        if grids and mid in grids:
            entry["grid"] = grids[mid]        # resolved by pipeline/autotile
        maps[mid] = entry
    return {
        "manifest_version": 1,
        "atlases": {a.name: a.meta() for a in atlases},
        "sprites": sprites,
        "anims": anims,
        "tiles": tiles,
        "props": {k: _prop(v, sprites) for k, v in content["props"].items()},
        "actors": {k: _strip(v) for k, v in content["actors"].items()},
        "items": {k: _strip(v) for k, v in content["items"].items()},
        "dialogue": {k: _strip(v) for k, v in content["dialogue"].items()},
        "quests": {k: _strip(v) for k, v in content["quests"].items()},
        "tileset": tileset or {},
        "maps": maps,
    }


def _strip(defn):
    return {k: v for k, v in defn.items() if not k.startswith("_")}

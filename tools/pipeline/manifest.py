"""Load authored content/ and merge it with the generated atlases.

The manifest is the single file the game loads. Definitions stay engine-neutral
JSON on disk; this turns them into one registry keyed by stable string IDs, so
nothing downstream ever refers to a sprite or a definition by position.
"""

import json
import os

KINDS = ("tiles", "props", "actors", "dialogue", "maps")


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


def build(content, atlases, sprites, anims):
    """Assemble the manifest dict the engine consumes."""
    tiles = {}
    for i, (tid, defn) in enumerate(sorted(content["tiles"].items())):
        rec = sprites[defn["sprite"]]
        tiles[tid] = {
            "index": rec["index"],
            "walkable": bool(defn.get("walkable", True)),
            "material": defn.get("material", "none"),
        }
    return {
        "manifest_version": 1,
        "atlases": {a.name: a.meta() for a in atlases},
        "sprites": sprites,
        "anims": anims,
        "tiles": tiles,
        "props": {k: _strip(v) for k, v in content["props"].items()},
        "actors": {k: _strip(v) for k, v in content["actors"].items()},
        "dialogue": {k: _strip(v) for k, v in content["dialogue"].items()},
        "maps": {k: _strip(v) for k, v in content["maps"].items()},
    }


def _strip(defn):
    return {k: v for k, v in defn.items() if not k.startswith("_")}

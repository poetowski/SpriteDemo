"""Build the game from the art library and the content.

    python tools/build.py

    assets/ (tools/art.py)  +  content/*.json
            |  resolve maps, assemble, validate
    build/manifest.json     one registry the engine and the editor read
    game/art-embed.js       the manifest plus the sheets as data URIs
    game/page.html          the whole game bundled into one shareable file

This build draws nothing. Art comes from assets/, where tools/art.py put it;
if the content names a sprite the library does not have, the fix is to run
the art pipeline, and the build says so. Nothing in build/ is hand-edited.
"""

import base64
import hashlib
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import make_page                                                     # noqa: E402
from pipeline import autotile, manifest as manifest_mod, validate    # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
BUILD = os.path.join(ROOT, "build")
GAME = os.path.join(ROOT, "game")
FULL = 255


class Sheet:
    """What manifest.build needs to know about an atlas: its name and meta."""

    def __init__(self, name, meta):
        self.name, self._meta = name, meta

    def meta(self):
        return dict(self._meta)


def load_library():
    path = os.path.join(ASSETS, "atlases.json")
    if not os.path.exists(path):
        sys.exit("[art-missing] assets/atlases.json not found - run python tools/art.py")
    with open(path, encoding="utf-8") as fh:
        lib = json.load(fh)
    for name, meta in lib["atlases"].items():
        if not os.path.exists(os.path.join(ASSETS, meta["image"])):
            sys.exit(f"[art-missing] assets/{meta['image']} not found - run python tools/art.py")
    return lib


def check_art_covers(content, lib):
    """Every sprite the content names must be in the library. This is the one
    failure whose fix is not in content/: it means the art is stale."""
    wanted = []
    for kind in ("tiles", "props", "items"):
        for defn in content[kind].values():
            wanted.append((defn["_file"], defn["sprite"], "sprites"))
    for defn in content["actors"].values():
        wanted.append((defn["_file"], f"{defn['sprite']}/idle/down", "anims"))
    for file, key, table in wanted:
        if key not in lib[table]:
            sys.exit(f"[art-stale] {file} names {key!r}, which assets/atlases.json "
                     f"does not have - run python tools/art.py")


# ------------------------------------------------------------------- main ---
def assemble():
    """Everything up to writing files; run twice to prove determinism."""
    content = manifest_mod.load_content(ROOT)
    lib = load_library()
    check_art_covers(content, lib)

    # A wielding actor's looks were worked out by the art pipeline; they ride
    # on the actor's own record so the engine can dress it by sprite swap.
    for aid, looks in lib.get("looks", {}).items():
        if aid in content["actors"]:
            content["actors"][aid]["looks"] = looks

    tiles = lib["tiles"]
    for tid, defn in content["tiles"].items():
        if tid not in tiles:
            sys.exit(f"[art-stale] {defn['_file']}: no tile art for {tid!r} - "
                     f"run python tools/art.py")

    def lookup(tid, x, y, mask):
        entry = tiles[tid]
        if mask != FULL and entry["masks"]:
            return entry["masks"][str(mask)]
        return entry["base"][autotile.pick_variant(x, y, len(entry["base"]))]

    grids = {mid: autotile.resolve(m, content["tiles"], lookup)
             for mid, m in content["maps"].items()}
    blocking = sorted(
        i for tid, e in tiles.items()
        if tid in content["tiles"] and not content["tiles"][tid].get("walkable", True)
        for i in list(e["base"]) + list(e["masks"].values())
        + [j for seq in e["anim"].values() for j in seq])
    tileset = {
        "blocking": blocking,
        "animated": {i: seq for e in tiles.values() for i, seq in e["anim"].items()},
        "anim_ms": lib["anim_ms"],
        "variants": {tid: e["base"] for tid, e in tiles.items()},
        "transitions": {tid: len(e["masks"]) for tid, e in tiles.items() if e["masks"]},
        # the full mask table, so the editor can resolve edges live exactly
        # the way the build does
        "masks": {tid: e["masks"] for tid, e in tiles.items() if e["masks"]},
        "standard": lib.get("standard", {}),
    }
    sheets = [Sheet(name, meta) for name, meta in lib["atlases"].items()]
    man = manifest_mod.build(content, sheets, lib["sprites"], lib["anims"],
                             tileset=tileset, grids=grids)
    return content, lib, man


def data_uri(path):
    with open(path, "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()


def write_embed(man, lib):
    images = {name: data_uri(os.path.join(ASSETS, meta["image"]))
              for name, meta in lib["atlases"].items()}
    cfg = {"manifest": man, "images": images}
    return ("// Generated by tools/build.py - do not edit.\n"
            "window.ART = " + json.dumps(cfg, separators=(",", ":")) + ";\n")


def main():
    content, lib, man = assemble()
    gates = validate.run(content, man, None)

    again = assemble()[2]
    if json.dumps(man, sort_keys=True) != json.dumps(again, sort_keys=True):
        sys.exit("[deterministic] two builds produced different manifests")
    gates.append("deterministic")

    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(GAME, exist_ok=True)
    with open(os.path.join(BUILD, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2)
    embed = write_embed(man, lib)
    with open(os.path.join(GAME, "art-embed.js"), "w", encoding="utf-8") as fh:
        fh.write(embed)
    make_page.build()

    n_defs = sum(len(v) for v in content.values())
    print(f"content   {n_defs} definitions from content/")
    print(f"art       assets/atlases.json: {len(lib['sprites'])} sprites, "
          f"{len(lib['anims'])} animations, {len(lib['atlases'])} atlases")
    for mid, m in content["maps"].items():
        w, h = m["size"]
        print(f"map       {mid}: {w}x{h}, {len(m['entities'])} entities, "
              f"{sum(1 for r in man['maps'][mid]['grid'] for i in r if str(i) in tileset_anim(man))} animated cells")
    for rel in ("build/manifest.json", "game/art-embed.js", "game/page.html"):
        print(f"  {rel:<22}{os.path.getsize(os.path.join(ROOT, rel)):>8} B")
    print(f"gates     {len(gates)} passed: {', '.join(gates)}")
    print(f"digest    {hashlib.md5(embed.encode()).hexdigest()[:12]}")


def tileset_anim(man):
    return man.get("tileset", {}).get("animated", {})


if __name__ == "__main__":
    main()

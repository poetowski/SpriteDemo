"""Build every art and data artifact for the game.

    python tools/build.py

    content/*.json  +  tools/gen/*.py
            |  generate
    build/atlas/*.png  +  build/manifest.json  +  build/aseprite/*.aseprite
            |  validate   (tools/pipeline/validate.py - all gates must pass)
    game/art-embed.js   the single file the game loads
    game/page.html      the whole game bundled into one shareable file

Nothing in build/ is hand-edited; delete it at any time and re-run. A gate
failure always points at an authored file in content/ or a generator.
"""

import base64
import hashlib
import io
import json
import os
import sys

from PIL import Image

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gen import (actor, animal, fx as fx_gen, items as items_gen,  # noqa: E402
                 props as props_gen, tiles as tiles_gen)
from gen.palette import PALETTE, VARIANTS, resolve                   # noqa: E402
import make_page                                                     # noqa: E402
from pipeline import aseprite, manifest as manifest_mod, validate    # noqa: E402
from pipeline.atlas import Atlas                                     # noqa: E402

BUILD = os.path.join(ROOT, "build")
GAME = os.path.join(ROOT, "game")
TAG_COLOR = (0x4f, 0xa5, 0x55)


# Rigs are interchangeable: same frame size, same anchor rule, same build_frames
# shape. Adding a species is a content field, not a pipeline change.
RIGS = {"biped": actor, "quadruped": animal}


# ------------------------------------------------------------- generation ---
def build_atlases(sprite_rigs):
    """sprite_rigs: {sprite_key: (rig_name, variant)}."""
    actors = Atlas("actors", actor.FRAME, actor.FRAME, 6)
    anims = {}
    by_sprite = {}
    for sprite_key, (rig_name, variant, states, held, worn) in sorted(sprite_rigs.items()):
        rig = RIGS[rig_name]
        pal = resolve(variant)
        frames = rig.build_frames(variant, states, held, worn)
        by_sprite[sprite_key] = (rig_name, variant, frames)
        for state, facing, i, cel, shadow, ms, loops in frames:
            base = f"{sprite_key}/{state}/{facing}"
            idx = actors.add(f"{base}/{i}", [shadow, cel], rig.ANCHOR, ms, pal)
            anims.setdefault(base, {"atlas": "actors", "frames": [], "ms": ms,
                                    "loop": loops})
            anims[base]["frames"].append(idx)

    tiles = Atlas("tiles", tiles_gen.SIZE, tiles_gen.SIZE, 8)
    tile_canvases = {}
    for tid, canvas in tiles_gen.build_tiles():
        tiles.add(tid, [canvas], (0, 0))
        tile_canvases[tid] = canvas

    # ART SCALE. Rigs redrawn natively at the 2x standard pass their canvases
    # through untouched; the ones still waiting are blown up here, in one
    # visible place, so it is never a mystery which is which.

    props = Atlas("props", actor.FRAME, actor.FRAME, 8)
    prop_canvases = {}
    for pid, canvas in props_gen.build_props():
        props.add(pid, [canvas], actor.ANCHOR)      # arrives at 2x already
        prop_canvases[pid] = canvas

    # Structures need more than the actor's frame, so they get their own sheet.
    # Nothing downstream cares: a sprite record carries its atlas and its
    # anchor, and the engine reads the frame size off the atlas.
    big = Atlas("props_big", props_gen.BIG_FRAME * 2, props_gen.BIG_FRAME * 2, 4)
    big_canvases = {}
    big_anchor = (props_gen.BIG_ANCHOR[0] * 2, props_gen.BIG_ANCHOR[1] * 2)
    for pid, canvas in props_gen.build_big_props():
        big.add(pid, [canvas], big_anchor)          # arrives at 2x already
        big_canvases[pid] = canvas

    # Items are 16x16: the same cell lies on the ground and sits in the HUD.
    items = Atlas("items", items_gen.SIZE, items_gen.SIZE, 8)
    item_canvases = {}
    for iid, canvas in items_gen.build_items():
        items.add(iid, [canvas], items_gen.ANCHOR)
        item_canvases[iid] = canvas

    # Effect glyphs: the digits a hit floats up, and the spark round them.
    fx = Atlas("fx", fx_gen.SIZE, fx_gen.SIZE, 11)
    fx_canvases = {}
    for gid, canvas in fx_gen.build_fx():
        fx.add(gid, [canvas], fx_gen.ANCHOR)
        fx_canvases[gid] = canvas

    sheets = [actors, tiles, props, big, items, fx]
    sprites = {}
    for a in sheets:
        sprites.update(a.sprites())
    return (sheets, sprites, anims, tile_canvases,
            {"props": prop_canvases, "props_big": big_canvases,
             "items": item_canvases, "fx": fx_canvases}, by_sprite)


# ---------------------------------------------------------------- exports ---
def write_aseprite(by_sprite, tile_canvases, prop_canvases):
    """Layered, tagged sources - the hand-editing escape hatch."""
    out = os.path.join(BUILD, "aseprite")
    os.makedirs(out, exist_ok=True)
    written = []

    for sprite_key, (rig_name, variant, frames) in sorted(by_sprite.items()):
        rig = RIGS[rig_name]
        tags = []                          # one tag per run of state-facing,
        for i, (state, facing, *_rest) in enumerate(frames):   # read off the
            name = f"{state}-{facing}"     # frames, so a frame set with slash
            if tags and tags[-1][0] == name:                   # and one without
                tags[-1] = (name, tags[-1][1], i, TAG_COLOR)   # both tag right
            else:
                tags.append((name, i, i, TAG_COLOR))
        pal = resolve(variant)
        path = os.path.join(out, f"{sprite_key.replace('.', '_')}.aseprite")
        aseprite.write(
            path, rig.FRAME, rig.FRAME, ["shadow", "actor"],
            [([s.rgba_bytes(pal), c.rgba_bytes(pal)], ms)
             for _st, _f, _i, c, s, ms, _loop in frames],
            [(pal[k], name) for k, (_rgba, name) in PALETTE.items()],
            tags,
        )
        _verify_ase(path, len(frames), ["shadow", "actor"], len(tags))
        written.append(path)

    for name, canvases, size in (
            ("tiles", tile_canvases, tiles_gen.SIZE),
            ("props", prop_canvases["props"], actor.FRAME),
            ("props_big", prop_canvases["props_big"], props_gen.BIG_FRAME * 2),
            ("items", prop_canvases["items"], items_gen.SIZE),
            ("fx", prop_canvases["fx"], fx_gen.SIZE)):
        path = os.path.join(out, f"{name}.aseprite")
        items = list(canvases.items())
        aseprite.write(
            path, size, size, [name],
            [([c.rgba_bytes()], 100) for _k, c in items],
            [(rgba, n) for rgba, n in PALETTE.values()],
            [(k, i, i, TAG_COLOR) for i, (k, _c) in enumerate(items)],
        )
        _verify_ase(path, len(items), [name], len(items))
        written.append(path)
    return written


def _verify_ase(path, n_frames, layers, n_tags):
    """Parse back what we just wrote - the round trip is the proof."""
    doc = aseprite.read(path)
    assert doc["layers"] == layers, (path, doc["layers"])
    assert len(doc["frames"]) == n_frames, (path, len(doc["frames"]))
    assert len(doc["tags"]) == n_tags, (path, len(doc["tags"]))


def write_preview(sheets):
    """One contact sheet, 4x, for eyeballing everything the build produced."""
    zoom, pad = 4, 10
    imgs = [a.render() for a in sheets]
    w = max(i.width for i in imgs) * zoom + pad * 2
    h = sum(i.height for i in imgs) * zoom + pad * (len(imgs) + 1)
    out = Image.new("RGBA", (w, h), (0x9a, 0xa2, 0xaa, 255))
    y = pad
    for img in imgs:
        big = img.resize((img.width * zoom, img.height * zoom), Image.NEAREST)
        out.alpha_composite(big, (pad, y))
        y += big.height + pad
    return out


def data_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def write_embed(man, sheets):
    cfg = {"manifest": man,
           "images": {a.name: data_uri(a.render()) for a in sheets}}
    return ("// Generated by tools/build.py - do not edit.\n"
            "window.ART = " + json.dumps(cfg, separators=(",", ":")) + ";\n")


# ------------------------------------------------------------------- main ---
def assemble():
    """Everything up to writing files; returned twice to prove determinism."""
    content = manifest_mod.load_content(ROOT)
    sprite_rigs = {}
    for d in content["actors"].values():
        rig_name = d.get("rig", "biped")
        variant = d["sprite"].split(".", 1)[1]
        if rig_name not in RIGS:
            sys.exit(f"[rig] {d['_file']}: unknown rig {rig_name!r}")
        if variant not in VARIANTS:
            sys.exit(f"[variant] {d['_file']}: sprite {d['sprite']!r} has no "
                     f"palette variant {variant!r} in tools/gen/palette.py")
        sprite_rigs[d["sprite"]] = (rig_name, variant, d.get("states"), None, None)
        if not d.get("wields"):
            continue
        # One frame set per look: every weapon the rig can draw crossed with
        # every armour, plus none of each. The engine dresses and arms a
        # character by switching sprite base and nothing else, so the map from
        # "<weapon>|<armor>" to sprite is written into the actor's own record.
        rig = RIGS[rig_name]
        weapons, armours = [(None, "")], [(None, "")]
        for iid, item in sorted(content["items"].items()):
            if item.get("held"):
                if item["held"] not in getattr(rig, "WEAPONS", {}):
                    sys.exit(f"[item-held] {item['_file']}: the {rig_name} rig has "
                             f"no drawing for {item['held']!r}")
                weapons.append((item["held"], iid))
            if item.get("worn"):
                if item["worn"] not in getattr(rig, "ARMOURS", {}):
                    sys.exit(f"[item-held] {item['_file']}: the {rig_name} rig has "
                             f"no drawing for {item['worn']!r}")
                armours.append((item["worn"], iid))
        d["looks"] = {}
        for held, wid in weapons:
            for worn, aid in armours:
                key = d["sprite"] + (f"_{held}" if held else "") + (f"_{worn}" if worn else "")
                sprite_rigs[key] = (rig_name, variant, d.get("states"), held, worn)
                d["looks"][f"{wid}|{aid}"] = key
    sheets, sprites, anims, tile_canvases, prop_canvases, by_sprite = \
        build_atlases(sprite_rigs)
    man = manifest_mod.build(content, sheets, sprites, anims)
    return content, sprite_rigs, sheets, man, tile_canvases, prop_canvases, by_sprite


def main():
    content, sprite_rigs, sheets, man, tile_canvases, prop_canvases, by_sprite = assemble()

    gates = validate.run(content, man, tile_canvases)

    # determinism gate: a second pass must produce byte-identical output
    again = assemble()[3]
    if json.dumps(man, sort_keys=True) != json.dumps(again, sort_keys=True):
        sys.exit("[deterministic] two builds produced different manifests")
    gates.append("deterministic")

    os.makedirs(os.path.join(BUILD, "atlas"), exist_ok=True)
    os.makedirs(GAME, exist_ok=True)
    for a in sheets:
        a.render().save(os.path.join(BUILD, "atlas", f"{a.name}.png"), optimize=True)
    with open(os.path.join(BUILD, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2)
    ase = write_aseprite(by_sprite, tile_canvases, prop_canvases)
    write_preview(sheets).save(os.path.join(BUILD, "preview.png"))
    embed = write_embed(man, sheets)
    with open(os.path.join(GAME, "art-embed.js"), "w", encoding="utf-8") as fh:
        fh.write(embed)

    page, page_size = make_page.build()

    n_defs = sum(len(v) for v in content.values())
    print(f"content   {n_defs} definitions from content/")
    rigs = ", ".join(f"{k.split('.')[1]}[{v[0]}]" for k, v in sorted(sprite_rigs.items()))
    print(f"actors    {rigs}")
    for a in sheets:
        p = os.path.join(BUILD, "atlas", f"{a.name}.png")
        print(f"  atlas/{a.name + '.png':<14}{os.path.getsize(p):>8} B  "
              f"{a.cols * a.fw}x{a.rows * a.fh}, {len(a.entries)} frames")
    for p in ase:
        print(f"  aseprite/{os.path.basename(p):<18}{os.path.getsize(p):>8} B"
              f"  [round-trip verified]")
    for rel in ("build/manifest.json", "build/preview.png", "game/art-embed.js",
                "game/page.html"):
        print(f"  {rel:<27}{os.path.getsize(os.path.join(ROOT, rel)):>8} B")
    print(f"gates     {len(gates)} passed: {', '.join(gates)}")
    print(f"digest    {hashlib.md5(embed.encode()).hexdigest()[:12]}")


if __name__ == "__main__":
    main()

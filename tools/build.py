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

from gen import actor, props as props_gen, tiles as tiles_gen        # noqa: E402
from gen.palette import PALETTE, VARIANTS, resolve                   # noqa: E402
import make_page                                                     # noqa: E402
from pipeline import aseprite, manifest as manifest_mod, validate    # noqa: E402
from pipeline.atlas import Atlas                                     # noqa: E402

BUILD = os.path.join(ROOT, "build")
GAME = os.path.join(ROOT, "game")
TAG_COLOR = (0x4f, 0xa5, 0x55)


# ------------------------------------------------------------- generation ---
def build_atlases(variants):
    """Returns (atlases, sprites, anims, tile_canvases)."""
    actors = Atlas("actors", actor.FRAME, actor.FRAME, 6)
    anims = {}
    frames = actor.build_frames()
    for variant in variants:
        pal = resolve(variant)
        for state, facing, i, cel, shadow, ms in frames:
            base = f"actor.{variant}/{state}/{facing}"
            idx = actors.add(f"{base}/{i}", [shadow, cel], actor.ANCHOR, ms, pal)
            anims.setdefault(base, {"atlas": "actors", "frames": [], "ms": ms})
            anims[base]["frames"].append(idx)

    tiles = Atlas("tiles", tiles_gen.SIZE, tiles_gen.SIZE, 8)
    tile_canvases = {}
    for tid, canvas in tiles_gen.build_tiles():
        tiles.add(tid, [canvas], (0, 0))
        tile_canvases[tid] = canvas

    props = Atlas("props", actor.FRAME, actor.FRAME, 8)
    prop_canvases = {}
    for pid, canvas in props_gen.build_props():
        props.add(pid, [canvas], actor.ANCHOR)
        prop_canvases[pid] = canvas

    sheets = [actors, tiles, props]
    sprites = {}
    for a in sheets:
        sprites.update(a.sprites())
    return sheets, sprites, anims, tile_canvases, prop_canvases, frames


# ---------------------------------------------------------------- exports ---
def write_aseprite(variants, frames, tile_canvases, prop_canvases):
    """Layered, tagged sources - the hand-editing escape hatch."""
    out = os.path.join(BUILD, "aseprite")
    os.makedirs(out, exist_ok=True)
    written = []

    tags, i = [], 0
    for facing in actor.FACINGS:
        for state in actor.STATE_ORDER:
            n = len(actor.STATES[state][0])
            tags.append((f"{state}-{facing}", i, i + n - 1, TAG_COLOR))
            i += n

    for variant in variants:
        pal = resolve(variant)
        path = os.path.join(out, f"actor_{variant}.aseprite")
        aseprite.write(
            path, actor.FRAME, actor.FRAME, ["shadow", "actor"],
            [([s.rgba_bytes(pal), c.rgba_bytes(pal)], ms)
             for _st, _f, _i, c, s, ms in frames],
            [(pal[k], name) for k, (_rgba, name) in PALETTE.items()],
            tags,
        )
        _verify_ase(path, len(frames), ["shadow", "actor"], len(tags))
        written.append(path)

    for name, canvases, size in (("tiles", tile_canvases, tiles_gen.SIZE),
                                 ("props", prop_canvases, actor.FRAME)):
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
    variants = sorted({d["sprite"].split(".", 1)[1]
                       for d in content["actors"].values()})
    for v in variants:
        if v not in VARIANTS:
            sys.exit(f"[variant] actor sprite 'actor.{v}' has no palette variant "
                     f"in tools/gen/palette.py")
    sheets, sprites, anims, tile_canvases, prop_canvases, frames = \
        build_atlases(variants)
    man = manifest_mod.build(content, sheets, sprites, anims)
    return content, variants, sheets, man, tile_canvases, prop_canvases, frames


def main():
    content, variants, sheets, man, tile_canvases, prop_canvases, frames = assemble()

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
    ase = write_aseprite(variants, frames, tile_canvases, prop_canvases)
    write_preview(sheets).save(os.path.join(BUILD, "preview.png"))
    embed = write_embed(man, sheets)
    with open(os.path.join(GAME, "art-embed.js"), "w", encoding="utf-8") as fh:
        fh.write(embed)

    page, page_size = make_page.build()

    n_defs = sum(len(v) for v in content.values())
    print(f"content   {n_defs} definitions from content/")
    print(f"variants  {', '.join(variants)}  (palette swaps of one rig)")
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

"""Generate the art library.

    python tools/art.py

    content/*.json (what exists)  +  tools/gen/*.py (how it is drawn)
            |  generate, pack, verify
    assets/atlases/*.png         the sheets, one per kind
    assets/atlases.json          every sprite's atlas, index and anchor; every
                                 animation; the tile index (variants,
                                 transitions, phases); each wielding actor's
                                 looks - everything the game build needs
    assets/aseprite/*.aseprite   layered, tagged sources
    assets/preview.png           a contact sheet of the lot

This is the art pipeline, and it is the only thing that knows about rigs,
palettes and generators. The game build (tools/build.py) consumes this library
and knows none of that. Art regenerates only when you run this, so an art
change is a deliberate, reviewable commit of assets/ rather than a side effect
of every build - and the map editor can load the same sheets the game does.

Every kind of art goes through the same steps: a generator draws canvases,
an Atlas packs them and records anchors, the .aseprite writer keeps a source,
and the same checks run - seams on tiles, a round trip on every .aseprite, and
a second full generation that must match the first byte for byte.
"""

import hashlib
import io
import json
import os
import sys

from PIL import Image

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gen import (actor, animal, fx as fx_gen, giant,              # noqa: E402
                 items as items_gen, props as props_gen, tiles as tiles_gen)
from gen.palette import PALETTE, VARIANTS, resolve                   # noqa: E402
from pipeline import aseprite                                        # noqa: E402
from pipeline.atlas import Atlas                                     # noqa: E402
from pipeline.manifest import load_content                           # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
TAG_COLOR = (0x4f, 0xa5, 0x55)

# Rigs are interchangeable: same anchor rule, same build_frames shape. Adding a
# species is a content field, not a pipeline change. A rig names the sheet it
# belongs on, so a rig too big for the 32x32 frame gets a sheet of its own
# rather than padding every hero frame out to the size of the largest thing in
# the game.
RIGS = {"biped": actor, "quadruped": animal, "giant": giant}


# ------------------------------------------------------------ what to draw ---
def sprite_rigs_from(content):
    """Which frame sets exist, from the content: one per actor sprite, plus one
    per weapon-and-armour look for every actor that wields. Returns the sets
    and, per wielding actor, the map from "<weapon>|<armor>" to sprite key."""
    sprite_rigs, looks = {}, {}
    for aid, d in content["actors"].items():
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
        looks[aid] = {}
        for held, wid in weapons:
            for worn, wear_id in armours:
                key = d["sprite"] + (f"_{held}" if held else "") + (f"_{worn}" if worn else "")
                sprite_rigs[key] = (rig_name, variant, d.get("states"), held, worn)
                looks[aid][f"{wid}|{wear_id}"] = key
    return sprite_rigs, looks


# ------------------------------------------------------------- generation ---
def build_atlases(sprite_rigs, content):
    # One sheet per actor frame size, made when the first sprite needs it: a
    # 64px giant on the 32px sheet would mean padding every frame in the game
    # to 64, and the sheet is loaded as a grid of one frame size.
    actor_sheets = {}
    anims = {}
    by_sprite = {}
    for sprite_key, (rig_name, variant, states, held, worn) in sorted(sprite_rigs.items()):
        rig = RIGS[rig_name]
        sheet = actor_sheets.get(rig.ATLAS)
        if sheet is None:
            sheet = actor_sheets[rig.ATLAS] = Atlas(rig.ATLAS, rig.FRAME,
                                                    rig.FRAME, rig.COLS)
        pal = resolve(variant)
        frames = rig.build_frames(variant, states, held, worn)
        by_sprite[sprite_key] = (rig_name, variant, frames)
        for state, facing, i, cel, shadow, ms, loops in frames:
            base = f"{sprite_key}/{state}/{facing}"
            idx = sheet.add(f"{base}/{i}", [shadow, cel], rig.ANCHOR, ms, pal)
            anims.setdefault(base, {"atlas": sheet.name, "frames": [], "ms": ms,
                                    "loop": loops})
            anims[base]["frames"].append(idx)

    # Tiles: every base in each of its seeded variants, then - for tiles the
    # content marks `blend` - the 47 transition arrangements, each in every
    # phase if the tile animates. The map build resolves cells against this.
    tiles = Atlas("tiles", tiles_gen.SIZE, tiles_gen.SIZE, 16)
    tile_canvases = {}
    tile_index = {}
    for tid in tiles_gen.TILE_ORDER:
        defn = content["tiles"].get(tid)
        if defn is None:
            continue                      # drawn but not defined: not shipped
        entry = {"base": [], "masks": {}, "anim": {}}
        phases = tiles_gen.ANIMATED.get(tid, 1)

        def add_frames(key, draw, entry=entry, phases=phases):
            first_canvas = draw(0)
            first = tiles.add(key, [first_canvas], (0, 0))
            tile_canvases[key] = first_canvas
            if phases > 1:
                seq = [first]
                for ph in range(1, phases):
                    cp = draw(ph)
                    seq.append(tiles.add(f"{key}/f{ph}", [cp], (0, 0)))
                    tile_canvases[f"{key}/f{ph}"] = cp
                entry["anim"][first] = seq
            return first

        for v in range(tiles_gen.VARIANTS.get(tid, 1)):
            key = tid if v == 0 else f"{tid}/v{v}"
            entry["base"].append(
                add_frames(key, lambda ph, v=v: tiles_gen.frame(tid, v, ph)))
        if defn.get("blend"):
            under = defn.get("blend_over", tiles_gen.BLEND_OVER)
            if under not in tiles_gen.BASE:
                sys.exit(f"[tile-blend] {defn['_file']}: blend_over names "
                         f"{under!r}, which has no drawing")
            if tid not in tiles_gen.STYLE:
                sys.exit(f"[tile-blend] {defn['_file']}: blend is set but "
                         f"tools/gen/tiles.py has no edge style for {tid!r}")
            for mask in tiles_gen.ALL_MASKS:
                if mask == tiles_gen.FULL:
                    continue
                entry["masks"][mask] = add_frames(
                    f"{tid}/m{mask}",
                    lambda ph, m=mask: tiles_gen.blend(tid, m, ph, under))
        tile_index[tid] = entry

    # Props. Most are one frame; the few that move get the rest of theirs
    # added after, and an animation naming them. The first frame keeps the
    # plain id as its key, so everything that only wants a picture of the
    # thing - the editor palette, the sprite-exists gate - is unaffected.
    def add_props(sheet, table, anchor, animated):
        canvases = {}
        for pid in table:
            frames = props_gen.prop_frames(pid, table)
            idx = sheet.add(pid, [frames[0]], anchor)
            canvases[pid] = frames[0]
            if len(frames) == 1:
                continue
            indices = [idx]
            for ph, cel in enumerate(frames[1:], start=1):
                indices.append(sheet.add(f"{pid}/{ph}", [cel], anchor))
                canvases[f"{pid}/{ph}"] = cel
            anims[pid] = {"atlas": sheet.name, "frames": indices,
                          "ms": animated[pid][1], "loop": True}
        return canvases

    props = Atlas("props", actor.FRAME, actor.FRAME, 8)
    prop_canvases = add_props(props, props_gen.PROPS, actor.ANCHOR,
                              props_gen.ANIMATED)

    big = Atlas("props_big", props_gen.BIG_FRAME, props_gen.BIG_FRAME, 4)
    big_anchor = props_gen.BIG_ANCHOR
    big_canvases = add_props(big, props_gen.BIG_PROPS, big_anchor,
                             props_gen.ANIMATED_BIG)

    huge = Atlas("props_huge", props_gen.HUGE_FRAME, props_gen.HUGE_FRAME, 2)
    huge_canvases = {}
    for pid, canvas in props_gen.build_huge_props():
        huge.add(pid, [canvas], props_gen.HUGE_ANCHOR)
        huge_canvases[pid] = canvas

    vast = Atlas("props_vast", props_gen.VAST_FRAME, props_gen.VAST_FRAME, 2)
    vast_canvases = {}
    for pid, canvas in props_gen.build_vast_props():
        vast.add(pid, [canvas], props_gen.VAST_ANCHOR)
        vast_canvases[pid] = canvas

    items = Atlas("items", items_gen.SIZE, items_gen.SIZE, 8)
    item_canvases = {}
    for iid, canvas in items_gen.build_items():
        items.add(iid, [canvas], items_gen.ANCHOR)
        item_canvases[iid] = canvas

    fx = Atlas("fx", fx_gen.SIZE, fx_gen.SIZE, 11)
    fx_canvases = {}
    for gid, canvas in fx_gen.build_fx():
        fx.add(gid, [canvas], fx_gen.ANCHOR)
        fx_canvases[gid] = canvas

    sheets = [*actor_sheets.values(), tiles, props, big, huge, vast, items, fx]
    sprites = {}
    for a in sheets:
        sprites.update(a.sprites())
    others = {"props": prop_canvases, "props_big": big_canvases,
              "props_huge": huge_canvases, "props_vast": vast_canvases,
              "items": item_canvases, "fx": fx_canvases}
    return tile_index, sheets, sprites, anims, tile_canvases, others, by_sprite


# ----------------------------------------------------------------- checks ---
def seam_check(tile_canvases):
    """A tile with a transparent edge pixel shows a seam when it repeats."""
    for key, c in tile_canvases.items():
        for y in range(c.h):
            if c.px[y][0] is None or c.px[y][c.w - 1] is None:
                sys.exit(f"[tile-seam] {key}: transparent pixel on a vertical edge")
        for x in range(c.w):
            if c.px[0][x] is None or c.px[c.h - 1][x] is None:
                sys.exit(f"[tile-seam] {key}: transparent pixel on a horizontal edge")


def _verify_ase(path, n_frames, layers, n_tags):
    doc = aseprite.read(path)
    assert doc["layers"] == layers, (path, doc["layers"])
    assert len(doc["frames"]) == n_frames, (path, len(doc["frames"]))
    assert len(doc["tags"]) == n_tags, (path, len(doc["tags"]))


# ---------------------------------------------------------------- exports ---
def write_aseprite(by_sprite, tile_canvases, others):
    out = os.path.join(ASSETS, "aseprite")
    os.makedirs(out, exist_ok=True)
    written = []
    for sprite_key, (rig_name, variant, frames) in sorted(by_sprite.items()):
        rig = RIGS[rig_name]
        tags = []
        for i, (state, facing, *_rest) in enumerate(frames):
            name = f"{state}-{facing}"
            if tags and tags[-1][0] == name:
                tags[-1] = (name, tags[-1][1], i, TAG_COLOR)
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
            ("props", others["props"], actor.FRAME),
            ("props_big", others["props_big"], props_gen.BIG_FRAME),
            ("props_huge", others["props_huge"], props_gen.HUGE_FRAME),
            ("props_vast", others["props_vast"], props_gen.VAST_FRAME),
            ("items", others["items"], items_gen.SIZE),
            ("fx", others["fx"], fx_gen.SIZE)):
        path = os.path.join(out, f"{name}.aseprite")
        entries = list(canvases.items())
        aseprite.write(
            path, size, size, [name],
            [([c.rgba_bytes()], 100) for _k, c in entries],
            [(rgba, n) for rgba, n in PALETTE.values()],
            [(k, i, i, TAG_COLOR) for i, (k, _c) in enumerate(entries)],
        )
        _verify_ase(path, len(entries), [name], len(entries))
        written.append(path)
    return written


def write_preview(sheets):
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


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def library(sheets, sprites, anims, tile_index, looks):
    return {
        "art_version": 1,
        "standard": {"tile": tiles_gen.SIZE, "actor": actor.FRAME,
                     "giant": giant.FRAME, "prop": actor.FRAME,
                     "structure": props_gen.BIG_FRAME,
                     "erratic": props_gen.VAST_FRAME,
                     "item": items_gen.SIZE, "fx": fx_gen.SIZE},
        "atlases": {a.name: {**a.meta(), "image": f"atlases/{a.name}.png"}
                    for a in sheets},
        "sprites": sprites,
        "anims": anims,
        "tiles": {tid: {"base": e["base"],
                        "masks": {str(m): i for m, i in e["masks"].items()},
                        "anim": {str(i): seq for i, seq in e["anim"].items()}}
                  for tid, e in tile_index.items()},
        "anim_ms": tiles_gen.ANIM_MS,
        "looks": looks,
    }


# ------------------------------------------------------------------- main ---
def generate(content):
    sprite_rigs, looks = sprite_rigs_from(content)
    tile_index, sheets, sprites, anims, tile_canvases, others, by_sprite = \
        build_atlases(sprite_rigs, content)
    lib = library(sheets, sprites, anims, tile_index, looks)
    pngs = {a.name: png_bytes(a.render()) for a in sheets}
    return lib, pngs, sheets, tile_canvases, others, by_sprite, sprite_rigs


def main():
    content = load_content(ROOT)
    lib, pngs, sheets, tile_canvases, others, by_sprite, sprite_rigs = generate(content)
    seam_check(tile_canvases)

    # Determinism: a second generation must match the first byte for byte, so
    # an art commit is only ever a real change and never a rerun.
    lib2, pngs2 = generate(content)[:2]
    if json.dumps(lib, sort_keys=True) != json.dumps(lib2, sort_keys=True) or pngs != pngs2:
        sys.exit("[deterministic] two generations differ")

    os.makedirs(os.path.join(ASSETS, "atlases"), exist_ok=True)
    for name, data in pngs.items():
        with open(os.path.join(ASSETS, "atlases", f"{name}.png"), "wb") as fh:
            fh.write(data)
    with open(os.path.join(ASSETS, "atlases.json"), "w", encoding="utf-8") as fh:
        json.dump(lib, fh, indent=1)
    ase = write_aseprite(by_sprite, tile_canvases, others)
    write_preview(sheets).save(os.path.join(ASSETS, "preview.png"))

    rigs = ", ".join(f"{k.split('.')[1]}[{v[0]}]" for k, v in sorted(sprite_rigs.items()))
    print(f"actors    {rigs}")
    for a in sheets:
        print(f"  atlases/{a.name + '.png':<14}{len(pngs[a.name]):>8} B  "
              f"{a.cols * a.fw}x{a.rows * a.fh}, {len(a.entries)} frames")
    for p in ase:
        print(f"  aseprite/{os.path.basename(p):<22}{os.path.getsize(p):>8} B  [round-trip verified]")
    lib_path = os.path.join(ASSETS, "atlases.json")
    print(f"  atlases.json{'':<12}{os.path.getsize(lib_path):>8} B  "
          f"{len(lib['sprites'])} sprites, {len(lib['anims'])} animations")
    print("checks    tile-seam, aseprite round-trip, deterministic")
    print(f"digest    {hashlib.md5(json.dumps(lib, sort_keys=True).encode()).hexdigest()[:12]}")


if __name__ == "__main__":
    main()

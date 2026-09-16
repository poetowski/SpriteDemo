"""Build every art artifact, either from the rig or from the .aseprite files.

    python tools/build.py                 # rig  -> .aseprite + png/json/svg/js
    python tools/build.py --from-aseprite # .aseprite -> png/json/svg/js

The second mode is the point of the pipeline: tools/hero.py generates the first
draft, you refine it by hand in Aseprite, and the build re-exports everything
from the edited .aseprite - without overwriting your edits, and without needing
Aseprite installed to do the exporting.

Outputs:
    art/hero.aseprite    layered (shadow + hero), tagged source    [rig mode]
    art/props.aseprite   ground tile + bush, tagged                [rig mode]
    art/hero.png         6-wide grid spritesheet, flattened
    art/props.png        prop spritesheet
    art/hero.json        Aseprite-format atlas + frameTags
    art/hero_sheet.svg   scalable reference sheet
    art/preview.png      6x zoom contact sheet for eyeballing frames
    web/art-embed.js     sheets as data URIs + Phaser animation config
    web/page.html        the whole demo bundled into one shareable file
"""

import base64
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aseprite
import hero
import make_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art")
WEB = os.path.join(ROOT, "web")
HERO_ASE = os.path.join(ART, "hero.aseprite")
PROPS_ASE = os.path.join(ART, "props.aseprite")

FW = FH = hero.W
COLS = hero.COLS
PALETTE = [(rgba, name) for rgba, name in hero.PALETTE.values()]
TAG_COLOR = (0x4f, 0xa5, 0x55)


def canvas_to_image(c):
    img = Image.new("RGBA", (c.w, c.h))
    img.frombytes(c.rgba_bytes())
    return img


def flatten(*canvases):
    """Composite canvases bottom-up, as Aseprite does when exporting."""
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    for c in canvases:
        out.alpha_composite(canvas_to_image(c))
    return out


# ------------------------------------------------------------------ inputs ---
# Both modes produce the same shape: cells = [(name, RGBA Image, duration_ms)]
# plus tags = [(name, from, to)]. Every exporter below consumes only that.

def cells_from_rig():
    frames = hero.build_frames()
    return [(n, flatten(s, h), ms) for n, h, s, ms in frames], hero.build_tags()


def props_from_rig():
    props = hero.build_props()
    return ([(n, canvas_to_image(c), 100) for n, c in props],
            [(n, i, i) for i, (n, _c) in enumerate(props)])


def cells_from_ase(path):
    """Read an .aseprite back out, flattening its layers per frame."""
    doc = aseprite.read(path)
    tags = [(t["name"], t["from"], t["to"]) for t in doc["tags"]]
    names = {}
    for name, f0, f1 in tags:
        for i in range(f0, f1 + 1):
            names[i] = f"{name}-{i - f0}" if f1 > f0 else name
    cells = []
    for i, f in enumerate(doc["frames"]):
        img = Image.new("RGBA", (doc["width"], doc["height"]), (0, 0, 0, 0))
        for cel in sorted(f["cels"], key=lambda c: c["layer"]):
            layer = Image.frombytes("RGBA", (cel["w"], cel["h"]), cel["pixels"])
            img.alpha_composite(layer, (cel["x"], cel["y"]))
        cells.append((names.get(i, f"frame-{i}"), img, f["duration"]))
    return cells, tags


# --------------------------------------------------------------- exporters ---
def write_ase(path, layers, frames, tags):
    """frames: [([Canvas|None per layer], duration_ms), ...]. Verifies itself."""
    aseprite.write(
        path, FW, FH, layers,
        [([c.rgba_bytes() if c else None for c in cels], ms) for cels, ms in frames],
        PALETTE,
        [(n, f, t, TAG_COLOR) for n, f, t in tags],
    )
    doc = aseprite.read(path)                       # round-trip the bytes back
    assert doc["layers"] == layers, doc["layers"]
    assert doc["width"] == FW and doc["height"] == FH
    assert doc["ncolors"] == len(hero.PALETTE), doc["ncolors"]
    assert len(doc["frames"]) == len(frames), len(doc["frames"])
    for i, (cels, ms) in enumerate(frames):
        f = doc["frames"][i]
        assert f["duration"] == ms, (i, f["duration"])
        got = {c["layer"]: c["pixels"] for c in f["cels"]}
        want = {li: c.rgba_bytes() for li, c in enumerate(cels) if c}
        assert got == want, f"frame {i}: cel pixels differ"
    assert [(t["name"], t["from"], t["to"]) for t in doc["tags"]] == tags
    return doc


def grid_sheet(cells, cols=COLS):
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * FW, rows * FH), (0, 0, 0, 0))
    for i, (_n, img, _ms) in enumerate(cells):
        sheet.alpha_composite(img, ((i % cols) * FW, (i // cols) * FH))
    return sheet


def build_preview(cells, zoom=6):
    """Contact sheet: checkerboard ground, 1px frame grid."""
    pad = 14
    rows = (len(cells) + COLS - 1) // COLS
    img = Image.new("RGBA", (COLS * FW * zoom + pad, rows * FH * zoom + pad),
                    (0x1b, 0x1f, 0x2a, 255))
    tile = 4 * zoom
    for i, (_n, cell, _ms) in enumerate(cells):
        ox = pad + (i % COLS) * FW * zoom
        oy = pad + (i // COLS) * FH * zoom
        for yy in range(0, FH * zoom, tile):
            for xx in range(0, FW * zoom, tile):
                shade = 0x9d if ((xx // tile) + (yy // tile)) % 2 else 0x92
                img.paste((shade, shade + 4, shade + 8, 255),
                          (ox + xx, oy + yy, ox + min(xx + tile, FW * zoom),
                           oy + min(yy + tile, FH * zoom)))
        img.alpha_composite(cell.resize((FW * zoom, FH * zoom), Image.NEAREST),
                            (ox, oy))
        for xx in range(FW * zoom):
            img.putpixel((ox + xx, oy), (0x44, 0x4c, 0x60, 255))
        for yy in range(FH * zoom):
            img.putpixel((ox, oy + yy), (0x44, 0x4c, 0x60, 255))
    return img


def build_svg(cells):
    """One <g> per frame; horizontal runs of one colour merge into one rect."""
    rows = (len(cells) + COLS - 1) // COLS
    w, h = COLS * FW, rows * FH
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * 4}" '
           f'height="{h * 4}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges">',
           '  <title>hero sprite sheet</title>']
    for i, (name, img, _ms) in enumerate(cells):
        ox, oy = (i % COLS) * FW, (i // COLS) * FH
        px = img.load()
        out.append(f'  <g id="{name}">')
        for y in range(img.height):
            x = 0
            while x < img.width:
                rgba = px[x, y]
                if rgba[3] == 0:
                    x += 1
                    continue
                run = 1
                while x + run < img.width and px[x + run, y] == rgba:
                    run += 1
                r, g, b, a = rgba
                op = '' if a == 255 else f' fill-opacity="{a / 255:.2f}"'
                out.append(f'    <rect x="{ox + x}" y="{oy + y}" width="{run}" '
                           f'height="1" fill="#{r:02x}{g:02x}{b:02x}"{op}/>')
                x += run
        out.append('  </g>')
    out.append('</svg>')
    return "\n".join(out)


def build_json(cells, tags, sheet_size):
    return {
        "frames": [{
            "filename": name,
            "frame": {"x": (i % COLS) * FW, "y": (i // COLS) * FH, "w": FW, "h": FH},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": FW, "h": FH},
            "sourceSize": {"w": FW, "h": FH},
            "duration": ms,
        } for i, (name, _img, ms) in enumerate(cells)],
        "meta": {
            "app": "demo_sprites_4move/tools/build.py",
            "version": "1.0",
            "image": "hero.png",
            "format": "RGBA8888",
            "size": {"w": sheet_size[0], "h": sheet_size[1]},
            "scale": "1",
            "frameTags": [{"name": n, "from": f, "to": t, "direction": "forward"}
                          for n, f, t in tags],
            "layers": [{"name": "shadow", "opacity": 255, "blendMode": "normal"},
                       {"name": "hero", "opacity": 255, "blendMode": "normal"}],
            "slices": [],
        },
    }


def data_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_embed(hero_sheet, cells, tags, props):
    """Data-URI sheets + anim config, so index.html also runs from file://."""
    anims = []
    for name, f0, f1 in tags:
        durations = [cells[i][2] for i in range(f0, f1 + 1)]
        base = min(durations)
        anims.append({
            "key": name,
            "frameRate": round(1000 / base, 3),
            "repeat": -1,
            # Phaser adds per-frame `duration` on top of the frame rate, so a
            # frame held longer in Aseprite survives the export.
            "frames": [{"frame": i, "duration": d - base}
                       for i, d in zip(range(f0, f1 + 1), durations)],
        })
    cfg = {
        "hero": {
            "image": data_uri(hero_sheet),
            "frameWidth": FW, "frameHeight": FH,
            "anims": anims,
        },
        # Props ship as standalone textures: a TileSprite tiles a whole texture
        # reliably on every renderer, an atlas frame does not.
        "props": {name: data_uri(img) for name, img, _ms in props},
    }
    return ("// Generated by tools/build.py - do not edit.\n"
            "window.ART = " + json.dumps(cfg, indent=2) + ";\n")


def main(from_aseprite=False):
    os.makedirs(ART, exist_ok=True)
    os.makedirs(WEB, exist_ok=True)

    if from_aseprite:
        for p in (HERO_ASE, PROPS_ASE):
            if not os.path.exists(p):
                sys.exit(f"{p} not found - run without --from-aseprite first")
        cells, tags = cells_from_ase(HERO_ASE)
        props, _ptags = cells_from_ase(PROPS_ASE)
        source = "art/*.aseprite (hand edits preserved)"
    else:
        frames = hero.build_frames()
        write_ase(HERO_ASE, ["shadow", "hero"],
                  [([s, h], ms) for _n, h, s, ms in frames], hero.build_tags())
        rig_props = hero.build_props()
        write_ase(PROPS_ASE, ["props"], [([c], 100) for _n, c in rig_props],
                  [(n, i, i) for i, (n, _c) in enumerate(rig_props)])
        cells, tags = cells_from_rig()
        props, _ptags = props_from_rig()
        source = "tools/hero.py rig"

    hero_sheet = grid_sheet(cells)
    props_sheet = grid_sheet(props, cols=len(props))
    hero_sheet.save(os.path.join(ART, "hero.png"), optimize=True)
    props_sheet.save(os.path.join(ART, "props.png"), optimize=True)
    build_preview(cells).save(os.path.join(ART, "preview.png"))
    with open(os.path.join(ART, "hero_sheet.svg"), "w", encoding="utf-8") as fh:
        fh.write(build_svg(cells))
    with open(os.path.join(ART, "hero.json"), "w", encoding="utf-8") as fh:
        json.dump(build_json(cells, tags, hero_sheet.size), fh, indent=2)
    with open(os.path.join(WEB, "art-embed.js"), "w", encoding="utf-8") as fh:
        fh.write(build_embed(hero_sheet, cells, tags, props))

    page, page_size = make_page.build()

    print(f"source: {source}")
    print(f"  {len(cells)} hero frames / {len(tags)} tags / {len(props)} props")
    for rel in ("art/hero.aseprite", "art/props.aseprite", "art/hero.png",
                "art/props.png", "art/hero.json", "art/hero_sheet.svg",
                "art/preview.png", "web/art-embed.js", "web/page.html"):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        note = ""
        if rel.endswith(".aseprite"):
            note = "  [untouched]" if from_aseprite else "  [round-trip verified]"
        print(f"  {rel:<22}{os.path.getsize(path):>8} B{note}")


if __name__ == "__main__":
    main(from_aseprite="--from-aseprite" in sys.argv[1:])

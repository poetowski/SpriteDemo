# demo_sprites_4move

A top-down RPG sandbox with code-generated pixel art. Characters, livestock,
tiles and props are drawn by parametric Python rigs, exported to spritesheets
plus `.aseprite` sources, and played in Phaser 3 — with the map, the props, the
NPCs and their dialogue all loaded from engine-neutral JSON. Sheep and goats
wander and graze on their own.

Riverside is 96×72 tiles — a forest, a lake and the river out of it, a village
at the crossroads, a quarry, a walled graveyard and a farm — with 33 kinds of
prop, every one of them solid.

![the world](build/map.png)

## Quick start

```sh
python tools/build.py          # regenerate all art + data  (needs Pillow)
node tools/shot.cjs            # boot the game headless, check it, photograph it
```

Then open `game/index.html` — double-click is enough, no server needed.
**Arrows / WASD** to move, **E** to talk. On a phone there is a d-pad.

`game/page.html` is the same game as a single self-contained file, which is what
gets published when a link is wanted.

## Layout

```
tools/gen/        the generators: palette, character rig, tiles, props
tools/pipeline/   aseprite I/O, atlas packing, manifest, validation gates
tools/build.py    entry point
tools/shot.cjs    headless-Chromium smoke test that leaves a screenshot behind
content/          AUTHORED data - engine-neutral JSON, human-diffable
build/            GENERATED - safe to delete at any time, never hand-edit
game/             the Phaser 3 game
CLAUDE.md         the change loop: build, screenshot, publish
```

The rule: `tools/` and `content/` are truth. Everything in `build/` and
`game/art-embed.js` is derived and reproducible.

## The pipeline

```
content/*.json  +  tools/gen/*.py
        │  generate
build/atlas/*.png  ·  build/manifest.json  ·  build/aseprite/*.aseprite
        │  validate   ← 16 gates, all must pass
game/art-embed.js  →  game/index.html + main.js  →  game/page.html
```

It also runs backwards for hand-drawn work: `build/aseprite/*.aseprite` are real
layered, tagged Aseprite files. `tools/pipeline/aseprite.py` is a from-scratch
ASE reader/writer (stdlib only), so neither direction needs Aseprite installed.

### The gates

`tools/pipeline/validate.py` is what keeps a generated asset set honest. Every
failure points at an authored file, never at generated output:

| Gate | Catches |
|---|---|
| `id-format`, `sprite-format` | typo'd or malformed IDs |
| `sprite-exists` | a definition pointing at art that was never generated |
| `actor-states` | an actor that declares no states |
| `actor-complete` | an actor declaring a state its rig cannot generate |
| `actor-anchor` | frames of one actor disagreeing on the anchor (jitter) |
| `anchor-bounds` | an anchor outside its own frame |
| `tile-seam` | a tile that would show a seam when repeated |
| `map-shape`, `map-legend` | a ragged map grid or an undefined legend character |
| `map-entity` | a placement pointing at nothing, or off the edge of the map |
| `map-footprint` | a cottage with one corner in the river |
| `map-overlap` | two solid things claiming the same tile |
| `map-spawn` | a spawn in water, or inside a wall |
| `dialogue-exists` | an NPC pointing at dialogue that does not exist |
| `deterministic` | the build drifting between runs |

## How the art works

**The character is a rig, not a pile of drawings.** `draw_actor(direction, bob,
leg, swing)` composes the same body-part functions for every frame, so the
character cannot drift between facings or states. Outlines are computed from the
silhouette, not drawn.

**A second character costs a palette, not art.** Sprites store palette *keys*,
so `VARIANTS` in `tools/gen/palette.py` turns one rig into many characters —
Arne the smith is the hero's frames with a rust apron and grey hair.

**Two rigs, one contract.** `tools/gen/actor.py` is the biped; `animal.py` is
the quadruped (walk, idle and a head-down `graze`). Both use a 32×32 frame, the
same ground line and the same `build_frames()` shape, so the atlas, the anchors
and the depth sorting treat them identically. A goat is the sheep rig with horns,
a beard, a smooth back and a tan palette — which species an actor uses is a
`"rig"` field in `content/`, not a pipeline change.

**Anchors, not offsets.** Every sprite exports the pixel that sits on a map tile
(`[16, 29]` — between the feet). The game sets sprite origin from it, so art of
any size lines up and sorting by `sprite.y` is correct depth sorting. That is
what lets structures use a bigger frame: cottages, the barn, the tower and the
windmill are drawn 48×48 on their own atlas with anchor `[24, 45]`, and the
scene needs no special case for them — it reads the frame size off the atlas.

**Light comes from the silhouette too.** `_shade()` in `tools/gen/props.py`
lights the pixels of a mass that face up-left and shades the ones that face
down-right, so a prop is drawn as a shape and lit as a consequence. Thirty
props fit in one file because none of them spells out its own shading.

## How the game works

`game/main.js` contains no art and no content. Frame sizes, animations, tiles,
props, actors, dialogue and the map all come from `window.ART.manifest`. Adding
an NPC means adding a JSON file and a line in the map — no JS change:

```json
{
  "id": "npc.sheep", "sprite": "actor.sheep", "rig": "quadruped",
  "states": ["walk", "idle", "graze"], "speed": 16, "blocks": false,
  "interact": "dlg.sheep_baa",
  "wander": { "radius": 4, "idle_ms": [900, 2200],
              "graze_ms": [2500, 6000], "graze_chance": 0.6 }
}
```

Wandering is content too: the radius, the pause lengths and how often an animal
would rather eat than walk are all tuned in JSON, not in the scene code.

Maps are human-editable ASCII with a legend, which diffs cleanly and ports to
any engine:

```json
"legend": { ".": "tile.grass", "p": "tile.path", "~": "tile.water" },
"ground": ["..............p.................", "..."]
```

**Collision is authored, not drawn.** A definition's `footprint` lists the tiles
it stands on as offsets from its anchor tile — `[[0, 0]]` for a barrel, six
offsets for a three-by-two cottage. The scene puts one static body on each, so a
tree's canopy can overhang ground you can still walk on, and a building is solid
across its whole base without being cut into three sprites.

## Verification

- Every `.aseprite` is parsed back at build time and checked against its source.
- The manifest is assembled twice per build and compared, so the build is proven
  deterministic rather than assumed to be.
- `node tools/shot.cjs` runs the real game in headless Chromium and asserts that
  it came up: no console errors, the physics world matching the map the manifest
  declares, one sprite per placed entity, one static body per blocked tile, and
  livestock actually wandering. It exits non-zero when a check fails — the
  screenshot it writes to `build/shot.png` is the by-product, not the point.
  `--talk` also presses **E** and checks the dialogue box opens; `--map` renders
  the whole 96×72 world as one frame.

## Engine note

The Godot-or-Phaser decision is deliberately still open. `content/` and
`build/manifest.json` are engine-neutral; only `game/` is Phaser-specific. Moving
to Godot means writing an importer for the same manifest, not redoing the art or
the content.

Requires Python 3.9+ with Pillow (`pip install pillow`). Phaser is vendored in
`game/vendor/`, so the game works offline; it falls back to the CDN if absent.

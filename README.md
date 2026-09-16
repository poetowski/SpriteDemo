# demo_sprites_4move

A top-down RPG sandbox with code-generated pixel art. Characters, tiles and
props are drawn by a parametric Python rig, exported to spritesheets plus a
`.aseprite` source, and played in Phaser 3 — with the map, the props, the NPC and
its dialogue all loaded from engine-neutral JSON.

![sprite sheet](build/preview.png)

## Quick start

```sh
python tools/build.py          # regenerate all art + data  (needs Pillow)
```

Then open `game/index.html` — double-click is enough, no server needed.
**Arrows / WASD** to move, **E** to talk.

## Layout

```
tools/gen/        the generators: palette, character rig, tiles, props
tools/pipeline/   aseprite I/O, atlas packing, manifest, validation gates
tools/build.py    entry point
content/          AUTHORED data - engine-neutral JSON, human-diffable
build/            GENERATED - safe to delete at any time, never hand-edit
game/             the Phaser 3 game
```

The rule: `tools/` and `content/` are truth. Everything in `build/` and
`game/art-embed.js` is derived and reproducible.

## The pipeline

```
content/*.json  +  tools/gen/*.py
        │  generate
build/atlas/*.png  ·  build/manifest.json  ·  build/aseprite/*.aseprite
        │  validate   ← 13 gates, all must pass
game/art-embed.js  →  game/index.html + main.js
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
| `actor-complete` | an actor missing a facing or a state |
| `actor-anchor` | frames of one actor disagreeing on the anchor (jitter) |
| `anchor-bounds` | an anchor outside its own frame |
| `tile-seam` | a tile that would show a seam when repeated |
| `map-shape`, `map-legend` | a ragged map grid or an undefined legend character |
| `map-entity`, `map-spawn` | an entity standing in water, a spawn inside a wall |
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

**Anchors, not offsets.** Every sprite exports the pixel that sits on a map tile
(`[16, 29]` — between the feet). The game sets sprite origin from it, so art of
any size lines up and sorting by `sprite.y` is correct depth sorting.

## How the game works

`game/main.js` contains no art and no content. Frame sizes, animations, tiles,
props, actors, dialogue and the map all come from `window.ART.manifest`. Adding
an NPC means adding a JSON file and a line in the map — no JS change:

```json
{
  "id": "npc.arne", "sprite": "actor.smith", "name": "Arne",
  "blocks": true, "facing": "down", "interact": "dlg.arne_intro"
}
```

Maps are human-editable ASCII with a legend, which diffs cleanly and ports to
any engine:

```json
"legend": { ".": "tile.grass", "p": "tile.path", "~": "tile.water" },
"ground": ["..............p.................", "..."]
```

## Verification

- Every `.aseprite` is parsed back at build time and checked against its source.
- The manifest is assembled twice per build and compared, so the build is proven
  deterministic rather than assumed to be.
- The game is driven in headless Chrome over the DevTools protocol: 16 checks
  covering boot, animations, the tilemap, entity spawning, collision against
  water, depth sorting, the interaction prompt, dialogue advance/close, and
  movement being locked while talking.

## Engine note

The Godot-or-Phaser decision is deliberately still open. `content/` and
`build/manifest.json` are engine-neutral; only `game/` is Phaser-specific. Moving
to Godot means writing an importer for the same manifest, not redoing the art or
the content.

Requires Python 3.9+ with Pillow (`pip install pillow`). Phaser is vendored in
`game/vendor/`, so the game works offline; it falls back to the CDN if absent.

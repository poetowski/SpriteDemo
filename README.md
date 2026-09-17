# demo_sprites_4move

A top-down RPG sandbox with code-generated pixel art. Characters, livestock,
tiles and props are drawn by parametric Python rigs, exported to spritesheets
plus `.aseprite` sources, and played in Phaser 3 — with the map, the props, the
NPCs and their dialogue all loaded from engine-neutral JSON. Sheep and goats
wander and graze on their own.

Riverside is 96×72 tiles — a forest, a lake and the river out of it, a village
at the crossroads, a quarry, a walled graveyard and a farm — with 33 kinds of
prop, every one of them solid, and thirteen kinds of thing to pick up, three
of which go in the weapon hand and swing.

![the world](build/map.png)

## Quick start

```sh
python tools/build.py          # regenerate all art + data  (needs Pillow)
node tools/shot.cjs            # boot the game headless, check it, photograph it
```

Then open `game/index.html` — double-click is enough, no server needed.
**Arrows / WASD** move · **E** talk / take · **Space** slash · **I** bag ·
**C** character sheet · **Q** swap weapon On a phone there is a d-pad.

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
        │  validate   ← 21 gates, all must pass
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
| `map-exit` | a way to another map that lands nowhere real, or lands on the way back |
| `dialogue-exists` | an NPC pointing at dialogue that does not exist |
| `dialogue-shape` | a conversation with no start, or a node that says nothing |
| `dialogue-links` | a reply pointing at a node that is not there, or writing nobody can reach |
| `dialogue-effects` | a branch waiting on a flag no choice ever sets, or trading an item that does not exist |
| `item-kind` | an item the engine has no idea what to do with, or a weapon with nothing to draw |
| `item-held` | a weapon the hero could equip but has no frames for - a sprite with holes |
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

## Talking

A conversation is a graph, not a script: **nodes** of text joined by the
**choices** the player is offered. Which choices appear is decided when the
node is entered, so a reply can be offered only while you are carrying
something, or only once an NPC has asked you for it.

```json
"start": [{ "when": { "flag": "chest.opened" }, "goto": "empty" },
          { "goto": "shut" }],
"nodes": {
  "shut": { "text": ["Locked. Someone went to real trouble over it."],
            "choices": [
              { "text": "Turn the key.", "goto": "open", "when": { "has": "item.key" },
                "take": "item.key", "give": "item.coin", "set": "chest.opened" },
              { "text": "Leave it." }] } }
```

**Entry rules** are what make a conversation remember: `start` is either a node
name or a list of rules, and the first whose condition holds is where you come
in. The condition language is deliberately tiny — `flag`, `noflag`, `has`,
`nothas`, and `all` to combine them — small enough that a gate can check every
branch is reachable and every flag is one some choice actually sets. A choice
with no `goto` ends the conversation.

Effects run **take, then give, then set**, so trading the last thing in a full
bag still works; anything given that will not fit drops at your feet rather
than vanishing.

That is enough for a quest without a quest system. Ask Arne for work and he
wants iron ore from the quarry; bring him a lump and he trades it for his
father's key; the key opens the chest in the barn yard, once, and afterwards
the chest knows it is empty. The flags live in the scene, so the world
remembers within a session.

The panel is the bag's planks, sliding up from the bottom: a speaker plate,
the line, and the replies numbered 1–4. Arrows or the number keys pick one,
**E** answers, and on a phone you just tap the reply.

## Items, the bag, and the weapon hand

An item is a 16×16 icon drawn once in `tools/gen/items.py` and used twice: it
lies on the ground with a slow bob, and the HUD cuts the same cell out of the
same atlas for the bag. What it *is* — `material` or `weapon`, whether it
stacks — is `content/items/`. Walk up to one and press **E**: the hero crouches
(`gather`, three frames of the same rig, hands to the ground) and it goes in
the bag. **I** slides the bag in from the left of the stage: a wooden panel of
4×4 slots, one thing per slot, nothing stacks — sixteen is the limit, and the
prompt says so when it is reached. Arrows walk the cursor; **E** draws the
weapon under it, or puts it away. The icons are the same 16×16 cells at 3×.

**A weapon is a sprite swap, not a second sprite.** The biped rig draws a held
weapon into every pose from the hand outward along a direction — so one
description of a sword serves the walk, the crouch and each frame of the swing,
and the same frame decides whether the blade is in front of the body or behind
it. `tools/build.py` bakes one frame set per weapon (`actor.hero_sword`,
`_axe`, `_spear`) and writes the map from item to frame set into the hero's
manifest record; the scene arms the hero by switching sprite base and nothing
else. **Space** swings (`slash`: wind up, strike, follow through, recover),
**Q** cycles what is in the bag. The strike lands on the second frame: anything
in the arc a tile ahead flashes, livestock bolts, and props marked `hittable`
shake — the scarecrow is there to be practised on. Each hit floats a number
off the target — the weapon's `damage`, give or take a fifth — with sparks
thrown out round it. The digits are 3×5 glyphs from `tools/gen/fx.py`, an
atlas of their own, so they are pixels the same size as the blade that caused
them rather than text blurred at 3×.

Picking up the first weapon draws it; the sword is by Arne's anvil, the felling
axe at the woodcutters' camp, the spear in the old tower.

**Armour is worn the same way a weapon is held.** `ARMOURS` in the rig draws a
mail shirt over the tunic after the torso and before the arms, so sleeves and
collar stay the character's own; the build bakes one frame set per
weapon-and-armour pair (`actor.hero_sword_mail` and the rest) and writes the
whole table into the hero's record as `looks`, keyed `"<weapon>|<armor>"`.
Putting the shirt on is the same one-string switch as drawing a sword. The
mail shirt lies a few steps from where you start; the first one picked up is
worn, and **E** on it in the bag takes it off again.

## Verification

- Every `.aseprite` is parsed back at build time and checked against its source.
- The manifest is assembled twice per build and compared, so the build is proven
  deterministic rather than assumed to be.
- `node tools/shot.cjs` runs the real game in headless Chromium and asserts that
  it came up: no console errors, the physics world matching the map the manifest
  declares, one sprite per placed entity, one static body per blocked tile, and
  livestock actually wandering. It exits non-zero when a check fails — the
  screenshot it writes to `build/shot.png` is the by-product, not the point.
  `--talk` presses **E** and checks the dialogue box opens; `--gather` presses
  it beside an item and checks the crouch played and the bag grew by one;
  `--bag` presses **I** and checks the panel opened and the cursor moves;
  `--give item.axe --slash` arms the hero, presses **Space** and checks the
  swing played and handed control back. `--map` renders the whole 96×72 world
  as one frame; `--pose slash,1 --page` freezes the strike and photographs the
  page with its bag and buttons.

## Engine note

The Godot-or-Phaser decision is deliberately still open. `content/` and
`build/manifest.json` are engine-neutral; only `game/` is Phaser-specific. Moving
to Godot means writing an importer for the same manifest, not redoing the art or
the content.

Requires Python 3.9+ with Pillow (`pip install pillow`). Phaser is vendored in
`game/vendor/`, so the game works offline; it falls back to the CDN if absent.

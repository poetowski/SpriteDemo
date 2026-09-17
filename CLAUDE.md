# Working on this repo

A top-down RPG sandbox whose art and content are generated from Python rigs and
engine-neutral JSON. `tools/` and `content/` are truth; `build/` and
`game/art-embed.js` are derived and must never be hand-edited.

## The loop

Every request that changes the game ends with a playable link and a picture.
Run all four steps, in order, every time:

```sh
python tools/build.py                    # 1. regenerate art + data, run the gates
node tools/shot.cjs                      # 2. smoke-test the real game, shoot it
node tools/shot.cjs --map                # 3. and shoot the whole world
                                         # 4. publish game/page.html (below)
```

1. **Build.** `tools/build.py` regenerates every atlas, the manifest, the
   `.aseprite` sources and `game/page.html`. All 24 gates must pass. A gate
   failure names an authored file - fix that file, never the generated output.
   Needs Pillow: `pip install pillow` if the import fails.

2. **Screenshot.** `tools/shot.cjs` loads `game/index.html` in headless
   Chromium, checks the scene actually booted (no console errors, every entity
   spawned, one collision body per blocked tile, livestock wandering) and writes
   `build/shot.png`. It exits non-zero if a check fails, so treat a red run as a
   broken build. Needs `NODE_PATH=/opt/node22/lib/node_modules` on Claude Code
   web, where playwright is installed globally. Useful flags:

   ```sh
   node tools/shot.cjs --tile 33,40         # stand at a tile and look
   node tools/shot.cjs --talk --tile 33,37  # talk to Arne, check the replies appear
   node tools/shot.cjs --talk --choose 2 --tile 33,37   # and take the second one
   node tools/shot.cjs --gather --tile 34,37   # stand by an item, press E, check the bag
   node tools/shot.cjs --give item.axe --slash # arm the hero and swing
   node tools/shot.cjs --give item.axe --bag   # open the bag (I), check the cursor moves
   node tools/shot.cjs --give item.axe --slash --mid --tile 40,62   # hit the scarecrow, shoot the impact
   node tools/shot.cjs --pose slash,1 --page   # freeze the strike, shoot the whole page
   node tools/shot.cjs --map                # the whole world in one frame
   node tools/shot.cjs --out /tmp/a.png --wait 1500
   ```

3. **Publish.** `game/page.html` is the whole game in one file (Phaser from a
   pinned CDN, art inlined as data URIs). Publish it with the `Artifact` tool -
   that URL is the thing the person opens on their phone and plays.

   **Reuse the existing artifact** — it is
   <https://claude.ai/artifact/Ex6wAvYHUJqhpC5KYqAwQm>. `action: "read"` it
   first, then publish with that `url`, so the link already on someone's phone
   keeps working. Publishing without `url` makes a *second* artifact with a
   different link, which is almost never what is wanted. (`action: "list"` finds
   it again if this line ever goes stale.)

4. **Reply** with the artifact link, and send `build/shot.png` (and
   `build/map.png` when the map changed) with `SendUserFile` so the result is
   visible without opening anything.

Then commit and push to the session's branch.

## The art scale standard

**Everything is drawn at the 2x standard.** These are the frame sizes, and the
`art-scale` gate enforces them:

| Atlas | Frame | Anchor | Rig |
|---|---|---|---|
| `tiles` | 32x32 | - | `gen/tiles.py` |
| `actors` | 64x64 | `(32, 58)` | `gen/actor.py`, `gen/animal.py` |
| `props` | 64x64 | `(32, 58)` | `gen/props.py` |
| `props_big` | 96x96 | `(48, 90)` | `gen/props.py` structures |
| `items` | 32x32 | `(16, 28)` | `gen/items.py` |
| `fx` | 16x16 | `(8, 8)` | `gen/fx.py` |

A rig that drifts back to an older size, or a new atlas added at the wrong one,
fails the build rather than looking subtly chunky in game. **New art is authored
at these sizes** - never drawn small and scaled up in the pipeline.

### Redraw, never upscale

Doubling coordinates makes every pixel a 2x2 block and adds no detail; it is not
a resolution change. Moving something up a scale means **redrawing it to use the
new pixels** - the face gains brows and a white in the eye, the fleece becomes a
texture rather than four bumps on an outline. There is deliberately no upscale
helper left in the codebase; wanting one is the signal to redraw.

### Shading

`_shade` lights the 1px rim of a mass; `_form` gives it volume by position
within its own bounds. Use `_form` on anything bigger than a few pixels, or it
reads as a flat sticker. **Shade inside the silhouette**: painting shading by
raw coordinate puts pixels outside the shape - that bug gave rocks striped tails
and a sack legs, and no assertion catches it. Render a contact sheet and look.

Texture comes from `scatter(seed)`, a fixed deterministic generator, so dense
detail never shimmers between frames and the build stays reproducible.

### Ground

Ground is authored as plain terrain and drawn with variation and edges:

- **Variants.** A base tile takes a seed (`tiles.VARIANTS` says how many) and a
  cell picks one by position, so a field is never one stamp repeated.
- **Transitions.** Tiles marked `"blend": true` in `content/tiles/` get the
  full 47-tile blob set, generated by carving the terrain out of grass along a
  wobbling boundary with a treatment per terrain (sand and foam for water, a
  trodden strip for a path, a shadow at the foot of stone).
  `pipeline/autotile.py` resolves each map cell from its 8 neighbours; tiles
  with the same `family` count as the same ground. The resolved grid ships in
  the manifest (`maps[id].grid`, `tileset.blocking`) and the `map-grid` gate
  checks it. A new terrain needs a base drawing, an edge style in
  `tiles.STYLE` if it blends, and a content file - never a hand-placed edge.
- **Animated ground.** `tiles.ANIMATED` names tiles drawn in phases (water:
  three). The build emits every phase of every variant and transition as its
  own frame and lists each base index's sequence in `tileset.animated`; the
  scene cycles them every `tileset.anim_ms` with `putTileAt`, re-asserting
  collision. Anything that must not flicker between phases (sand, wear) is
  decided by a per-row rng seeded from the mask, not the phase.
- **Edges know their direction.** `depth()` returns which open edge placed the
  boundary, so a style can treat downhill differently: stone's south-facing
  edge is a cliff face with a lit lip and a shadow on the grass below, and a
  path is worn darkest on its bends.
- Base textures wrap: place detail with `_put`, and it continues across the
  seam instead of being kept away from the edges.

## Where things live

```
tools/gen/palette.py   the one palette; a character variant is a key remap
tools/gen/actor.py     the biped rig      (64x64 frame, anchor [32, 58])
tools/gen/animal.py    the quadruped rig  (same frame, same contract)
tools/gen/props.py     props 64x64, structures 96x96 (anchor [48, 90])
tools/gen/tiles.py     32x32 ground tiles, variants and the blob transitions
tools/pipeline/        aseprite I/O, atlas packing, autotile, manifest, the 24 gates
content/               AUTHORED json - actors, props, tiles, dialogue, maps
game/main.js           the Phaser scene: no art, no content, no hardcoded ids
```

## Adding things

**A prop** is three edits and no engine change: a drawing function in
`tools/gen/props.py` (added to `PROPS` or `BIG_PROPS`), a file in
`content/props/`, and an entry in a map's `entities`.

**Collision is authored, not drawn.** A definition's `footprint` is the list of
tile offsets it stands on - `[[0, 0]]` for most things, six offsets for a
three-by-two structure. The gates check every footprint tile is real ground and
that no two solid things claim the same tile; `game/main.js` puts one static
body on each.

**An NPC** is a file in `content/actors/` plus a line in the map. Its `rig`
(`biped` / `quadruped`), `states`, `speed`, `blocks`, `interact` and `wander`
settings are all content. No JS changes.

**An item** is a 32x32 icon function in `tools/gen/items.py` (added to
`ITEMS`), a file in `content/items/` with `kind` `material`, `weapon` or
`armor`, and a line in the map. A weapon also carries a positive integer
`damage` (the number a hit floats up) and names what the hand holds
(`"held": "sword"`), which must be a `WEAPONS` entry in `tools/gen/actor.py` -
that is where a new weapon's shape is described, once, as a line from the hand
with a guard or a head hung off it. Armor names what is worn
(`"worn": "mail"`), an `ARMOURS` entry in the same file, drawn over the torso
before the arms. The build bakes one frame set per weapon-and-armour pair for
every actor with `"wields": true` (that table is the actor's `looks`) and the
`item-held` gate checks every one is complete.

**A conversation** is a file in `content/dialogue/` and an `interact` on the
thing that says it. It is a graph: `nodes` of `text` joined by `choices`, and
`start` is either a node name or a list of entry rules whose first matching
`when` decides where you come in - that is how a conversation remembers. A
choice may carry `when` (`flag` / `noflag` / `has` / `nothas` / `all`) and the
effects `set`, `give` and `take`; no `goto` ends it. Effects run take, give,
set, so a trade works with a full bag. Keep the condition language as small as
it is - the gates can only check branches they understand.

**A map** is ASCII rows plus a legend. Roads must stay clear - scenery placed on
a path tile can wall off the only route across the world.

**Placing scenery is composition, not sprinkling.** A uniform random dusting is
the one thing that reliably looks wrong, and it is what you get by default:

- Things clump. Trees come in groves that overlap into canopy and leave glades
  between them; stone comes up in outcrops. Almost nothing stands alone, so the
  few things that do read as landmarks.
- Ecology decides where. Mushrooms under a canopy, stumps and cut logs only in
  the clearing being felled, rock only where there is rock or water to explain
  it, bushes thickening along the water - which is what gives a shoreline an
  edge instead of a hard pixel boundary.
- Settlements are laid out first and the wilderness fills in around them, with a
  clear shoulder either side of every road.
- Human places are arranged: a market row, a smithy facing it, a yard in front
  of the barn, graves ranked along an aisle, a flock gathered at its trough.
- Open country is allowed to be open. A wood only reads as a wood if somewhere
  nearby is not one.

Audit the result against its own meaning before shipping it: count the props
with no tree near them that need shade, the ones nothing else is within four
tiles of, and the ones standing somewhere their own definition contradicts.
That check is what caught a scarecrow guarding a graveyard.

## House style

Match what is already there: short module docstrings that say *why*, comments
that explain a decision rather than restate the code, and no new dependency
without a reason. Python is stdlib + Pillow only; the game vendors Phaser and
needs no server or build step.

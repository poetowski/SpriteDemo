# Working on this repo

A top-down RPG sandbox whose art and content are generated from Python rigs and
engine-neutral JSON. `tools/` and `content/` are truth; `build/` and
`game/art-embed.js` are derived and must never be hand-edited.

## Two pipelines

Art and game are separate, and art does not regenerate on every build:

```sh
python tools/art.py        # only when a generator or the palette changed
python tools/build.py      # every time content or a map changed
python tools/editor.py     # the map editor, at http://127.0.0.1:8765/
```

- **`tools/art.py`** is the only thing that knows about rigs, palettes and
  generators. It draws everything, packs the atlases, writes the `.aseprite`
  sources, and emits `assets/atlases.json` - every sprite's atlas, index and
  anchor, every animation, the tile index, each wielding actor's looks. It
  checks itself: tile seams, an `.aseprite` round trip, and a second full
  generation that must match byte for byte.
- **`tools/build.py`** consumes `assets/` and `content/` and draws nothing. It
  resolves maps, assembles `build/manifest.json`, and writes the game. If the
  content names art the library does not have, it fails with `art-stale` and
  tells you to run the art pipeline - it will never quietly draw it for you.
- **`assets/` is committed**; `build/` is not. The art library is the
  reviewable record of what the art looks like. `build/` is derived, and
  committing it produced a phantom diff of every PNG on every machine.

## The loop

Every request that changes the game ends with a playable link and a picture:

```sh
python tools/build.py        # 1. rebuild and run the gates (art.py first if art changed)
node tools/shot.cjs          # 2. smoke-test the real game and shoot it
node tools/shot.cjs --map    # 3. and shoot the whole world
                             # 4. publish game/page.html (below)
```

1. **Build.** All 25 gates must pass. A gate failure names an authored file -
   fix that file, never the generated output. Needs Pillow.

2. **Screenshot.** `tools/shot.cjs` loads `game/index.html` in a headless
   browser, checks the scene actually booted (no console errors, every entity
   spawned, one collision body per blocked tile, livestock wandering) and
   writes `build/shot.png`. It exits non-zero if a check fails, so treat a red
   run as a broken build. It uses Playwright when it is installed and otherwise
   drives an installed Chrome or Edge through `tools/cdp.cjs`, so it runs on a
   developer machine with nothing to set up (`CHROME_PATH` overrides the
   search). Useful flags:

   ```sh
   node tools/shot.cjs --tile 33,40         # stand at a tile and look
   node tools/shot.cjs --talk --tile 33,37  # talk to Arne, check the replies appear
   node tools/shot.cjs --talk --choose 2 --tile 33,37   # and take the second one
   node tools/shot.cjs --gather --tile 34,37   # stand by an item, press E, check the bag
   node tools/shot.cjs --give item.axe --slash # arm the hero and swing
   node tools/shot.cjs --give item.axe --bag   # open the bag (I), check the cursor moves
   node tools/shot.cjs --pose slash,1 --page   # freeze the strike, shoot the whole page
   node tools/shot.cjs --map                # the whole world in one frame
   node tools/shot.cjs --on map.wilderness2 # start on another map, not the default
   node tools/shot.cjs --cross              # walk out of the map, check the bag arrives
   ```

3. **Publish.** `game/page.html` is the whole game in one file. Publish it with
   the `Artifact` tool.

   **There is exactly one artifact for this game** -
   <https://claude.ai/code/artifact/355a8c48-d634-4c00-9a5f-9df0ab78c216>.
   Publish with that `url` every time so the link already in someone's hands
   keeps working. Publishing without `url` makes a *second* artifact with a
   different link, which is never what is wanted. (`action: "list"` finds it
   again if this line ever goes stale.)

4. **Reply** with the artifact link, and send `build/shot.png` (and
   `build/map.png` when the map changed) with `SendUserFile`.

Then commit and push.

## The map editor

`python tools/editor.py` serves `editor/` at <http://127.0.0.1:8765/>. It reads
`build/manifest.json` and the same sheets the game loads, and resolves terrain
edges live with the mask table the build exported - so the preview is the
build's own answer, not an approximation of it. It writes
`content/maps/<name>.json` in the plain format, so a map made in the editor is
indistinguishable from one written by hand.

A save may only write over the map it came from - the server compares the
incoming `id` with the one in the target file and refuses a mismatch, so a map
can never be destroyed by a save meant for another.

Paint terrain, place and erase objects, move the spawn, undo, save, and
**save + build** to run the gates without leaving the page. Terrain and objects
are exclusive sets: the tool decides which palette is on screen, so the panel
never offers a swatch you cannot paint with. Objects are grouped by kind
(props, actors, items) and marked solid or walkable ground. Painting unwalkable ground over
something removes what stood there and says so, because the `map-footprint`
gate would refuse the map otherwise.

Nothing hot-reloads: F5 the page after editing `editor/*`, restart the server
after editing `tools/editor.py`. **Stop the old server before starting a new
one.** It refuses to start on a port already in use, because on Windows
SO_REUSEADDR happily lets a second server bind the same port and then requests
go to whichever instance wins the race - an old server serving stale code and
stale saves. That is not hypothetical: eight of them accumulated here and one
overwrote a map. `node tools/editor_test.cjs` drives the real
editor in a headless browser and checks all of the above
(`EDITOR_SHOT=path` also leaves a screenshot).

## The art scale standard

**These are the frame sizes, and the `art-scale` gate enforces them:**

| Atlas | Frame | Anchor | Rig |
|---|---|---|---|
| `tiles` | 16x16 | - | `gen/tiles.py` |
| `actors` | 32x32 | `(16, 29)` | `gen/actor.py`, `gen/animal.py` |
| `props` | 32x32 | `(16, 29)` | `gen/props.py` |
| `props_big` | 48x48 | `(24, 45)` | `gen/props.py` structures |
| `items` | 16x16 | `(8, 14)` | `gen/items.py` |
| `fx` | 8x8 | `(4, 4)` | `gen/fx.py` |

A rig that drifts to another size, or a new atlas added at the wrong one, fails
the build rather than looking subtly wrong in game. **New art is authored at
these sizes** - never drawn at another scale and resized in the pipeline. There
is deliberately no upscale helper in the codebase.

This scale was chosen on purpose. The art was once redrawn at twice this size;
the detail was real but every new prop then cost four times the pixel work, and
the effort was not worth it for a game this size. Everything here is drawn to
suit 16px ground, and anything new should be too.

### Shading

`_shade` lights the 1px rim of a mass; `_form` gives it volume by position
within its own bounds. **Shade inside the silhouette**: painting shading by raw
coordinate puts pixels outside the shape, and no assertion catches it. Render a
contact sheet and look.

Texture comes from `scatter(seed)`, a fixed deterministic generator. It returns
the *high* bits of its state: the low bits of an LCG cycle with a period as
short as the modulus, which laid tufts out in diagonal stripes and made grass
read as hatching. Use `_put` to place detail, so it wraps at the tile edge and
the tile repeats seamlessly.

### Ground

Ground is authored as plain terrain and drawn with variation and edges:

- **Variants.** A base tile takes a seed (`tiles.VARIANTS` says how many) and a
  cell picks one by position, so a field is never one stamp repeated.
- **Transitions.** Tiles marked `"blend": true` in `content/tiles/` get the
  full 47-tile blob set, generated by carving the terrain out of the ground it
  sits on along a wobbling boundary, with a treatment per terrain (sand and
  foam for water, a trodden strip for a path, a crumbling dither for sand and
  leaf litter, a kerb for cobble, a shadow at the foot of stone). What it is
  carved out of is `blend_over` in the content, grass unless stated - a field
  is cut out of bare earth, a shoal out of sand.
  **The limit:** a terrain's edge is drawn against its declared base, not
  against whatever happens to be next to it on the map. Two different blending
  terrains placed directly against each other will show that base between them.
  Give them the same base, or leave a tile of it between them.
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
- **Cost.** A blending terrain is 47 frames (1 base + 46 transitions), times
  its phases if it animates; a non-blending one is 1-3. All tiles live in one
  sheet, 16 columns wide, so 4096 frames fit before it reaches 4096px tall -
  there is a lot of room.
- Base textures wrap: place detail with `_put`, and it continues across the
  seam instead of being kept away from the edges.

## Where things live

```
tools/gen/palette.py   the one palette; a character variant is a key remap
tools/gen/actor.py     the biped rig      (32x32 frame, anchor [16, 29])
tools/gen/animal.py    the quadruped rig  (same frame, same contract)
tools/gen/props.py     props 32x32, structures 48x48 (anchor [24, 45])
tools/gen/tiles.py     16x16 ground tiles, variants and the blob transitions
tools/art.py           the art pipeline: draws everything -> assets/
tools/build.py         the game build: assets/ + content/ -> build/ + game/
tools/editor.py        serves the map editor in editor/
tools/cdp.cjs          drives an installed Chrome when Playwright is absent
tools/pipeline/        aseprite I/O, atlas packing, autotile, manifest, the 25 gates
assets/                COMMITTED art library: atlases, atlases.json, .aseprite
build/                 DERIVED, gitignored - manifest, screenshots
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

`blocks` means something different for something that walks. A static thing
gets a still body on each footprint tile and its tiles go into the blocked set
once. A `wander`er gets a single immovable body that travels with it, and
claims no tile in that set - it would be standing on its own wall and could
never leave the tile it spawned on. Because two immovable bodies do not push
each other apart, solid animals also reserve the tile they are heading for, so
a pair of sheep cannot walk into one spot and fuse. `node tools/shot.cjs
--bump` walks the hero into one and checks it is stopped.

**An item** is a 16x16 icon function in `tools/gen/items.py` (added to
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

**A way from one map to another** is an `exits` entry on the map you leave -
no engine change, like everything else here:

```json
"exits": [{ "tiles":  [[0, 18], [0, 19]], "to": "map.wilderness2",
            "spawns": [[30, 30], [30, 31]], "facing": "left" }]
```

`tiles` are the doorway. A door into a building gives one `spawn` and everyone
arrives there; an edge between two maps gives `spawns`, one per doorway tile,
paired by position - **step off the west edge at a given height and come out at
the same height on the east edge of the next map.** That is what makes a seam
read as more country rather than as a door, and it is worth the extra data:
funnelling a ten-tile edge through a single arrival tile is exactly what made
the first version feel wrong. Wilderness I and II are joined along a band ten
tiles deep measured *up from the bottom of each*, so their bottom rows align
even though one map is 20 tall and the other 32. Arrivals sit one tile inside
the far edge, never on the far map's own doorway column. The
crossing **restarts the scene**, so anything the player must keep - bag, gear,
level, xp, flags - is carried across explicitly in `checkExit()`; a field added
to the scene and not to that list is silently lost at the map edge. Write the
way back as an `exits` entry on the other map. Two rules the `map-exit` gate
enforces on *every* arrival, both of which are bugs you would otherwise find by
playing: an arrival tile has to be standable (in bounds, walkable, not inside a
solid), and it must not itself be an exit - landing on the way back bounces the
player straight through it, which looks like the two maps flickering. `node
tools/shot.cjs --cross` walks it for real, crossing at the middle of the band
where an off-by-one in the pairing would show, and checks the bag arrived and
the height was kept.

**Draw the road up to the seam, not into the corner.** A track that runs out
through the very corner tile reads as having nowhere left to go; ending it a
couple of rows short, at the height the other map's road meets its own edge,
is what makes the two halves look like one road.

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

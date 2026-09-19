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
  A different Pillow re-encodes every sheet it writes, identical pixel for
  pixel and different byte for byte, so **an art commit that touches sheets
  you did not change is that and not a redraw** - compare the decoded pixels
  before believing it, and put the untouched ones back.

## The loop

Every request that changes the game ends with a playable link and a picture:

```sh
python tools/build.py        # 1. rebuild and run the gates (art.py first if art changed)
node tools/shot.cjs          # 2. smoke-test the real game and shoot it
node tools/shot.cjs --map    # 3. and shoot the whole world
                             # 4. publish game/page.html (below)
```

1. **Build.** All 32 gates must pass. A gate failure names an authored file -
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
   node tools/shot.cjs --exit 3 --cross     # ...by its fourth doorway, not its first
   node tools/shot.cjs --on map.wilderness3 --boar   # stand still, get charged
   node tools/shot.cjs --quest              # take every errand on offer and run it
   node tools/shot.cjs --kill               # strike a hostile until it dies
   node tools/shot.cjs --journal            # open the quest log
   node tools/shot.cjs --spawn npc.troll     # something no map carries yet
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
can never be destroyed by a save meant for another. A save also carries through
every key it does not understand. `save()` names the fields it writes, and
`exits` was once not among them, so opening a joined map and pressing save
quietly disconnected the world - and no gate caught it, because a map without
exits is perfectly legal. Anything added to the map format needs to survive
that round trip.

Paint terrain, place and erase objects, move the spawn, undo, save, and
**save + build** to run the gates without leaving the page. **W** is the world
atlas, **Q** the quest board and **D** the conversation graph (below). Terrain and objects
are exclusive sets: the tool decides which palette is on screen, so the panel
never offers a swatch you cannot paint with. Objects are grouped by kind
(props, actors, items) and marked solid or walkable ground. Painting unwalkable ground over
something removes what stood there and says so, because the `map-footprint`
gate would refuse the map otherwise.

### The world view

Press **W**, or the `world` button, for the atlas. A map carries no world
position - only doorways, each saying "this edge of mine leads to that map, and
you arrive over there". That is enough to place them: follow the doorways and
every map lands against the one it joins, lined up on the row the player walks
across. So the atlas is not a diagram kept alongside the content, it is the
shape the content already has, and a wrong join shows up as a map in the wrong
place rather than as a note nobody reads.

A **gate** is the way through between two maps, and it has a mouth on each
side. The two mouths are the thing that has to be read together, so each gate
gets a colour and a number used everywhere it is drawn: a filled band on the
mouth, an arrow running to where it puts you down, a dashed arrow if the trip
is one-way, and a matching row in the panel giving the pair, the edge and how
wide the crossing is. The mouths on the map you are editing carry the same
colour and number, with an arrow per tile pointing the way you leave, and
arrivals from elsewhere drawn as a dashed outline - so both ends of a crossing
are visible without leaving the map.

Maps that reach each other form one world; maps that reach nothing are stacked
below. That is what the view is for: the two Riverside maps sat there as their
own islands for a while, 159 entities of one of them, with nothing in the game
able to reach either - and no gate treats that as an error, because a map
nobody walks to is still a valid map. The panel also reports one-way links.
Clicking a map or a gate opens it.

**Where a gate sits on the new map decides where that map lands**, and the
ground next door may already be taken. Wilderness VI is 40x40 against
Wilderness I's 20, joined along the whole of Wilderness I's north edge: joined
at its *middle* it would hang ten tiles west, straight over Wilderness IV,
which is already north of Wilderness II. So the seam is its south-west twenty
columns and the map runs east instead. No gate catches two maps in one place -
the editor's world view does, and `no two maps overlap on the atlas` in
`editor_test.cjs` is the check that says so.

**A gap is as wrong as an overlap, and nothing was checking for one.** The
layout places a map two ways: hanging the destination off a doorway of the map
it already has, or - for a map reached only by a doorway *pointing at* it -
hanging it off that doorway instead. The second case took both the edge and the
width from the wrong one of the two maps, which is invisible while every map
placed that way is the same size as its neighbour, and every one of them was
20x20 for a long time. Wilderness V is sixty wide: open Wilderness VII and V
landed forty tiles east of where it joins, with a hole between them. Which map
is open must not move anything, so the check is now `every seam is flush and
lined up, whichever map is open` - it opens each map in turn and asserts, for
every edge-aligned gate, that the two maps share that edge and the crossing
rows line up.

Gates run north-south as readily as east-west - Wilderness IV sits above
Wilderness II - and which coordinate a crossing preserves depends on the edge:
cross a side edge and you keep your row, cross a top or bottom edge and you
keep your column. `--cross` measured the row either way for as long as every
gate in the game ran east to west, and passed for the wrong reason until the
first north-south one was built.

**A door is not a seam.** A doorway that sits inland - the shed on Wilderness
I, whose art always drew a door on its front tile - leads somewhere that is not
next to anything, so the atlas keeps interiors off the grid entirely: they sit
in a band below the world on a plate of their own, with a line drawn back to
the exact tile their door stands on. That is the half a reader needs, because
the room is nowhere but its door is somewhere precise. `interiorsOf()` decides
it: a map with no edge-aligned way in is an interior. A prop can only be a door
if its footprint leaves the doorway tile out - the shed's was solid, so for a
while the door was a picture of a door.

**Arriving faces the way you were walking.** Reaching an edge-wide doorway
means walking at that edge, so west means left, east means right, and a
crossing that hands you a different facing spins the player round on the spot.
`map-exit` enforces it for every edge-aligned doorway, which is how the
Wilderness II crossing was caught; an inland doorway is exempt, having no edge
to infer a direction from. `node tools/shot.cjs --cross` walks a gate for real
and checks the arrival, the row, the bag and the facing.

**Gatherable, or just scenery.** The game decides that one way: a definition
that comes from `content/items/` becomes a pickup, and a prop or an actor never
does however much it looks like loot. The editor reads the same fact rather
than keeping a list - items are marked with a gold diamond in the palette and
ringed on the map, against solid and walkable-scenery marks for everything
else, so placing a thing tells you whether it can end up in the bag.

The map's in-game name is editable in the bar; it was previously hand-edited
JSON only.

### The quest board and the conversation graph

Two more views, **Q** and **D**, both read-only: quests and conversations are
authored as JSON and checked hard by the build, so the editor's job is not to
write them but to show the half of them no single file contains.

**The quest board** answers the one question a quest file cannot: whether the
world can pay it. Each objective says how much of what it asks for is actually
placed (`7/3 placed`, and which maps), and goes red when it is short. That
count is of the maps as they stand *including the one on screen, unsaved* -
paint over the last berry and the board goes red before the build ever sees it,
which is the whole reason it lives here rather than in a gate alone. A card
also names who gives the errand and links to the replies that offer and take
it. Anything a quest depends on is marked on the map view with a gold star and
named in the status bar, because erasing one of those looks like any other
erase.

**The conversation view** draws a dialogue as the graph it already is: a box
per node, laid out in columns by how many replies deep it is, so the way in is
on the left and the endings are on the right. Replies are arrows - solid
forward, dashed back - and each carries marks for what it does (`?` conditional,
`⚑` sets a flag, `+`/`−` gives or takes, `✦` starts a quest, `✓` hands one in),
because the shape of a conversation is mostly in its effects and they are
invisible if only the text is drawn. Click a node to read the whole of it with
every condition and effect spelled out. `no two nodes are drawn on top of each
other` and `every reply lands on a node that is drawn` are the checks in
`editor_test.cjs` that keep the picture honest.

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
| `actors_huge` | 64x64 | `(24, 61)` | `gen/giant.py` |
| `props` | 32x32 | `(16, 29)` | `gen/props.py` |
| `props_big` | 48x48 | `(24, 45)` | `gen/props.py` structures |
| `props_huge` | 64x64 | `(24, 61)` | `gen/props.py` four tiles wide |
| `props_vast` | 128x128 | `(56, 125)` | `gen/props.py` four by four |
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
tools/gen/giant.py     the giant rig      (64x64 frame, anchor [24, 61])
tools/gen/props.py     props 32x32, structures 48x48, and the 64/128 erratics
tools/gen/tiles.py     16x16 ground tiles, variants and the blob transitions
tools/art.py           the art pipeline: draws everything -> assets/
tools/build.py         the game build: assets/ + content/ -> build/ + game/
tools/editor.py        serves the map editor in editor/
tools/cdp.cjs          drives an installed Chrome when Playwright is absent
tools/pipeline/        aseprite I/O, atlas packing, autotile, manifest, the 32 gates
assets/                COMMITTED art library: atlases, atlases.json, .aseprite
build/                 DERIVED, gitignored - manifest, screenshots
content/               AUTHORED json - actors, props, tiles, dialogue, quests, maps
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

**A prop that moves** names itself in the `ANIMATED` table for its frame size
(`ANIMATED`, `ANIMATED_BIG`, `ANIMATED_HUGE`, `ANIMATED_VAST`) in
`tools/gen/props.py` with a frame count and a frame time, and its draw function
takes `phase`. All four sheets are packed by the same helper, so a thing four
tiles across moves for the same reason a campfire does - the two biggest
classes each had a loop of their own and no animation at all until the temple
wanted fire. The first frame keeps the plain id as its atlas key, so the
editor palette, the `sprite-exists` gate and anything else that only wants a
picture of the thing are unaffected; the rest are added after and named by an
animation the engine already knows how to create. In game each instance starts
at a different point in the cycle, keyed off its tile - a row of campfires
flickering in step reads as one object repeated rather than as several things
burning. The palette marks them, from the animations that exist rather than
from a second list that could drift.

Seven move: campfire, hearth, lamp_post, beehive, trough, windmill and temple.
Everything else is still on purpose - the trees, bushes and flowers are the most
numerous props in the game, so animating them multiplies the sheet and pulls the
eye to the background, and a table has no reason to move by itself.

**A prop bigger than a building** goes in the 64x64 class: a function in
`tools/gen/props.py` added to `HUGE_PROPS`, and a file in `content/props/`.
Four tiles wide. An even tile count has no middle tile, so the anchor cannot
sit at both the frame centre and a tile centre - it sits at a tile centre
(x=24) because that is what keeps the sprite square on the grid, and the art is
drawn centred in the frame, which means the sprite covers tile offsets -1, 0,
+1 and +2. `prop.burrow_tree` is the first of them; its root flare reaches
nearly the full width of the frame on purpose, because that is what makes a
four-tile footprint read as solid rather than as a canopy floating over
walkable ground. Nothing else needs wiring: the editor loads whatever atlases
the manifest lists, and `art-scale` accepts a new one at any multiple of 16.

**A prop that stands on a square of ground** - four tiles by four - needs the
128x128 class (`VAST_PROPS`), and that is the only reason the frame exists: a
mass four tiles deep eats 64px of the frame from the bottom before any of it is
height, and there is nothing left of a 64px frame to be tall with. Same rule
again - anchor on a tile centre (x=56), art centred - so it covers offsets -1,
0, +1, +2 and rises most of four tiles over them. `prop.boulder_16` was the one;
`prop.temple` is the second and the first thing this size that moves.

**The temple** is what the 128 frame is for when the thing on it is built
rather than dumped: a stone podium, four vermilion columns under two tiers of
upswept tile roof, guardians at the foot of the steps, a pair of lamp columns
burning at the front, and dust hanging over the stairs. Grey-blue tile against
vermilion post is the whole colour idea - the roof reads as one mass and the
posts as another, which is what stops a facade this size turning into texture.
Two things had to be fixed by looking at it rather than by reasoning: the
guardians were cut in the same stone as the podium and vanished into it
completely (they are `STD`/`STX` now, with `FIL` eyes catching the fire), and
the lamp columns were stone on stone for the same reason and are painted. The
fire is four frames from `TEMPLE_FLAME`, all ending in the bowl; the dust is
drawn *after* `outline()`, because a translucent mote with a hard line round it
is a pebble in the air.

**The boulders are a size ladder**, and that is the point of them: 2, 4, 6, 8
and 16 tiles, from something you walk round to something a road stops at. A
field of rock drawn from one rock at one size reads as a repeated stamp however
carefully it is scattered. Each is authored at the frame its footprint needs
(`boulder_2`, `_4`, `_6` at 48x48, `_8` at 64x64, `_16` at 128x128) rather than
drawn once and scaled, and all five share three helpers in `tools/gen/props.py`
worth knowing about before drawing any other rock:

- `_mass` unions discs and then fills each column between its own topmost and
  bottommost pixel. Filling down to the ground line instead - which was the
  first thing tried - gives every boulder vertical sides and a flat top, a mesa
  rather than a rock. The lobes that carry the weight are placed *through* the
  ground line and cut off by it, which is what leaves a broad flat base.
- `_form` partitions the mass between a few planes by straight lines, because
  that is what a facet is. A gradient quantised into bands was tried first and
  a mass this size shaded that way reads as an airbrushed ball with contour
  lines on it, whatever the thresholds. Its grain is divided by the mass's own
  span: a fixed jitter frays a small rock by a pixel and a large one across a
  quarter of its face.
- `_moss` thins each lichen patch towards its rim. A solid disc of one colour
  on a boulder reads as a sticker.

**An NPC** is a file in `content/actors/` plus a line in the map. Its `rig`
(`biped` / `quadruped` / `giant`), `states`, `speed`, `blocks`, `interact` and
`wander` settings are all content. No JS changes.

**A new face is a palette entry, not a drawing** - `VARIANTS` in
`tools/gen/palette.py`, and the actor's `sprite` names it (`actor.monk` ->
variant `monk`). Friedrich is the hero's frames with a saffron robe, and
**bald is a remap too**: the rig draws a crown of hair over the skull, so
pointing `HR` and `HRL` at the skin keys leaves a shaved head with the light
still on the dome. Nothing in the rig knows there is a bald character, which
is the whole point of storing keys rather than colours.

**A monster bigger than a person** uses the `giant` rig - 48px tall and 32
wide, drawn in a 64x64 frame on its own sheet, because a creature three tiles
tall does not fit in the frame the people and the livestock share. A rig names
the sheet it belongs on (`ATLAS`, `COLS`) and `art.py` makes one sheet per
actor frame size, so a fourth rig at a fourth size is two constants and an
entry in `RIGS`. The anchor sits at a tile centre (x=24) like the 64x64 props,
so the art covers tile offsets 0 and +1 and the definition says so with
`"footprint": [[0, 0], [1, 0]]`. Nothing else needs wiring: the editor loads
whatever atlases the manifest lists, the engine reads the frame size and anchor
off the atlas, and a wanderer's collision body is derived from its footprint -
`npc.troll` is two tiles of body, not the sheep's one.

**Something that swings rather than just touching you** declares an `attack`
state, which the rig draws and the engine plays when a hostile lands a blow;
it plants its feet for as long as the swing runs. An actor without one still
hurts on contact, which is what the boar does. The animation is content: no
list of creatures that punch exists anywhere in the engine. The quadruped rig
has one too now - head down and thrown forward, since a deer has nothing else
to hit you with - and adding it to `STATE_ORDER` changed nothing for the sheep,
the goat or the boar, because a rig only draws the states its actor declares.

**Putting the hero somewhere, in a test:** `body.reset(x, y)`, never
`sprite.setPosition(x, y)`. A dynamic Arcade body writes its own position back
over the sprite on the next step, so setPosition teleports nothing and the
hero snaps to where it was. This is not cosmetic - it made the collision test
pass without the hero ever standing next to the animal, and it made the boar
look as though it never charged. A test that moves the hero and then asserts
they did not get somewhere is exactly the test this silently breaks, so assert
contact (`body.touching`) rather than distance alone.

`blocks` means something different for something that walks. A static thing
gets a still body on each footprint tile and its tiles go into the blocked set
once. A `wander`er gets a single immovable body that travels with it, and
claims no tile in that set - it would be standing on its own wall and could
never leave the tile it spawned on. Because two immovable bodies do not push
each other apart, solid animals also reserve the tile they are heading for, so
a pair of sheep cannot walk into one spot and fuse. `node tools/shot.cjs
--bump` walks the hero into one and checks it is stopped.

**Something that attacks you** is the same file plus a `hostile` block, and
chasing is a mode a wanderer drops into rather than a second kind of creature:

```json
"hostile": { "sight": 68, "lose": 132, "leash": 80, "charge_speed": 62,
             "damage": 4, "reach": 18, "cooldown_ms": 1100 }
```

**`leash` is the one that keeps it an animal rather than a missile.** It is the
furthest the creature will get from where it spawned; past that it breaks off
whatever it can see, walks home *at its own `speed` rather than the charge* -
being chased across the whole map is not a fight, it is a nuisance, and a boar
that jogged home at charging speed would still be on top of you - and then goes
back to wandering like any sheep. It does not notice you again until it is home,
so you cannot lead it away and pin it. If it wedges on a tree on the way back it
settles where it stands after a couple of seconds rather than pushing into the
trunk for ever.

`lose` is wider than `sight` on purpose: equal, and the animal flickers in and
out of the chase at exactly the distance you happen to be standing at. **`reach`
is centre to centre, and both bodies are solid** - the collider holds those
centres about 14px apart side on, so a reach below that can never land a hit
however close the animal gets. It is the one number here that is easy to set to
something quietly impossible. A charge heads straight at the hero rather than
tile by tile, and tests each axis against `isWalkable` first, because the body
is immovable and nothing else would stop it coming through the rock.

**Something that only fights back** adds `"provoked": true` to that same block.
It is one flag rather than a second kind of creature: the elk carries the whole
hostile block from the start and simply does not use it until something hits
it, and after that it is a boar with antlers until it gets home again, where it
forgets. `provoke()` in `game/main.js` is the only thing that sets the flag, so
nothing in the engine knows what an elk is - and it fires for *anything* with a
`hostile` block, so a struck boar now turns on you rather than bolting. Because
it does, a creature that turns cannot also run: `strike()` startles it or
provokes it, never both.

The `actor-hostile` gate requires every field, positive, with `lose` outside
`sight` and a `wander` block to fall back to. `node tools/shot.cjs --on
map.wilderness3 --boar` stands in front of one and checks four things: it
notices, it closes, it costs hp, and it goes home and settles - and on a
`provoked` creature it first checks the other half, that being left alone
leaves you alone, because a test that only watched it charge would pass just as
well with the flag deleted. **Give a wanderer room to charge in**: `leash` is
measured from where it spawned, so a wide `wander.radius` and a short leash
leaves it no distance to charge in at all - it notices, takes two steps, and
breaks off at the end of its own tether.

Damage to the hero goes through `hurt()`, which subtracts armour but never all
of it, and running out of hp is not death: `blackOut()` puts you back at the
map's spawn whole, which keeps a boar a hazard to respect rather than a way to
lose an hour of picking things up.

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
choice may carry `when` (`flag` / `noflag` / `has` / `nothas` / `quest` /
`all`) and the effects `set`, `give`, `take`, `start` and `finish`; no `goto`
ends it. Effects run finish, take, give, set, start - handing a quest in is
what empties the bag, so it goes before anything that tries to fill it, and a
quest taken here has nothing to do with what was just handed over. Keep the
condition language as small as it is - the gates can only check branches they
understand.

**An errand** is a file in `content/quests/` plus the two replies that offer it
and take it back. The engine knows four kinds of objective and nothing about
any particular quest:

```json
{ "id": "quest.arne_berries", "name": "A Handful of Berries",
  "giver": "npc.arne", "summary": "Arne wants three handfuls of berries.",
  "objectives": [
    { "id": "ask",  "kind": "talk",    "target": "npc.goat",
      "text": "Have a word with the goat" },
    { "id": "pick", "kind": "collect", "target": "item.berries", "count": 3,
      "text": "Gather three handfuls of berries" }],
  "reward": { "xp": 30, "give": "item.coin", "set": "arne.berries_done" } }
```

`collect` counts what is in the bag, `kill` counts what has died since the
quest was taken, `talk` is met by speaking to that definition, and `visit` by
standing on that map (a `tile` and `radius` narrow it to a spot).

**A quest is in one of four states, and those four words are the whole language
a conversation has for asking about one**: `none`, `active`, `ready` (every
objective met, not handed in) and `done`. A reply asks with
`"when": {"quest": {"id": "quest.x", "is": "ready"}}` - `is` may be a list, and
that is also how "taken but not finished" is said without a negation. One key
rather than four, and a gate can check the word.

**Fetching is counted off the bag, not remembered.** Put a berry down and the
tick goes away again, which is the only version of this that cannot drift out
of step with what the player is actually carrying. The other three kinds are
things that happened, so those are what the record holds - and a quest that has
been handed in shows every objective met regardless, because the berries are in
Arne's hands by then and a finished errand reading 0/3 looks like a bug.

**Handing in takes what the quest asked for**, so no content says twice what
three berries means; mark a `collect` objective `"keep": true` if the player
was only ever asked to *have* it. A quest marked `"auto": true` needs no
hand-in and finishes itself the moment it is ready.

Five gates cover the ways an errand breaks silently: `quest-shape`,
`quest-target` (nothing to say, nothing to kill, no such map),
`quest-reward`, `quest-supply` - **the maps must place at least as much of a
thing as the quest asks for**, which is what catches "fetch three berries"
where two exist - and `quest-reach`, which requires that some reply starts it
and, unless it is `auto`, that some reply takes it back.

**Anything carried across a map edge has to be in `checkExit()`.** The journal
is exactly the kind of field that gets forgotten there; `node tools/shot.cjs
--cross` now starts an errand before it walks the doorway and checks it arrived.

**A creature dies only if its definition says how much it can take.** `"hp"` on
an actor is the whole rule - the sheep and the goat have none and can be hit
all day, and nothing in the engine knows which animals those are. A `kill`
objective on something with no `hp` fails `quest-target`, because it is a
bounty that can never be collected.

**A way from one map to another** is an `exits` entry on the map you leave -
no engine change, like everything else here:

```json
"exits": [{ "tiles":  [[0, 18], [0, 19]], "to": "map.wilderness2",
            "spawns": [[18, 18], [18, 19]], "facing": "left" }]
```

`tiles` are the doorway. A door into a building gives one `spawn` and everyone
arrives there; an edge between two maps gives `spawns`, one per doorway tile,
paired by position - **step off the west edge at a given height and come out at
the same height on the east edge of the next map.** That is what makes a seam
read as more country rather than as a door, and it is worth the extra data:
funnelling a ten-tile edge through a single arrival tile is exactly what made
the first version feel wrong. Wilderness I and II are both 20x20 and joined
along the bottom ten rows, so the crossing is row for row. Pair the band by
distance *up from the bottom* rather than by row number, and two maps of
different heights join just as cleanly. Arrivals sit one tile inside the far
edge, never on the far map's own doorway column - and remember an arrival tile
belongs to the map you land on while being named by the map you left, so it is
easy to build something on top of one. The
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

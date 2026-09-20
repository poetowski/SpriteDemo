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
  before believing it, and put the untouched ones back. **Then run the build
  again**, before committing: `game/art-embed.js` carries every sheet inline
  as base64, so putting a PNG back after the build leaves the embed holding
  an encoding that is in no file in the tree. That went in once - the game was
  identical to play, and the derived file simply did not come from the
  committed one.

## The loop

Every request that changes the game ends with a playable link and a picture:

```sh
python tools/build.py        # 1. rebuild and run the gates (art.py first if art changed)
node tools/shot.cjs          # 2. smoke-test the real game and shoot it
node tools/shot.cjs --map    # 3. and shoot the whole world
                             # 4. publish game/page.html (below)
```

1. **Build.** All 34 gates must pass. A gate failure names an authored file -
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
   # Coordinates are per map and these are real ones: the examples used to
   # name tiles on the 96x72 Riverside map, which has not existed for a long
   # time, so every one of them pointed off the edge of the world.
   node tools/shot.cjs --on map.wilderness6 --tile 24,19   # stand at a tile and look
   node tools/shot.cjs --on map.wilderness2 --talk --tile 13,17  # talk to Arne
   node tools/shot.cjs --on map.wilderness2 --talk --choose 2 --tile 13,17  # take reply 2
   node tools/shot.cjs --on map.wilderness2 --gather --tile 4,7  # press E by an item
   node tools/shot.cjs --give item.axe --slash # arm the hero and swing
   node tools/shot.cjs --give item.axe --bag   # open the bag (I), check the cursor moves
   node tools/shot.cjs --pose slash,1 --page   # freeze the strike, shoot the whole page
   node tools/shot.cjs --map                # the whole world in one frame
   node tools/shot.cjs --on map.wilderness2 # start on another map, not the default
   node tools/shot.cjs --cross              # walk out of the map, check the bag arrives
   node tools/shot.cjs --exit 3 --cross     # ...by its fourth doorway, not its first
   node tools/shot.cjs --on map.wilderness3 --boar   # stand still, get charged
   node tools/shot.cjs --on map.wilderness9 --tile 9,17   # the fen, and a heron over it
   node tools/shot.cjs --on map.wilderness9 --talk --tile 15,29  # Goor, at the gate
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

**A zone is a tag its maps share.** `"tags": ["desert"]` on a map, edited in
the bar beside the name, and the world view groups by it: a heading per zone
over its own maps, a chip on each line, and the zone's name over its plate on
the atlas. A tag is not a second way of saying what a doorway already says -
the layout is still derived from doorways alone and a tag moves nothing. It is
for the case doorways cannot cover: a region that is coming but is not joined
yet. The desert is that case, and until a portal exists it is an island on the
atlas. So the tag also decides what the panel *says* about an unreached map -
a tagged one is "a zone of its own until something reaches it", informational;
an untagged one is still the red "nothing reaches it", which is the failure
the view exists for. Getting those two the same way round is the whole value:
tagging must not be a way to silence the check on a map somebody forgot.

A tag also decides that the map is **not a room**. An inland doorway is what a
door into a building looks like, and it is also what a portal looks like, so
the far side of one is filed as an interior unless it carries a tag - which is
how the desert ended up under the world in the interiors band, marked
"inside", the moment the portal joined it.

**A zone does not have to be an island, and the second one is not.** The
jungle begins at Wilderness IX and carries on into Wilderness X, both joined
to the rest by ordinary seams - you walk into them. So the tag is doing its
other job there: the maps have places on the grid like any others, and what
the tag adds is the heading they are filed under and the name the zone goes by
before there is anything else in it. A plate is captioned only when every map
on it shares one tag, so the wildernesses' plate stays uncaptioned with two
jungle maps on its southern corner, which is right - that plate really is two
countries now.

**The wilderness runs out at X**, and the way on is not another seam. The
crystal gate on the knoll at the bottom of Wilderness IX is a prop and nothing
else: no `exits` entry, because it does not go anywhere yet, and Goor standing
on the court in front of it is the reason rather than an apology for one. A
gate that is shut is content; a gate that is shut *and unexplained* is a bug
report waiting to be filed.

`map-tags` keeps the vocabulary usable rather than the tags correct: a list if
present, non-empty, lowercase, no spaces, no duplicates - so `Desert` and
`desert` cannot become two zones. The bar lowercases and joins up what you
type rather than refusing it, because nobody should have to remember a gate's
rules while typing.

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
| `actors_huge` | 64x64 | `(24, 61)` | `gen/giant.py`, `gen/beast.py` |
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

**`outline()` decides how thin anything is allowed to be**, and it is the one
constraint that catches every new plant. A feature one pixel wide gets a black
border on both sides and comes back as a *hair*: the marsh bush's first spray
of leaves was a fuzzy black crest where its foliage should have been, and a
reed bed drawn as six parallel stalks came out as a dark comb. Three pixels
thick is the thinnest thing that survives, which is why a leaf uses the palm's
`_frond` rather than a line of pixels. Spacing has the same arithmetic: a
two-pixel stalk takes a border each side, so two of them five pixels apart
leave no daylight between and six is the first gap that shows. Work it out
before drawing eight of anything - and leaves standing clear of a mass want
the *light* tone, because a spray of shade-coloured ribs on a shade-coloured
mound is a hedgehog.

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
  **`family` is the answer whenever two terrains should not edge against each
  other at all**, and it is easy to reach for the wrong tool first. Lilies
  blended over the oasis and were kept two clear tiles off every shore, which
  fixed nothing: the problem was never the lily's edge but the *water's*, and
  every oasis tile touching a patch drew its shore against it, so each drift
  came out ringed in sand in the middle of the lake. One shared family and
  neither draws an edge against the other. It also made the lily five frames
  a phase instead of forty-seven, because a tile that never meets a different
  family never needs a transition and does not have to blend at all.
- **Animated ground.** `tiles.ANIMATED` names tiles drawn in phases (water:
  three; a bog: two, because nothing stirs one and all the phases have to do
  is move the light about on it). The build emits every phase of every variant and transition as its
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

### A second biome

The desert is the first ground that is not the wilderness's, and it is a
worked example of everything above rather than a special case. Nothing in the
pipeline knows there are two biomes:

- **It is its own family of palette keys, not a recolour.** `DN`/`SL`/`SS`/
  `SC`/`OA` (dune, salt, sandstone, scrub, oasis) plus `GD` gold and `LP`
  lapis sit alongside the grass keys in `tools/gen/palette.py`. Tinting the
  green keys sand-coloured would have made every existing tile change with
  them, which is the thing a shared palette is supposed to prevent.
- **Everything blends over `tile.dune`.** Salt, sandstone, scrub and the oasis
  all name dune as their `blend_over`, which is what lets any of them sit
  against any other - the limit above is a limit on terrains with *different*
  bases, and one base for the whole biome makes it go away.
- **Dune is the only non-blending one**, so it is 4 variants rather than 47,
  and it is the ground everything else is cut out of. The oasis animates like
  water (three phases), which is 141 frames for the one terrain.
- **The edge styles carry the biome's meaning.** Salt and sandstone use
  `_edge_drift`, which heaps sand on the lee side, because in a desert the
  thing that rubs out an edge is wind. The oasis gets `_edge_oasis`: a wet
  shore and a lit rim, and deliberately no foam, because still water has none.

**Not everything in a desert is desert-coloured.** The lily pads are the
wilderness's bush green, because they are the one genuinely lush thing in the
biome - the plant growing in the only water for a day's walk. Drawn in the
desert's own greens they were a khaki disc on teal, which reads as sand
floating on the surface. Borrow from the other palette when the *thing* calls
for it, rather than because the map it sits on does.

**Lapis and gold on sandstone is the whole colour idea**, and it is worth
saying out loud because it is what makes the built things read as one
civilisation: the urn, the obelisk, the sun gate and the colossus are all
sandstone with the same two accents, and the desert tunic is the same idea
worn. Three colours doing the work of a style guide.

### A third biome, and the first one that has to meet another

The wetland starts on Wilderness IX, and it is a different problem from the
desert: the desert is reached through a portal, so it never touches the
meadow and never had to look like anywhere in particular next to it. A
transition map has that as its whole job. Two terrains, and everything
interesting about them is in how they meet what is beside them:

- **`tile.marsh` is cut out of the wilderness's own grass.** That is what
  makes the fringe a transition rather than a join, and its edge style,
  `_edge_sedge`, is the biome's meaning again: the desert's boundary is
  drifted over by wind and the river's is cut by water, but what rubs out a
  fen's edge is *growth*, so the outermost thing in it is a stalk standing
  out in the turf. Everything it draws goes outside the fen. The first
  version scattered lit seed heads in a band just inside the boundary, and a
  band that follows an outline *is* an outline - every patch came out ringed
  in a dotted yellow line, like something a highlighter had been round.
- **`tile.bog` shares the marsh's `family` and does not blend at all**, which
  is the lily's answer to the lily's problem. Drawn as its own family with its
  own shore, every marsh tile beside a pool saw a different ground next to it
  and drew *its* edge - against grass, the only thing it knows how to be cut
  out of - so each pool came out ringed in meadow in the middle of a fen. The
  pool's shore was never the problem; the marsh's was. **When two terrains
  ring each other wrongly, look at the edge of the one you were not
  thinking about.**

That choice has a price, and it is worth knowing which way it runs: a
terrain with no transitions has a bank on the tile grid, and nothing in the
pipeline will soften it. You cannot have both - the machinery cannot say
"edge against grass but not against bog" - so the fringe gets the soft edge,
because a transition map is mostly fringe. What pays for the banks instead is
authored: pools built as two lobes with a waist, single-tile bites and a
tussock left standing in the water, and reeds along the waterline. That is
where a bank's raggedness belongs anyway.

**Ground with water in it is darker than turf, and that has to be measured.**
Grass is luma 105, marsh 86, bog 65 - a ladder you can see from across the
map, which is what tells you the ground has changed before you can make out a
single blade. The first marsh was an olive a step *brighter* than the meadow
and it read as a dry field whatever its hue. The one colour idea in the
biome is that **the wetland's green leans blue where the meadow's leans
yellow** - which is also the note the jungle south of here carries on - and
it survives in the hue, not in the value.

### Adding a key

**Check the name is free first, and the `palette-keys` gate now does it for
you.** `PALETTE` is a dict literal, so a repeated key takes the last value
without a word: the portal's violet went in as `AR`, which had meant the elk's
rump patch since the elk was drawn, and the elk would have quietly turned
purple with nothing anywhere to say why. The drawing that loses its colour is
never the one you are editing, which is what makes it worth a gate rather than
a habit. The violet is `PO` now.

A key also wants to be its own family rather than a shade of an existing one
when the thing it is for belongs to nothing already here - the portal is
violet because violet is in neither biome, and a gateway painted in the local
greens or the local golds reads as a floor tile somebody laid.

## Where things live

```
tools/gen/palette.py   the one palette; a character variant is a key remap
tools/gen/actor.py     the biped rig      (32x32 frame, anchor [16, 29])
tools/gen/animal.py    the quadruped rig  (same frame, same contract)
tools/gen/giant.py     the giant rig      (64x64 frame, anchor [24, 61])
tools/gen/beast.py     the big-quadruped rig (64x64 frame, anchor [24, 61])
tools/gen/bird.py      the flier rig      (32x32 frame, drawn in the air)
tools/gen/props.py     props 32x32, structures 48x48, and the 64/128 erratics
tools/gen/tiles.py     16x16 ground tiles, variants and the blob transitions
tools/art.py           the art pipeline: draws everything -> assets/
tools/build.py         the game build: assets/ + content/ -> build/ + game/
tools/editor.py        serves the map editor in editor/
tools/cdp.cjs          drives an installed Chrome when Playwright is absent
tools/pipeline/        aseprite I/O, atlas packing, autotile, manifest, the 34 gates
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

**The crystal gate** is the third thing this size, and it taught three rules
that apply to anything drawn as a front elevation rather than as a lump:

- **Anything drawn inside a silhouette has to bring its own edge.** The ring
  is laid over the two columns, and the first version gave it the same grey as
  the shafts behind it - so the whole upper half came out as one grey slab
  with a blue hole in it and there was no ring at all. `outline()` only wraps
  the *outside* of a sprite; a band a shade lighter with a near-black rim on
  both its edges is what separates it, which is the same trick the giant rig's
  `_limb` uses for an arm lying over a belly.
- **A rune needs a socket.** Drawn as bright strokes laid on the face of the
  stone, a mark this size is a speck of dirt. Sunk in a near-black cut, the
  same strokes read as something carved with light coming out of it. What says
  "written" at 16px is never the shape of the glyph - it is that one angular
  shape repeats round a band, the way real carved work does.
- **Light is a glint, not a body.** The crystals turning in the ring were
  built white with a blue edge and came out as ice cubes floating in a bowl.
  Blue with one lit facet is a crystal.

Its four frames are also worth copying for anything that rotates: each shard
advances **a quarter of its own spacing** per frame, so after four frames every
one has arrived exactly where its neighbour started and the loop closes with
nothing jumping. Turning each a quarter of the way round the ring instead -
the obvious thing to do with four frames - is four separate pictures shown in
sequence, and reads as a stutter.

**Something standing guard in front of a tall prop has to stand south of it.**
Depth is the anchor row, so a guard placed above a gate eight tiles high is
drawn behind eight tiles of stone and is simply not in the picture. Goor is
two rows below the gate's base, which also means the player comes down the
fen, round the court, and meets him with the ring at his back - the
composition the encounter needs, arrived at from the depth rule rather than
in spite of it.

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

**A new animal is a set of silhouette flags plus a palette**, not a second rig.
`SPECIES` in `tools/gen/animal.py` carries them and every one is read with
`.get`, so adding a flag leaves the other four animals alone. What a species
needs is whatever makes its outline unmistakable at 32px and nothing else: the
boar bristles and has tusks, the elk is `tall` with antlers and a pale rump,
and the bear is `bulk` (a deeper, wider barrel), `hump` (the rise over the
shoulders nothing else here has), `round_ears`, `paws`, `stub_tail` and
`snout` - a pale blunt muzzle drawn with the horn keys. The ears were the
whole job: drawn at the head's own height they sat under the hump and the bear
stopped reading as one, so they are placed clear of the shoulders instead.

The zebra is the flag model taken as far as it goes: `stripes` and `crest`,
plus a palette, and nothing else. Two things about it are worth keeping:
**a zebra is a white animal with black on it**, so `AF` - the head key - is
white and it is the *shade* key that carries every bar, the mane and the
muzzle; pointing the head at the black made a black horse with pale legs.
And **the bars are every fourth pixel, not every third**: at every third the
animal read as solid dark. The front and back views needed their own answer,
because the rig draws the head over the body head-on, so the barrel's bars are
hidden: head-on the bars are on the *forehead* (the eye row left clear, or the
face becomes one smudge), and from behind they run *across* the rump, which is
both where a zebra's are boldest and out of the way of the tail.

**A predator is the same flags plus a `hostile` block**, and the jackal is
the shortest possible version of one: `prick_ears`, a `brush` of a tail, a
dark `saddle`, and the boar's numbers tuned a little faster and a little
weaker. What it needed was ear discipline - at 32px a dog *is* its ears, and
two rows above the skull is not enough height for a pixel to read as an ear
rather than as a bump in the outline. They are drawn clear of the body in
every view, which is the only reason they read. The saddle wanted the
opposite: painted over the whole back it was a dark slab with legs, and the
animal lost the sand colour that makes it a desert dog. It is a stripe down
the spine now.

**An animal bigger than the livestock** uses the `beast` rig in
`tools/gen/beast.py` - the same four facings, walk, idle and graze, but drawn
at the giant's size and on the giant's sheet, because the frame size is what
decides which sheet a rig belongs on. An elephant in the 32x32 frame the sheep
share comes out the size of a bear, and the whole point of one is that it is
not. It was three things to add - the module, an entry in `RIGS` in `art.py`,
and `"rig": "beast"` in the content - and nothing else in the pipeline changed.
Two lessons from drawing it, both only visible once rendered:

- **The head has to step above the line of the back.** Drawn level with the
  barrel and in the same tone, an elephant in profile is one long grey brick
  with a hose on the end. That step is the whole silhouette.
- **An ear is hung, not stuck on.** Drawn as a lens centred on the shoulder it
  was an oval floating on the animal's side - a sticker. A straight top edge
  where it attaches, and the rest falling away loose, is what reads.
  And it has to be a *different tone* from the shoulder it covers.

Legs, too: four columns eight pixels wide put the feet in contact and the four
of them merged into one black plinth the length of the animal, which reads as a
thing on a stand rather than a thing standing. Narrower, and daylight between
the front pair and the rear.

**The giraffe is that rig at its other extreme**, and one flag - `neck` -
switches every view to a different set of proportions rather than adding a
part to the elephant's. That is still one rig: same frame, same anchor, same
sheet, same `build_frames`. Three things it taught:

- **Where the mass is, is the animal.** Drawn with a barrel as deep as the
  elephant's it came out a tall horse with a crane on the front. Most of a
  giraffe is leg and neck; the body between them is shallow and slopes down
  to the rump.
- **A wide front view is a building.** Head on, the first version was two
  posts under a lintel, and at map scale a group of them read as a colonnade.
  A giraffe is deep through the chest and narrow across it - the front view
  had to lose a third of its width before it read as an animal at all.
- The graze pose carries `head_down` beside the elephant's `trunk_down`. Both
  live in the same pose dicts and each animal reads only its own with `.get`,
  so adding the second changed nothing about the first.

**Something that flies** uses the `bird` rig in `tools/gen/bird.py`. It is a
fourth rig rather than a flag on the quadruped because a bird shares no part
with one - no barrel on four legs, no head on a neck out front - and it is on
the *same sheet* as the people and the livestock, because it is the same
32x32 frame: the frame size is what decides the sheet, not the kind of
creature. Module, an entry in `RIGS`, `"rig": "bird"` in the content, nothing
else.

**A flying thing is drawn at the top of the frame and anchored at the bottom
of it**, and that costs nothing at all. The anchor is the point the sprite is
placed and sorted by, not a point the art has to touch, so twenty pixels of
air between the shadow and the bird puts it in the sky while it still stands
in the tile the engine thinks it is in - every existing rule about depth,
collision and wandering goes on working. **The shadow is what sells it**: a
bird with no shadow reads as a sprite that forgot to land. It is small and
tight rather than scaled to the wingspan, because the thing casting it is a
long way up, and a stain the width of the tile under something you can see
daylight through is a dark puddle.

Three things about drawing one at this size:

- **Head on, a wing is edge-on and has no area**, so drawn honestly it is a
  line - and a line either side of an upright body is a scarecrow, which is
  exactly what the front and back views were at first. What fixes it is
  admitting the view is from slightly *above*: from there a wing sweeps back
  as it goes out, and that curve is the whole difference between a bird and
  a cross. The beat then only decides how far the tips are flicked over it.
- **A pair of legs is one line, not two.** A heron's trail behind it, and
  drawn either side of the tail they picked up an outline each, closed into
  a single dark block under the body, and the bird came back wearing
  trousers. Together, with the feet turned out at the end, reads as legs.
- The engine's third wander state is called `graze` because the first thing
  that used it was a sheep; it is really "what this creature does when it
  stops". For a bird that is a long coast, wings flat and losing height.
  Naming it anything else here would mean teaching `game/main.js` about
  birds, and nothing in the engine knows what any of these creatures are.

`"blocks": false` is the other half of a bird: a wanderer that claims no tile
and is never added to the collider, so the hero walks underneath it. Give it
a big `wander.radius` - the herons on Wilderness IX have 11, against a sheep's
4 - or it hangs over one spot like an ornament.

**A new face is a palette entry, not a drawing** - `VARIANTS` in
`tools/gen/palette.py`, and the actor's `sprite` names it (`actor.monk` ->
variant `monk`). Friedrich is the hero's frames with a saffron robe, and
**bald is a remap too**: the rig draws a crown of hair over the skull, so
pointing `HR` and `HRL` at the skin keys leaves a shaved head with the light
still on the dome. Nothing in the rig knows there is a bald character, which
is the whole point of storing keys rather than colours.

**A headcloth is that same trick run the other way.** Ibn Abn the nomad is the
hair keys pointed at indigo instead of at skin, which puts a wrapped head on a
character the rig has never heard of - and the robe keys carried down to the
ankle like the monk's, so his legs are cloth rather than trousers. Two remaps
and a content file is the whole of a new person.

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

**Goor the stone golem is that rig's second species**, and he is the proof the
flag model holds at this size too: `{"crystals": True}` and a palette variant,
and nothing else. No tusks and no gas - both are the troll's, and a golem that
shared them would read as a recoloured troll however different the stone was.
What he adds is a `CRYSTALS` table of (x, y, height) per view, drawn as shards
that **break the silhouette above the shoulder line**: laid flat against the
back they were a coloured patch, and the whole point of them is the shape they
make against the sky. Same lesson as the jackal's ears.

His value ramp is the troll's lesson applied twice over. He stands on a cobble
court (luma 92) in a fen (86) with meadow (105) behind him, so the ramp has to
run well under *and* well over all three rather than sit among them: 32 / 50 /
73 / 125. And the one warm thing on him is the red crystal, which is also what
is banked in his eye sockets - whatever is in the stone is also looking at you.

**A guard is a standing thing, not a wandering one.** No `wander` block at all,
so the engine gives him a static body on each footprint tile exactly like a
boulder and never steps him; `"states": ["idle"]` is then the whole rig cost,
because a rig only draws the states its actor declares. `interact` is what
makes him a person rather than a wall.

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

**Another armour costs a function and a line**, and is worth noting for what
it does to the sheet: the table is a *product*, so each one multiplies the
baked hero frame sets rather than adding to them. Five weapons (none, sword,
axe, spear, azure blade) times four looks (bare, mail, desert tunic, nomad
robe) is twenty, and the fifth weapon cost 209 frames on its own. That is
fine at this size and would not be at ten of each - which is the reason
`looks` is a table the build writes rather than something content has to
spell out.

**A weapon that is not metal** is the azure blade, and it took three things
that are worth knowing before drawing another one. A weapon is a *line* from
the hand, so:

- **Width is the only thing that can say "lit".** A blade the sword's two
  pixels thick in a bright blue reads as a sword somebody painted. The blade
  carries a third row - `glow`, on the side the steel ones leave dark - and
  that is what makes it read as light rather than paint.
- **The perpendicular is the wrong step on a diagonal.** Extra rows go on at
  `(-dy, dx)`, which is diagonal too when the weapon points diagonally, so
  they land on diagonal neighbours and the blade comes out a chequerboard - a
  barber's pole, not a sword. A sideways step, `(dx, 0)`, gives a solid
  parallel line. The steel three sidestep this by being one pixel wide on a
  diagonal, which is fine for them and throws away everything that makes this
  one what it is, so it asks for `thick` instead.
- Every new field on a `WEAPONS` entry is read with `.get` and a default of
  whatever the wooden haft does, so adding one leaves the other three byte
  for byte identical. That is checkable and worth checking: compare the
  decoded cells of every sprite key present in both the old and new
  `atlases.json` before believing a shared drawing function still draws the
  same thing.

Its 16px icon draws the light *after* `outline()`, which is the temple's dust
rule and matters more here: a mote with a hard black line round it is a
pebble, and an icon of a magic sword whose magic reads as gravel is worse
than one carrying no magic at all.

Two cloth armours also have to read apart *as cloth*, which the icon cannot do
alone: the desert tunic is one bright band at the collar over pale linen, and
the nomad robe is the reverse - dark at the shoulders under an indigo mantle,
pale below. Same material, opposite distribution of value, legible at a
glance in a bag of sixteen slots.

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

**A portal is an `exits` entry that does not sit on an edge**, and that is the
whole of it - no engine change, no new field. `checkExit()` matches by tile, so
an inland doorway has always worked; the shed's door is one. What is new is
where it leads: the gateway on the temple step in Wilderness VII and the one in
front of the desert sun gate are two tiles wide each, and each puts you one
tile short of the other, facing it, so walking north through one and carrying
on walks you back.

The ground under it is `tile.portal`, and two things about it are worth
keeping:

- **It wraps, like a ground texture.** The first version was a rune plate with
  a ring centred in the tile, which at two tiles wide read as two glowing
  donuts side by side rather than as one threshold. A seamless surface runs
  straight across the join, so a gateway is one pool of light however wide it
  is laid. Everything the wrapping rule says about ground applies to anything
  laid more than one tile wide.
- **It is built up from the mid violet, not the dark one.** A portal is a
  light source; started from the dark end it reads as a hole cut in the floor
  however bright the marks on it are. And it is *calm* - every stroke given a
  shadow and sparks scattered over the rest made a tile of violet static,
  which reads as a rendering fault rather than as magic.

**Where a portal can go is decided by what covers it.** The desert end was
first put north of the sun gate, which is where the user asked for it and
where it is completely invisible: the gate is a 48px prop anchored at its foot,
so its art covers the three tiles *behind* it. It is on the court in front
instead. Check what a tall prop hides before putting anything on the tiles
above it.

**A portal is not a seam, and the atlas has to be told.** A doorway places one
map against another; a portal places nothing, because the country it leads to
is nowhere near. `componentsOf()` therefore joins maps by edge-aligned
doorways *only* - counting the portal as adjacency put the desert in the
wildernesses' component, where nothing could place it, and every map in that
component then landed somewhere wrong. Three more things follow from the same
fact, all of which broke when the first portal was built:

- A map whose only way in is inland was filed as an **interior**, so the
  desert went under the world in the interiors band marked "inside" the moment
  it was joined. A tagged map is never a room: a zone is a whole country
  however you reach it.
- The note that reports an inland doorway as an oddity now names a portal as a
  portal instead - on **either** end, since the way back is the untagged half
  of the pair.
- `every gate is a seam, a door into a room, or a portal to a zone` is the
  check in `editor_test.cjs`; it asserted an edge on every gate when every gate
  was a seam, and allowed a door once the shed was built.

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

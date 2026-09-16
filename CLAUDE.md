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
   `.aseprite` sources and `game/page.html`. All 18 gates must pass. A gate
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
   node tools/shot.cjs --talk --tile 37,37  # walk up to someone and press E
   node tools/shot.cjs --gather --tile 34,37   # stand by an item, press E, check the bag
   node tools/shot.cjs --give item.axe --slash # arm the hero and swing
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

## Where things live

```
tools/gen/palette.py   the one palette; a character variant is a key remap
tools/gen/actor.py     the biped rig      (32x32 frame, anchor [16, 29])
tools/gen/animal.py    the quadruped rig  (same frame, same contract)
tools/gen/props.py     props 32x32, structures 48x48 (anchor [24, 45])
tools/gen/tiles.py     16x16 ground tiles
tools/pipeline/        aseprite I/O, atlas packing, manifest, the 16 gates
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

**An item** is a 16x16 icon function in `tools/gen/items.py` (added to
`ITEMS`), a file in `content/items/` with `kind` `material` or `weapon`, and a
line in the map. A weapon also names what the hand holds (`"held": "sword"`),
which must be a `WEAPONS` entry in `tools/gen/actor.py` - that is where a new
weapon's shape is described, once, as a line from the hand with a guard or a
head hung off it. The build then bakes a wielding frame set for every actor
with `"wields": true` and the `item-held` gate checks it is complete.

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

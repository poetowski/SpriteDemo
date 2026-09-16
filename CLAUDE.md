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
   `.aseprite` sources and `game/page.html`. All 16 gates must pass. A gate
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

**A map** is ASCII rows plus a legend. Roads must stay clear - scenery placed on
a path tile can wall off the only route across the world.

## House style

Match what is already there: short module docstrings that say *why*, comments
that explain a decision rather than restate the code, and no new dependency
without a reason. Python is stdlib + Pillow only; the game vendors Phaser and
needs no server or build step.

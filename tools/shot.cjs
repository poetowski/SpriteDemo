/* Drive the real game in headless Chromium and photograph it.
 *
 *   node tools/shot.cjs                          build/shot.png, at the spawn
 *   node tools/shot.cjs --tile 33,40             stand somewhere and look
 *   node tools/shot.cjs --map                    the whole world, one image
 *   node tools/shot.cjs --talk --tile 37,37      walk up to someone and press E
 *   node tools/shot.cjs --gather --tile 34,37    stand by an item, press E, check the bag
 *   node tools/shot.cjs --give item.sword --slash   arm the hero and swing
 *   node tools/shot.cjs --bump                   walk into an animal, check it blocks
 *   node tools/shot.cjs --quest                  take every errand on offer and run it
 *   node tools/shot.cjs --kill                   strike a hostile until it dies
 *   node tools/shot.cjs --journal                open the quest log
 *   node tools/shot.cjs --spawn npc.troll        put one next to the hero and look
 *   node tools/shot.cjs --out /tmp/a.png --wait 1500
 *
 * It loads game/index.html (vendored Phaser - no network), so what is captured
 * is the game, not a mock-up. Before it takes the picture it checks that the
 * scene actually came up: no console errors, a hero, the tilemap at the size
 * the manifest declares, one sprite per placed entity, every item lying where
 * the map put it. A failed check exits non-zero, which makes this a smoke test
 * that happens to leave a screenshot behind rather than a screenshot tool that
 * might be photographing a crash.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const args = process.argv.slice(2);
// Modes asked of a map that has no such creature: reported, but not failures.
// A boar test on a map with no boar says nothing about the game either way.
const skipped = [];

function flag(name) { return args.includes(name); }
function value(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}

const MAP_MODE = flag('--map');
const TALK = flag('--talk');
const GATHER = flag('--gather');
const SLASH = flag('--slash');
const GIVE = value('--give', null);
const POSE = value('--pose', null);       // state,frame - hold one pose for the picture
const PAGE = flag('--page');              // the whole page, buttons included
const BAG = flag('--bag');                // open the bag before the picture
const JOURNAL = flag('--journal');        // and the quest log
const QUEST = flag('--quest');            // run every errand this map can offer
const MID = flag('--mid');                // with --slash: photograph the moment of impact
const CHOOSE = args.includes('--choose')  // with --talk: take the nth reply (1-based)
  ? Number(value('--choose', '1')) - 1 : null;
const TILE = value('--tile', null);
// Which doorway --cross walks. A map has more than one way out of it the
// moment it is joined to a second neighbour, and the first one authored is
// then the only one anything ever tests.
const EXIT = Number(value('--exit', '0'));
// Something the maps do not carry yet. New art is drawn before it is placed,
// and a creature nobody has put down anywhere still has to be looked at in
// the real game rather than on a contact sheet.
const SPAWN = value('--spawn', null);
const ON = value('--on', null);           // start on a map other than the default
const WAIT = Number(value('--wait', MAP_MODE ? 1200 : 900));
const OUT = path.resolve(ROOT, value('--out', MAP_MODE ? 'build/map.png' : 'build/shot.png'));

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  try {
    ({ chromium } = require(path.join(
      process.env.NODE_PATH || '/opt/node22/lib/node_modules', 'playwright')));
  } catch (e2) {
    // No Playwright here. Drive whatever Chrome or Edge is installed over the
    // DevTools protocol instead; tools/cdp.cjs speaks the slice of the
    // Playwright page API this script uses. Set CHROME_PATH if it cannot find
    // a browser on its own.
    ({ chromium } = require('./cdp.cjs'));
  }
}

/** Resolve after the scene has booted and its first frames have run. */
const BOOTED = () => !!(window.game && window.game.scene
  && window.game.scene.scenes[0] && window.game.scene.scenes[0].hero);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });

  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push(String(e)));

  await page.goto('file://' + path.join(ROOT, 'game', 'index.html'));
  await page.waitForFunction(BOOTED, null, { timeout: 20000 });
  await page.evaluate(() => {                       // drop the "click to play" veil
    const f = document.getElementById('focus');
    if (f) f.classList.remove('show');
  });

  if (ON) {
    // Crossing a map edge restarts the scene, so starting somewhere else is
    // the same operation the game itself performs.
    // Braced deliberately: restart() hands back Phaser's scene plugin, and
    // returning that asks the browser to serialise the whole scene graph -
    // which fails with "object reference chain is too long" and takes --on
    // with it. Nothing here needs the return value.
    await page.evaluate((id) => {
      window.game.scene.scenes[0].scene.restart({ map: id });
    }, ON);
    await page.waitForFunction(
      (id) => window.game.scene.scenes[0].mapId === id && !!window.game.scene.scenes[0].hero,
      ON, { timeout: 20000 });
    await page.waitForTimeout(250);
  }

  if (TILE) {
    const [tx, ty] = TILE.split(',').map(Number);
    await page.evaluate(([x, y]) => {
      const s = window.game.scene.scenes[0];
      const p = s.tileCentre(x, y);
      s.hero.setPosition(p.x, p.y);
      s.cameras.main.centerOn(p.x, p.y);
    }, [tx, ty]);
  }
  if (GIVE) {
    await page.evaluate((id) => window.game.scene.scenes[0].addItem(id), GIVE);
  }
  let spawnedAt = null;
  if (SPAWN) {
    // The first spot near the hero that the thing actually fits on, footprint
    // and all - the same question the editor asks before it lets you place it.
    // Nothing is returned but the tile: handing back what spawn() returns asks
    // the browser to serialise the whole scene graph.
    spawnedAt = await page.evaluate((id) => {
      const s = window.game.scene.scenes[0];
      const m = window.ART.manifest;
      const def = m.actors[id] || m.props[id] || m.items[id];
      if (!def) return null;
      const fp = (def.footprint && def.footprint.length) ? def.footprint : [[0, 0]];
      const [hx, hy] = s.heroTile();
      for (const [dx, dy] of [[3, 0], [-4, 0], [0, 3], [0, -3], [3, 3],
                              [-4, 3], [5, 0], [0, 5], [-4, -3]]) {
        const tx = hx + dx;
        const ty = hy + dy;
        if (fp.every(([ox, oy]) => s.isWalkable(tx + ox, ty + oy)
                                && !s.penned.has(`${tx + ox},${ty + oy}`))) {
          s.spawn(id, tx, ty);
          return [tx, ty];
        }
      }
      return null;
    }, SPAWN);
  }

  await page.waitForTimeout(WAIT);

  // --- the checks ------------------------------------------------------------
  const snapshot = () => page.evaluate(() => {
    const s = window.game.scene.scenes[0];
    const m = window.ART.manifest;
    // The map the scene actually loaded, not a name written down here: with
    // the id hardcoded, pointing the game at another map left these checks
    // comparing one map's manifest against another map's scene.
    const map = s.map;
    const cur = s.hero.anims.currentAnim ? s.hero.anims.currentAnim.key : '';
    return {
      size: map.size,
      tileSize: map.tile_size,
      entities: map.entities.length,
      itemEntities: map.entities.filter((e) => m.items[e.def]).length,
      // Things that put a tile in the blocked set: solid, and not a wanderer -
      // a wanderer carries its body with it and claims no tile. Counted from
      // the definitions rather than inferred by subtracting the kinds we know
      // about, which quietly broke the moment a prop was authored walkable.
      staticBlockers: map.entities.filter((e) => {
        const d = m.props[e.def] || m.actors[e.def];
        return !!(d && d.blocks && !d.wander);
      }).length,
      // Entity sprites only. The fx atlas is transient - a hit spark, an
      // alert - so counting every sprite in the scene made this check depend
      // on what happened to be on screen at the instant of the snapshot. It
      // held while one boar per map meant effects were rare.
      sprites: s.children.list.filter(
        (o) => o.type === 'Sprite' && !(o.texture && o.texture.key === 'fx')).length,
      pickups: s.pickups.length,
      solids: s.solid.getChildren().length,
      blocked: s.blocked.size,
      wanderers: s.wanderers.length,
      interactables: s.interactables.length,
      inventory: s.inventory.filter(Boolean),
      bagOpen: s.bagOpen,
      hits: s.hits || 0,
      fxOnScreen: s.children.list.filter((o) => o.texture && o.texture.key === 'fx').length,
      weapon: s.weapon,
      armor: s.armor,
      heroSprite: s.heroSprite,
      anim: cur,
      busy: s.busy,
      heroTile: [Math.floor(s.hero.x / s.ts), Math.floor(s.hero.y / s.ts)],
      worldBounds: [s.physics.world.bounds.width, s.physics.world.bounds.height],
      props: Object.keys(m.props).length,
      items: Object.keys(m.items).length,
      atlases: Object.keys(m.atlases),
    };
  });
  const report = await snapshot();
  const count = (inv) => inv.length;

  const [cols, rows] = report.size;
  if (report.wanderers === 0 && report.entities > 0) {
    skipped.push(['livestock', 'nothing wanders on this map']);
  }
  const checks = [
    ['no console errors', problems.length === 0, problems.join(' | ')],
    ['world matches the map', report.worldBounds[0] === cols * report.tileSize
      && report.worldBounds[1] === rows * report.tileSize, JSON.stringify(report.worldBounds)],
    ['every entity spawned', report.sprites === report.entities + 1 + (SPAWN ? 1 : 0),
      `${report.sprites} sprites vs ${report.entities} entities + hero`
      + (SPAWN ? ` + ${SPAWN}` : '')],
    ['every item lying in the world', report.pickups === report.itemEntities,
      `${report.pickups} pickups vs ${report.itemEntities} placed`],
    ['collision tiles claimed', report.blocked >= report.staticBlockers,
      `${report.blocked} blocked tiles for ${report.staticBlockers} solid things`],
    ['one body per blocked tile', report.solids === report.blocked,
      `${report.solids} bodies vs ${report.blocked} tiles`],
    // Only where there is livestock to wander. An interior has none, and a
    // room full of nothing is not a failure of the wander code.
    ...(report.wanderers > 0 || report.entities === 0
        ? [['livestock is wandering', report.wanderers > 0, `${report.wanderers}`]]
        : []),
  ];
  if (GIVE) {
    const on = (report.weapon === GIVE || report.armor === GIVE)
      && report.heroSprite !== 'actor.hero';
    checks.push(['gear equipped and drawn on the hero', on,
      `weapon=${report.weapon} armor=${report.armor} sprite=${report.heroSprite}`]);
  }
  if (SPAWN) {
    checks.push([`${SPAWN} stands next to the hero`, !!spawnedAt,
      'no room near the hero, or no such definition']);
  }

  if (TALK) {
    await page.keyboard.press('KeyE');
    await page.waitForTimeout(250);
    const talking = await page.evaluate(() =>
      document.getElementById('dialogue').classList.contains('show'));
    checks.push(['dialogue opened', talking, 'nothing in range to talk to?']);
    // Run out the node's lines; the replies appear on the last one.
    for (let i = 0; i < 6; i++) {
      const shown = await page.evaluate(() =>
        document.querySelectorAll('#choices button').length);
      if (shown) break;
      await page.keyboard.press('KeyE');
      await page.waitForTimeout(140);
    }
    const state = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      return { n: document.querySelectorAll('#choices button').length,
               node: s.dialogue && s.dialogue.node.text[0] };
    });
    checks.push(['replies offered', state.n > 0, `after "${state.node}"`]);
    if (CHOOSE !== null) {
      const before = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        return { node: s.dialogue && s.dialogue.node.text[0],
                 flags: [...s.flags], inv: s.inventory.filter(Boolean) };
      });
      await page.keyboard.press(['Digit1', 'Digit2', 'Digit3', 'Digit4'][CHOOSE]);
      await page.waitForTimeout(220);
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        return { open: !!s.dialogue, node: s.dialogue && s.dialogue.node.text[0],
                 flags: [...s.flags], inv: s.inventory.filter(Boolean) };
      });
      const moved = !after.open || after.node !== before.node
        || after.flags.length !== before.flags.length;
      checks.push([`reply ${CHOOSE + 1} taken`, moved,
        `node unchanged: "${after.node}"`]);
      console.log(`dialogue  "${before.node}" -> ${after.open ? `"${after.node}"` : 'closed'}`
        + `  flags [${after.flags}]  bag [${after.inv}]`);
    }
  }
  if (GATHER) {
    const before = count(report.inventory);
    await page.keyboard.press('KeyE');
    await page.waitForTimeout(120);
    const mid = await snapshot();
    await page.waitForTimeout(600);
    const after = await snapshot();
    checks.push(['gather animation played', mid.anim.includes('/gather/'), mid.anim]);
    checks.push(['item went into the bag', count(after.inventory) === before + 1
      && after.pickups === report.pickups - 1,
      `${JSON.stringify(after.inventory)}, ${after.pickups} left on the ground`]);
    checks.push(['control handed back', after.busy === false, 'still busy']);
  }
  if (BAG) {
    await page.keyboard.press('KeyI');
    await page.waitForTimeout(350);                 // let the panel slide in
    const st = await snapshot();
    const shown = await page.evaluate(() =>
      document.getElementById('bag').classList.contains('open'));
    checks.push(['bag opened on I', st.bagOpen && shown, `state=${st.bagOpen} panel=${shown}`]);
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(60);
    const moved = await page.evaluate(() => window.game.scene.scenes[0].cursor);
    checks.push(['cursor moves in the bag', moved === 1, `cursor=${moved}`]);
  }
  if (flag('--bump')) {
    // Walk the hero into a standing animal and check it is stopped. A solid
    // thing that moves is the one kind of collision a static body cannot do,
    // so it is worth proving rather than assuming.
    const setup = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      // Something solid that is not hostile. This asks whether a solid animal
      // stops the player, and a boar will not hold still to be asked - it
      // charges, shoves the hero past it, and the measurement is about
      // aggression instead. That is what --boar is for.
      const i = s.wanderers.findIndex((a) => a.def.blocks && !a.def.hostile);
      if (i < 0) return null;
      const w = s.wanderers[i];
      w.state = 'idle';                       // hold still for the experiment
      w.timer = 99999;
      w.sprite.body.setVelocity(0, 0);
      // body.reset, not setPosition: a dynamic body writes its own position
      // back over the sprite, so setPosition alone snaps straight back and
      // the hero never actually stands where the test put them.
      s.hero.body.reset(w.sprite.x - s.ts * 1.5, w.sprite.y);
      return { i, def: w.def.sprite, gap: w.sprite.x - s.hero.x,
               tile: w.tile.slice(), map: s.mapId };
    });
    if (setup) {
      await page.keyboard.down('ArrowRight');
      await page.waitForTimeout(900);
      await page.keyboard.up('ArrowRight');
      // By index, not by repeating the predicate. The two halves once held
      // predicates that had drifted apart, so the hero was stood next to a
      // goat and the distance measured to a boar thirty tiles away - and the
      // check reported a catastrophe that was not happening.
      const after = await page.evaluate((i) => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers[i];
        return { gap: w.sprite.x - s.hero.x, heroX: s.hero.x, animalX: w.sprite.x,
                 tile: w.tile.slice(), map: s.mapId,
                 touching: !!s.hero.body.touching.right };
      }, setup.i);
      // Two things, because either alone can pass for the wrong reason: the
      // hero is in contact with the animal, and did not pass through it. A
      // hero that never moved would satisfy the second on its own.
      checks.push([`walking into a ${setup.def.split('.')[1]} is blocked`,
        after.touching && after.gap > 8,
        `gap ${setup.gap.toFixed(1)} -> ${after.gap.toFixed(1)}, `
        + `touching: ${after.touching}, `
        + `subject ${setup.map} ${JSON.stringify(setup.tile)} `
        + `-> ${after.map} ${JSON.stringify(after.tile)}`]);
    } else {
      skipped.push(['--bump', 'no solid, non-hostile animal on this map']);
    }
  }

  if (flag('--cross')) {
    // Walk out of one map and into the next. The crossing restarts the scene,
    // so the thing worth proving is not that the map changed but that the
    // player arrived with what they were carrying - a restart hands out a
    // fresh bag unless the state is carried across on purpose.
    const before = await page.evaluate((n) => {
      const s = window.game.scene.scenes[0];
      const ex = (s.map.exits || [])[n];
      if (!ex) return null;
      // Cross in the middle of the band rather than at an end: an off-by-one
      // in the pairing shows up there and nowhere else.
      const door = ex.tiles[Math.floor(ex.tiles.length / 2)];
      s.addItem('item.axe');
      // And an errand in hand. A field added to the scene but not to the list
      // checkExit() carries is lost silently at the map edge, and the journal
      // is exactly the kind of field that happens to.
      const errand = Object.keys(window.ART.manifest.quests)[0];
      if (errand) s.startQuest(errand);
      const p = s.tileCentre(door[0], door[1]);
      s.hero.body.reset(p.x, p.y);
      s.exitLocked = false;                   // as if we had walked onto it
      // Which way you must have been walking to step onto that tile. Reaching
      // an edge-wide doorway means walking at that edge, and that is the way
      // you should still be looking on the far side.
      const [cols, rows] = s.map.size;
      const way = ex.tiles.every((t) => t[0] === 0) ? 'left'
                : ex.tiles.every((t) => t[0] === cols - 1) ? 'right'
                : ex.tiles.every((t) => t[1] === 0) ? 'up'
                : ex.tiles.every((t) => t[1] === rows - 1) ? 'down' : null;
      const at = ex.tiles.indexOf(door);
      return { from: s.mapId, to: ex.to, bag: s.inventory.filter(Boolean).length,
               door, way, errand,
               quests: Object.keys(s.quests).length,
               want: (ex.spawns && ex.spawns[at]) || ex.spawn };
    }, EXIT);
    if (before) {
      await page.waitForFunction(
        (to) => window.game.scene.scenes[0].mapId === to && !!window.game.scene.scenes[0].hero,
        before.to, { timeout: 10000 }).catch(() => {});
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const t = s.heroTile();
        return { map: s.mapId, bag: s.inventory.filter(Boolean).length, tile: t,
                 facing: s.facing, onExit: !!s.exits.get(t.join(',')),
                 quests: Object.keys(s.quests).length };
      });
      checks.push([`${before.from} leads to ${before.to}`,
        after.map === before.to, after.map]);
      checks.push(['the bag came across',
        after.bag === before.bag, `${before.bag} -> ${after.bag}`]);
      checks.push(['and so did the journal',
        !before.errand || after.quests === before.quests,
        `${before.quests} quest(s) -> ${after.quests}`]);
      // Against the arrival the doorway declares for the tile we stepped on,
      // not against the tile's own coordinates. Two earlier versions of this
      // check compared coordinates and were both wrong: the first measured the
      // row whichever edge you crossed, and the second assumed the two maps
      // share an origin - true only while every map was the same size. A wide
      // map laid under three narrow ones meets them at a 20-tile offset, and
      // there is nothing in the game that knows that but the pairing itself.
      checks.push(['you come out where the doorway says',
        !!before.want && after.tile[0] === before.want[0]
                      && after.tile[1] === before.want[1],
        `${before.door} going ${before.way} should arrive `
        + `${JSON.stringify(before.want)}, arrived ${JSON.stringify(after.tile)}`]);
      checks.push(['and not on the way back',
        !after.onExit, `arrived at ${after.tile}`]);
      checks.push(['still facing the way you were walking',
        !before.way || after.facing === before.way,
        `walked ${before.way}, arrived facing ${after.facing}`]);
    } else {
      checks.push([`the map has an exit ${EXIT} to cross`, false, 'none authored']);
    }
  }

  // --- the errands ----------------------------------------------------------
  // Take every quest the people on this map can offer and run it to the end.
  // Nothing below names a quest, a reply or an item: the route through each
  // conversation is worked out from the choices actually on offer, and the
  // objectives are whatever content/quests/ says they are - so this keeps
  // testing the system rather than one errand somebody wrote down here.

  /** Stand next to something and let a frame go by, so the scene's own "what
   *  is in range" pass catches up before E is pressed. */
  async function standBy(defId) {
    const ok = await page.evaluate((id) => {
      const s = window.game.scene.scenes[0];
      const it = s.interactables.find((x) => x.id === id);
      if (!it) return false;
      // body.reset, not setPosition: a dynamic body writes its own position
      // back over the sprite, and the hero would never actually be there.
      s.hero.body.reset(it.sprite.x, it.sprite.y + 10);
      s.cameras.main.centerOn(s.hero.x, s.hero.y);
      return true;
    }, defId);
    await page.waitForTimeout(160);
    return ok;
  }

  /** Run out the lines of the node being read, so the replies are live. A
   *  choice taken mid-sentence is ignored by the scene, on purpose. */
  async function readOn() {
    for (let i = 0; i < 8; i++) {
      const state = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        if (!s.dialogue) return 'closed';
        return s.dialogue.line >= s.dialogue.node.text.length - 1 ? 'ready' : 'reading';
      });
      if (state !== 'reading') return state;
      await page.keyboard.press('KeyE');
      await page.waitForTimeout(130);
    }
    return 'stuck';
  }

  /** One step of a conversation towards a choice that carries `effect` for
   *  this quest - taking it if it is on offer now, and otherwise the reply
   *  that gets closest to one. */
  const stepToward = (effect, qid) => page.evaluate(([eff, id]) => {
    const s = window.game.scene.scenes[0];
    if (!s.dialogue) return { fired: false, why: 'nothing is being said' };
    const d = s.dialogue.dlg;
    const distFrom = (start) => {                 // breadth first, by replies
      const seen = new Set([start]);
      let frontier = [start];
      let depth = 0;
      while (frontier.length) {
        const next = [];
        for (const nid of frontier) {
          for (const c of d.nodes[nid].choices || []) {
            if (c[eff] === id) return depth;
            if (c.goto && !seen.has(c.goto)) { seen.add(c.goto); next.push(c.goto); }
          }
        }
        frontier = next;
        depth += 1;
      }
      return Infinity;
    };
    const offered = s.dialogue.choices;
    let pick = -1;
    let best = Infinity;
    offered.forEach((c, i) => {
      if (best === -1) return;
      if (c[eff] === id) { pick = i; best = -1; return; }
      const dd = c.goto ? distFrom(c.goto) : Infinity;
      if (dd < best) { best = dd; pick = i; }
    });
    if (pick < 0) {
      return { fired: false, why: 'no reply leads there',
               offered: offered.map((c) => c.text) };
    }
    const took = offered[pick].text;
    const fired = offered[pick][eff] === id;
    s.choose(pick);
    return { fired, took };
  }, [effect, qid]);

  /** Walk a conversation until the quest has been started, or handed in. */
  async function pushThrough(effect, qid) {
    const said = [];
    for (let i = 0; i < 8; i++) {
      if ((await readOn()) === 'closed') break;
      const step = await stepToward(effect, qid);
      if (step.took) said.push(step.took);
      if (step.fired) return { ok: true, said };
      if (!step.took) return { ok: false, said, why: step.why, offered: step.offered };
    }
    return { ok: false, said, why: 'went round in circles' };
  }

  /** The crossing, without the walk: restart on another map carrying
   *  everything, exactly as checkExit() does at a map edge. */
  const goTo = (mapId) => page.evaluate((id) => {
    const s = window.game.scene.scenes[0];
    s.scene.restart({
      map: id,
      carry: { inventory: s.inventory, weapon: s.weapon, armor: s.armor,
               level: s.level, xp: s.xp, hp: s.hp, flags: [...s.flags],
               quests: s.quests },
    });
  }, mapId);

  async function waitForMap(mapId) {
    await page.waitForFunction(
      (id) => window.game.scene.scenes[0].mapId === id
           && !!window.game.scene.scenes[0].hero, mapId, { timeout: 20000 });
    await page.waitForTimeout(250);
  }

  /** Walk up to something lying on the ground and press E, the whole way
   *  through the gather animation. */
  async function gatherOne(defId) {
    const there = await page.evaluate((id) => {
      const s = window.game.scene.scenes[0];
      const p = s.pickups.find((x) => x.id === id);
      if (!p) return false;
      s.hero.body.reset(p.sprite.x, p.sprite.y + 6);
      s.cameras.main.centerOn(s.hero.x, s.hero.y);
      return true;
    }, defId);
    if (!there) return false;
    await page.waitForTimeout(140);
    await page.keyboard.press('KeyE');
    await page.waitForTimeout(650);
    return true;
  }

  /** Stand over a creature and hit it until it is not there any more. */
  const slay = (defId) => page.evaluate((id) => {
    const s = window.game.scene.scenes[0];
    const w = s.wanderers.find((a) => a.def.id === id);
    if (!w) return false;
    for (let i = 0; i < 80 && s.wanderers.includes(w); i++) {
      s.hero.body.reset(w.sprite.x, w.sprite.y + s.ts);
      s.facing = 'up';
      s.invuln = 900;                 // it is fighting back; this is not that test
      s.strike();
    }
    return !s.wanderers.includes(w);
  }, defId);

  if (QUEST) {
    const home = await page.evaluate(() => window.game.scene.scenes[0].mapId);
    const errands = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      const m = window.ART.manifest;
      return Object.entries(m.quests)
        .filter(([, q]) => q.giver && s.interactables.some((it) => it.id === q.giver))
        .map(([id, q]) => ({ id, name: q.name, giver: q.giver,
                             objectives: q.objectives || [], reward: q.reward || {} }));
    });
    if (!errands.length) {
      skipped.push(['--quest', 'nobody on this map has work going']);
    }
    for (const q of errands) {
      // --- take it ---------------------------------------------------------
      if (await page.evaluate(() => window.game.scene.scenes[0].mapId) !== home) {
        await goTo(home);
        await waitForMap(home);
      }
      const met = await standBy(q.giver);
      await page.keyboard.press('KeyE');
      await page.waitForTimeout(200);
      const took = await pushThrough('start', q.id);
      const after = await page.evaluate((id) =>
        window.game.scene.scenes[0].questState(id), q.id);
      checks.push([`${q.name}: ${q.giver.split('.')[1]} offers it`,
        met && took.ok && after !== 'none',
        `${took.why || ''} said: ${took.said.join(' / ')}`
        + (took.offered ? ` | offered: ${took.offered.join(' / ')}` : '')]);
      if (after === 'none') continue;
      await page.evaluate(() => window.game.scene.scenes[0].closeDialogue());

      // --- do it -----------------------------------------------------------
      for (const ob of q.objectives) {
        if (ob.kind === 'talk') {
          if (await standBy(ob.target)) {
            await page.keyboard.press('KeyE');
            await page.waitForTimeout(220);
            await page.evaluate(() => window.game.scene.scenes[0].closeDialogue());
          }
        } else if (ob.kind === 'visit') {
          await goTo(ob.target);
          await waitForMap(ob.target);
        } else if (ob.kind === 'collect') {
          // Off the ground where the map put it, the way a player would; only
          // what this map cannot supply is handed over.
          for (let i = 0; i < (ob.count || 1); i++) {
            if (!(await gatherOne(ob.target))) {
              await page.evaluate((id) => window.game.scene.scenes[0].addItem(id), ob.target);
            }
          }
        } else if (ob.kind === 'kill') {
          for (let i = 0; i < (ob.count || 1); i++) {
            if (!(await slay(ob.target))) break;
          }
        }
        const done = await page.evaluate(([id, oid]) => {
          const s = window.game.scene.scenes[0];
          return s.questProgress(id).find((o) => o.id === oid);
        }, [q.id, ob.id]);
        checks.push([`${q.name}: ${ob.text.toLowerCase()}`,
          !!done && done.met, done ? `${done.have}/${done.need}` : 'no such objective']);
      }
      const ready = await page.evaluate((id) =>
        window.game.scene.scenes[0].questState(id), q.id);
      checks.push([`${q.name}: ready to hand in`, ready === 'ready', ready]);

      // --- hand it in -------------------------------------------------------
      if (await page.evaluate(() => window.game.scene.scenes[0].mapId) !== home) {
        await goTo(home);
        await waitForMap(home);
        // The log has to survive the crossing, which is the one thing a scene
        // restart quietly takes away.
        const kept = await page.evaluate((id) =>
          window.game.scene.scenes[0].questState(id), q.id);
        checks.push([`${q.name}: still in hand after crossing a map edge`,
          kept === 'ready', kept]);
      }
      const before = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        return { xp: s.xp, level: s.level, inv: s.inventory.filter(Boolean) };
      });
      await standBy(q.giver);
      await page.keyboard.press('KeyE');
      await page.waitForTimeout(200);
      const gave = await pushThrough('finish', q.id);
      const paid = await page.evaluate(([id, reward]) => {
        const s = window.game.scene.scenes[0];
        return { state: s.questState(id), xp: s.xp, level: s.level,
                 inv: s.inventory.filter(Boolean),
                 holds: reward.give
                   ? s.countItem(reward.give) > 0 : true,
                 flag: reward.set ? s.flags.has(reward.set) : true };
      }, [q.id, q.reward]);
      await page.evaluate(() => window.game.scene.scenes[0].closeDialogue());
      checks.push([`${q.name}: handed in and paid`,
        gave.ok && paid.state === 'done' && paid.holds && paid.flag,
        `${paid.state}; said: ${gave.said.join(' / ')}`
        + (gave.offered ? ` | offered: ${gave.offered.join(' / ')}` : '')
        + `; bag ${JSON.stringify(paid.inv)}`]);
      // What the errand asked for is what it takes back, without the content
      // having to say so twice.
      const owed = q.objectives.filter((o) => o.kind === 'collect' && !o.keep);
      if (owed.length && paid.state === 'done') {
        const left = await page.evaluate((ids) => {
          const s = window.game.scene.scenes[0];
          return ids.map((id) => s.countItem(id));
        }, owed.map((o) => o.target));
        checks.push([`${q.name}: what it asked for was handed over`,
          left.every((n, i) => n === 0
            || n < (before.inv.filter((x) => x === owed[i].target).length)),
          owed.map((o, i) => `${o.target} x${left[i]} left`).join(', ')]);
      }
      if (q.reward.xp) {
        checks.push([`${q.name}: it was worth something`,
          paid.level > before.level || paid.xp > before.xp,
          `${before.level}/${before.xp}xp -> ${paid.level}/${paid.xp}xp`]);
      }
    }
  }

  if (flag('--kill')) {
    // A creature dies only if its definition says how much it can take, and
    // when it does it has to let go of everything: the lists it was stepped
    // through, the tile it reserved, the body the hero was colliding with.
    const before = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      const w = s.wanderers.find((a) => a.def.hp);
      if (!w) return null;
      return { def: w.def.id, hp: w.def.hp, wanderers: s.wanderers.length,
               penned: s.penned.size, livestock: s.livestock.length };
    });
    if (!before) {
      skipped.push(['--kill', 'nothing on this map can be killed']);
    } else {
      const died = await slay(before.def);
      await page.waitForTimeout(600);
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        return { wanderers: s.wanderers.length, penned: s.penned.size,
                 livestock: s.livestock.length,
                 sprites: s.children.list.filter((o) => o.type === 'Sprite'
                   && !(o.texture && o.texture.key === 'fx')).length };
      });
      checks.push([`a ${before.def.split('.')[1]} can be killed`, died,
        `${before.hp} hp, ${before.wanderers} -> ${after.wanderers} wanderers`]);
      checks.push(['and it lets go of the ground it stood on',
        after.penned < before.penned && after.livestock < before.livestock,
        `penned ${before.penned} -> ${after.penned}, `
        + `bodies ${before.livestock} -> ${after.livestock}`]);
    }
  }

  if (JOURNAL) {
    await page.evaluate(() => window.game.scene.scenes[0].closeDialogue());
    await page.keyboard.press('KeyJ');
    await page.waitForTimeout(350);                 // let the panel slide in
    const log = await page.evaluate(() => ({
      open: window.game.scene.scenes[0].questOpen,
      shown: document.getElementById('journal').classList.contains('open'),
      cards: document.querySelectorAll('#qlist .quest').length,
      ticked: document.querySelectorAll('#qlist .quest li.met').length,
    }));
    checks.push(['the journal opened on J', log.open && log.shown,
      `state=${log.open} panel=${log.shown}`]);
    checks.push(['and lists what has been taken on', log.cards > 0,
      `${log.cards} quests, ${log.ticked} objectives ticked`]);
  }

  if (flag('--boar')) {
    // Stand in front of a hostile and do nothing. Two things have to be true
    // and neither is obvious from the code: it has to notice and close the
    // distance, and reaching the hero has to actually cost hp. A creature that
    // charges and cannot land a hit looks far worse than one that never moves.
    const before = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      const w = s.wanderers.find((a) => a.def.hostile);
      if (!w) return null;
      // Hold every other hostile still. The test stands the hero next to one
      // boar and measures that one; on a map with five, a second boar was
      // charging in and shoving the hero around, so the number being measured
      // was the distance to an animal that had nothing to do with it.
      for (const other of s.wanderers) {
        if (other === w || !other.def.hostile) continue;
        other.state = 'idle';
        other.timer = 99999;
        other.chasing = false;
        other.sprite.body.setVelocity(0, 0);
        other.def = Object.assign({}, other.def, { hostile: null });
      }
      const p = s.tileCentre(...w.tile);
      // Which side to stand on. West by preference: a charging boar shoves the
      // hero, and east of the one this was written for is the seam, so the test
      // kept being pushed onto the next map. But a valley full of boulders can
      // have rock on that side, and then the animal charges into a wall - it
      // closes to a tile and a half, never lands a blow, and the failure reads
      // as "the elk cannot reach" when what cannot reach is the test.
      const clear = (dx, dy) => [1, 2, 3].every((n) => {
        const tx = w.tile[0] + dx * n;
        const ty = w.tile[1] + dy * n;
        return s.isWalkable(tx, ty) && !s.exits.get(`${tx},${ty}`);
      });
      const side = [[-1, 0], [1, 0], [0, -1], [0, 1]]
        .find(([dx, dy]) => clear(dx, dy)) || [-1, 0];
      s.hero.body.reset(p.x + side[0] * s.ts * 2.5,     // just inside its sight
                        p.y + side[1] * s.ts * 2.5);
      s.cameras.main.centerOn(s.hero.x, s.hero.y);
      s.invuln = 0;
      // What it plays while it closes in, sampled rather than read once at the
      // end: a creature with an attack state has to be seen throwing the blow,
      // and the swing is over long before the checks below run.
      window.__seen = new Set();
      s.time.addEvent({ delay: 60, loop: true, callback: () => {
        const a = w.sprite.anims.currentAnim;
        if (a) window.__seen.add(a.key);
      } });
      return { def: w.def.sprite, hp: s.hp, side,
               attack: (w.def.states || []).includes('attack'),
               provoked: !!w.def.hostile.provoked,
               gap: Phaser.Math.Distance.Between(s.hero.x, s.hero.y,
                                                 w.sprite.x, w.sprite.y) };
    });
    if (before && before.provoked) {
      // Something that only fights back has two halves to prove, and the
      // second one is worthless without the first: it has to ignore the hero
      // while it is left alone, and then charge once it is hit. A test that
      // only watched it charge would pass just as well with the flag deleted.
      await page.waitForTimeout(1400);
      const calm = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        return { chasing: !!w.chasing, hp: s.hp, state: w.state };
      });
      checks.push([`the ${before.def.split('.')[1]} leaves the hero alone `
        + `until it is hit`,
        !calm.chasing && calm.hp === before.hp,
        `chasing=${calm.chasing}, grazing=${calm.state}, hp ${calm.hp}`]);
      // Now hit it, through the same call the swing animation makes rather
      // than by setting the flag: what is being tested is that a blow angers
      // it, not that an angry creature charges.
      const angered = await page.evaluate(([ox, oy]) => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        s.facing = ox ? (ox < 0 ? 'right' : 'left') : (oy < 0 ? 'down' : 'up');
        s.hero.body.reset(w.sprite.x + ox * s.ts, w.sprite.y + oy * s.ts);
        s.strike();                                   // within a tile, so it lands
        const hit = !!w.angered;
        s.hero.body.reset(w.sprite.x + ox * s.ts * 2.5,
                          w.sprite.y + oy * s.ts * 2.5);
        s.invuln = 0;
        return hit;
      }, before.side);
      checks.push(['and a blow turns it on the hero', angered, `angered=${angered}`]);
    }
    if (before) {
      await page.waitForTimeout(2600);
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        if (!w) return { gone: s.mapId };               // shoved off the map
        return { hp: s.hp, chasing: !!w.chasing, reach: w.def.hostile.reach,
                 gap: Phaser.Math.Distance.Between(s.hero.x, s.hero.y,
                                                   w.sprite.x, w.sprite.y) };
      });
      checks.push([`the ${before.def.split('.')[1]} noticed and closed in`,
        !after.gone && after.chasing && after.gap < before.gap,
        after.gone ? `hero ended up on ${after.gone}`
                   : `${before.gap.toFixed(0)}px -> ${after.gap.toFixed(0)}px`]);
      checks.push(['and goring the hero costs hp',
        !after.gone && after.hp < before.hp,
        after.gone ? 'n/a'
                   : `${before.hp} -> ${after.hp}, closed to `
                     + `${after.gap.toFixed(0)}px of a ${after.reach}px reach`]);
      if (before.attack) {
        const seen = await page.evaluate(() => [...(window.__seen || [])]);
        checks.push(['and the blow is thrown, not just dealt',
          seen.some((k) => k.includes('/attack/')), seen.join(' ') || 'nothing played']);
      }

      // Now walk away. It must break off rather than follow across the map,
      // go home at its own pace, and end up wandering again - a hostile that
      // gives up but then stands where it stopped is a statue, not an animal.
      // Right out of its world, not just to the map's spawn: the spawn is
      // inside this one's "lose" radius, so it kept chasing until the leash
      // stopped it and the check was really timing the walk back from there.
      await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        const far = s.tileCentre(w.home[0] < 10 ? s.map.size[0] - 2 : 1,
                                 w.home[1] < 10 ? s.map.size[1] - 2 : 1);
        s.hero.body.reset(far.x, far.y);
      });
      await page.waitForTimeout(7000);   // it walks home at its own slow speed
      const home = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        if (!w) return { gone: s.mapId };
        const h = s.tileCentre(...w.home);
        return { chasing: !!w.chasing, returning: !!w.returning, state: w.state,
                 fromHome: Phaser.Math.Distance.Between(w.sprite.x, w.sprite.y,
                                                        h.x, h.y) };
      });
      checks.push(['it breaks off rather than following',
        !home.gone && !home.chasing, home.gone ? 'n/a' : `chasing=${home.chasing}`]);
      checks.push(['and settles back to wandering, not frozen',
        !home.gone && !home.returning && !home.chasing,
        home.gone ? 'n/a'
                  : `${home.fromHome.toFixed(0)}px from home, ${home.state}`]);
    } else {
      skipped.push(['--boar', 'nothing hostile on this map']);
    }
  }

  let shotTaken = false;
  if (SLASH) {
    await page.keyboard.press('Space');
    await page.waitForTimeout(120);
    const mid = await snapshot();
    if (MID) {                                     // the number is up, the blade is out
      fs.mkdirSync(path.dirname(OUT), { recursive: true });
      await page.locator('.stage').screenshot({ path: OUT });
      shotTaken = true;
    }
    await page.waitForTimeout(500);
    const after = await snapshot();
    checks.push(['slash animation played', mid.anim.includes('/slash/'), mid.anim]);
    checks.push(['control handed back', after.busy === false, 'still busy']);
    if (after.hits > 0) {                          // something was in the arc
      checks.push(['damage number floated on hit', mid.fxOnScreen > 0,
        `${after.hits} hit(s), ${mid.fxOnScreen} fx sprites mid-swing`]);
    }
  }

  // --- the picture -----------------------------------------------------------
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  if (POSE) {
    // Freeze the hero on one frame of a state - the strike of a slash, the
    // bottom of a gather - so a still can show what a 90ms frame is doing.
    const [state, idx] = POSE.split(',');
    await page.evaluate(([st, i]) => {
      const s = window.game.scene.scenes[0];
      const a = window.ART.manifest.anims[`${s.heroSprite}/${st}/${s.facing}`];
      s.busy = true;                        // so update() leaves the frame alone
      s.hero.anims.stop();
      s.hero.setFrame(a.frames[Number(i) || 0]);
    }, [state, idx]);
    await page.waitForTimeout(80);
  }
  if (shotTaken) {
    // already photographed mid-swing
  } else if (PAGE) {
    await page.screenshot({ path: OUT, fullPage: true });
  } else if (MAP_MODE) {
    // Resize the renderer to the whole world and snapshot its buffer, so the
    // overview is one real frame of the game rather than a stitched mosaic.
    const b64 = await page.evaluate(([w, h]) => new Promise((done) => {
      const g = window.game;
      const s = g.scene.scenes[0];
      g.scale.resize(w, h);
      s.cameras.main.stopFollow();
      s.cameras.main.setBounds(0, 0, w, h);
      s.cameras.main.setSize(w, h);
      s.cameras.main.centerOn(w / 2, h / 2);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        g.renderer.snapshot((img) => done(img.src));
      }));
    }), [cols * report.tileSize, rows * report.tileSize]);
    fs.writeFileSync(OUT, Buffer.from(b64.split(',')[1], 'base64'));
  } else {
    await page.locator('.stage').screenshot({ path: OUT });
  }

  await browser.close();

  const failed = checks.filter(([, ok]) => !ok);
  for (const [mode, why] of skipped) {
    console.log(`  skip  ${mode}: ${why}`);
  }
  for (const [name, ok, detail] of checks) {
    console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : '   ' + detail}`);
  }
  console.log(`map       ${cols}x${rows} tiles, ${report.entities} entities, `
              + `${report.props} prop definitions, ${report.items} items, `
              + `atlases: ${report.atlases.join(', ')}`);
  console.log(`collision ${report.blocked} blocked tiles, `
              + `${report.interactables} things to talk to or take`);
  console.log(`shot      ${path.relative(ROOT, OUT)}  `
              + `${fs.statSync(OUT).size} B  (hero at ${report.heroTile})`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });

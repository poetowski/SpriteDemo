/* Drive the real game in headless Chromium and photograph it.
 *
 *   node tools/shot.cjs                          build/shot.png, at the spawn
 *   node tools/shot.cjs --tile 33,40             stand somewhere and look
 *   node tools/shot.cjs --map                    the whole world, one image
 *   node tools/shot.cjs --talk --tile 37,37      walk up to someone and press E
 *   node tools/shot.cjs --gather --tile 34,37    stand by an item, press E, check the bag
 *   node tools/shot.cjs --give item.sword --slash   arm the hero and swing
 *   node tools/shot.cjs --bump                   walk into an animal, check it blocks
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
const MID = flag('--mid');                // with --slash: photograph the moment of impact
const CHOOSE = args.includes('--choose')  // with --talk: take the nth reply (1-based)
  ? Number(value('--choose', '1')) - 1 : null;
const TILE = value('--tile', null);
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
  const checks = [
    ['no console errors', problems.length === 0, problems.join(' | ')],
    ['world matches the map', report.worldBounds[0] === cols * report.tileSize
      && report.worldBounds[1] === rows * report.tileSize, JSON.stringify(report.worldBounds)],
    ['every entity spawned', report.sprites === report.entities + 1,
      `${report.sprites} sprites vs ${report.entities} entities + hero`],
    ['every item lying in the world', report.pickups === report.itemEntities,
      `${report.pickups} pickups vs ${report.itemEntities} placed`],
    ['collision tiles claimed', report.blocked >= report.staticBlockers,
      `${report.blocked} blocked tiles for ${report.staticBlockers} solid things`],
    ['one body per blocked tile', report.solids === report.blocked,
      `${report.solids} bodies vs ${report.blocked} tiles`],
    ['livestock is wandering', report.wanderers > 0, `${report.wanderers}`],
  ];
  if (GIVE) {
    const on = (report.weapon === GIVE || report.armor === GIVE)
      && report.heroSprite !== 'actor.hero';
    checks.push(['gear equipped and drawn on the hero', on,
      `weapon=${report.weapon} armor=${report.armor} sprite=${report.heroSprite}`]);
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
    const before = await page.evaluate(() => {
      const s = window.game.scene.scenes[0];
      const ex = (s.map.exits || [])[0];
      if (!ex) return null;
      // Cross in the middle of the band rather than at an end: an off-by-one
      // in the pairing shows up there and nowhere else.
      const door = ex.tiles[Math.floor(ex.tiles.length / 2)];
      s.addItem('item.axe');
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
               door, way,
               want: (ex.spawns && ex.spawns[at]) || ex.spawn };
    });
    if (before) {
      await page.waitForFunction(
        (to) => window.game.scene.scenes[0].mapId === to && !!window.game.scene.scenes[0].hero,
        before.to, { timeout: 10000 }).catch(() => {});
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const t = s.heroTile();
        return { map: s.mapId, bag: s.inventory.filter(Boolean).length, tile: t,
                 facing: s.facing, onExit: !!s.exits.get(t.join(',')) };
      });
      checks.push([`${before.from} leads to ${before.to}`,
        after.map === before.to, after.map]);
      checks.push(['the bag came across',
        after.bag === before.bag, `${before.bag} -> ${after.bag}`]);
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
      checks.push(['the map has an exit to cross', false, 'none authored']);
    }
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
      // West of it, not east: a charging boar shoves the hero, and east of
      // this one is the seam - the test kept being pushed onto the next map.
      s.hero.body.reset(p.x - s.ts * 2.5, p.y);        // just inside its sight
      s.cameras.main.centerOn(s.hero.x, s.hero.y);
      s.invuln = 0;
      return { def: w.def.sprite, hp: s.hp,
               gap: Phaser.Math.Distance.Between(s.hero.x, s.hero.y,
                                                 w.sprite.x, w.sprite.y) };
    });
    if (before) {
      await page.waitForTimeout(2600);
      const after = await page.evaluate(() => {
        const s = window.game.scene.scenes[0];
        const w = s.wanderers.find((a) => a.def.hostile);
        if (!w) return { gone: s.mapId };               // shoved off the map
        return { hp: s.hp, chasing: !!w.chasing,
                 gap: Phaser.Math.Distance.Between(s.hero.x, s.hero.y,
                                                   w.sprite.x, w.sprite.y) };
      });
      checks.push([`the ${before.def.split('.')[1]} noticed and closed in`,
        !after.gone && after.chasing && after.gap < before.gap,
        after.gone ? `hero ended up on ${after.gone}`
                   : `${before.gap.toFixed(0)}px -> ${after.gap.toFixed(0)}px`]);
      checks.push(['and goring the hero costs hp',
        !after.gone && after.hp < before.hp,
        after.gone ? 'n/a' : `${before.hp} -> ${after.hp}`]);

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

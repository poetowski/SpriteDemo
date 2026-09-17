/* Drive the map editor in a headless browser and check it works.
 *
 *   python tools/editor.py --no-open &      (or let this start nothing and
 *   node tools/editor_test.cjs               point EDITOR_URL at a running one)
 *
 * It opens the editor against a scratch map, paints terrain, places and erases
 * an object, moves the spawn, undoes, saves, and asks the server to build -
 * checking after each step that the thing actually changed. A failure exits
 * non-zero, so this is a smoke test for the editor the way tools/shot.cjs is
 * for the game.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const URL = process.env.EDITOR_URL || 'http://127.0.0.1:8765/';
const MAP = process.env.EDITOR_TEST_MAP || '_scratch';

let chromium;
try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require('./cdp.cjs')); }

const checks = [];
const check = (name, ok, detail = '') => checks.push([name, !!ok, detail]);

// The test edits a throwaway copy of a real map, so a failed run can never
// leave someone's map half-painted. It makes the copy itself and removes it
// afterwards, so there is nothing to set up and nothing left behind.
const MAPS = path.join(ROOT, 'content', 'maps');
const scratch = path.join(MAPS, `${MAP}.json`);
let madeScratch = false;
function makeScratch() {
  if (fs.existsSync(scratch)) return;
  const source = fs.readdirSync(MAPS).find((f) => f.endsWith('.json') && !f.startsWith('_'));
  if (!source) throw new Error('no map to copy for the scratch map');
  const m = JSON.parse(fs.readFileSync(path.join(MAPS, source), 'utf-8'));
  m.id = 'map.scratch';
  m.name = 'Scratch';
  fs.writeFileSync(scratch, JSON.stringify(m, null, 2) + '\n');
  madeScratch = true;
}
function dropScratch() {
  if (madeScratch && fs.existsSync(scratch)) fs.unlinkSync(scratch);
}

(async () => {
  makeScratch();
  // Fingerprint every other map before touching anything: the one thing an
  // editor must never do is write over a map you did not open, and a test that
  // edits maps is exactly where that would first show up.
  const otherMaps = fs.readdirSync(MAPS).filter((f) => f !== `${MAP}.json`);
  const otherBefore = Object.fromEntries(otherMaps.map((f) =>
    [f, fs.readFileSync(path.join(MAPS, f), 'utf-8')]));

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push(String(e)));

  await page.goto(URL);
  await page.waitForFunction(() => window.editor && window.editor.M && window.editor.map,
                             null, { timeout: 20000 });

  // Everything below drives the page's own functions and events, so a pass
  // means the editor works, not that a copy of its logic works.
  await page.evaluate((name) => window.openMap(name), MAP);
  await page.waitForFunction((n) => window.editor.mapName === n, MAP, { timeout: 5000 });

  const boot = await page.evaluate(() => ({
    canvas: [document.getElementById('view').width, document.getElementById('view').height],
    size: state.map.size,
    ts: state.map.tile_size,
    zoom: state.zoom,
    tiles: document.querySelectorAll('#pal-terrain .swatch').length,
    definedTiles: Object.keys(state.M.tiles).length,
    objects: document.querySelectorAll('#pal-objects .swatch').length,
    entities: state.map.entities.length,
    solidSwatches: document.querySelectorAll('#pal-objects .swatch.solid').length,
    groundSwatches: document.querySelectorAll('#pal-objects .swatch.ground').length,
  }));
  const [w, h] = boot.size;
  check('map opened and canvas sized',
        boot.canvas[0] === w * boot.ts * boot.zoom && boot.canvas[1] === h * boot.ts * boot.zoom,
        `${boot.canvas} for ${w}x${h} at ${boot.ts}px x${boot.zoom}`);
  check('terrain palette offers every defined terrain',
        boot.tiles === boot.definedTiles && boot.tiles > 0,
        `${boot.tiles} swatches for ${boot.definedTiles} terrains`);
  check('object palette built', boot.objects > 40, `${boot.objects} swatches`);
  check('solid and ground objects both offered',
        boot.solidSwatches > 0 && boot.groundSwatches > 0,
        `${boot.solidSwatches} solid, ${boot.groundSwatches} walkable`);

  // The two sets are exclusive: what is on screen must follow the tool, and
  // `hidden` must actually hide (an author display rule beats the UA one).
  const shown = () => page.evaluate(() => {
    const vis = (id) => getComputedStyle(document.getElementById(id)).display !== 'none';
    return { terrain: vis('pal-terrain'), objects: vis('pal-objects'),
             groups: [...document.querySelectorAll('#pal-objects .group h3')]
               .map((h) => h.firstChild.textContent) };
  });
  await page.evaluate(() => setTool('paint'));
  const onPaint = await shown();
  check('paint shows terrain only', onPaint.terrain && !onPaint.objects,
        `terrain=${onPaint.terrain} objects=${onPaint.objects}`);
  await page.evaluate(() => setTool('place'));
  const onPlace = await shown();
  check('place shows objects only', onPlace.objects && !onPlace.terrain,
        `terrain=${onPlace.terrain} objects=${onPlace.objects}`);
  check('objects are grouped by kind',
        onPlace.groups.join(',') === 'props,actors,items', onPlace.groups.join(','));
  await page.evaluate(() => document.getElementById('tab-terrain').click());
  const viaTab = await page.evaluate(() => ({ tool: state.tool,
    terrain: getComputedStyle(document.getElementById('pal-terrain')).display !== 'none' }));
  check('the terrain tab picks up the paint tool', viaTab.tool === 'paint' && viaTab.terrain,
        `tool=${viaTab.tool}`);

  // A click at a cell, through the page's real pointer handlers.
  const click = (cell, button = 0) => page.evaluate(([c, b]) => {
    const cv = document.getElementById('view');
    const r = cv.getBoundingClientRect();
    const ts = state.map.tile_size * state.zoom;
    const at = (type, buttons) => cv.dispatchEvent(new PointerEvent(type, {
      clientX: r.left + (c[0] + 0.5) * ts, clientY: r.top + (c[1] + 0.5) * ts,
      button: b, buttons, bubbles: true, pointerId: 1,
    }));
    at('pointerdown', b === 2 ? 2 : 1);
    at('pointerup', 0);
  }, [cell, button]);

  // --- painting terrain, and the edges resolving ----------------------------
  const target = [3, 3];
  await page.evaluate(() => { state.terrain = 'tile.water'; state.brush = 1; setTool('paint'); });
  const before = await page.evaluate((t) => terrainAt(t[0], t[1]), target);
  await click(target);
  const painted = await page.evaluate((t) => ({
    terrain: terrainAt(t[0], t[1]),
    index: indexAt(t[0], t[1]),
    lone: state.M.tileset.variants['tile.water'],
    dirty: state.dirty,
  }), target);
  check('paint changed the terrain', painted.terrain === 'tile.water' && before !== 'tile.water',
        `${before} -> ${painted.terrain}`);
  check('a lone tile resolves to a transition, not the plain fill',
        !painted.lone.includes(painted.index),
        `index ${painted.index}, plain variants ${painted.lone}`);

  // Fill a 3x3 so the middle becomes fully surrounded, and check it flips to
  // the plain tile - which is the whole point of the mask resolution.
  await page.evaluate(() => { state.brush = 3; });
  await click([4, 4]);
  const middle = await page.evaluate(() => ({
    index: indexAt(4, 4), plain: state.M.tileset.variants['tile.water'],
  }));
  check('a surrounded tile resolves to the plain fill',
        middle.plain.includes(middle.index), `index ${middle.index}`);

  // Flooding ground that something stands on has to take the object with it,
  // or the build would refuse the map.
  const flood = await page.evaluate(() => {
    const [w] = state.map.size;
    const victim = state.map.entities.find((e) => e.tile[1] > 6 && e.tile[0] < w - 2
      && state.M.tiles[terrainAt(e.tile[0], e.tile[1])].walkable);
    const before = state.map.entities.length;
    state.terrain = 'tile.water'; state.brush = 1; setTool('paint');
    // applyAt, not paint: it takes the undo snapshot, so the undo below
    // reverts this flood rather than an earlier edit.
    applyAt(victim.tile[0], victim.tile[1], 0);
    return { def: victim.def, before, after: state.map.entities.length,
             msg: document.getElementById('msg').textContent };
  });
  check('flooding ground removes what stood on it',
        flood.after === flood.before - 1, `${flood.def}: ${flood.before} -> ${flood.after}`);
  check('and says so', /cannot stand on water/.test(flood.msg), flood.msg);
  await page.evaluate(() => { state.brush = 1; undo(); });

  // --- placing and erasing objects -----------------------------------------
  const spot = [10, 10];
  await page.evaluate((s) => {
    state.terrain = 'tile.grass';
    state.brush = 3; setTool('paint');
  }, spot);
  await click(spot);                                  // clear ground to build on
  await page.evaluate(() => { state.brush = 1; state.object = 'prop.barrel'; setTool('place'); });
  const n0 = await page.evaluate(() => state.map.entities.length);
  await click(spot);
  const n1 = await page.evaluate(() => state.map.entities.length);
  check('object placed', n1 === n0 + 1, `${n0} -> ${n1}`);

  const blockedAttempt = await page.evaluate((s) => {
    const before = state.map.entities.length;
    place(s[0], s[1]);                                 // a solid on a solid
    return state.map.entities.length === before;
  }, spot);
  check('a solid will not stack on a solid', blockedAttempt);

  const onWater = await page.evaluate(() => {
    const before = state.map.entities.length;
    place(4, 4);                                       // water is not walkable
    return state.map.entities.length === before;
  });
  check('nothing can be placed on unwalkable ground', onWater);

  await click(spot, 2);                                // right-click erases
  const n2 = await page.evaluate(() => state.map.entities.length);
  check('right-click erased it', n2 === n0, `${n1} -> ${n2}`);

  // --- spawn, undo ----------------------------------------------------------
  await page.evaluate(() => setTool('spawn'));
  await click(spot);
  const spawn = await page.evaluate(() => state.map.spawn.tile);
  check('spawn moved', spawn[0] === spot[0] && spawn[1] === spot[1], JSON.stringify(spawn));

  await page.evaluate(() => undo());
  const undone = await page.evaluate(() => state.map.spawn.tile);
  check('undo put the spawn back', !(undone[0] === spot[0] && undone[1] === spot[1]),
        JSON.stringify(undone));

  // --- saving and building --------------------------------------------------
  const file = path.join(ROOT, 'content', 'maps', `${MAP}.json`);
  const diskBefore = fs.readFileSync(file, 'utf-8');
  await page.evaluate(() => save());
  await page.waitForFunction(() => state.dirty === false, null, { timeout: 8000 });
  const diskAfter = fs.readFileSync(file, 'utf-8');
  check('save wrote the map to disk', diskAfter !== diskBefore,
        `${diskBefore.length} -> ${diskAfter.length} bytes`);
  const parsed = JSON.parse(diskAfter);
  check('saved map is the plain format', Array.isArray(parsed.ground)
    && parsed.ground.length === h && typeof parsed.legend === 'object'
    && Array.isArray(parsed.entities), 'ground/legend/entities');
  check('legend only holds characters the map uses',
        Object.keys(parsed.legend).every((ch) => parsed.ground.join('').includes(ch)),
        Object.keys(parsed.legend).join(''));

  const built = await page.evaluate(async () => {
    const r = await fetch('/api/build', { method: 'POST' });
    return r.json();
  });
  check('server ran the build and it passed', built.ok,
        (built.output || '').split('\n').slice(-2).join(' '));

  const touched = otherMaps.filter((f) =>
    fs.readFileSync(path.join(MAPS, f), 'utf-8') !== otherBefore[f]);
  check('no other map was written', touched.length === 0, touched.join(', '));

  // And the server must refuse a save aimed at someone else's file.
  const crossWrite = await page.evaluate(async (other) => {
    const r = await fetch(`/api/save?map=${other}`, {
      method: 'POST', body: JSON.stringify({ id: 'map.scratch', ground: [], size: [1, 1] }),
    });
    return { status: r.status, body: await r.json() };
  }, otherMaps[0].replace('.json', ''));
  check('the server refuses to write one map over another',
        crossWrite.status === 409 && /refusing/.test(crossWrite.body.error || ''),
        `${crossWrite.status} ${JSON.stringify(crossWrite.body)}`);
  const stillClean = otherMaps.filter((f) =>
    fs.readFileSync(path.join(MAPS, f), 'utf-8') !== otherBefore[f]);
  check('and left it untouched', stillClean.length === 0, stillClean.join(', '));

  check('no console errors', problems.length === 0, problems.join(' | '));

  const shot = process.env.EDITOR_SHOT;
  if (shot) {                       // --shot: a picture of the editor at work
    await page.evaluate(() => {
      state.zoom = 1; state.object = 'prop.tree_oak'; setTool('place');
      document.getElementById('zoom').value = '1';
      markSelection(); render();
      message('ready');
    });
    await page.waitForTimeout(400);
    await page.screenshot({ path: shot });
    console.log(`shot      ${shot}`);
  }

  await browser.close();
  dropScratch();
  const failed = checks.filter(([, ok]) => !ok);
  for (const [name, ok, detail] of checks) {
    console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : '   ' + detail}`);
  }
  console.log(`editor    ${boot.tiles} terrains, ${boot.objects} objects, `
              + `${boot.entities} entities on ${MAP} (${w}x${h})`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { dropScratch(); console.error(e); process.exit(1); });

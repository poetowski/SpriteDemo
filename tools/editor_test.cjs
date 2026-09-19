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
const { execFileSync } = require('child_process');

const ROOT = path.dirname(__dirname);
const URL = process.env.EDITOR_URL || 'http://127.0.0.1:8765/';
const MAP = process.env.EDITOR_TEST_MAP || '_scratch';

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  try {
    // A globally installed Playwright is not on a script's own require path.
    ({ chromium } = require(path.join(
      process.env.NODE_PATH || '/opt/node22/lib/node_modules', 'playwright')));
  } catch (e2) {
    ({ chromium } = require('./cdp.cjs'));   // or whatever Chrome is installed
  }
}

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
  // No way in and no way out, deliberately. The world view has to report a map
  // nothing reaches, and for a while the only maps like that were two real ones
  // sitting in the repo - so deleting them broke a check that had nothing to do
  // with them. The test brings its own orphan now.
  delete m.exits;
  fs.writeFileSync(scratch, JSON.stringify(m, null, 2) + '\n');
  madeScratch = true;
}
function dropScratch() {
  if (!madeScratch) return;
  if (fs.existsSync(scratch)) fs.unlinkSync(scratch);
  // And put the build back. The test asks the server to build while its
  // scratch map exists, which bakes that map into game/art-embed.js and
  // game/page.html - so a run that only deleted the file left the generated
  // game carrying a map that is not in content any more. It got committed
  // once. Rebuilding here means the test leaves the tree as it found it.
  try {
    execFileSync(process.env.PYTHON || 'python', [path.join(ROOT, 'tools', 'build.py')],
                 { cwd: ROOT, stdio: 'pipe' });
  } catch (e) {
    console.error('could not rebuild after the scratch map was removed:',
                  (e.stdout || e.message || '').toString().slice(-300));
  }
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
  // The cross-write check below asks the server to write one map over another
  // and expects to be refused, which the browser logs as a failed request.
  // That one is the test working, not the editor breaking.
  const expected = /409 \(Conflict\)/;
  page.on('console', (m) => {
    if (m.type() === 'error' && !expected.test(m.text())) problems.push(m.text());
  });
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
    actors: Object.keys(state.M.actors).length,
    actorSwatches: [...document.querySelectorAll('#pal-objects .swatch')]
      .filter((el) => state.M.actors[el.dataset.id]).length,
  }));
  const [w, h] = boot.size;
  check('map opened and canvas sized',
        boot.canvas[0] === w * boot.ts * boot.zoom && boot.canvas[1] === h * boot.ts * boot.zoom,
        `${boot.canvas} for ${w}x${h} at ${boot.ts}px x${boot.zoom}`);
  check('terrain palette offers every defined terrain',
        boot.tiles === boot.definedTiles && boot.tiles > 0,
        `${boot.tiles} swatches for ${boot.definedTiles} terrains`);
  check('object palette built', boot.objects > 40, `${boot.objects} swatches`);
  // A creature that is drawn and defined but missing from the palette cannot
  // be placed at all, and nothing else in the build would say so.
  check('every actor is offered in the palette',
        boot.actorSwatches === boot.actors && boot.actors > 0,
        `${boot.actorSwatches} swatches for ${boot.actors} actors`);
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

  // --- the world view -------------------------------------------------------
  // The doorways are what make a world out of separate maps, so the checks
  // are about the join: that saving keeps it, and that the atlas puts the
  // maps where the doorways say they belong.

  // Opening a map with doorways and pressing save must not drop them. It did:
  // save() named the fields it wrote, `exits` was not among them, and no gate
  // treats a missing exits list as an error - so the world came apart quietly.
  // fetch is stubbed so this proves the body without writing a real map.
  const kept = await page.evaluate(async () => {
    await window.loadWorld();
    const withExits = window.editor.world.entries.find((e) => (e.map.exits || []).length);
    if (!withExits) return { skipped: true };
    await window.openMap(withExits.name);
    const before = JSON.parse(JSON.stringify(window.editor.map.exits));
    const real = window.fetch;
    let sent = null;
    window.fetch = (url, opts) => {
      if (String(url).startsWith('/api/save')) {
        sent = JSON.parse(opts.body);
        return Promise.resolve({ json: () => Promise.resolve({ ok: true, path: 'dry-run' }) });
      }
      return real(url, opts);
    };
    try { await window.save(); } finally { window.fetch = real; }
    return { name: withExits.name, before, sent: sent && sent.exits };
  });
  check('saving a map keeps its doorways', !kept.skipped
    && JSON.stringify(kept.sent) === JSON.stringify(kept.before),
    `${kept.name}: ${JSON.stringify(kept.sent) === undefined ? 'dropped' : 'kept'}`);

  const world = await page.evaluate(async () => {
    await window.setView('world');
    const cv = document.getElementById('world');
    const placed = [...window.editor.layout.placed].map(([id, p]) => ({
      id, name: p.name, ox: p.ox, oy: p.oy, w: p.map.size[0], h: p.map.size[1],
      label: p.map.name,
    }));
    return {
      canvas: [cv.width, cv.height],
      hidden: cv.hidden,
      viewHidden: document.getElementById('view').hidden,
      placed,
      groups: window.editor.layout.groups,
      maps: window.editor.world.entries.length,
      lines: document.querySelectorAll('#world-maps .mapline').length,
      orphans: document.querySelectorAll('#world-maps .mapline.orphan').length,
      notes: [...document.querySelectorAll('#world-notes .note')].map((n) => n.textContent),
    };
  });
  check('the world view draws', !world.hidden && world.viewHidden
    && world.canvas[0] > 40 && world.canvas[1] > 40, world.canvas.join('x'));
  check('every map is on the atlas', world.placed.length === world.maps
    && world.lines === world.maps, `${world.placed.length} of ${world.maps}`);

  // The wildernesses join west-to-east, so each should sit exactly one map
  // width from its neighbour with the crossing rows lined up - that is the
  // whole claim the atlas makes, and it is arithmetic, not a look.
  const by = Object.fromEntries(world.placed.map((p) => [p.id, p]));
  const w1 = by['map.wilderness1'];
  const w2 = by['map.wilderness2'];
  if (w1 && w2) {
    check('maps sit against the edge they join',
          w2.ox + w2.w === w1.ox, `w2 ends at ${w2.ox + w2.w}, w1 starts at ${w1.ox}`);
    const rows = await page.evaluate(() => {
      const { byId } = window.editor.world;
      const ex = byId.get('map.wilderness1').map.exits.find((e) => e.to === 'map.wilderness2');
      const p1 = window.editor.layout.placed.get('map.wilderness1');
      const p2 = window.editor.layout.placed.get('map.wilderness2');
      return ex.tiles.map((t, i) => [p1.oy + t[1], p2.oy + window.arrivalsOf(ex)[i][1]]);
    });
    check('the crossing rows line up', rows.every(([a, b]) => a === b),
          rows.filter(([a, b]) => a !== b).map((r) => r.join('!=')).join(' ') || 'all aligned');
  } else {
    check('the wildernesses are on the atlas', false, Object.keys(by).join(', '));
  }

  // Nothing may be drawn on top of anything else, or the atlas lies about
  // where a place is.
  const overlaps = [];
  for (let i = 0; i < world.placed.length; i++) {
    for (let j = i + 1; j < world.placed.length; j++) {
      const a = world.placed[i];
      const b = world.placed[j];
      if (a.ox < b.ox + b.w && b.ox < a.ox + a.w
          && a.oy < b.oy + b.h && b.oy < a.oy + a.h) overlaps.push(`${a.id}/${b.id}`);
    }
  }
  check('no two maps overlap on the atlas', overlaps.length === 0, overlaps.join(', '));

  // A map nothing can reach is the failure this view exists to make obvious.
  check('a map nothing reaches is called out', world.orphans > 0
    && world.notes.some((t) => /joins nothing/.test(t)),
    `${world.orphans} orphan lines`);

  // Clicking a map on the atlas opens it.
  const jumped = await page.evaluate(async () => {
    const target = [...window.editor.layout.placed].find(
      ([id]) => id !== (window.editor.map && window.editor.map.id));
    if (!target) return null;
    const [id, p] = target;
    const hit = window.mapAtWorld(...window.worldPointOf(id));
    if (!hit) return { found: false };
    await window.openMap(hit.name);
    await window.setView('map');
    return { found: true, wanted: p.name, got: window.editor.mapName,
             view: window.editor.view };
  });
  check('clicking a map on the atlas opens it', jumped && jumped.found
    && jumped.got === jumped.wanted && jumped.view === 'map',
    jumped ? `${jumped.wanted} -> ${jumped.got}` : 'nothing to click');

  // The name is content the editor could not previously set at all.
  const named = await page.evaluate(async (m) => {
    await window.openMap(m);
    const field = document.getElementById('mapName');
    const shown = field.value;
    field.value = 'Renamed By Test';
    field.dispatchEvent(new Event('input'));
    const held = window.editor.map.name;
    field.value = shown;
    field.dispatchEvent(new Event('input'));
    return { shown, held, restored: window.editor.map.name };
  }, MAP);
  check('the map name is shown and editable', named.shown === 'Scratch'
    && named.held === 'Renamed By Test' && named.restored === 'Scratch',
    `${named.shown} -> ${named.held} -> ${named.restored}`);

  const stillCleanAfterWorld = otherMaps.filter((f) =>
    fs.readFileSync(path.join(MAPS, f), 'utf-8') !== otherBefore[f]);
  check('the world view wrote nothing', stillCleanAfterWorld.length === 0,
        stillCleanAfterWorld.join(', '));

  // Every definition must actually draw. The editor loads whatever atlases the
  // manifest lists, so a new sheet needs no wiring - but if one failed to
  // load, its swatches would be blank rather than missing, and a blank swatch
  // is easy to scroll past. Counting painted pixels catches that.
  const drawn = await page.evaluate(() => {
    const blank = [];
    for (const el of document.querySelectorAll('#pal-objects .swatch')) {
      const cv = el.querySelector('canvas');
      if (!cv) { blank.push(el.dataset.id + ' (no canvas)'); continue; }
      const px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
      let on = 0;
      for (let i = 3; i < px.length; i += 4) if (px[i] > 0) on++;
      if (on < 8) blank.push(`${el.dataset.id} (${on}px)`);
    }
    return { blank, atlases: Object.keys(window.editor.images).sort() };
  });
  check('every object in the palette draws something', drawn.blank.length === 0,
        drawn.blank.join(', ') || `atlases: ${drawn.atlases.join(', ')}`);

  // Animated objects carry a mark. The palette is where you choose what to
  // place, so "does this move?" has to be answerable there - and the mark has
  // to come from the animations that exist rather than from a second list
  // that can drift out of step with them.
  const moving = await page.evaluate(() => ({
    marked: [...document.querySelectorAll('#pal-objects .swatch.anim')]
      .map((e) => e.dataset.id).sort(),
    animated: Object.keys(window.editor.M.anims).filter((k) => k.startsWith('prop.')).sort(),
    stacked: [...document.querySelectorAll('#pal-objects .swatch.anim')]
      .filter((e) => e.classList.contains('solid') || e.classList.contains('ground')
                  || e.classList.contains('gather')).length,
    frames: [...document.querySelectorAll('#pal-objects .swatch.anim span')]
      .every((e) => /animated - \d+ frames/.test(e.title)),
  }));
  check('every animated object is marked, and only those',
        JSON.stringify(moving.marked) === JSON.stringify(moving.animated)
          && moving.animated.length > 0,
        `${moving.marked.length} marked, ${moving.animated.length} animated`);
  check('the mark stacks with solid rather than replacing it',
        moving.stacked === moving.marked.length,
        `${moving.stacked} of ${moving.marked.length} keep their other mark`);
  check('and it says how many frames', moving.frames, 'titles carry the count');

  // --- interiors ------------------------------------------------------------
  // A room entered through a door is not next to the map it is entered from,
  // so the atlas must not place it on the grid as though it were - it gets a
  // band of its own and a line back to the doorway.
  const rooms = await page.evaluate(async () => {
    await window.setView('world');
    const L = window.editor.layout;
    const inside = [...L.interiors].map(([id, v]) => ({ id, ...v }));
    const placed = [...L.placed].map(([id, p]) => ({
      id, ox: p.ox, oy: p.oy, w: p.map.size[0], h: p.map.size[1],
      interior: !!p.interior, parent: p.parent || null,
    }));
    return {
      inside, placed,
      lines: [...document.querySelectorAll('#world-maps .mapline.inside')]
        .map((n) => n.textContent),
      notes: [...document.querySelectorAll('#world-notes .note')].map((n) => n.textContent),
    };
  });
  check('a room behind a door is known to be an interior',
        rooms.inside.some((r) => r.id === 'map.shed_interior'),
        rooms.inside.map((r) => r.id).join(', ') || 'none found');
  const room = rooms.placed.find((p) => p.id === 'map.shed_interior');
  const outdoor = rooms.placed.filter((p) => !p.interior);
  check('it is kept off the grid the outdoor maps sit on',
        !!room && room.interior
          && outdoor.every((o) => !(room.ox < o.ox + o.w && o.ox < room.ox + room.w
                                 && room.oy < o.oy + o.h && o.oy < room.oy + room.h)),
        room ? `at ${room.ox},${room.oy}` : 'not placed');
  check('and it is tied back to the door it is behind',
        !!room && room.parent === 'map.wilderness1'
          && rooms.lines.some((t) => /through the door at 12,8/.test(t)),
        room ? `parent ${room.parent}` : '-');
  // The note about an inland doorway is for a doorway that is not a door into
  // a room. Reporting every interior as an oddity would bury the real ones.
  check('a door into a room is not reported as an oddity',
        !rooms.notes.some((t) => /inland doorway/.test(t)),
        rooms.notes.filter((t) => /inland/.test(t)).join(' | ') || 'none');

  // --- gates ----------------------------------------------------------------
  // A gate is the pair of mouths, not one exit, so the checks are about the
  // pairing: that the two sides are found to belong together, that a
  // reciprocal pair is not counted twice, and that every mouth carries the
  // number the panel lists it under.
  const gates = await page.evaluate(async () => {
    await window.setView('world');
    const gs = window.editor.gates.map((g) => ({
      n: g.n, from: g.from, to: g.to, edge: g.edge, oneWay: g.oneWay,
      colour: g.colour, partner: g.partner ? g.partner.id : null,
      tiles: g.ex.tiles.length,
      toInterior: window.editor.layout.interiors.has(g.to)
               || window.editor.layout.interiors.has(g.from),
    }));
    return {
      gates: gs,
      rows: document.querySelectorAll('#world-gates .gate').length,
      exits: [...window.editor.world.byId.values()]
        .reduce((n, e) => n + (e.map.exits || []).length, 0),
      lookup: window.gateFor('map.wilderness1', 0) === window.gateFor('map.wilderness2', 0),
    };
  });
  const twoWay = gates.gates.filter((g) => !g.oneWay);
  check('both mouths of a gate are one gate',
        gates.gates.length + twoWay.length === gates.exits,
        `${gates.exits} exits -> ${gates.gates.length} gates (${twoWay.length} two-way)`);
  check('a gate is listed once per pair', gates.rows === gates.gates.length,
        `${gates.rows} rows, ${gates.gates.length} gates`);
  check('both sides of a gate share its number and colour', gates.lookup,
        'wilderness1#0 and wilderness2#0 resolve to the same gate');
  // A seam leaves by an edge; a door does not, and that is the difference
  // between the two kinds of crossing rather than a gap in the data. This
  // asserted an edge on every gate back when every gate was a seam.
  check('every gate is a seam on an edge or a door into a room',
        gates.gates.every((g) => g.edge || g.oneWay || g.toInterior),
        gates.gates.map((g) => `${g.n}:${g.edge || (g.toInterior ? 'door' : '?')}`).join(' '));

  // --- the rotation when crossing ------------------------------------------
  // Walking off an edge and arriving spun round is the bug this catches. The
  // editor reports it and the build now refuses it, so both are checked.
  const spun = await page.evaluate(() => {
    const want = { west: 'left', east: 'right', north: 'up', south: 'down' };
    const wrong = [];
    for (const { map } of window.editor.world.byId.values()) {
      (map.exits || []).forEach((ex, i) => {
        const edge = window.edgeOf(map, ex.tiles);
        if (edge && ex.facing && ex.facing !== want[edge]) {
          wrong.push(`${map.id}#${i} ${edge} -> ${ex.facing}`);
        }
      });
    }
    return wrong;
  });
  check('no crossing leaves the player turned around', spun.length === 0, spun.join(', '));

  // --- gatherable things versus scenery ------------------------------------
  // The game makes something a pickup because its definition is an item, not
  // because of a flag - so the editor must agree with that, not guess.
  const loot = await page.evaluate(() => {
    const ids = Object.keys(window.editor.M.items);
    const props = Object.keys(window.editor.M.props);
    return {
      itemsAllGatherable: ids.every((id) => window.gatherableOf(id)),
      propsNoneGatherable: props.every((id) => !window.gatherableOf(id)),
      gatherSwatches: document.querySelectorAll('#pal-objects .swatch.gather').length,
      drawnItems: ids.filter((id) => window.spriteFor && true).length,
      solidAndGather: [...document.querySelectorAll('#pal-objects .swatch.gather')]
        .filter((el) => el.classList.contains('solid')
                     || el.classList.contains('ground')).length,
      titles: [...document.querySelectorAll('#pal-objects .swatch.gather span')]
        .slice(0, 2).map((el) => el.title),
    };
  });
  check('every item is gatherable and no prop is',
        loot.itemsAllGatherable && loot.propsNoneGatherable,
        `items ${loot.itemsAllGatherable}, props ${loot.propsNoneGatherable}`);
  check('gatherable things are marked in the palette', loot.gatherSwatches > 0,
        `${loot.gatherSwatches} swatches`);
  check('a swatch is gatherable or scenery, never both', loot.solidAndGather === 0,
        `${loot.solidAndGather} wearing two marks`);
  check('the mark says what it is', loot.titles.every((t) => /gatherable/.test(t)),
        loot.titles.join(' | '));

  // --- the quest board ------------------------------------------------------
  // The build already refuses a quest the world cannot pay. What this view is
  // for is the edit in progress: the maps it counts include the one on screen,
  // unsaved, so erasing the last berry has to show up here before the build
  // ever sees it.
  const board = await page.evaluate(async () => {
    await window.setView('quests');
    return {
      quests: window.questsOf().length,
      cards: document.querySelectorAll('#quests .card').length,
      broken: document.querySelectorAll('#quests .card.broken').length,
      short: document.querySelectorAll('#quests .supply.short').length,
      notes: [...document.querySelectorAll('#quest-notes .note')].map((n) => n.textContent),
      rows: document.querySelectorAll('#quest-list .dlgline').length,
      // Every objective names something, and the board says where it is.
      supplies: [...document.querySelectorAll('#quests .supply')].map((e) => e.textContent),
    };
  });
  check('the quest board lists every quest',
        board.quests > 0 && board.cards === board.quests && board.rows === board.quests,
        `${board.cards} cards, ${board.rows} rows, ${board.quests} quests`);
  check('and every one of them is offered, payable and handed in',
        board.broken === 0 && board.short === 0
          && board.notes.some((t) => /offered, can be handed in/.test(t)),
        `${board.broken} broken, ${board.short} short: ${board.notes.join(' | ')}`);

  // The count is of the world as it stands, not of the world as last built.
  const live = await page.evaluate(async (m) => {
    const berries = 'item.berries';
    const before = window.placementsOf(berries).reduce((n, p) => n + p.n, 0);
    const carrier = [...window.editor.world.byId.values()]
      .find((e) => (e.map.entities || []).some((x) => x.def === berries));
    if (!carrier) return { skipped: true };
    await window.openMap(carrier.name);
    let erased = 0;
    for (const e of [...window.editor.map.entities]) {
      if (e.def !== berries) continue;
      window.snapshot();
      window.erase(e.tile[0], e.tile[1]);
      erased += 1;
    }
    await window.setView('quests');
    const after = window.placementsOf(berries).reduce((n, p) => n + p.n, 0);
    for (let i = 0; i < erased; i++) window.undo();
    await window.setView('quests');
    const back = window.placementsOf(berries).reduce((n, p) => n + p.n, 0);
    window.editor.dirty = false;
    return { map: carrier.name, before, after, back, erased };
  }, MAP);
  check('what the board counts is the map on screen, not the last build',
        !live.skipped && live.erased > 0 && live.after === live.before - live.erased
          && live.back === live.before,
        live.skipped ? 'no map carries the item'
          : `${live.before} -> ${live.after} after erasing ${live.erased} on `
            + `${live.map}, ${live.back} after undo`);

  // And a quest the world cannot pay has to look like one. Asking for more
  // than exists is the shape of that failure, so it is what is asked for here.
  const red = await page.evaluate(async () => {
    const q = window.questsOf().find((x) => (x.objectives || [])
      .some((o) => o.kind === 'collect'));
    if (!q) return { skipped: true };
    const ob = q.objectives.find((o) => o.kind === 'collect');
    const was = ob.count;
    ob.count = 9999;
    await window.setView('quests');
    const out = {
      broken: document.querySelectorAll('#quests .card.broken').length,
      short: document.querySelectorAll('#quests .supply.short').length,
      note: [...document.querySelectorAll('#quest-notes .note')]
        .some((n) => /cannot be finished/.test(n.textContent)),
    };
    ob.count = was;
    await window.setView('quests');
    return out;
  });
  check('a quest the world cannot pay is marked, and said out loud',
        red.skipped || (red.broken > 0 && red.short > 0 && red.note),
        `${red.broken} broken cards, ${red.short} short objectives, note=${red.note}`);

  // --- the conversation view -----------------------------------------------
  // A conversation is a graph; the point of drawing it is that every node
  // lands somewhere and every reply's arrow has a box at the far end.
  const talk = await page.evaluate(async () => {
    const withQuest = Object.values(window.editor.M.dialogue).find((d) =>
      Object.values(d.nodes).some((n) => (n.choices || [])
        .some((c) => c.start || c.finish)));
    const did = (withQuest || Object.values(window.editor.M.dialogue)[0]).id;
    await window.showDialogue(did);
    const d = window.editor.M.dialogue[did];
    const L = window.editor.dlgLayout;
    const gotos = [];
    for (const n of Object.values(d.nodes)) {
      for (const c of n.choices || []) if (c.goto) gotos.push(c.goto);
    }
    const cv = document.getElementById('dlg');
    return {
      did,
      nodes: Object.keys(d.nodes).length,
      boxes: L.boxes.size,
      entries: [...L.boxes.values()].filter((b) => b.entry).length,
      landed: gotos.every((g) => L.boxes.has(g)),
      canvas: [cv.width, cv.height],
      hidden: cv.hidden,
      rows: document.querySelectorAll('#dlg-list .dlgline').length,
      dialogues: Object.keys(window.editor.M.dialogue).length,
      // No two boxes may sit on top of each other, or the picture lies about
      // which reply leads where.
      overlaps: (() => {
        const bs = [...L.boxes.values()];
        let n = 0;
        for (let i = 0; i < bs.length; i++) {
          for (let j = i + 1; j < bs.length; j++) {
            const a = bs[i];
            const b = bs[j];
            if (a.x < b.x + b.w && b.x < a.x + a.w
                && a.y < b.y + b.h && b.y < a.y + a.h) n += 1;
          }
        }
        return n;
      })(),
    };
  });
  check('the conversation view draws every node',
        !talk.hidden && talk.boxes === talk.nodes && talk.canvas[0] > 40,
        `${talk.boxes} boxes for ${talk.nodes} nodes in ${talk.did}`);
  check('every reply lands on a node that is drawn', talk.landed, 'a goto with no box');
  check('no two nodes are drawn on top of each other', talk.overlaps === 0,
        `${talk.overlaps} overlapping`);
  check('the way in is marked', talk.entries > 0, `${talk.entries} entry nodes`);
  check('and every conversation is listed', talk.rows === talk.dialogues,
        `${talk.rows} rows for ${talk.dialogues} conversations`);

  // Clicking a node reads it out in full - the conditions and effects that the
  // boxes only have room to mark.
  const inspected = await page.evaluate(() => {
    const L = window.editor.dlgLayout;
    const d = window.editor.M.dialogue[window.editor.dlgId];
    const withEffect = [...L.boxes.values()].find((b) => (b.node.choices || [])
      .some((c) => c.start || c.finish || c.when));
    const box = withEffect || [...L.boxes.values()][0];
    const cv = document.getElementById('dlg');
    const r = cv.getBoundingClientRect();
    cv.dispatchEvent(new MouseEvent('click', {
      clientX: r.left + box.x + 10, clientY: r.top + box.y + 10, bubbles: true,
    }));
    return { picked: window.editor.dlgNode, wanted: box.nid,
             head: document.getElementById('dlg-node-head').textContent,
             lines: document.querySelectorAll('#dlg-node .line').length,
             replies: document.querySelectorAll('#dlg-node .reply').length,
             tags: [...document.querySelectorAll('#dlg-node .tag')].map((t) => t.textContent),
             wantLines: (d.nodes[box.nid].text || []).length,
             wantReplies: (d.nodes[box.nid].choices || []).length };
  });
  check('clicking a node reads the whole of it',
        inspected.picked === inspected.wanted
          && inspected.head === inspected.wanted
          && inspected.lines === inspected.wantLines
          && inspected.replies === inspected.wantReplies,
        `${inspected.picked}: ${inspected.lines}/${inspected.wantLines} lines, `
        + `${inspected.replies}/${inspected.wantReplies} replies`);
  check('and says what each reply does',
        inspected.tags.some((t) => /^(starts|hands in) quest\./.test(t))
          || inspected.tags.length > 0,
        inspected.tags.join(' | ') || 'no tags');

  // A quest card links to the conversation that offers it, which is the whole
  // reason the two views are in one tool.
  const linked = await page.evaluate(async () => {
    await window.setView('quests');
    const link = document.querySelector('#quests .card .link');
    if (!link) return { skipped: true };
    const wanted = link.textContent;
    link.click();
    await new Promise((r) => setTimeout(r, 60));
    return { wanted, view: window.editor.view, dlg: window.editor.dlgId,
             node: window.editor.dlgNode };
  });
  check('a quest links to the conversation that offers it',
        linked.skipped
          || (linked.view === 'dlg'
              && linked.wanted === `${linked.dlg.replace('dlg.', '')}/${linked.node}`),
        `${linked.wanted} -> ${linked.dlg}/${linked.node} in ${linked.view}`);

  // Back on the map, anything a quest depends on is marked - because erasing
  // one of those is the edit that quietly makes an errand impossible.
  const marked = await page.evaluate(async () => {
    await window.setView('map');
    const named = window.questTargets();
    const givers = window.questsOf().map((q) => q.giver).filter(Boolean);
    const targets = window.questsOf().flatMap((q) => (q.objectives || [])
      .filter((o) => o.kind !== 'visit').map((o) => o.target));
    return { named: [...named.keys()].sort(),
             wanted: [...new Set([...givers, ...targets])].sort(),
             why: [...named.values()].every((v) => v.length > 0) };
  });
  check('the map marks what the quests depend on',
        JSON.stringify(marked.named) === JSON.stringify(marked.wanted)
          && marked.named.length > 0 && marked.why,
        marked.named.join(', '));

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

/* Drive the real game in headless Chromium and photograph it.
 *
 *   node tools/shot.cjs                          build/shot.png, at the spawn
 *   node tools/shot.cjs --tile 33,40             stand somewhere and look
 *   node tools/shot.cjs --map                    the whole world, one image
 *   node tools/shot.cjs --talk --tile 37,37      walk up to someone and press E
 *   node tools/shot.cjs --out /tmp/a.png --wait 1500
 *
 * It loads game/index.html (vendored Phaser - no network), so what is captured
 * is the game, not a mock-up. Before it takes the picture it checks that the
 * scene actually came up: no console errors, a hero, the tilemap at the size
 * the manifest declares, and one sprite per placed entity. A failed check exits
 * non-zero, which makes this a smoke test that happens to leave a screenshot
 * behind rather than a screenshot tool that might be photographing a crash.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const args = process.argv.slice(2);

function flag(name) { return args.includes(name); }
function value(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}

const MAP_MODE = flag('--map');
const TALK = flag('--talk');
const TILE = value('--tile', null);
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
    console.error('playwright not found. npm i -g playwright (Chromium is at '
                  + '/opt/pw-browsers in this environment).');
    process.exit(2);
  }
}

/** Resolve after the scene has booted and its first frames have run. */
const BOOTED = () => !!(window.game && window.game.scene
  && window.game.scene.scenes[0] && window.game.scene.scenes[0].hero);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 940 } });

  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push(String(e)));

  await page.goto('file://' + path.join(ROOT, 'game', 'index.html'));
  await page.waitForFunction(BOOTED, null, { timeout: 20000 });
  await page.evaluate(() => {                       // drop the "click to play" veil
    const f = document.getElementById('focus');
    if (f) f.classList.remove('show');
  });

  if (TILE) {
    const [tx, ty] = TILE.split(',').map(Number);
    await page.evaluate(([x, y]) => {
      const s = window.game.scene.scenes[0];
      const p = s.tileCentre(x, y);
      s.hero.setPosition(p.x, p.y);
      s.cameras.main.centerOn(p.x, p.y);
    }, [tx, ty]);
  }

  await page.waitForTimeout(WAIT);

  // --- the checks ------------------------------------------------------------
  const report = await page.evaluate(() => {
    const s = window.game.scene.scenes[0];
    const m = window.ART.manifest;
    const map = m.maps['map.riverside'];
    return {
      size: map.size,
      entities: map.entities.length,
      sprites: s.children.list.filter((o) => o.type === 'Sprite').length,
      solids: s.solid.getChildren().length,
      blocked: s.blocked.size,
      wanderers: s.wanderers.length,
      interactables: s.interactables.length,
      heroTile: [Math.floor(s.hero.x / s.ts), Math.floor(s.hero.y / s.ts)],
      worldBounds: [s.physics.world.bounds.width, s.physics.world.bounds.height],
      props: Object.keys(m.props).length,
      atlases: Object.keys(m.atlases),
    };
  });

  const [cols, rows] = report.size;
  const checks = [
    ['no console errors', problems.length === 0, problems.join(' | ')],
    ['world matches the map', report.worldBounds[0] === cols * 16
      && report.worldBounds[1] === rows * 16, JSON.stringify(report.worldBounds)],
    ['every entity spawned', report.sprites === report.entities + 1,
      `${report.sprites} sprites vs ${report.entities} entities + hero`],
    ['collision tiles claimed', report.blocked >= report.entities,
      `${report.blocked} blocked tiles`],
    ['one body per blocked tile', report.solids === report.blocked,
      `${report.solids} bodies vs ${report.blocked} tiles`],
    ['livestock is wandering', report.wanderers > 0, `${report.wanderers}`],
  ];

  if (TALK) {
    await page.keyboard.press('KeyE');
    await page.waitForTimeout(250);
    const talking = await page.evaluate(() =>
      document.getElementById('dialogue').classList.contains('show'));
    checks.push(['dialogue opened', talking, 'nothing in range to talk to?']);
  }

  // --- the picture -----------------------------------------------------------
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  if (MAP_MODE) {
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
    }), [cols * 16, rows * 16]);
    fs.writeFileSync(OUT, Buffer.from(b64.split(',')[1], 'base64'));
  } else {
    await page.locator('.stage').screenshot({ path: OUT });
  }

  await browser.close();

  const failed = checks.filter(([, ok]) => !ok);
  for (const [name, ok, detail] of checks) {
    console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : '   ' + detail}`);
  }
  console.log(`map       ${cols}x${rows} tiles, ${report.entities} entities, `
              + `${report.props} prop definitions, atlases: ${report.atlases.join(', ')}`);
  console.log(`collision ${report.blocked} blocked tiles, `
              + `${report.interactables} things to talk to`);
  console.log(`shot      ${path.relative(ROOT, OUT)}  `
              + `${fs.statSync(OUT).size} B  (hero at ${report.heroTile})`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });

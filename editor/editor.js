/* The map editor.
 *
 * It reads build/manifest.json and the same atlas sheets the game loads, so
 * what you place here is what the game draws - there is no second description
 * of the world anywhere. Terrain edges resolve live using the mask table the
 * build exported, by the same rules pipeline/autotile.py applies, so the
 * preview is the build's own answer rather than an approximation.
 *
 * It writes content/maps/<name>.json: plain ASCII rows, a legend, a spawn and
 * a list of entities. Nothing editor-specific is stored in the map, so a map
 * made here is indistinguishable from one written by hand.
 */

const $ = (id) => document.getElementById(id);

// Neighbour bits, clockwise from north - the order tools/gen/tiles.py uses.
const N = 1, NE = 2, E = 4, SE = 8, S = 16, SW = 32, W = 64, NW = 128;
const NEIGHBOURS = [[N, 0, -1], [NE, 1, -1], [E, 1, 0], [SE, 1, 1],
                    [S, 0, 1], [SW, -1, 1], [W, -1, 0], [NW, -1, -1]];

/** A diagonal only matters when both cardinals beside it are set. */
function canonical(mask) {
  if (!((mask & N) && (mask & E))) mask &= ~NE;
  if (!((mask & E) && (mask & S))) mask &= ~SE;
  if (!((mask & S) && (mask & W))) mask &= ~SW;
  if (!((mask & W) && (mask & N))) mask &= ~NW;
  return mask & 255;
}

// Must match pipeline/autotile.pick_variant exactly, including Python's
// arbitrary-precision arithmetic - hence BigInt, memoised per cell.
const variantCache = new Map();
function pickVariant(x, y, n) {
  if (n <= 1) return 0;
  const key = `${x},${y},${n}`;
  let v = variantCache.get(key);
  if (v === undefined) {
    const h = (BigInt(x) * 73856093n) ^ (BigInt(y) * 19349663n) ^ 0x2F6Bn;
    v = Number(h % BigInt(n));
    variantCache.set(key, v);
  }
  return v;
}

const CHARS = ".,p~#tdabcefghijklmnoqrsuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

const state = {
  M: null,            // the manifest
  images: {},         // atlas name -> Image
  map: null,          // the map being edited
  mapName: "",
  tool: "paint",
  brush: 1,
  zoom: 2,
  grid: true,
  terrain: null,      // selected tile id
  object: null,       // selected definition id
  hover: null,
  undo: [],
  dirty: false,
};

// ---------------------------------------------------------------- loading --
async function loadJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function loadImage(src) {
  return new Promise((res, rej) => {
    const i = new Image();
    i.onload = () => res(i);
    i.onerror = () => rej(new Error(`could not load ${src}`));
    i.src = src;
  });
}

async function boot() {
  try {
    state.M = await loadJSON("/build/manifest.json");
  } catch (e) {
    return message("no build/manifest.json - run python tools/build.py", true);
  }
  const atlases = state.M.atlases;
  await Promise.all(Object.entries(atlases).map(async ([name, meta]) => {
    const src = meta.image.startsWith("atlases/") ? `/assets/${meta.image}`
                                                  : `/assets/atlases/${name}.png`;
    state.images[name] = await loadImage(src);
  }));

  const { maps } = await loadJSON("/api/maps");
  const sel = $("mapSel");
  sel.replaceChildren(...maps.map((m) => new Option(m, m)));
  sel.onchange = () => openMap(sel.value);

  buildPalettes();
  wire();
  await openMap(maps.includes("riverside") ? "riverside" : maps[0]);
}

async function openMap(name) {
  state.mapName = name;
  state.map = await loadJSON(`/content/maps/${name}.json`);
  $("mapSel").value = name;
  $("mapW").value = state.map.size[0];
  $("mapH").value = state.map.size[1];
  state.undo = [];
  state.dirty = false;
  variantCache.clear();
  render();
  message(`opened ${name}`);
}

// ------------------------------------------------------------- the world --
/** Terrain id at a cell; null off the map. */
function terrainAt(x, y) {
  const m = state.map;
  const [w, h] = m.size;
  if (x < 0 || y < 0 || x >= w || y >= h) return null;
  return m.legend[m.ground[y][x]] || null;
}

function familyOf(tid) {
  const t = state.M.tiles[tid];
  return (t && t.family) || tid;
}

/** The atlas index for a cell, resolved exactly as the build resolves it. */
function indexAt(x, y) {
  const tid = terrainAt(x, y);
  const entry = state.M.tileset.masks[tid];
  const variants = state.M.tileset.variants[tid] || [state.M.tiles[tid].index];
  if (!entry) return variants[pickVariant(x, y, variants.length)];
  const fam = familyOf(tid);
  let mask = 0;
  for (const [bit, dx, dy] of NEIGHBOURS) {
    const n = terrainAt(x + dx, y + dy);
    if (n === null || familyOf(n) === fam) mask |= bit;
  }
  mask = canonical(mask);
  if (mask === 255) return variants[pickVariant(x, y, variants.length)];
  const idx = entry[String(mask)];
  return idx === undefined ? variants[0] : idx;
}

/** Char for a terrain id, adding it to the legend when it is new. */
function charFor(tid) {
  const legend = state.map.legend;
  for (const [ch, id] of Object.entries(legend)) if (id === tid) return ch;
  const used = new Set(Object.keys(legend));
  const ch = [...CHARS].find((c) => !used.has(c));
  if (!ch) throw new Error("ran out of legend characters");
  legend[ch] = tid;
  return ch;
}

function defOf(id) {
  const M = state.M;
  return M.props[id] || M.actors[id] || M.items[id] || null;
}

function footprintOf(id) {
  const d = defOf(id);
  return (d && d.footprint && d.footprint.length) ? d.footprint : [[0, 0]];
}

function blocksOf(id) {
  const d = defOf(id);
  return !!(d && d.blocks);
}

/** The sprite record to draw for a definition - actors show their idle frame.
 *  Cached: this is called for every entity on every repaint. */
const spriteCache = new Map();
let byAtlasIndex = null;

function spriteFor(id) {
  if (spriteCache.has(id)) return spriteCache.get(id);
  const M = state.M;
  const d = defOf(id);
  let rec = null;
  if (d && M.actors[id]) {
    const anim = M.anims[`${d.sprite}/idle/${d.facing || "down"}`]
              || M.anims[`${d.sprite}/idle/down`];
    if (anim) {
      if (!byAtlasIndex) {
        byAtlasIndex = new Map();
        for (const r of Object.values(M.sprites)) byAtlasIndex.set(`${r.atlas}:${r.index}`, r);
      }
      rec = byAtlasIndex.get(`${anim.atlas}:${anim.frames[0]}`) || null;
    }
  } else if (d) {
    rec = M.sprites[d.sprite] || null;
  }
  spriteCache.set(id, rec);
  return rec;
}

// ------------------------------------------------------------- rendering --
function drawSprite(ctx, rec, cx, cy, z) {
  const meta = state.M.atlases[rec.atlas];
  const [fw, fh] = meta.frame;
  const sx = (rec.index % meta.cols) * fw;
  const sy = Math.floor(rec.index / meta.cols) * fh;
  const [ax, ay] = rec.anchor;
  ctx.drawImage(state.images[rec.atlas], sx, sy, fw, fh,
                Math.round((cx - ax) * z), Math.round((cy - ay) * z),
                fw * z, fh * z);
}

function render() {
  const m = state.map;
  if (!m) return;
  const [w, h] = m.size;
  const ts = m.tile_size;
  const z = state.zoom;
  const cv = $("view");
  cv.width = w * ts * z;
  cv.height = h * ts * z;
  const ctx = cv.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, cv.width, cv.height);

  const tiles = state.M.atlases.tiles;
  const [tw, th] = tiles.frame;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = indexAt(x, y);
      ctx.drawImage(state.images.tiles,
                    (i % tiles.cols) * tw, Math.floor(i / tiles.cols) * th, tw, th,
                    x * ts * z, y * ts * z, ts * z, ts * z);
    }
  }

  // Entities in the order the game draws them: by the y their anchor sits on.
  const ents = [...m.entities].sort((a, b) => a.tile[1] - b.tile[1]);
  for (const e of ents) {
    const rec = spriteFor(e.def);
    if (!rec) continue;
    drawSprite(ctx, rec, e.tile[0] * ts + ts / 2, e.tile[1] * ts + ts / 2, z);
  }

  if (state.grid) {
    ctx.strokeStyle = "rgba(255,255,255,.07)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x <= w; x++) { ctx.moveTo(x * ts * z + .5, 0); ctx.lineTo(x * ts * z + .5, cv.height); }
    for (let y = 0; y <= h; y++) { ctx.moveTo(0, y * ts * z + .5); ctx.lineTo(cv.width, y * ts * z + .5); }
    ctx.stroke();
  }

  // Footprints of solid things, so blocked ground is visible while editing.
  for (const e of m.entities) {
    if (!blocksOf(e.def)) continue;
    ctx.fillStyle = "rgba(224,106,90,.20)";
    for (const [dx, dy] of footprintOf(e.def)) {
      ctx.fillRect((e.tile[0] + dx) * ts * z, (e.tile[1] + dy) * ts * z, ts * z, ts * z);
    }
  }

  const sp = m.spawn && m.spawn.tile;
  if (sp) {
    // Rose, not the old green: the map is green from edge to edge now, and a
    // green spawn marker sat on the grass it was meant to be pointing at.
    ctx.strokeStyle = "#e5c2c0";
    ctx.lineWidth = 2;
    ctx.strokeRect(sp[0] * ts * z + 1, sp[1] * ts * z + 1, ts * z - 2, ts * z - 2);
  }

  if (state.hover) {
    const [hx, hy] = state.hover;
    const n = state.tool === "paint" ? state.brush : 1;
    const o = Math.floor((n - 1) / 2);
    ctx.strokeStyle = "rgba(255,255,255,.55)";
    ctx.lineWidth = 1;
    ctx.strokeRect((hx - o) * ts * z + .5, (hy - o) * ts * z + .5, ts * z * n - 1, ts * z * n - 1);
  }
  updateStatus();
}

function updateStatus() {
  const m = state.map;
  $("st-count").textContent = `${m.entities.length}${state.dirty ? " *" : ""}`;
  if (!state.hover) { $("st-tile").textContent = "-"; return; }
  const [x, y] = state.hover;
  $("st-tile").textContent = `${x},${y}`;
  $("st-terrain").textContent = terrainAt(x, y) || "-";
  const here = m.entities.filter((e) => footprintOf(e.def)
    .some(([dx, dy]) => e.tile[0] + dx === x && e.tile[1] + dy === y));
  $("st-objects").textContent = here.length ? here.map((e) => e.def).join(", ") : "-";
}

// -------------------------------------------------------------- palettes --
function swatchCanvas(rec, size) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const meta = state.M.atlases[rec.atlas];
  const [fw, fh] = meta.frame;
  ctx.drawImage(state.images[rec.atlas],
                (rec.index % meta.cols) * fw, Math.floor(rec.index / meta.cols) * fh,
                fw, fh, 0, 0, size, size);
  return c;
}

function buildPalettes() {
  const M = state.M;
  const terrain = $("pal-terrain");
  terrain.replaceChildren();
  for (const [tid, t] of Object.entries(M.tiles)) {
    const el = document.createElement("div");
    el.className = "swatch" + (t.walkable ? "" : " solid");
    el.append(swatchCanvas({ atlas: "tiles", index: t.index }, 48));
    const label = document.createElement("span");
    label.textContent = tid.replace("tile.", "");
    el.append(label);
    el.onclick = () => { state.terrain = tid; setTool("paint"); markSelection(); };
    el.dataset.id = tid;
    terrain.append(el);
  }

  // Objects are grouped by what they are, so the tab is three short lists
  // rather than one wall of fifty icons.
  const objects = $("pal-objects");
  objects.replaceChildren();
  const groups = [["props", M.props], ["actors", M.actors], ["items", M.items]];
  for (const [kind, table] of groups) {
    const ids = Object.keys(table).filter((id) => spriteFor(id));
    if (!ids.length) continue;
    const group = document.createElement("div");
    group.className = "group";
    const head = document.createElement("h3");
    head.append(document.createTextNode(kind));
    const count = document.createElement("em");
    count.textContent = ids.length;
    head.append(count);
    const grid = document.createElement("div");
    grid.className = "palette";
    for (const id of ids) {
      const el = document.createElement("div");
      el.className = "swatch " + (blocksOf(id) ? "solid" : "ground");
      el.append(swatchCanvas(spriteFor(id), 48));
      const label = document.createElement("span");
      label.textContent = id.split(".")[1];
      label.title = `${id} (${kind}, ${blocksOf(id) ? "solid" : "walkable"})`;
      el.append(label);
      el.onclick = () => { state.object = id; setTool("place"); markSelection(); };
      el.dataset.id = id;
      grid.append(el);
    }
    group.append(head, grid);
    objects.append(group);
  }
  state.terrain = Object.keys(M.tiles)[0];
  state.object = Object.keys(M.props)[0];
  markSelection();
}

function markSelection() {
  for (const el of document.querySelectorAll("#pal-terrain .swatch")) {
    el.classList.toggle("on", el.dataset.id === state.terrain);
  }
  for (const el of document.querySelectorAll("#pal-objects .swatch")) {
    el.classList.toggle("on", el.dataset.id === state.object);
  }
}

// ---------------------------------------------------------------- editing --
function snapshot() {
  const m = state.map;
  state.undo.push(JSON.stringify({ ground: m.ground, entities: m.entities,
                                   legend: m.legend, spawn: m.spawn }));
  if (state.undo.length > 60) state.undo.shift();
  state.dirty = true;
}

function undo() {
  const prev = state.undo.pop();
  if (!prev) return message("nothing to undo");
  Object.assign(state.map, JSON.parse(prev));
  render();
  message("undone");
}

function paint(x, y) {
  const m = state.map;
  const [w, h] = m.size;
  const ch = charFor(state.terrain);
  const n = state.brush;
  const o = Math.floor((n - 1) / 2);
  const cells = [];
  let changed = false;
  for (let dy = 0; dy < n; dy++) {
    for (let dx = 0; dx < n; dx++) {
      const px = x - o + dx, py = y - o + dy;
      if (px < 0 || py < 0 || px >= w || py >= h) continue;
      cells.push([px, py]);
      const row = m.ground[py];
      if (row[px] === ch) continue;
      m.ground[py] = row.slice(0, px) + ch + row.slice(px + 1);
      changed = true;
    }
  }
  // Painting water over a wood drowns the trees. Nothing may stand on ground
  // it cannot stand on, and the build's map-footprint gate would refuse the
  // map anyway - better to say so here, while it is still one undo away.
  if (changed && !state.M.tiles[state.terrain].walkable) {
    const drowned = m.entities.filter((e) => footprintOf(e.def)
      .some(([dx, dy]) => cells.some(([cx, cy]) => e.tile[0] + dx === cx && e.tile[1] + dy === cy)));
    if (drowned.length) {
      m.entities = m.entities.filter((e) => !drowned.includes(e));
      message(`${drowned.length} object${drowned.length > 1 ? 's' : ''} removed: `
              + `${[...new Set(drowned.map((e) => e.def))].join(", ")} cannot stand on `
              + `${state.terrain.replace("tile.", "")}`);
    }
  }
  return changed;
}

function place(x, y) {
  const id = state.object;
  const m = state.map;
  const [w, h] = m.size;
  const cells = footprintOf(id).map(([dx, dy]) => [x + dx, y + dy]);
  for (const [cx, cy] of cells) {
    if (cx < 0 || cy < 0 || cx >= w || cy >= h) return message("off the map", true);
    const t = state.M.tiles[terrainAt(cx, cy)];
    if (!t || !t.walkable) return message(`${terrainAt(cx, cy)} is not walkable`, true);
  }
  if (blocksOf(id)) {
    for (const e of m.entities) {
      if (!blocksOf(e.def)) continue;
      for (const [dx, dy] of footprintOf(e.def)) {
        if (cells.some(([cx, cy]) => e.tile[0] + dx === cx && e.tile[1] + dy === cy)) {
          return message(`${e.def} is already there`, true);
        }
      }
    }
  }
  m.entities.push({ def: id, tile: [x, y] });
  return true;
}

function erase(x, y) {
  const m = state.map;
  const before = m.entities.length;
  const hit = m.entities.filter((e) => footprintOf(e.def)
    .some(([dx, dy]) => e.tile[0] + dx === x && e.tile[1] + dy === y));
  if (!hit.length) return false;
  const last = hit[hit.length - 1];          // the most recently placed
  m.entities.splice(m.entities.indexOf(last), 1);
  return m.entities.length !== before;
}

function setSpawn(x, y) {
  const t = state.M.tiles[terrainAt(x, y)];
  if (!t || !t.walkable) return message("spawn must be on walkable ground", true);
  state.map.spawn = { tile: [x, y], facing: (state.map.spawn || {}).facing || "down" };
  return true;
}

function pick(x, y) {
  const here = state.map.entities.filter((e) => footprintOf(e.def)
    .some(([dx, dy]) => e.tile[0] + dx === x && e.tile[1] + dy === y));
  if (here.length) {
    state.object = here[here.length - 1].def;
    setTool("place");
  } else {
    state.terrain = terrainAt(x, y);
    setTool("paint");
  }
  markSelection();
  message(`picked ${here.length ? state.object : state.terrain}`);
}

function applyAt(x, y, button) {
  if (button === 2) {                        // right-click always erases
    snapshot();
    if (!erase(x, y)) state.undo.pop();
    return render();
  }
  snapshot();
  let ok = false;
  if (state.tool === "paint") ok = paint(x, y);
  else if (state.tool === "place") ok = place(x, y) === true;
  else if (state.tool === "erase") ok = erase(x, y);
  else if (state.tool === "spawn") ok = setSpawn(x, y) === true;
  if (!ok) state.undo.pop();
  render();
}

// --------------------------------------------------------------- resizing --
function resize(nw, nh) {
  const m = state.map;
  const [w, h] = m.size;
  if (nw === w && nh === h) return;
  snapshot();
  const fill = charFor(Object.keys(state.M.tiles)[0]);
  const rows = [];
  for (let y = 0; y < nh; y++) {
    const old = y < h ? m.ground[y] : "";
    rows.push((old.slice(0, nw) + fill.repeat(Math.max(0, nw - old.length))));
  }
  m.ground = rows;
  m.size = [nw, nh];
  m.entities = m.entities.filter((e) => e.tile[0] < nw && e.tile[1] < nh);
  if (m.spawn && (m.spawn.tile[0] >= nw || m.spawn.tile[1] >= nh)) m.spawn.tile = [0, 0];
  variantCache.clear();
  render();
  message(`resized to ${nw}x${nh}`);
}

// ------------------------------------------------------------ persistence --
function tidyLegend() {
  const m = state.map;
  const used = new Set(m.ground.join(""));
  const legend = {};
  for (const [ch, id] of Object.entries(m.legend)) if (used.has(ch)) legend[ch] = id;
  m.legend = legend;
}

async function save() {
  tidyLegend();
  const body = {
    id: state.map.id, name: state.map.name, tile_size: state.map.tile_size,
    size: state.map.size, spawn: state.map.spawn, legend: state.map.legend,
    ground: state.map.ground, entities: state.map.entities,
  };
  const r = await fetch(`/api/save?map=${encodeURIComponent(state.mapName)}`, {
    method: "POST", body: JSON.stringify(body),
  });
  const out = await r.json();
  if (!out.ok) return message(out.error || "save failed", true);
  state.dirty = false;
  updateStatus();
  message(`saved ${out.path}`);
  return true;
}

async function saveAndBuild() {
  if (!(await save())) return;
  message("building...");
  const r = await fetch("/api/build", { method: "POST" });
  const out = await r.json();
  const log = $("log");
  log.textContent = out.output;
  log.classList.add("show");
  message(out.ok ? "build passed" : "build FAILED - see the log", !out.ok);
  if (out.ok) {
    state.M = await loadJSON("/build/manifest.json");   // gates may have changed it
  }
}

// ------------------------------------------------------------------ wiring --
function setTool(name) {
  state.tool = name;
  for (const t of ["paint", "place", "erase", "spawn"]) {
    $(`t-${t}`).classList.toggle("on", t === name);
  }
  // Terrain and objects are exclusive: the tool you are holding decides which
  // set is on screen, so the panel never shows a palette you cannot paint with.
  if (name === "paint") showTab(true);
  else if (name === "place") showTab(false);
}

function message(text, bad = false) {
  const el = $("msg");
  el.textContent = text;
  el.classList.toggle("bad", bad);
}

function wire() {
  const cv = $("view");
  let down = false;
  const cellAt = (ev) => {
    const r = cv.getBoundingClientRect();
    const ts = state.map.tile_size * state.zoom;
    return [Math.floor((ev.clientX - r.left) / ts), Math.floor((ev.clientY - r.top) / ts)];
  };
  cv.addEventListener("contextmenu", (e) => e.preventDefault());
  cv.addEventListener("pointerdown", (e) => {
    const [x, y] = cellAt(e);
    if (e.altKey) return pick(x, y);
    down = true;
    try { cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic event */ }
    applyAt(x, y, e.button);
  });
  cv.addEventListener("pointermove", (e) => {
    const [x, y] = cellAt(e);
    const changed = !state.hover || state.hover[0] !== x || state.hover[1] !== y;
    state.hover = [x, y];
    if (down && changed && (state.tool === "paint" || e.buttons === 2)) {
      applyAt(x, y, e.buttons === 2 ? 2 : 0);
    } else if (changed) {
      render();
    }
  });
  cv.addEventListener("pointerup", () => { down = false; });
  cv.addEventListener("pointerleave", () => { state.hover = null; down = false; render(); });

  for (const t of ["paint", "place", "erase", "spawn"]) $(`t-${t}`).onclick = () => setTool(t);
  $("brush").onchange = (e) => { state.brush = Number(e.target.value); render(); };
  $("zoom").onchange = (e) => { state.zoom = Number(e.target.value); render(); };
  $("grid").onchange = (e) => { state.grid = e.target.checked; render(); };
  $("undo").onclick = undo;
  $("save").onclick = save;
  $("build").onclick = saveAndBuild;
  $("resize").onclick = () => resize(Number($("mapW").value), Number($("mapH").value));
  $("tab-terrain").onclick = () => setTool("paint");
  $("tab-objects").onclick = () => setTool("place");

  addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); return undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); return save(); }
    const keys = { p: "paint", o: "place", x: "erase", s: "spawn" };
    if (keys[e.key.toLowerCase()]) setTool(keys[e.key.toLowerCase()]);
  });
  addEventListener("beforeunload", (e) => {
    if (state.dirty) { e.preventDefault(); e.returnValue = ""; }
  });
}

function showTab(terrain) {
  $("pal-terrain").hidden = !terrain;
  $("pal-objects").hidden = terrain;
  $("tab-terrain").classList.toggle("on", terrain);
  $("tab-objects").classList.toggle("on", !terrain);
}

// Exposed deliberately: the browser console and tools/editor_test.cjs drive
// the editor through these, so the test exercises the editor itself rather
// than a copy of its logic. (A top-level `const` in a classic script is not a
// window property, hence the explicit handle.)
Object.assign(window, {
  editor: state, openMap, terrainAt, indexAt, paint, place, erase, applyAt,
  snapshot, undo, save, setTool, showTab, render,
});

boot().catch((e) => message(String(e.message || e), true));

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
  view: "map",        // "map" edits one, "world" shows how they join
  world: null,        // every map's content, once the world view has read it
  layout: null,       // where the world view put each map
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
  // Whichever map comes first, rather than one named here: the name that used
  // to be hardcoded outlived the map it pointed at.
  await openMap(maps[0]);
  // The gates are a property of every map together, not of the open one, so
  // they are read once up front - the tile view colours and numbers its
  // mouths the same way the atlas does.
  try { await refreshWorld(); render(); } catch (e) { message(String(e.message || e), true); }
}

async function openMap(name) {
  state.mapName = name;
  state.map = await loadJSON(`/content/maps/${name}.json`);
  $("mapSel").value = name;
  $("mapW").value = state.map.size[0];
  $("mapH").value = state.map.size[1];
  $("mapName").value = state.map.name || "";
  state.undo = [];
  state.dirty = false;
  variantCache.clear();
  render();
  message(`opened ${name}`);
}

// ------------------------------------------------------------- the world --
/** Terrain id at a cell; null off the map. */
function terrainAt(x, y, m = state.map) {
  const [w, h] = m.size;
  if (x < 0 || y < 0 || x >= w || y >= h) return null;
  return m.legend[m.ground[y][x]] || null;
}

function familyOf(tid) {
  const t = state.M.tiles[tid];
  return (t && t.family) || tid;
}

/** The atlas index for a cell, resolved exactly as the build resolves it. */
function indexAt(x, y, m = state.map) {
  const tid = terrainAt(x, y, m);
  const entry = state.M.tileset.masks[tid];
  const variants = state.M.tileset.variants[tid] || [state.M.tiles[tid].index];
  if (!entry) return variants[pickVariant(x, y, variants.length)];
  const fam = familyOf(tid);
  let mask = 0;
  for (const [bit, dx, dy] of NEIGHBOURS) {
    const n = terrainAt(x + dx, y + dy, m);
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

/** Whether placing this puts something the player can pick up on the ground.
 *  The game decides this by where the definition comes from - an item becomes
 *  a pickup, a prop or an actor never does, however much it looks like loot -
 *  so the editor reads the same fact rather than keeping its own list. */
function gatherableOf(id) {
  return !!(state.M.items && state.M.items[id]);
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

  // Anything the player can pick up gets a ring. A dropped apple and a
  // painted flower pot are both just sprites on the ground otherwise, and
  // only one of them ends up in the bag.
  for (const e of m.entities) {
    if (!gatherableOf(e.def)) continue;
    ctx.strokeStyle = "#e0c341";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc((e.tile[0] + .5) * ts * z, (e.tile[1] + .5) * ts * z,
            ts * z * .42, 0, Math.PI * 2);
    ctx.stroke();
  }

  // The mouths of this map's gates, in the colour and number the world view
  // gives them. Over the footprints, because standing in one is the whole
  // point of the tile.
  (m.exits || []).forEach((ex, i) => {
    const gate = gateFor(m.id, i);
    const colour = gate ? gate.colour : "#6cc0e0";
    const cell = ts * z;
    ctx.fillStyle = colour + "4d";
    for (const [tx, ty] of ex.tiles) ctx.fillRect(tx * cell, ty * cell, cell, cell);
    ctx.strokeStyle = colour;
    ctx.lineWidth = 1;
    for (const [tx, ty] of ex.tiles) {
      ctx.strokeRect(tx * cell + .5, ty * cell + .5, cell - 1, cell - 1);
    }
    // An arrow per tile, pointing the way you leave - which is the thing that
    // was wrong in the content and invisible until it was drawn.
    const edge = edgeOf(m, ex.tiles);
    const step = { west: [-1, 0], east: [1, 0], north: [0, -1], south: [0, 1] }[edge];
    if (step) {
      ctx.fillStyle = colour;
      for (const [tx, ty] of ex.tiles) {
        const cx = tx * cell + cell / 2 + step[0] * cell * .22;
        const cy = ty * cell + cell / 2 + step[1] * cell * .22;
        arrowHead(ctx, cx, cy, step[0], step[1], cell * .3);
      }
    }
    const [lx, ly] = ex.tiles[Math.floor(ex.tiles.length / 2)];
    const to = (state.M.maps[ex.to] && state.M.maps[ex.to].name) || ex.to;
    const label = gate ? `${gate.n}  ${to}` : to;
    ctx.font = "600 11px ui-monospace, Consolas, monospace";
    const wid = ctx.measureText(label).width + 10;
    const lift = edge === "east" ? -wid - 3 : cell + 3;
    ctx.fillStyle = "rgba(14,16,21,.85)";
    ctx.fillRect(lx * cell + lift, ly * cell, wid, 14);
    ctx.fillStyle = colour;
    ctx.fillText(label, lx * cell + lift + 5, ly * cell + 11);
  });

  // And where this map's own arrivals land, so both ends of a crossing are
  // visible without leaving the map you are editing.
  for (const { map: other } of (state.world ? state.world.byId.values() : [])) {
    (other.exits || []).forEach((ex, i) => {
      if (ex.to !== m.id) return;
      const gate = gateFor(other.id, i);
      const colour = gate ? gate.colour : "#6cc0e0";
      const cell = ts * z;
      for (const [ax, ay] of arrivalsOf(ex) || []) {
        ctx.strokeStyle = colour;
        ctx.setLineDash([3, 2]);
        ctx.lineWidth = 1;
        ctx.strokeRect(ax * cell + 2.5, ay * cell + 2.5, cell - 5, cell - 5);
        ctx.setLineDash([]);
      }
    });
  }

  const sp = m.spawn && m.spawn.tile;
  if (sp) {
    ctx.strokeStyle = "#74c46b";
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
  $("st-objects").textContent = here.length
    ? here.map((e) => e.def + (gatherableOf(e.def) ? " (gatherable)"
        : blocksOf(e.def) ? " (solid)" : "")).join(", ")
    : "-";
  let said = "";
  (m.exits || []).forEach((ex, i) => {
    if (!ex.tiles.some(([tx, ty]) => tx === x && ty === y)) return;
    const g = gateFor(m.id, i);
    const arrivals = arrivalsOf(ex) || [];
    const k = ex.tiles.findIndex(([tx, ty]) => tx === x && ty === y);
    const land = arrivals[k] || arrivals[0];
    said = `gate ${g ? g.n : "?"} to ${ex.to}`
         + (land ? ` at ${land[0]},${land[1]} facing ${ex.facing || "-"}` : "");
  });
  $("st-world").textContent = said;
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
      // Three states, not two: solid, walkable scenery, or something that
      // leaves the ground and goes in the bag.
      const gather = gatherableOf(id);
      const el = document.createElement("div");
      el.className = "swatch " + (gather ? "gather" : blocksOf(id) ? "solid" : "ground");
      el.append(swatchCanvas(spriteFor(id), 48));
      const label = document.createElement("span");
      label.textContent = id.split(".")[1];
      const d = defOf(id);
      label.title = `${id} (${kind}, `
        + (gather ? `gatherable${d && d.kind ? " " + d.kind : ""}`
                  : blocksOf(id) ? "solid" : "walkable")
        + ")";
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
  const m = state.map;
  // Named field by field so a save writes the plain format rather than
  // whatever the editor hung off the object - but anything the editor does
  // not understand has to survive the round trip, or opening a map and
  // pressing save quietly deletes it. `exits` was the first of those: the
  // gates treat them as optional, so wiping them disconnected the world
  // without failing a single check.
  const body = {
    id: m.id, name: m.name, tile_size: m.tile_size,
    size: m.size, spawn: m.spawn, legend: m.legend,
    ground: m.ground, entities: m.entities,
  };
  const KNOWN = new Set([...Object.keys(body), "exits"]);
  if (m.exits) body.exits = m.exits;
  for (const [k, v] of Object.entries(m)) if (!KNOWN.has(k)) body[k] = v;
  const r = await fetch(`/api/save?map=${encodeURIComponent(state.mapName)}`, {
    method: "POST", body: JSON.stringify(body),
  });
  const out = await r.json();
  if (!out.ok) return message(out.error || "save failed", true);
  state.dirty = false;
  updateStatus();
  message(`saved ${out.path}`);
  try { await refreshWorld(); } catch (e) { /* the atlas can wait */ }
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

// --------------------------------------------------------- the world map --
// Maps do not carry a world position - only doorways, which say "my west edge
// leads to that map, and you come in over there". That is enough to place them:
// follow the doorways and each map lands against the one it joins, aligned on
// the row the player crosses. So this is not a diagram drawn beside the
// content, it is the shape the content already has.

// Leaving by the west edge means walking left, so left is the way you should
// still be looking when you arrive.
const EDGE_FACING = { west: "left", east: "right", north: "up", south: "down" };
const WORLD_GUTTER = 3;      // tiles between two worlds that do not join
const WORLD_PAD = 16;        // px of margin around the whole atlas

/** Px per tile on the atlas. Coarser than the tile view - a whole world has
 *  to fit - but not so coarse that a 20-wide map is a postage stamp. */
function worldScale() { return 2 + state.zoom * 4; }

/** Which edge of `m` a doorway lies on, or null if it sits inland. */
function edgeOf(m, tiles) {
  const [w, h] = m.size;
  if (tiles.every(([x]) => x === 0)) return "west";
  if (tiles.every(([x]) => x === w - 1)) return "east";
  if (tiles.every(([, y]) => y === 0)) return "north";
  if (tiles.every(([, y]) => y === h - 1)) return "south";
  return null;
}

/** Where each doorway tile puts you down. One arrival, or one per tile. */
function arrivalsOf(ex) {
  if (ex.spawns) return ex.spawns;
  if (ex.spawn) return ex.tiles.map(() => ex.spawn);
  return null;
}

/** Every map's content. The open one comes from memory, so unsaved edits show. */
async function loadWorld() {
  const { maps } = await loadJSON("/api/maps");
  const entries = await Promise.all(maps.map(async (name) => ({
    name,
    map: name === state.mapName ? state.map
                                : await loadJSON(`/content/maps/${name}.json`),
  })));
  const byId = new Map(entries.map((e) => [e.map.id, e]));
  state.world = { entries, byId };
  return state.world;
}

/** Maps that reach each other, in either direction, belong on one atlas. */
function componentsOf(byId) {
  const adj = new Map([...byId.keys()].map((id) => [id, new Set()]));
  for (const { map } of byId.values()) {
    for (const ex of map.exits || []) {
      if (!byId.has(ex.to)) continue;
      adj.get(map.id).add(ex.to);
      adj.get(ex.to).add(map.id);
    }
  }
  const seen = new Set();
  const out = [];
  for (const id of adj.keys()) {
    if (seen.has(id)) continue;
    const comp = [];
    const queue = [id];
    seen.add(id);
    while (queue.length) {
      const n = queue.shift();
      comp.push(n);
      for (const nb of adj.get(n)) if (!seen.has(nb)) { seen.add(nb); queue.push(nb); }
    }
    out.push(comp);
  }
  return out;
}

/** Where a doorway puts the map on the far side, in tile space.
 *  Forward: `here` is placed and the destination hangs off its edge.
 *  Inverted: the destination is placed and `here` is the one being hung, which
 *  is how a map reached only by a doorway pointing at it gets positioned. */
function placeAcross(here, ex, destMap, invert) {
  const edge = edgeOf(here.map, ex.tiles);
  const arrivals = arrivalsOf(ex);
  if (!edge || !arrivals) return null;
  const [tx, ty] = ex.tiles[0];
  const [sx, sy] = arrivals[0];
  const [hw, hh] = here.map.size;
  const [dw, dh] = destMap.size;
  if (!invert) {
    if (edge === "west") return { ox: here.ox - dw, oy: here.oy + ty - sy };
    if (edge === "east") return { ox: here.ox + hw, oy: here.oy + ty - sy };
    if (edge === "north") return { ox: here.ox + tx - sx, oy: here.oy - dh };
    return { ox: here.ox + tx - sx, oy: here.oy + hh };
  }
  if (edge === "west") return { ox: here.ox + dw, oy: here.oy + sy - ty };
  if (edge === "east") return { ox: here.ox - hw, oy: here.oy + sy - ty };
  if (edge === "north") return { ox: here.ox + sx - tx, oy: here.oy + dh };
  return { ox: here.ox + sx - tx, oy: here.oy - hh };
}

/** Lay every map out, one atlas per connected group, stacked down the canvas. */
function layoutWorld() {
  const { byId } = state.world;
  const openId = state.map && state.map.id;
  const comps = componentsOf(byId).sort((a, b) => {
    const ai = a.includes(openId) ? 0 : 1;
    const bi = b.includes(openId) ? 0 : 1;
    return ai - bi || String(a[0]).localeCompare(String(b[0]));
  });

  const placed = new Map();
  const loose = [];
  let cursorY = 0;

  for (const comp of comps) {
    const local = new Map();
    const root = comp.includes(openId) ? openId : [...comp].sort()[0];
    local.set(root, { ...byId.get(root), ox: 0, oy: 0 });

    // Follow doorways out of what is placed, and pull in anything reachable
    // only by a doorway pointing at it, until nothing moves.
    for (let progress = true; progress; ) {
      progress = false;
      for (const id of comp) {
        const entry = byId.get(id);
        for (const ex of entry.map.exits || []) {
          if (!byId.has(ex.to)) continue;
          const mine = local.get(id);
          const theirs = local.get(ex.to);
          if (mine && !theirs) {
            const at = placeAcross(mine, ex, byId.get(ex.to).map, false);
            if (at) { local.set(ex.to, { ...byId.get(ex.to), ...at }); progress = true; }
          } else if (theirs && !mine) {
            const at = placeAcross(theirs, ex, entry.map, true);
            if (at) { local.set(id, { ...entry, ...at }); progress = true; }
          }
        }
      }
    }

    // A doorway that sits inland has no shared edge to show, so it is drawn
    // as an arrow instead of a seam.
    for (const id of comp) {
      for (const ex of byId.get(id).map.exits || []) {
        if (!byId.has(ex.to)) continue;
        if (!edgeOf(byId.get(id).map, ex.tiles) || !arrivalsOf(ex)) {
          loose.push({ from: id, to: ex.to, ex });
        }
      }
    }
    // Anything in the group with no placeable link still has to go somewhere.
    let spare = 0;
    for (const id of comp) {
      if (local.has(id)) continue;
      const e = byId.get(id);
      local.set(id, { ...e, ox: (spare++) * (e.map.size[0] + WORLD_GUTTER),
                      oy: -e.map.size[1] - WORLD_GUTTER });
    }

    let minX = Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of local.values()) {
      minX = Math.min(minX, p.ox);
      minY = Math.min(minY, p.oy);
      maxY = Math.max(maxY, p.oy + p.map.size[1]);
    }
    for (const [id, p] of local) {
      placed.set(id, { ...p, ox: p.ox - minX, oy: p.oy - minY + cursorY });
    }
    cursorY += (maxY - minY) + WORLD_GUTTER * 2;
  }
  return { placed, loose, groups: comps.length };
}

/** What is worth saying about how the maps join up. */
function worldNotes() {
  const { byId } = state.world;
  const notes = [];
  const nameOf = (id) => (byId.has(id) ? byId.get(id).map.name || id : id);
  const leadsTo = (id) => [...byId.values()].filter(
    (e) => e.map.id !== id && (e.map.exits || []).some((x) => x.to === id));

  for (const { map } of byId.values()) {
    const out = map.exits || [];
    if (!out.length && !leadsTo(map.id).length) {
      notes.push({ bad: true, html: `<b>${map.name || map.id}</b> joins nothing. `
        + "It loads, but no doorway reaches it, so the player cannot walk there." });
      continue;
    }
    for (const ex of out) {
      if (!byId.has(ex.to)) {
        notes.push({ bad: true, html: `<b>${map.name}</b> has a doorway to `
          + `<b>${ex.to}</b>, which is not a map here.` });
        continue;
      }
      if (!(byId.get(ex.to).map.exits || []).some((b) => b.to === map.id)) {
        notes.push({ bad: true, html: `<b>${map.name}</b> leads to `
          + `<b>${nameOf(ex.to)}</b>, but nothing leads back - a one-way trip.` });
      }
      const edge = edgeOf(map, ex.tiles);
      if (!edge) {
        notes.push({ bad: false, html: `<b>${map.name}</b> has an inland doorway to `
          + `<b>${nameOf(ex.to)}</b> - drawn as an arrow, since it is not a seam.` });
      } else if (ex.facing && ex.facing !== EDGE_FACING[edge]) {
        notes.push({ bad: true, html: `<b>${map.name}</b> leaves by its ${edge} edge, `
          + `so the player is walking ${EDGE_FACING[edge]} - but they arrive on `
          + `<b>${nameOf(ex.to)}</b> facing ${ex.facing}, turned around.` });
      }
    }
  }
  if (!notes.length) {
    notes.push({ bad: false, html: "Every map joins up both ways, and every "
      + "crossing leaves the player pointed the way they were walking." });
  }
  return notes;
}

// A gate is one way through between two maps. Each side has a mouth - a run of
// doorway tiles - and the two mouths are what has to be read together, so they
// are given one colour and one number wherever they are drawn.
const GATE_COLOURS = ["#6cc0e0", "#e0a340", "#b98ce0", "#6ad7b0", "#e8788f", "#c9d05f"];

function gatesOf() {
  const { byId } = state.world;
  const used = new Set();
  const gates = [];
  for (const { map } of byId.values()) {
    (map.exits || []).forEach((ex, i) => {
      if (used.has(`${map.id}#${i}`)) return;
      const dest = byId.get(ex.to);
      let partner = null;
      if (dest) {
        const arrivals = arrivalsOf(ex) || [];
        let best = Infinity;
        (dest.map.exits || []).forEach((b, j) => {
          if (b.to !== map.id || used.has(`${dest.map.id}#${j}`)) return;
          // The far mouth is the one nearest where this one puts you down.
          // Two gates between the same pair of maps stay told apart that way.
          let d = Infinity;
          for (const a of arrivals) {
            for (const t of b.tiles) {
              d = Math.min(d, Math.max(Math.abs(a[0] - t[0]), Math.abs(a[1] - t[1])));
            }
          }
          if (d < best) { best = d; partner = { id: dest.map.id, index: j, ex: b }; }
        });
      }
      used.add(`${map.id}#${i}`);
      if (partner) used.add(`${partner.id}#${partner.index}`);
      gates.push({
        n: gates.length + 1,
        colour: GATE_COLOURS[gates.length % GATE_COLOURS.length],
        from: map.id, index: i, ex, to: ex.to, partner,
        edge: edgeOf(map, ex.tiles), oneWay: !partner,
      });
    });
  }
  state.gates = gates;
  state.gateBy = new Map();
  for (const g of gates) {
    state.gateBy.set(`${g.from}#${g.index}`, g);
    if (g.partner) state.gateBy.set(`${g.partner.id}#${g.partner.index}`, g);
  }
  return gates;
}

/** Read every map and work out the gates. Cheap enough to do on any change. */
async function refreshWorld() {
  await loadWorld();
  gatesOf();
}

/** The gate a given exit belongs to, or null before the world has been read. */
function gateFor(mapId, i) {
  return (state.gateBy && state.gateBy.get(`${mapId}#${i}`)) || null;
}

function arrowHead(ctx, x, y, dx, dy, size) {
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x - ux * size - uy * size * .55, y - uy * size + ux * size * .55);
  ctx.lineTo(x - ux * size + uy * size * .55, y - uy * size - ux * size * .55);
  ctx.closePath();
  ctx.fill();
}

/** A number in a filled disc - the key that ties a mouth to the gate list. */
function gateBadge(ctx, x, y, n, colour, r) {
  ctx.fillStyle = colour;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#11141c";
  ctx.font = `700 ${Math.round(r * 1.5)}px ui-monospace, Consolas, monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(n), x, y + .5);
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function renderWorld() {
  const layout = state.layout = layoutWorld();
  const z = worldScale();
  const cv = $("world");
  const ctx = cv.getContext("2d");
  const tiles = state.M.atlases.tiles;
  const [tw, th] = tiles.frame;

  let maxX = 0, maxY = 0;
  for (const p of layout.placed.values()) {
    maxX = Math.max(maxX, p.ox + p.map.size[0]);
    maxY = Math.max(maxY, p.oy + p.map.size[1]);
  }
  cv.width = maxX * z + WORLD_PAD * 2;
  cv.height = maxY * z + WORLD_PAD * 2;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#0e1015";
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.translate(WORLD_PAD, WORLD_PAD);

  for (const [id, p] of layout.placed) {
    const [w, h] = p.map.size;
    const px = p.ox * z;
    const py = p.oy * z;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = indexAt(x, y, p.map);
        ctx.drawImage(state.images.tiles,
                      (i % tiles.cols) * tw, Math.floor(i / tiles.cols) * th, tw, th,
                      px + x * z, py + y * z, z, z);
      }
    }
    // Solid things as a wash - enough to tell a village from an open fell.
    ctx.fillStyle = "rgba(20,24,33,.34)";
    for (const e of p.map.entities || []) {
      if (!blocksOf(e.def)) continue;
      for (const [dx, dy] of footprintOf(e.def)) {
        ctx.fillRect(px + (e.tile[0] + dx) * z, py + (e.tile[1] + dy) * z, z, z);
      }
    }
    // And where the loot is, which is worth seeing across a whole world.
    ctx.fillStyle = "#e0c341";
    for (const e of p.map.entities || []) {
      if (!gatherableOf(e.def)) continue;
      ctx.fillRect(px + e.tile[0] * z + z * .3, py + e.tile[1] * z + z * .3,
                   Math.max(2, z * .4), Math.max(2, z * .4));
    }
    (p.map.exits || []).forEach((ex, i) => {
      const gate = gateFor(id, i);
      ctx.fillStyle = (gate ? gate.colour : "#6cc0e0") + "99";
      for (const [tx, ty] of ex.tiles) ctx.fillRect(px + tx * z, py + ty * z, z, z);
      // Where this mouth puts you down, on whichever map that is. Ticked
      // rather than filled, so a mouth and an arrival never look alike.
      const dst = layout.placed.get(ex.to);
      const arrivals = arrivalsOf(ex);
      if (dst && arrivals) {
        ctx.fillStyle = (gate ? gate.colour : "#6cc0e0") + "55";
        for (const [ax, ay] of arrivals) {
          ctx.fillRect((dst.ox + ax) * z + z * .3, (dst.oy + ay) * z + z * .3, z * .4, z * .4);
        }
      }
    });

    const open = id === (state.map && state.map.id);
    ctx.strokeStyle = open ? "#74c46b" : "#55607a";
    ctx.lineWidth = open ? 2 : 1;
    ctx.strokeRect(px + .5, py + .5, w * z - 1, h * z - 1);

    if (p.map.spawn && p.map.spawn.tile) {
      const [sx, sy] = p.map.spawn.tile;
      ctx.fillStyle = "#74c46b";
      ctx.beginPath();
      ctx.arc(px + sx * z + z / 2, py + sy * z + z / 2, Math.max(3, z * .7), 0, Math.PI * 2);
      ctx.fill();
    }

    // The plate sits inside the map and is clipped to it. Above the map it
    // would collide with the neighbour's, since maps are drawn edge to edge.
    const label = `${p.map.name || id}  ${w}x${h}`;
    ctx.save();
    ctx.beginPath();
    ctx.rect(px, py, w * z, h * z);
    ctx.clip();
    ctx.font = "600 11px ui-monospace, Consolas, monospace";
    ctx.fillStyle = "rgba(14,16,21,.82)";
    ctx.fillRect(px + 1, py + 1, Math.min(ctx.measureText(label).width + 10, w * z - 2), 15);
    ctx.fillStyle = open ? "#d8f2cf" : "#e8e4da";
    ctx.fillText(label, px + 6, py + 12);
    ctx.restore();
  }

  // The gates themselves, over the maps: which way you travel, and the number
  // that ties each mouth to the list in the panel.
  for (const g of state.gates || []) {
    const a = layout.placed.get(g.from);
    const dst = layout.placed.get(g.to);
    const arrivals = arrivalsOf(g.ex);
    if (!a) continue;
    const mid = g.ex.tiles[Math.floor(g.ex.tiles.length / 2)];
    const mx = (a.ox + mid[0]) * z + z / 2;
    const my = (a.oy + mid[1]) * z + z / 2;
    if (dst && arrivals) {
      const land = arrivals[Math.floor(arrivals.length / 2)];
      const lx = (dst.ox + land[0]) * z + z / 2;
      const ly = (dst.oy + land[1]) * z + z / 2;
      ctx.strokeStyle = g.colour;
      ctx.fillStyle = g.colour;
      ctx.lineWidth = 2;
      if (g.oneWay) ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(mx, my);
      ctx.lineTo(lx, ly);
      ctx.stroke();
      ctx.setLineDash([]);
      arrowHead(ctx, lx, ly, lx - mx, ly - my, Math.max(5, z * .8));
    }
    gateBadge(ctx, mx, my, g.n, g.colour, Math.max(7, z * .75));
  }

  // Inland doorways: no shared edge to read, so draw the hop.
  for (const link of layout.loose) {
    const a = layout.placed.get(link.from);
    const b = layout.placed.get(link.to);
    if (!a || !b) continue;
    const [tx, ty] = link.ex.tiles[0];
    const x1 = (a.ox + tx) * z + z / 2;
    const y1 = (a.oy + ty) * z + z / 2;
    const x2 = (b.ox + b.map.size[0] / 2) * z;
    const y2 = (b.oy + b.map.size[1] / 2) * z;
    ctx.strokeStyle = "#6cc0e0";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#6cc0e0";
    ctx.beginPath();
    ctx.arc(x1, y1, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);

  buildWorldPanel();
  const n = layout.placed.size;
  $("st-world").textContent = `${n} map${n === 1 ? "" : "s"} in `
    + `${layout.groups} world${layout.groups === 1 ? "" : "s"}`;
}

/** Which map a point on the world canvas lands in. */
function mapAtWorld(px, py) {
  if (!state.layout) return null;
  const z = worldScale();
  const x = (px - WORLD_PAD) / z;
  const y = (py - WORLD_PAD) / z;
  for (const [id, p] of state.layout.placed) {
    if (x >= p.ox && y >= p.oy && x < p.ox + p.map.size[0] && y < p.oy + p.map.size[1]) {
      return { id, ...p };
    }
  }
  return null;
}

/** Where on the atlas a map's middle is. Exposed so a test can click it
 *  without knowing how the atlas is laid out. */
function worldPointOf(id) {
  const p = state.layout && state.layout.placed.get(id);
  if (!p) return null;
  const z = worldScale();
  return [WORLD_PAD + (p.ox + p.map.size[0] / 2) * z,
          WORLD_PAD + (p.oy + p.map.size[1] / 2) * z];
}

function buildWorldPanel() {
  const { byId, entries } = state.world;
  const list = $("world-maps");
  list.replaceChildren(...entries.map(({ name, map }) => {
    const out = (map.exits || []).length;
    const inbound = [...byId.values()].filter(
      (e) => e.map.id !== map.id && (e.map.exits || []).some((x) => x.to === map.id)).length;
    const dest = (map.exits || []).map((x) => (byId.has(x.to) ? byId.get(x.to).map.name : x.to));
    const el = document.createElement("div");
    el.className = "mapline " + (out + inbound ? "linked" : "orphan")
                 + (map.id === (state.map && state.map.id) ? " on" : "");
    el.innerHTML = `<b>${map.name || name}</b>`
      + `<span>${name}.json &middot; ${map.size[0]}x${map.size[1]}</span>`
      + `<span>${out ? "out to " + dest.join(", ") : "no way out"}`
      + `${inbound ? ` &middot; ${inbound} in` : ""}</span>`;
    el.onclick = async () => { await openMap(name); await setView("map"); };
    return el;
  }));

  const { byId: ids } = state.world;
  const nameOf = (id) => (ids.has(id) ? ids.get(id).map.name || id : id);
  $("world-gates").replaceChildren(...(state.gates || []).map((g) => {
    const el = document.createElement("div");
    el.className = "gate" + (g.oneWay ? " oneway" : "");
    el.style.borderLeftColor = g.colour;
    const join = g.oneWay ? "&rarr;" : "&#8646;";
    el.innerHTML = `<b><i style="background:${g.colour}">${g.n}</i>`
      + `${nameOf(g.from)} ${join} ${nameOf(g.to)}</b>`
      + `<span>${g.edge ? g.edge + " edge" : "inland"} &middot; `
      + `${g.ex.tiles.length} tile${g.ex.tiles.length === 1 ? "" : "s"} wide`
      + `${g.oneWay ? " &middot; one way only" : ""}</span>`;
    el.onclick = async () => {
      const file = ids.has(g.from) ? ids.get(g.from).name : null;
      if (file) { await openMap(file); await setView("map"); }
    };
    return el;
  }));

  const notes = $("world-notes");
  notes.replaceChildren(...worldNotes().map((n) => {
    const el = document.createElement("div");
    el.className = "note" + (n.bad ? "" : " info");
    el.innerHTML = n.html;
    return el;
  }));
}

async function setView(name) {
  state.view = name;
  const world = name === "world";
  $("v-map").classList.toggle("on", !world);
  $("v-world").classList.toggle("on", world);
  $("view").hidden = world;
  $("world").hidden = !world;
  $("legend-map").hidden = world;
  $("legend-world").hidden = !world;
  $("side-world").hidden = !world;
  $("pal-terrain").hidden = world || state.tool === "place";
  $("pal-objects").hidden = world || state.tool !== "place";
  if (world) {
    message("reading the maps...");
    await refreshWorld();
    renderWorld();
    message("click a map to open it");
  } else {
    $("st-world").textContent = "";
    render();
  }
}

// ------------------------------------------------------------------ wiring --
function setTool(name) {
  state.tool = name;
  if (state.view === "world") setView("map");
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

  const wv = $("world");
  wv.addEventListener("click", async (e) => {
    const r = wv.getBoundingClientRect();
    const hit = mapAtWorld(e.clientX - r.left, e.clientY - r.top);
    if (!hit) return;
    await openMap(hit.name);
    await setView("map");
  });
  wv.addEventListener("pointermove", (e) => {
    const r = wv.getBoundingClientRect();
    const hit = mapAtWorld(e.clientX - r.left, e.clientY - r.top);
    wv.style.cursor = hit ? "pointer" : "default";
    if (hit) {
      const z = worldScale();
      const tx = Math.floor((e.clientX - r.left - WORLD_PAD) / z) - hit.ox;
      const ty = Math.floor((e.clientY - r.top - WORLD_PAD) / z) - hit.oy;
      $("st-tile").textContent = `${tx},${ty}`;
      $("st-terrain").textContent = terrainAt(tx, ty, hit.map) || "-";
      $("st-objects").textContent = hit.map.name || hit.id;
    }
  });
  $("v-map").onclick = () => setView("map");
  $("v-world").onclick = () => setView("world");
  $("mapName").oninput = (e) => {
    state.map.name = e.target.value;
    state.dirty = true;
    updateStatus();
  };

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
    if (e.key.toLowerCase() === "w") return setView(state.view === "world" ? "map" : "world");
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
  setView, loadWorld, layoutWorld, renderWorld, worldNotes, edgeOf, arrivalsOf,
  componentsOf, mapAtWorld, worldPointOf, worldScale,
  gatesOf, gateFor, refreshWorld, gatherableOf, blocksOf,
});

boot().catch((e) => message(String(e.message || e), true));

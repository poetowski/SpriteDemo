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
  $("mapTags").value = (state.map.tags || []).join(", ");
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

/** Whether a tile carries the 47-tile transition set the build exported.
 *  This is the same test indexAt makes before it resolves an edge, and it is
 *  deliberately the same table rather than a list kept alongside it: a mark
 *  that can disagree with what painting actually does is worse than no mark. */
function autotiles(tid) {
  return Boolean(state.M.tileset.masks[tid]);
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

/** Every definition some quest depends on, and why - so the map view can mark
 *  them and the status bar can say which errand an object belongs to. */
function questTargets() {
  const out = new Map();
  const note = (id, why) => {
    if (!id) return;
    if (!out.has(id)) out.set(id, []);
    out.get(id).push(why);
  };
  for (const q of Object.values((state.M && state.M.quests) || {})) {
    note(q.giver, `${q.name}: gives it`);
    for (const ob of q.objectives || []) {
      if (ob.kind !== "visit") note(ob.target, `${q.name}: ${ob.text}`);
    }
  }
  return out;
}

function footprintOf(id) {
  const d = defOf(id);
  return (d && d.footprint && d.footprint.length) ? d.footprint : [[0, 0]];
}

function blocksOf(id) {
  const d = defOf(id);
  return !!(d && d.blocks);
}

/** How many frames this thing is drawn in. One means it does not move. */
function framesOf(id) {
  const a = state.M.anims && state.M.anims[id];
  return a ? a.frames.length : 1;
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

  // Anything a quest names - who offers it, what it sends you to fetch, kill
  // or have a word with - gets a mark. Erasing one of these is the edit that
  // quietly makes an errand impossible, and it looks like any other erase.
  const named = questTargets();
  ctx.font = "600 10px ui-monospace, Consolas, monospace";
  for (const e of m.entities) {
    if (!named.has(e.def)) continue;
    ctx.fillStyle = "#e0c341";
    ctx.fillText("✦", e.tile[0] * ts * z + ts * z - 9, e.tile[1] * ts * z + 10);
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
  const named = questTargets();
  $("st-objects").textContent = here.length
    ? here.map((e) => e.def + (gatherableOf(e.def) ? " (gatherable)"
        : blocksOf(e.def) ? " (solid)" : "")
        + (named.has(e.def) ? ` ✦ ${named.get(e.def).join("; ")}` : "")).join(", ")
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
    // Whether a tile resolves its own edges is the thing worth knowing before
    // painting with it - it is the difference between a shore and a hard seam -
    // so it belongs on the swatch rather than being something you discover by
    // painting and undoing.
    const auto = autotiles(tid);
    el.className = "swatch" + (t.walkable ? "" : " solid") + (auto ? " auto" : "");
    el.append(swatchCanvas({ atlas: "tiles", index: t.index }, 48));
    // How many drawings of this tile exist. Which one a cell gets is decided
    // by where the cell is, not by a die roll, so a map looks the same every
    // time it loads - but a tile with one variant repeats visibly over a
    // field and that is worth knowing before painting one.
    const nvar = (t.variants || [t.index]).length;
    const vtag = document.createElement("i");
    vtag.className = "size";
    vtag.textContent = "×" + nvar;
    vtag.title = nvar > 1
      ? `${nvar} variants, picked per cell by position`
      : "one drawing - it repeats over a large area";
    el.append(vtag);
    const label = document.createElement("span");
    label.textContent = tid.replace("tile.", "");
    label.title = `${tid} (${t.walkable ? "walkable" : "solid"}, `
      + (auto ? "autotiles - edges resolve against its neighbours"
              : "no transitions - a hard edge against anything else")
      + `, ${nvar} variant${nvar === 1 ? "" : "s"})`;
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
      const frames = framesOf(id);
      const el = document.createElement("div");
      el.className = "swatch " + (gather ? "gather" : blocksOf(id) ? "solid" : "ground")
                   + (frames > 1 ? " anim" : "");
      const rec = spriteFor(id);
      el.append(swatchCanvas(rec, 48));
      // Every swatch is drawn at 48px whatever it really is, so the palette
      // says nothing about size unless it is told to. Which frame a thing is
      // on decides how many tiles it covers and which sheet it costs space
      // on, so it is worth knowing before placing one.
      // A frame that is not square has to say both numbers, or props_tall
      // reads as the smallest class in the game rather than the narrowest.
      const [fw, fh] = state.M.atlases[rec.atlas].frame;
      const px = fw === fh ? fw + "px" : fw + "x" + fh;
      const size = document.createElement("i");
      size.className = "size";
      size.textContent = px;
      el.append(size);
      const label = document.createElement("span");
      label.textContent = id.split(".")[1];
      const d = defOf(id);
      // Its own element rather than another ::after, because the animation
      // mark already owns that pseudo-element and two flags on one swatch
      // would mean one of them silently winning.
      if (d && d.equippable) {
        const eq = document.createElement("i");
        eq.className = "equip";
        eq.textContent = "E";
        eq.title = "equippable";
        label.append(eq);
      }
      label.title = `${id} (${kind}, `
        + (gather ? `gatherable${d && d.kind ? " " + d.kind : ""}`
                  : blocksOf(id) ? "solid" : "walkable")
        + (frames > 1 ? `, animated - ${frames} frames` : "")
        + (d && d.equippable ? ", equippable" : "")
        + `, ${px} frame)`;
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
  const KNOWN = new Set([...Object.keys(body), "exits", "tags"]);
  if (m.tags && m.tags.length) body.tags = m.tags;
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

/** Maps entered through a door rather than over a seam: an interior.
 *  Keyed by map id, valued by the doorway that leads in. A map with any
 *  edge-aligned way in is not one of these, however many doors it also has -
 *  it has a place on the grid, and the grid should show it. */
function interiorsOf(byId) {
  const inside = new Map();
  for (const { map } of byId.values()) {
    for (const ex of map.exits || []) {
      if (!byId.has(ex.to) || edgeOf(map, ex.tiles)) continue;
      // A zone is never a room. An inland doorway usually means a door into
      // a building, but it is also what a portal looks like - and the map on
      // the far side of one is a whole country, not a shed. Without this the
      // desert went under the world in the interiors band the moment it was
      // joined, marked "inside", which is the opposite of what the tag says.
      if ((byId.get(ex.to).map.tags || []).length) continue;
      if (!inside.has(ex.to)) {
        inside.set(ex.to, { parent: map.id, door: ex.tiles[0].slice() });
      }
    }
  }
  for (const id of [...inside.keys()]) {
    const bySeam = [...byId.values()].some((e) => (e.map.exits || [])
      .some((x) => x.to === id && edgeOf(e.map, x.tiles)));
    if (bySeam) inside.delete(id);
  }
  return inside;
}

/** Maps that lie against each other belong on one atlas.
 *
 *  Only a seam counts. A doorway that sits inland joins two maps in the game
 *  but says nothing about where either of them is, so it cannot place one
 *  against the other - which is why a door into a room was never a seam, and
 *  a portal is the same thing at the scale of a country. Counting one as
 *  adjacency put the desert in the wildernesses' component, where nothing
 *  could place it, and every map in that component then landed somewhere
 *  wrong. */
function componentsOf(byId, inside = new Map()) {
  const outdoor = [...byId.keys()].filter((id) => !inside.has(id));
  const adj = new Map(outdoor.map((id) => [id, new Set()]));
  for (const { map } of byId.values()) {
    if (inside.has(map.id)) continue;
    for (const ex of map.exits || []) {
      if (!byId.has(ex.to) || inside.has(ex.to)) continue;
      if (!edgeOf(map, ex.tiles) || !arrivalsOf(ex)) continue;
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
 *  is how a map reached only by a doorway pointing at it gets positioned.
 *
 *  The two cases do not share a doorway. Forward, `ex` is one of `here`'s own
 *  exits; inverted, it is one of the *destination's*, pointing back at `here`.
 *  So which edge it lies on has to be measured against whichever map owns it,
 *  and which map's width the far one steps over changes with it. Both were
 *  taken from `here` either way, and it went unnoticed for as long as every
 *  map placed that way was the same size as its neighbour - Wilderness V is
 *  sixty wide, and it landed forty tiles out with a hole beside it. */
function placeAcross(here, ex, destMap, invert) {
  const edge = edgeOf(invert ? destMap : here.map, ex.tiles);
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
  // The doorway is on the map being placed and leads back to `here`, so a
  // west-edge doorway means the destination sits east of `here` - over
  // `here`'s width - and an east-edge one means it sits west, over its own.
  if (edge === "west") return { ox: here.ox + hw, oy: here.oy + sy - ty };
  if (edge === "east") return { ox: here.ox - dw, oy: here.oy + sy - ty };
  if (edge === "north") return { ox: here.ox + sx - tx, oy: here.oy + hh };
  return { ox: here.ox + sx - tx, oy: here.oy - dh };
}

/** Lay every map out, one atlas per connected group, stacked down the canvas. */
function layoutWorld() {
  const { byId } = state.world;
  const openId = state.map && state.map.id;
  const inside = interiorsOf(byId);
  const comps = componentsOf(byId, inside).sort((a, b) => {
    const ai = a.includes(openId) ? 0 : 1;
    const bi = b.includes(openId) ? 0 : 1;
    return ai - bi || String(a[0]).localeCompare(String(b[0]));
  });

  const placed = new Map();
  const loose = [];
  const zones = [];
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

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of local.values()) {
      minX = Math.min(minX, p.ox);
      minY = Math.min(minY, p.oy);
      maxX = Math.max(maxX, p.ox + p.map.size[0]);
      maxY = Math.max(maxY, p.oy + p.map.size[1]);
    }
    for (const [id, p] of local) {
      placed.set(id, { ...p, ox: p.ox - minX, oy: p.oy - minY + cursorY });
    }
    // A plate that is all one zone gets named, because that is the whole point
    // of a tag: the second biome is a separate world on this atlas until a
    // portal joins it, and without the name it is just another island.
    const tags = [...comp].map((id) => (byId.get(id).map.tags || [])[0]);
    zones.push({ zone: tags.every((t) => t && t === tags[0]) ? tags[0] : null,
                 ox: 0, oy: cursorY, w: maxX - minX, h: maxY - minY });
    cursorY += (maxY - minY) + WORLD_GUTTER * 2;
  }

  // The interiors, in a row under the world proper. Each one keeps the tile
  // its door stands on, so the view can draw the line back to it rather than
  // implying it sits somewhere.
  let ix = 0;
  for (const [id, where] of inside) {
    const e = byId.get(id);
    if (!e) continue;
    placed.set(id, { ...e, ox: ix, oy: cursorY + WORLD_GUTTER,
                     interior: true, parent: where.parent, door: where.door });
    ix += e.map.size[0] + WORLD_GUTTER * 2;
  }
  return { placed, loose, zones, groups: comps.length, interiors: inside };
}

/** What is worth saying about how the maps join up. */
function worldNotes() {
  const { byId } = state.world;
  const interiors = (state.layout && state.layout.interiors) || new Map();
  const notes = [];
  const nameOf = (id) => (byId.has(id) ? byId.get(id).map.name || id : id);
  const leadsTo = (id) => [...byId.values()].filter(
    (e) => e.map.id !== id && (e.map.exits || []).some((x) => x.to === id));

  for (const { map } of byId.values()) {
    const out = map.exits || [];
    if (!out.length && !leadsTo(map.id).length) {
      // A tagged map that joins nothing is a zone waiting for its way in,
      // which is a different thing from a map somebody forgot to connect -
      // and the tag is what says which.
      const zone = (map.tags || [])[0];
      notes.push(zone
        ? { bad: false, html: `<b>${map.name || map.id}</b> is <b>${zone}</b> and `
            + "joins nothing yet - a zone of its own until something reaches it." }
        : { bad: true, html: `<b>${map.name || map.id}</b> joins nothing. `
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
        // Only worth saying when it is neither a door into a room nor a
        // portal into a zone. Both are *supposed* to be entered from the
        // middle of a map; what the note is for is a seam somebody drew in
        // the wrong place.
        // Either end: a portal out of the desert is as much a portal as the
        // one into it, and the way back is the untagged half of the pair.
        const zone = (byId.get(ex.to).map.tags || [])[0] || (map.tags || [])[0];
        if (zone) {
          notes.push({ bad: false, html: `<b>${map.name}</b> opens on <b>${zone}</b> `
            + `at <b>${nameOf(ex.to)}</b> - a portal, drawn as an arrow, since `
            + "it puts that map nowhere in particular." });
        } else if (!interiors.has(ex.to) && !interiors.has(map.id)) {
          notes.push({ bad: false, html: `<b>${map.name}</b> has an inland doorway to `
            + `<b>${nameOf(ex.to)}</b> - drawn as an arrow, since it is not a seam.` });
        }
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

  // The zone name over its plate, drawn first so a map can never sit on it.
  // Only when there is more than one plate: with a single world the caption
  // would be a label on the whole picture, which says nothing.
  if (layout.groups > 1) {
    ctx.font = "600 11px ui-monospace, Consolas, monospace";
    ctx.textBaseline = "alphabetic";
    for (const g of layout.zones) {
      if (!g.zone) continue;
      ctx.fillStyle = "#c9a86c";
      ctx.fillText(g.zone.toUpperCase().split("").join(" "), g.ox * z, g.oy * z - 5);
    }
  }

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
    if (p.interior) {
      // A room, drawn as one: a plate around it and a dashed edge, so it
      // never reads as another field of the world lying next to the rest.
      ctx.fillStyle = "rgba(14,16,21,.55)";
      ctx.fillRect(px - 5, py - 5, w * z + 10, h * z + 10);
      ctx.strokeStyle = open ? "#74c46b" : "#c9a86c";
      ctx.lineWidth = open ? 2 : 1;
      ctx.setLineDash([5, 3]);
      ctx.strokeRect(px - 5.5, py - 5.5, w * z + 11, h * z + 11);
      ctx.setLineDash([]);
    }
    ctx.strokeStyle = open ? "#74c46b" : (p.interior ? "#c9a86c" : "#55607a");
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
    const label = (p.interior ? "\u25a3 inside  " : "") + `${p.map.name || id}  ${w}x${h}`;
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
    // A door into a room already has its own line, drawn from the doorway to
    // the room's plate. A second arrow for the same crossing, run across the
    // whole atlas to a map that is not anywhere, is noise on top of it.
    if (a.interior || (dst && dst.interior)) {
      gateBadge(ctx, (a.ox + g.ex.tiles[0][0]) * z + z / 2,
                (a.oy + g.ex.tiles[0][1]) * z + z / 2, g.n, g.colour,
                Math.max(7, z * .75));
      continue;
    }
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

  // Every interior, tied back to the tile its door stands on. This is the
  // whole point of the treatment: the room is not anywhere, but its door is
  // somewhere exact, and that is what the reader needs to find.
  for (const [, p] of layout.placed) {
    if (!p.interior) continue;
    const parent = layout.placed.get(p.parent);
    if (!parent) continue;
    const dx = (parent.ox + p.door[0]) * z + z / 2;
    const dy = (parent.oy + p.door[1]) * z + z / 2;
    const rx = (p.ox + p.map.size[0] / 2) * z;
    const ry = p.oy * z - 6;
    ctx.strokeStyle = "#c9a86c";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(dx, dy);
    ctx.bezierCurveTo(dx, (dy + ry) / 2, rx, (dy + ry) / 2, rx, ry);
    ctx.stroke();
    ctx.setLineDash([]);
    // The door end gets the marker, because that is the half you go looking
    // for on the map you are standing on.
    ctx.fillStyle = "#c9a86c";
    ctx.fillRect(dx - z * .35, dy - z * .5, z * .7, z);
    ctx.fillStyle = "#11141c";
    ctx.fillRect(dx - z * .15, dy - z * .2, z * .3, z * .6);
    ctx.fillStyle = "#c9a86c";
    ctx.beginPath();
    ctx.arc(rx, ry, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  // Inland doorways: no shared edge to read, so draw the hop.
  for (const link of layout.loose) {
    const a = layout.placed.get(link.from);
    const b = layout.placed.get(link.to);
    if (!a || !b) continue;
    if (a.interior || b.interior) continue;       // the door line covers it
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
  const ids = byId;
  const interiors = (state.layout && state.layout.interiors) || new Map();
  const list = $("world-maps");
  const line = ({ name, map }) => {
    const out = (map.exits || []).length;
    const inbound = [...byId.values()].filter(
      (e) => e.map.id !== map.id && (e.map.exits || []).some((x) => x.to === map.id)).length;
    const dest = (map.exits || []).map((x) => (byId.has(x.to) ? byId.get(x.to).map.name : x.to));
    const el = document.createElement("div");
    const room = interiors.get(map.id);
    el.className = "mapline " + (room ? "inside" : out + inbound ? "linked" : "orphan")
                 + (map.id === (state.map && state.map.id) ? " on" : "");
    const parent = room && ids.has(room.parent) ? ids.get(room.parent).map.name : null;
    el.innerHTML = `<b>${room ? "&#9635; " : ""}${map.name || name}</b>`
      + `<span>${name}.json &middot; ${map.size[0]}x${map.size[1]}</span>`
      + `<span>${room ? `inside &mdash; through the door at `
                        + `${room.door[0]},${room.door[1]} on ${parent}`
                      : out ? "out to " + dest.join(", ") : "no way out"}`
      + `${!room && inbound ? ` &middot; ${inbound} in` : ""}</span>`
      + ((map.tags || []).length
         ? `<span class="tags">${map.tags.map((t) => `<i class="chip">${t}</i>`).join("")}</span>`
         : "");
    el.onclick = async () => { await openMap(name); await setView("map"); };
    return el;
  };
  // Grouped by tag, so a zone is a heading rather than something you have to
  // spot by reading every line. A map with no tags goes under the world it is
  // actually joined to, which is what "untagged" has always meant here.
  const zones = new Map();
  for (const e of entries) {
    const key = ((e.map.tags || [])[0]) || "";
    if (!zones.has(key)) zones.set(key, []);
    zones.get(key).push(e);
  }
  const blocks = [];
  for (const [zone, members] of [...zones].sort((a, b) => a[0].localeCompare(b[0]))) {
    if (zones.size > 1) {
      const h = document.createElement("div");
      h.className = "zone";
      h.innerHTML = `<span>${zone || "untagged"}</span><em>${members.length}</em>`;
      blocks.push(h);
    }
    blocks.push(...members.map(line));
  }
  list.replaceChildren(...blocks);

  const nameOf = (id) => (ids.has(id) ? ids.get(id).map.name || id : id);
  $("world-gates").replaceChildren(...(state.gates || []).map((g) => {
    const el = document.createElement("div");
    el.className = "gate" + (g.oneWay ? " oneway" : "");
    el.style.borderLeftColor = g.colour;
    const join = g.oneWay ? "&rarr;" : "&#8646;";
    el.innerHTML = `<b><i style="background:${g.colour}">${g.n}</i>`
      + `${nameOf(g.from)} ${join} ${nameOf(g.to)}</b>`
      + `<span>${g.edge ? g.edge + " edge" : "a door"} &middot; `
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


// --- item and actor sheets ---------------------------------------------------
/** What a sheet lets you change, per kind. Everything else in a definition -
 *  the sprite, the rig, the states, the wandering - is structure, and structure
 *  is not something a number box should be able to break. So the sheet shows
 *  those and edits these, and the server patches field by field rather than
 *  replacing the file, so a field the editor has never heard of survives it. */
const DEF_FIELDS = {
  items: [
    { key: "price", label: "price", type: "int", min: 0,
      hint: "in coins; 0 means nobody will buy it" },
    { key: "consumable", label: "consumable", type: "bool" },
    { key: "equippable", label: "equippable", type: "bool",
      hint: "has to agree with the slot shown above" },
    { key: "stack", label: "stacks", type: "bool" },
    { key: "stack_max", label: "max stack", type: "int", min: 2,
      only: (d) => d.stack, hint: "how many fit in one inventory slot" },
    { key: "description", label: "description", type: "text" },
    { key: "note", label: "note", type: "text", optional: true,
      hint: "anything worth knowing that is not part of the description" },
  ],
  actors: [
    { key: "speed", label: "speed", type: "int", min: 1,
      hint: "pixels a second when it is walking" },
    { key: "hostile.sight", label: "sight", type: "int", min: 1,
      only: (d) => d.behaviour !== "passive",
      hint: "how far off it notices the hero; hostile.lose has to be wider" },
    { key: "behaviour", label: "behaviour", type: "choice",
      choices: ["passive", "defensive", "offensive"],
      hint: "passive leaves you alone; defensive hits back once hit; "
          + "offensive starts it" },
    { key: "walking", label: "walks", type: "bool" },
    { key: "walk_radius", label: "walk radius", type: "int", min: 1,
      only: (d) => d.walking, hint: "how far from where it started it will go" },
    { key: "level", label: "level", type: "int", min: 1 },
    { key: "hp", label: "hp", type: "int", min: 1, optional: true,
      hint: "leave it empty and the thing cannot be killed" },
    { key: "attack", label: "attack", type: "int", min: 0,
      hint: "what one of its blows deals" },
    { key: "armor", label: "armor", type: "int", min: 0,
      hint: "comes off every blow it takes, to a floor of 1" },
    { key: "description", label: "description", type: "text" },
  ],
};

/** The structural facts, shown so the numbers have something to mean. */
const DEF_META = {
  items: (d) => [d.id, d.kind, d.slot ? d.slot + " slot" : null,
                 d.damage ? d.damage + " damage" : null,
                 d.defense ? d.defense + " armour" : null].filter(Boolean).join(" · "),
  actors: (d) => [d.id, d.rig,
                  d.hostile ? "chases from " + d.hostile.lose : null,
                  d.wander ? "wanders" : null].filter(Boolean).join(" · "),
};

function defTable(kind) { return kind === "items" ? state.M.items : state.M.actors; }
/** Read a field that may live one level inside a block, like hostile.sight. */
function fieldOf(d, key) {
  return key.split(".").reduce((o, k) => (o == null ? undefined : o[k]), d);
}
function defFile(id) { return id.split(".")[1]; }
/** The name to list something under. Falls back to the filename, capitalised -
 *  a definition with no "name" used to sit lowercase in a column of capitals
 *  and read as a different kind of thing. */
function defName(d, id) {
  const n = d.name || defFile(id);
  return n.charAt(0).toUpperCase() + n.slice(1);
}

function renderDefs(kind) {
  const table = defTable(kind);
  const ids = Object.keys(table).sort();
  state.defId = state.defId || {};
  if (!state.defId[kind] || !table[state.defId[kind]]) state.defId[kind] = ids[0];
  const pane = $(kind === "items" ? "defs-items" : "defs-actors");
  pane.replaceChildren();
  if (!ids.length) { pane.textContent = "nothing defined"; return; }

  const wrap = document.createElement("div");
  wrap.className = "defs";
  const list = document.createElement("div");
  list.className = "list";
  for (const id of ids) {
    const b = document.createElement("button");
    if (id === state.defId[kind]) b.className = "on";
    b.dataset.id = id;
    const rec = spriteFor(id);
    if (rec) b.append(swatchCanvas(rec, 24));
    const s = document.createElement("span");
    s.textContent = defName(table[id], id);
    b.append(s);
    b.onclick = () => { state.defId[kind] = id; renderDefs(kind); };
    list.append(b);
  }
  wrap.append(list, defSheet(kind, state.defId[kind]));
  pane.append(wrap);
}

function defSheet(kind, id) {
  const d = defTable(kind)[id];
  const form = document.createElement("div");
  form.className = "sheet";
  form.dataset.id = id;

  const h = document.createElement("h2");
  const rec = spriteFor(id);
  if (rec) h.append(swatchCanvas(rec, 32));
  h.append(document.createTextNode(defName(d, id)));
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = DEF_META[kind](d);
  form.append(h, meta);

  const inputs = {};
  // A max stack beside "does not stack" is meaningless, and the build refuses
  // it - so the row goes away rather than sitting there inviting the mistake.
  const redraw = () => {
    for (const f of DEF_FIELDS[kind]) {
      if (!f.only || !inputs[f.key]) continue;
      inputs[f.key].closest("label").hidden = !f.only(readSheet(kind, inputs));
    }
  };
  for (const f of DEF_FIELDS[kind]) {
    const label = document.createElement("label");
    const name = document.createElement("span");
    name.textContent = f.label;
    const cell = document.createElement("div");
    let input;
    if (f.type === "bool") {
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(fieldOf(d, f.key));
    } else if (f.type === "choice") {
      input = document.createElement("select");
      for (const c of f.choices) {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        input.append(opt);
      }
      input.value = fieldOf(d, f.key) || f.choices[0];
    } else if (f.type === "text") {
      input = document.createElement("textarea");
      input.value = fieldOf(d, f.key) || "";
    } else {
      input = document.createElement("input");
      input.type = "number";
      input.min = String(f.min);
      const v = fieldOf(d, f.key);
      input.value = v === undefined ? "" : String(v);
      if (f.optional) input.placeholder = "none";
    }
    input.dataset.key = f.key;
    const touched = () => { markDefDirty(form); redraw(); };
    input.oninput = touched;
    input.onchange = touched;
    inputs[f.key] = input;
    cell.append(input);
    if (f.hint) {
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = f.hint;
      cell.append(hint);
    }
    label.append(name, cell);
    form.append(label);
  }

  const actions = document.createElement("div");
  actions.className = "actions";
  const saveBtn = document.createElement("button");
  saveBtn.className = "primary";
  saveBtn.id = "def-save";
  saveBtn.textContent = "save";
  saveBtn.onclick = () => saveDef(kind, id, readSheet(kind, inputs), form);
  const flag = document.createElement("span");
  flag.className = "unsaved";
  actions.append(saveBtn, flag);
  form.append(actions);
  form._inputs = inputs;
  redraw();
  return form;
}

function readSheet(kind, inputs) {
  const out = {};
  for (const f of DEF_FIELDS[kind]) {
    const el = inputs[f.key];
    if (!el) continue;
    if (f.type === "bool") out[f.key] = el.checked;
    else if (f.type === "choice") out[f.key] = el.value;
    else if (f.type === "text") out[f.key] = el.value.trim();
    else out[f.key] = el.value === "" ? null : Number(el.value);
  }
  return out;
}

function markDefDirty(form) {
  const flag = form.querySelector(".unsaved");
  if (flag) flag.textContent = "unsaved";
}

/** Send only the fields the sheet owns. A field that is allowed to be empty
 *  and is empty goes as null, which is the server's word for "take this out" -
 *  so an emptied note is removed from the file rather than written as "". */
async function saveDef(kind, id, values, form) {
  const patch = {};
  for (const f of DEF_FIELDS[kind]) {
    let v = values[f.key];
    if (f.only && !f.only(values)) v = null;      // a cap with nothing to cap
    if (f.type === "text" && v === "" && f.optional) v = null;
    // walk_radius follows "walks": a radius on something that stands still is
    // refused by the build, so it goes out with the flag rather than lingering.
    if (f.key === "walk_radius" && !values.walking) v = 0;
    patch[f.key] = v;
  }
  const url = "/api/def?kind=" + kind + "&name=" + defFile(id);
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.ok) { message((body && body.error) || "save failed"); return false; }
  // Keep memory level with disk, so the list and the next sheet read true
  // without a reload.
  // Replace the record outright: deleting the patched keys one by one cannot
  // undo a nested write, and body.def is the file as it now stands anyway.
  defTable(kind)[id] = body.def;
  if (form) {
    const flag = form.querySelector(".unsaved");
    if (flag) flag.textContent = "";
  }
  message("saved " + body.path + " - run save + build to check it");
  renderDefs(kind);
  return true;
}

const VIEWS = { map: "v-map", world: "v-world", quests: "v-quests", dlg: "v-dlg",
                items: "v-items", actors: "v-actors" };
const PANES = { map: "view", world: "world", quests: "quests", dlg: "dlg",
                items: "defs-items", actors: "defs-actors" };
const SIDES = { world: "side-world", quests: "side-quests", dlg: "side-dlg" };
const LEGENDS = { map: "legend-map", world: "legend-world",
                  quests: "legend-quests", dlg: "legend-dlg",
                  items: "legend-items", actors: "legend-actors" };

async function setView(name) {
  state.view = name;
  for (const [view, id] of Object.entries(VIEWS)) $(id).classList.toggle("on", view === name);
  for (const [view, id] of Object.entries(PANES)) $(id).hidden = view !== name;
  for (const [view, id] of Object.entries(SIDES)) $(id).hidden = view !== name;
  for (const [view, id] of Object.entries(LEGENDS)) $(id).hidden = view !== name;
  const map = name === "map";
  $("pal-terrain").hidden = !map || state.tool === "place";
  $("pal-objects").hidden = !map || state.tool !== "place";
  if (name === "world" || name === "quests") {
    // Both read every map, and the open one comes from memory - so an edit
    // that has not been saved is already reflected in what they say.
    message("reading the maps...");
    await refreshWorld();
    if (name === "world") { renderWorld(); message("click a map to open it"); }
    else { renderQuests(); message("click a quest to read the conversation"); }
  } else if (name === "items" || name === "actors") {
    renderDefs(name);
    message("click one on the left to read and edit it");
  } else if (name === "dlg") {
    if (!state.dlgId) state.dlgId = Object.keys(state.M.dialogue || {}).sort()[0];
    renderDialogueList();
    renderDialogueGraph();
    renderDialogueNode();
    message("click a node to read the whole of it");
  } else {
    $("st-world").textContent = "";
    render();
  }
}

// ------------------------------------------------------------- the quests --
// A quest is authored in content/quests/ and the build checks it hard. The one
// thing no single file shows you is whether the world can actually pay it: how
// many berries are lying about, whether the thing you are sent to kill is
// placed anywhere, whether anyone offers the errand at all. That is a question
// about every map at once - which is exactly what this view has already read,
// the open map included, so painting over the last berry turns the board red
// before you have saved, never mind built.

const OBJ_MARK = { collect: "◆", kill: "⚔", talk: "☰", visit: "⚑" };

function questsOf() {
  return Object.values((state.M && state.M.quests) || {});
}

/** Every condition in a when-clause, flattened - the same little language the
 *  build checks and the game runs. */
function condsOf(c) {
  const w = c.when;
  if (!w) return [];
  return w.all ? w.all : [w];
}

/** Every map that carries this definition, and how many of it. */
function placementsOf(defId) {
  const out = [];
  for (const { map } of (state.world ? state.world.byId.values() : [])) {
    const n = (map.entities || []).filter((e) => e.def === defId).length;
    if (n) out.push({ id: map.id, name: map.name || map.id, n });
  }
  return out;
}

/** Where each quest is offered, handed in, and asked about. */
function questRefs() {
  const refs = new Map();
  const touch = (qid, key, at) => {
    if (!refs.has(qid)) refs.set(qid, { start: [], finish: [], asks: [] });
    refs.get(qid)[key].push(at);
  };
  for (const d of Object.values(state.M.dialogue || {})) {
    for (const [nid, node] of Object.entries(d.nodes || {})) {
      for (const c of node.choices || []) {
        if (c.start) touch(c.start, "start", { dlg: d.id, node: nid });
        if (c.finish) touch(c.finish, "finish", { dlg: d.id, node: nid });
        for (const cond of condsOf(c)) {
          if (cond.quest) touch(cond.quest.id, "asks", { dlg: d.id, node: nid });
        }
      }
    }
  }
  return refs;
}

/** What the world cannot currently deliver. The build refuses all of this, so
 *  anything here is an edit that has not been built yet - which is the point:
 *  it is the edit you are making now. */
function questNotes() {
  const refs = questRefs();
  const notes = [];
  for (const q of questsOf()) {
    const ref = refs.get(q.id) || { start: [], finish: [], asks: [] };
    for (const ob of q.objectives || []) {
      if (ob.kind === "visit") {
        if (!state.M.maps[ob.target]) {
          notes.push({ bad: true, html: `<b>${q.name}</b> sends the player to `
            + `<b>${ob.target}</b>, which is not a map.` });
        }
        continue;
      }
      const have = placementsOf(ob.target).reduce((n, p) => n + p.n, 0);
      const want = ob.count || 1;
      if (have < want) {
        notes.push({ bad: true, html: `<b>${q.name}</b> asks for ${want} `
          + `&times; <b>${ob.target}</b>, and the maps place ${have}. `
          + `It cannot be finished.` });
      }
    }
    if (!ref.start.length) {
      notes.push({ bad: true, html: `<b>${q.name}</b> is offered by nobody - no `
        + "reply anywhere starts it, so it can never appear in the game." });
    }
    if (!ref.finish.length && !q.auto) {
      notes.push({ bad: true, html: `<b>${q.name}</b> can be finished but not `
        + "handed in, and it is not marked <b>auto</b> - the player would do "
        + "all of it and never be paid." });
    }
  }
  if (!notes.length) {
    notes.push({ bad: false, html: questsOf().length
      ? "Every quest is offered, can be handed in, and the maps place enough "
        + "of what it asks for."
      : "No quests yet. They are files in <b>content/quests/</b>." });
  }
  return notes;
}

function renderQuests() {
  const refs = questRefs();
  const board = $("quests");
  board.replaceChildren();
  const link = (text, did, nid) => {
    const a = document.createElement("span");
    a.className = "link";
    a.textContent = text;
    a.onclick = () => showDialogue(did, nid);
    return a;
  };

  for (const q of questsOf()) {
    const ref = refs.get(q.id) || { start: [], finish: [], asks: [] };
    const card = document.createElement("div");
    let broken = !ref.start.length || (!ref.finish.length && !q.auto);

    const head = document.createElement("h3");
    head.append(document.createTextNode(q.name || q.id));
    const id = document.createElement("em");
    id.textContent = q.id;
    head.append(id);

    const sum = document.createElement("div");
    sum.className = "sum";
    sum.textContent = q.summary || "";

    const ul = document.createElement("ul");
    for (const ob of q.objectives || []) {
      const li = document.createElement("li");
      const mark = document.createElement("i");
      mark.textContent = OBJ_MARK[ob.kind] || "·";
      mark.title = ob.kind;
      const what = document.createElement("span");
      what.textContent = ob.text;
      what.title = `${ob.kind} ${ob.target}`
                 + ((ob.count || 1) > 1 ? ` × ${ob.count}` : "");
      const sup = document.createElement("span");
      sup.className = "supply";
      if (ob.kind === "visit") {
        const m = state.M.maps[ob.target];
        sup.textContent = m ? (m.name || ob.target) : "no such map";
        if (!m) { sup.classList.add("short"); broken = true; }
      } else {
        const where = placementsOf(ob.target);
        const have = where.reduce((n, p) => n + p.n, 0);
        const want = ob.count || 1;
        sup.textContent = `${have}/${want} placed`;
        sup.title = where.length
          ? where.map((p) => `${p.n} on ${p.name}`).join(", ")
          : "nowhere in the world";
        if (have < want) { sup.classList.add("short"); broken = true; }
      }
      li.append(mark, what, sup);
      ul.append(li);
    }

    const meta = document.createElement("div");
    meta.className = "meta";
    const giver = q.giver && state.M.actors[q.giver];
    if (giver) {
      const where = placementsOf(q.giver);
      const span = document.createElement("span");
      span.innerHTML = `given by <b>${giver.name || q.giver}</b>`
        + (where.length ? ` on ${where.map((p) => p.name).join(", ")}`
                        : " &mdash; <span style='color:var(--bad)'>placed nowhere</span>");
      if (!where.length) broken = true;
      meta.append(span);
    }
    const pay = [q.reward && q.reward.xp ? `${q.reward.xp} xp` : null,
                 q.reward && q.reward.give
                   ? ((state.M.items[q.reward.give] || {}).name || q.reward.give)
                   : null].filter(Boolean).join(" + ");
    if (pay) {
      const span = document.createElement("span");
      span.innerHTML = `pays <b>${pay}</b>`;
      meta.append(span);
    }
    for (const [key, word] of [["start", "offered at"], ["finish", "handed in at"]]) {
      if (!ref[key].length) continue;
      const span = document.createElement("span");
      span.append(document.createTextNode(`${word} `));
      ref[key].forEach((at, i) => {
        if (i) span.append(document.createTextNode(", "));
        span.append(link(`${at.dlg.replace("dlg.", "")}/${at.node}`, at.dlg, at.node));
      });
      meta.append(span);
    }
    if (q.auto) {
      const span = document.createElement("span");
      span.innerHTML = "<b>auto</b> &mdash; finishes itself";
      meta.append(span);
    }

    card.className = "card" + (broken ? " broken" : "");
    card.append(head, sum, ul, meta);
    board.append(card);
  }

  $("quest-list").replaceChildren(...questsOf().map((q) => {
    const el = document.createElement("div");
    el.className = "dlgline";
    const ref = refs.get(q.id) || { start: [] };
    el.innerHTML = `<b>${q.name || q.id}</b>`
      + `<span>${(q.objectives || []).length} objective`
      + `${(q.objectives || []).length === 1 ? "" : "s"}`
      + `${ref.start[0] ? ` &middot; ${ref.start[0].dlg.replace("dlg.", "")}` : ""}</span>`;
    el.onclick = () => ref.start[0] && showDialogue(ref.start[0].dlg, ref.start[0].node);
    return el;
  }));
  $("quest-notes").replaceChildren(...questNotes().map((n) => {
    const el = document.createElement("div");
    el.className = "note" + (n.bad ? "" : " info");
    el.innerHTML = n.html;
    return el;
  }));
  const n = questsOf().length;
  $("st-world").textContent = `${n} quest${n === 1 ? "" : "s"}`;
}

// ------------------------------------------------------ the conversations --
// A conversation is already a graph - nodes of text joined by the replies the
// player is offered - so this draws it as one rather than as a list of names
// you have to hold in your head. Columns are how many replies deep a node is,
// which puts the way in on the left and the endings on the right.

const NODE_W = 220;
const NODE_GAP_X = 78;
const NODE_GAP_Y = 14;
const NODE_PAD = 18;
const LINE_H = 13;
const ROW_H = 15;
const HEAD_H = 20;

function entriesOf(d) {
  return typeof d.start === "string" ? [{ goto: d.start }] : (d.start || []);
}

/** Every prop or actor whose "interact" names this conversation. */
function speakersOf(did) {
  const M = state.M;
  return [...Object.entries(M.props || {}), ...Object.entries(M.actors || {})]
    .filter(([, d]) => d.interact === did)
    .map(([id]) => id);
}

/** What a reply does, as marks: the shape of a conversation is mostly in its
 *  effects, and they are invisible if only the text is drawn. */
function choiceMarks(c) {
  const m = [];
  if (c.when) m.push("?");
  if (c.set) m.push("⚑");
  if (c.give) m.push("+");
  if (c.take) m.push("−");
  if (c.start) m.push("✦");
  if (c.finish) m.push("✓");
  return m.join("");
}

function describeCond(cond) {
  if (cond.flag) return `remembers ${cond.flag}`;
  if (cond.noflag) return `has not ${cond.noflag}`;
  if (cond.has) return `carrying ${cond.has}`;
  if (cond.nothas) return `not carrying ${cond.nothas}`;
  if (cond.quest) {
    const want = [].concat(cond.quest.is || "active");
    return `${cond.quest.id} is ${want.join(" or ")}`;
  }
  return JSON.stringify(cond);
}

/** Boxes and arrows for one conversation. */
function layoutDialogue(d) {
  const order = Object.keys(d.nodes || {});
  const depth = new Map();
  let frontier = [];
  for (const r of entriesOf(d)) {
    if (d.nodes[r.goto] && !depth.has(r.goto)) { depth.set(r.goto, 0); frontier.push(r.goto); }
  }
  let layer = 0;
  while (frontier.length) {
    const next = [];
    for (const nid of frontier) {
      for (const c of d.nodes[nid].choices || []) {
        if (!c.goto || !d.nodes[c.goto] || depth.has(c.goto)) continue;
        depth.set(c.goto, layer + 1);
        next.push(c.goto);
      }
    }
    frontier = next;
    layer += 1;
  }
  // A node nothing reaches is a gate failure, not a drawing problem - but a
  // draft has them, and leaving it off the picture is the one way to make it
  // harder to find.
  for (const nid of order) if (!depth.has(nid)) depth.set(nid, layer);

  const cols = new Map();
  for (const nid of order) {
    const lv = depth.get(nid);
    if (!cols.has(lv)) cols.set(lv, []);
    cols.get(lv).push(nid);
  }
  const boxes = new Map();
  let maxY = 0;
  let maxLayer = 0;
  for (const [lv, ids] of cols) {
    let y = NODE_PAD;
    for (const nid of ids) {
      const node = d.nodes[nid];
      const h = HEAD_H + (node.text || []).length * LINE_H
              + (node.choices || []).length * ROW_H + 10;
      boxes.set(nid, {
        nid, node, h, w: NODE_W, y,
        x: NODE_PAD + lv * (NODE_W + NODE_GAP_X),
        entry: entriesOf(d).some((r) => r.goto === nid),
      });
      y += h + NODE_GAP_Y;
    }
    maxY = Math.max(maxY, y);
    maxLayer = Math.max(maxLayer, lv);
  }
  return {
    boxes,
    width: NODE_PAD * 2 + (maxLayer + 1) * NODE_W + maxLayer * NODE_GAP_X,
    height: maxY + NODE_PAD,
  };
}

/** The y a reply's arrow leaves from. */
function rowY(box, i) {
  return box.y + HEAD_H + (box.node.text || []).length * LINE_H + 6 + i * ROW_H + ROW_H / 2;
}

function clipText(ctx, text, width) {
  if (ctx.measureText(text).width <= width) return text;
  let s = text;
  while (s.length > 1 && ctx.measureText(s + "…").width > width) s = s.slice(0, -1);
  return s + "…";
}

function renderDialogueGraph() {
  const d = state.M.dialogue[state.dlgId];
  const cv = $("dlg");
  if (!d) { cv.width = cv.height = 1; return; }
  const L = state.dlgLayout = layoutDialogue(d);
  cv.width = L.width;
  cv.height = L.height;
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#0e1015";
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.textBaseline = "alphabetic";

  // Arrows first, so a box always sits on top of the lines that reach it.
  for (const box of L.boxes.values()) {
    (box.node.choices || []).forEach((c, i) => {
      const to = c.goto && L.boxes.get(c.goto);
      if (!to) return;
      const x1 = box.x + box.w;
      const y1 = rowY(box, i);
      const x2 = to.x;
      const y2 = to.y + Math.min(to.h / 2, 24);
      const back = x2 <= x1;                       // a reply that goes back
      ctx.strokeStyle = back ? "#3f4759" : "#45526b";
      ctx.lineWidth = back ? 1 : 1.4;
      if (back) ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      if (back) {
        // Out to the right, down and back in: a straight line would run
        // through every box between here and there. Kept shallow on purpose -
        // there are a lot of these ("something else", "another time"), and a
        // deep loop each makes the picture mostly loops.
        const lift = 30 + i * 7;
        ctx.bezierCurveTo(x1 + 36, y1 + lift, x2 - 36, y2 + lift, x2, y2);
      } else {
        ctx.bezierCurveTo(x1 + NODE_GAP_X * 0.6, y1, x2 - NODE_GAP_X * 0.6, y2, x2, y2);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = back ? "#5d6679" : "#45526b";
      arrowHead(ctx, x2, y2, 1, 0, 6);
    });
  }

  for (const box of L.boxes.values()) {
    const on = box.nid === state.dlgNode;
    ctx.fillStyle = "#1b2130";
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.strokeStyle = on ? "#74c46b" : (box.entry ? "#6cc0e0" : "#2e3748");
    ctx.lineWidth = on ? 2 : 1;
    ctx.strokeRect(box.x + .5, box.y + .5, box.w - 1, box.h - 1);
    if (box.entry) {
      ctx.fillStyle = "#74c46b";
      ctx.beginPath();
      ctx.arc(box.x - 7, box.y + HEAD_H / 2 + 2, 3.5, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.font = "600 11px ui-monospace, Consolas, monospace";
    ctx.fillStyle = on ? "#d8f2cf" : "#e8e4da";
    ctx.fillText(clipText(ctx, box.nid, box.w - 16), box.x + 8, box.y + 14);

    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.fillStyle = "#8b93a7";
    (box.node.text || []).forEach((t, i) => {
      ctx.fillText(clipText(ctx, t, box.w - 16), box.x + 8, box.y + HEAD_H + 10 + i * LINE_H);
    });

    (box.node.choices || []).forEach((c, i) => {
      const y = rowY(box, i);
      const marks = choiceMarks(c);
      ctx.fillStyle = c.goto ? "#c9d2e4" : "#7f8798";     // no goto: it ends here
      ctx.font = "11px ui-monospace, Consolas, monospace";
      const room = box.w - 18 - (marks ? ctx.measureText(marks).width + 8 : 0);
      ctx.fillText(clipText(ctx, c.text, room), box.x + 10, y + 4);
      if (marks) {
        ctx.fillStyle = c.start || c.finish ? "#e0c341" : "#6cc0e0";
        ctx.fillText(marks, box.x + box.w - 8 - ctx.measureText(marks).width, y + 4);
      }
    });
  }
}

/** Which node a point on the conversation canvas lands in. */
function nodeAtDialogue(px, py) {
  if (!state.dlgLayout) return null;
  for (const box of state.dlgLayout.boxes.values()) {
    if (px >= box.x && py >= box.y && px < box.x + box.w && py < box.y + box.h) return box;
  }
  return null;
}

function renderDialogueList() {
  const ids = Object.keys(state.M.dialogue || {}).sort();
  const refs = questRefs();
  const questy = new Set();
  for (const [, r] of refs) {
    for (const at of [...r.start, ...r.finish, ...r.asks]) questy.add(at.dlg);
  }
  $("dlg-list").replaceChildren(...ids.map((did) => {
    const d = state.M.dialogue[did];
    const who = speakersOf(did);
    const el = document.createElement("div");
    el.className = "dlgline" + (did === state.dlgId ? " on" : "")
                 + (questy.has(did) ? " quest" : "");
    el.innerHTML = `<b>${d.speaker || did.replace("dlg.", "")}</b>`
      + `<span>${did} &middot; ${Object.keys(d.nodes || {}).length} nodes</span>`
      + `<span>${who.length ? who.join(", ") : "nothing says it"}</span>`;
    el.onclick = () => showDialogue(did);
    return el;
  }));
}

function renderDialogueNode() {
  const d = state.M.dialogue[state.dlgId];
  const node = d && d.nodes[state.dlgNode];
  const panel = $("dlg-node");
  $("dlg-node-head").textContent = node ? state.dlgNode : "the node";
  panel.replaceChildren();
  if (!node) {
    const el = document.createElement("div");
    el.className = "legend";
    el.textContent = "Click a node to read the whole of it.";
    panel.append(el);
    return;
  }
  for (const t of node.text || []) {
    const el = document.createElement("div");
    el.className = "line";
    el.textContent = t;
    panel.append(el);
  }
  for (const c of node.choices || []) {
    const el = document.createElement("div");
    el.className = "reply";
    const b = document.createElement("b");
    b.textContent = c.text;
    el.append(b);
    const tags = document.createElement("div");
    for (const cond of condsOf(c)) {
      const t = document.createElement("span");
      t.className = "tag " + (cond.quest ? "quest" : "when");
      t.textContent = describeCond(cond);
      tags.append(t);
    }
    for (const [key, word, cls] of [["set", "sets", ""], ["give", "gives", "item"],
                                    ["take", "takes", "item"],
                                    ["start", "starts", "quest"],
                                    ["finish", "hands in", "quest"]]) {
      if (!c[key]) continue;
      const t = document.createElement("span");
      t.className = "tag " + cls;
      t.textContent = `${word} ${c[key]}`;
      tags.append(t);
    }
    if (tags.childElementCount) el.append(tags);
    const go = document.createElement("span");
    go.textContent = c.goto ? `→ ${c.goto}` : "ends the conversation";
    el.append(go);
    panel.append(el);
  }
}

async function showDialogue(did, nid) {
  state.dlgId = did || state.dlgId || Object.keys(state.M.dialogue || {}).sort()[0];
  state.dlgNode = nid || null;
  if (state.view !== "dlg") await setView("dlg");
  renderDialogueList();
  renderDialogueGraph();
  renderDialogueNode();
  message(`${state.dlgId}${nid ? ` · ${nid}` : ""}`);
}

// ------------------------------------------------------------------ wiring --
function setTool(name) {
  state.tool = name;
  if (state.view !== "map") setView("map");
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
  const dv = $("dlg");
  dv.addEventListener("click", (e) => {
    const r = dv.getBoundingClientRect();
    const hit = nodeAtDialogue(e.clientX - r.left, e.clientY - r.top);
    if (!hit) return;
    state.dlgNode = hit.nid;
    renderDialogueGraph();
    renderDialogueNode();
  });
  dv.addEventListener("pointermove", (e) => {
    const r = dv.getBoundingClientRect();
    dv.style.cursor = nodeAtDialogue(e.clientX - r.left, e.clientY - r.top)
      ? "pointer" : "default";
  });

  $("v-map").onclick = () => setView("map");
  $("v-world").onclick = () => setView("world");
  $("v-quests").onclick = () => setView("quests");
  $("v-dlg").onclick = () => setView("dlg");
  $("v-items").onclick = () => setView("items");
  $("v-actors").onclick = () => setView("actors");
  $("mapName").oninput = (e) => {
    state.map.name = e.target.value;
    state.dirty = true;
    updateStatus();
  };
  // Tags are what make a second zone read as one before anything joins it to
  // the first. Lowercased here rather than rejected, because the gate wants
  // one lowercase word and nobody should have to remember that while typing.
  $("mapTags").oninput = (e) => {
    const tags = e.target.value.split(",").map((t) => t.trim().toLowerCase())
      .filter(Boolean).map((t) => t.replace(/\s+/g, "_"));
    state.map.tags = [...new Set(tags)];
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
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT"
        || e.target.tagName === "TEXTAREA") return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); return undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); return save(); }
    const views = { w: "world", q: "quests", d: "dlg",
                    i: "items", a: "actors" };
    const view = views[e.key.toLowerCase()];
    if (view) return setView(state.view === view ? "map" : view);
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
  setView, renderDefs, saveDef, DEF_FIELDS, loadWorld, layoutWorld, renderWorld, worldNotes, edgeOf, arrivalsOf,
  componentsOf, mapAtWorld, worldPointOf, worldScale,
  gatesOf, gateFor, refreshWorld, gatherableOf, blocksOf, interiorsOf, framesOf,
  questsOf, questRefs, questNotes, renderQuests, placementsOf, questTargets,
  layoutDialogue, renderDialogueGraph, renderDialogueList, renderDialogueNode,
  showDialogue, nodeAtDialogue, speakersOf, condsOf, spriteFor,
});

boot().catch((e) => message(String(e.message || e), true));

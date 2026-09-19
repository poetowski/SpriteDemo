/* Milestone 6: things to pick up, a bag to keep them in, a weapon in hand, and
 * errands worth using all three for.
 *
 * This scene knows no art and no content. Every sprite, animation, tile, prop,
 * actor, item, dialogue line, quest and map comes from window.ART.manifest,
 * which tools/build.py assembles from content/*.json and the generators.
 * Nothing here hardcodes a frame number, a tile index or a piece of text -
 * which is also why this file would port to another engine without touching
 * content/.
 *
 * Arming the hero is a sprite swap: the manifest's actor record carries a map
 * from weapon item to a frame set with the weapon baked into every pose, so
 * the walk, the gather and the slash all just work with a different base key.
 *
 * A quest is the same idea applied to progress. The engine knows four kinds of
 * objective - fetch, kill, talk, go - and nothing about any particular errand:
 * which ones exist, what they ask for and what they pay lives in
 * content/quests/, and a conversation starts and finishes them by id.
 */

const M = ART.manifest;
const DEFAULT_MAP = 'map.wilderness1';   // where a fresh game starts
const VIEW_W = 320;
const VIEW_H = 240;

/** Origin that puts a sprite's authored anchor on its world position. */
function originOf(spriteKey) {
  const rec = M.sprites[spriteKey];
  const [fw, fh] = M.atlases[rec.atlas].frame;
  return { ox: rec.anchor[0] / fw, oy: rec.anchor[1] / fh, rec };
}

function defOf(id) {
  return M.props[id] || M.actors[id] || M.items[id] || null;
}

/** Tiles a definition stands on, as offsets from its anchor tile. Art and
 *  collision are authored separately: a tree's canopy is wider than its trunk,
 *  and a cottage is three tiles across without needing three sprites. */
function footprintOf(def) {
  return def.footprint && def.footprint.length ? def.footprint : [[0, 0]];
}

/** The feet box for something that walks: as wide as its own footprint and
 *  centred on it, resting on the anchor row. A wanderer claims no tile in the
 *  blocked set - it carries its body with it - so this box is the whole of it,
 *  and a troll standing on two tiles needs two tiles of body. Derived, so the
 *  engine still knows nothing about what any particular creature is. */
function feetBody(sprite, def, anchor, ts) {
  const xs = footprintOf(def).map(([dx]) => dx);
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  const w = ts * (hi - lo + 1);
  const cx = anchor[0] + (ts * (lo + hi)) / 2;   // the anchor is tile lo, not
  sprite.body.setSize(w, 8).setOffset(cx - w / 2, anchor[1] - 8);  // the middle
}

const DIR = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
const BAG_COLS = 4;
const BAG_SLOTS = BAG_COLS * 4;

function facingOf([dx, dy]) {
  if (dy < 0) return 'up';
  if (dy > 0) return 'down';
  return dx < 0 ? 'left' : 'right';
}

class World extends Phaser.Scene {
  preload() {
    // Data URIs, so the game also runs straight from file:// with no server.
    for (const [name, meta] of Object.entries(M.atlases)) {
      this.load.spritesheet(name, ART.images[name], {
        frameWidth: meta.frame[0], frameHeight: meta.frame[1],
      });
    }
    this.load.image('tileset', ART.images.tiles);
  }

  /** Walking off one map and onto another restarts this scene, so everything
   *  that has to survive the crossing arrives here as data rather than living
   *  on the scene object - which Phaser throws away on restart. */
  init(data) {
    const d = data || {};
    this.mapId = d.map || DEFAULT_MAP;
    this.entryTile = d.spawn || null;      // where to come in, if not the
    this.entryFacing = d.facing || null;   // map's own spawn
    this.carry = d.carry || null;          // bag, gear, level, what was said
  }

  create() {
    const map = M.maps[this.mapId];
    this.map = map;
    this.ts = map.tile_size;
    const [cols, rows] = map.size;

    for (const [key, a] of Object.entries(M.anims)) {
      if (this.anims.exists(key)) continue;   // a crossing re-runs create()
      this.anims.create({
        key,
        frames: a.frames.map((f) => ({ key: a.atlas, frame: f })),
        frameRate: 1000 / a.ms,
        repeat: a.loop === false ? 0 : -1,   // one-shots hand control back
      });
    }

    // --- ground ---------------------------------------------------------
    // The build resolves each cell to a variant or a transition tile; the
    // legend fallback keeps an unresolved map drawable.
    const grid = map.grid || map.ground.map((row) =>
      [...row].map((ch) => M.tiles[map.legend[ch]].index));
    const tilemap = this.make.tilemap({
      data: grid, tileWidth: this.ts, tileHeight: this.ts,
    });
    const layer = tilemap.createLayer(0, tilemap.addTilesetImage('tileset'), 0, 0);
    layer.setDepth(-1000);
    const blocking = (M.tileset && M.tileset.blocking) ||
      Object.values(M.tiles).filter((t) => !t.walkable).map((t) => t.index);
    layer.setCollision(blocking);

    // Animated ground. The build drew the water in phases and listed each
    // base index's frame sequence; cycling them is all the engine has to know.
    const animated = (M.tileset && M.tileset.animated) || {};
    this.animatedTiles = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const frames = animated[grid[y][x]];
        if (frames) this.animatedTiles.push({ x, y, frames, solid: blocking.includes(frames[0]) });
      }
    }
    this.tilePhase = 0;
    if (this.animatedTiles.length) {
      this.time.addEvent({
        delay: (M.tileset && M.tileset.anim_ms) || 420,
        loop: true,
        callback: () => {
          this.tilePhase += 1;
          for (const t of this.animatedTiles) {
            const tile = layer.putTileAt(t.frames[this.tilePhase % t.frames.length], t.x, t.y, false);
            if (tile) tile.setCollision(t.solid);
          }
        },
      });
    }

    const worldW = cols * this.ts;
    const worldH = rows * this.ts;
    this.physics.world.setBounds(0, 0, worldW, worldH);
    this.cameras.main.setBounds(0, 0, worldW, worldH);

    // --- entities from the map's placement list --------------------------
    this.solid = this.physics.add.staticGroup();
    this.livestock = [];                  // solid things that move: see spawn()
    this.penned = new Set();              // tiles solid animals have claimed
    this.interactables = [];
    this.wanderers = [];
    this.pickups = [];
    this.hittable = [];
    this.blocked = new Set();
    for (const e of map.entities) {
      this.spawn(e.def, e.tile[0], e.tile[1]);
    }

    // --- player ----------------------------------------------------------
    const hero = M.actors['actor.hero'];
    const { ox, oy } = originOf(`${hero.sprite}/idle/down/0`);
    const start = this.entryTile || map.spawn.tile;
    const p = this.tileCentre(start[0], start[1]);
    this.hero = this.physics.add.sprite(p.x, p.y, 'actors').setOrigin(ox, oy);
    this.hero.body.setSize(12, 8).setOffset(10, 21);   // feet, not the whole frame
    this.hero.setCollideWorldBounds(true);
    this.heroDef = hero;
    this.heroSprite = hero.sprite;        // swapped for a wielding set when armed
    this.speed = hero.speed;
    this.facing = this.entryFacing || map.spawn.facing;
    this.hero.anims.play(`${hero.sprite}/idle/${this.facing}`);
    this.hero.on('animationcomplete', (anim) => this.onAnimDone(anim));
    this.hero.on('animationupdate', (anim, frame) => this.onAnimFrame(anim, frame));

    // The bag: a fixed grid of slots, one thing per slot, nothing stacks. The
    // panel that shows it is DOM (index.html); this is the only state.
    this.inventory = new Array(BAG_SLOTS).fill(null);
    this.cursor = 0;                      // the slot the panel's cursor is on
    this.bagOpen = false;
    // Worn gear lives here, not in a bag slot: a drawn sword is in the hero's
    // hand, so it should not also be taking up room in the pack.
    this.weapon = null;                   // item id in the weapon hand
    this.armor = null;                    // item id worn over the tunic

    // --- the character sheet ----------------------------------------------
    this.who = hero.display_name;
    this.level = hero.level;
    this.hpMax = hero.hp_max;
    this.hp = this.hpMax;
    this.xp = 0;
    this.sheetOpen = false;
    this.sheetCursor = 0;                 // 0 weapon, 1 armour
    this.flags = new Set();               // what conversations remember
    this.busy = false;                    // a one-shot animation owns the hero
    this.pending = null;                  // the pickup a gather will collect
    this.invuln = 0;                      // ms of grace after taking a hit

    // --- the journal --------------------------------------------------------
    // One record per quest the player has taken: what state it is in and the
    // progress that cannot be read back off the world. A fetch objective is
    // not in here at all - it is counted from the bag every time it is asked
    // for, so dropping a berry un-ticks it and no bookkeeping can drift out of
    // step with what you are actually carrying.
    this.quests = {};                     // quest id -> { state, ticks }
    this.questOpen = false;

    // --- what came across the map edge with us -----------------------------
    // Crossing restarts the scene, which would otherwise hand the player a
    // fresh bag and a level 1 sheet every time they walked west.
    if (this.carry) {
      this.inventory = this.carry.inventory.slice();
      this.weapon = this.carry.weapon;
      this.armor = this.carry.armor;
      this.level = this.carry.level;
      this.xp = this.carry.xp;
      this.hp = this.carry.hp;
      this.flags = new Set(this.carry.flags);
      this.quests = this.carry.quests;
      this.refreshLook();
    }
    // Arriving somewhere is itself progress, so it is checked before the first
    // frame rather than waiting for the player to move.
    this.noteVisit();

    // --- the ways out ------------------------------------------------------
    // An exit is authored in content/maps/: which tiles are the doorway, where
    // they lead, and where you come in at the other end. Arriving next to the
    // way back must not throw you straight through it, so exits stay locked
    // until the hero has stepped clear of every one of them.
    //
    // A doorway one tile wide sends everyone to the same "spawn". A doorway a
    // whole edge wide pairs each of its tiles with its own arrival in
    // "spawns", so walking west off one map comes out at the matching row of
    // the next - cross at the same height you left at, and the seam between
    // two maps stops feeling like a door and starts feeling like more country.
    this.exits = new Map();
    for (const ex of map.exits || []) {
      ex.tiles.forEach((t, i) => {
        const spawn = (ex.spawns && ex.spawns[i]) || ex.spawn;
        this.exits.set(`${t[0]},${t[1]}`, { to: ex.to, spawn, facing: ex.facing });
      });
    }
    this.exitLocked = true;
    this.travelling = false;

    this.physics.add.collider(this.hero, layer);
    this.physics.add.collider(this.hero, this.solid);
    this.physics.add.collider(this.hero, this.livestock);
    this.cameras.main.startFollow(this.hero, true, 0.16, 0.16);

    // --- input ------------------------------------------------------------
    this.keys = this.input.keyboard.addKeys({
      up: 'UP', down: 'DOWN', left: 'LEFT', right: 'RIGHT',
      w: 'W', a: 'A', s: 'S', d: 'D',
      talk: 'E', space: 'SPACE', swap: 'Q', bag: 'I', sheet: 'C', esc: 'ESC',
      journal: 'J',
    });
    const axisOf = { up: 'y', down: 'y', w: 'y', s: 'y',
                     left: 'x', right: 'x', a: 'x', d: 'x' };
    const stepOf = { up: [0, -1], w: [0, -1], down: [0, 1], s: [0, 1],
                     left: [-1, 0], a: [-1, 0], right: [1, 0], d: [1, 0] };
    this.lastAxis = 'y';
    for (const [name, key] of Object.entries(this.keys)) {
      if (!axisOf[name]) continue;
      key.on('down', () => {
        this.lastAxis = axisOf[name];
        // On the event, not polled: a tap shorter than a frame must still
        // move the cursor one slot, and JustDown loses it to the key-up.
        if (this.bagOpen) this.moveCursor(...stepOf[name]);
        else if (this.sheetOpen) this.moveGearCursor(stepOf[name][0]);
        else if (this.dialogue) this.moveChoice(stepOf[name][1]);
      });
    }
    // 1-4 pick a reply outright; the panel numbers them for exactly this
    for (let i = 0; i < 4; i++) {
      this.input.keyboard.on(`keydown-${['ONE', 'TWO', 'THREE', 'FOUR'][i]}`,
                             () => this.dialogue && this.choose(i));
    }
    window.__choose = (i) => this.choose(i);    // tapping a reply comes in here
    this.keys.talk.on('down', () => this.act('talk'));
    this.keys.space.on('down', () => this.act('slash'));
    this.keys.swap.on('down', () => this.act('swap'));
    this.keys.bag.on('down', () => this.act('bag'));
    this.keys.sheet.on('down', () => this.act('sheet'));
    this.keys.journal.on('down', () => this.act('journal'));
    this.keys.esc.on('down', () => {
      if (this.sheetOpen) return this.act('sheet');
      if (this.bagOpen) return this.act('bag');
      if (this.questOpen) return this.act('journal');
      this.closeDialogue();
    });
    window.__act = (name) => this.act(name);   // the touch buttons come in here
    window.__gear = (i) => {                   // tapping a gear slot on the sheet
      this.sheetCursor = i;
      this.useGearSlot(i);
      this.pushSheet();
    };

    this.dialogue = null;
    this.nearest = null;
    this.pushInventory();
    this.pushSheet();
    this.pushQuests();
  }

  tileCentre(tx, ty) {
    return { x: tx * this.ts + this.ts / 2, y: ty * this.ts + this.ts / 2 };
  }

  /** The hero's tile, which is the tile under the feet: the sprite's origin is
   *  its authored anchor, so its y is already the ground line. */
  heroTile() {
    return [Math.floor(this.hero.x / this.ts), Math.floor(this.hero.y / this.ts)];
  }

  /** Step onto an exit tile and come out on another map, carrying everything.
   *  The scene restarts rather than rebuilding in place, so nothing from the
   *  old map - a body, a timer, a wandering sheep - can outlive the crossing. */
  checkExit() {
    if (this.travelling || !this.exits.size) return;
    const [tx, ty] = this.heroTile();
    const ex = this.exits.get(`${tx},${ty}`);
    if (!ex) { this.exitLocked = false; return; }
    if (this.exitLocked) return;
    this.travelling = true;
    this.hero.setVelocity(0, 0);
    this.scene.restart({
      map: ex.to,
      spawn: ex.spawn,
      facing: ex.facing,
      carry: {
        inventory: this.inventory, weapon: this.weapon, armor: this.armor,
        level: this.level, xp: this.xp, hp: this.hp, flags: [...this.flags],
        quests: this.quests,
      },
    });
  }

  /** Create one entity from its definition id, at a tile. */
  spawn(defId, tx, ty) {
    const def = defOf(defId);
    const isActor = !!M.actors[defId];
    const isItem = !!M.items[defId];
    const key = isActor ? `${def.sprite}/idle/${def.facing || 'down'}/0` : def.sprite;
    const { ox, oy, rec } = originOf(key);
    const p = this.tileCentre(tx, ty);

    const sprite = this.add.sprite(p.x, p.y, rec.atlas, rec.index).setOrigin(ox, oy);
    sprite.setDepth(p.y);
    if (isActor) {
      sprite.play(`${def.sprite}/idle/${def.facing || 'down'}`);
    } else if (M.anims[def.sprite]) {
      // A prop that moves of its own accord - a fire, a sail, the bees. Each
      // one starts at a different point in the cycle, keyed off its tile:
      // a row of campfires flickering in step reads as one object repeated
      // rather than as several things burning.
      sprite.play(def.sprite);
      sprite.anims.setProgress((((tx * 7 + ty * 13) % 16) + 0.5) / 16);
    }

    if (isItem) {
      // Lying on the ground, with a slow bob so it reads as something to take.
      this.tweens.add({ targets: sprite, y: p.y - 2, duration: 700,
                        yoyo: true, repeat: -1, ease: 'Sine.inOut' });
      const pick = { id: defId, def, sprite, item: true };
      this.pickups.push(pick);
      this.interactables.push(pick);
      return sprite;
    }
    if (def.blocks && !def.wander) {
      // Static things claim their tiles once. Something that walks needs a
      // body that travels with it instead - see below.
      for (const [dx, dy] of footprintOf(def)) {
        const q = this.tileCentre(tx + dx, ty + dy);
        const body = this.add.zone(q.x, q.y, this.ts, this.ts);
        this.physics.add.existing(body, true);
        this.solid.add(body);
        this.blocked.add(`${tx + dx},${ty + dy}`);
      }
    }
    if (def.hittable) {
      this.hittable.push({ def, sprite });
    }
    if (def.interact) {
      // position is read from the sprite, so a wandering animal stays talkable
      this.interactables.push({ id: defId, def, sprite });
    }
    if (def.wander) {
      // Wanderers are moved by their body rather than by setting x/y, so the
      // body goes where the animal goes. A solid one is immovable: the player
      // is pushed out of it, and the animal carries on grazing regardless.
      this.physics.add.existing(sprite);
      feetBody(sprite, def, rec.anchor, this.ts);    // feet, not the frame
      sprite.body.setImmovable(!!def.blocks);
      if (def.blocks) {
        // Two immovable bodies do not push each other apart, so without a
        // claim on the tile a pair of sheep would walk into one spot and stay
        // there as one four-legged smear. They reserve where they stand and
        // where they are heading instead.
        this.livestock.push(sprite);
        for (const [dx, dy] of footprintOf(def)) this.penned.add(`${tx + dx},${ty + dy}`);
      }
      this.wanderers.push({
        def, sprite, home: [tx, ty], tile: [tx, ty],
        facing: def.facing || 'down', state: 'idle', timer: 0,
        goalX: p.x, goalY: p.y, bolt: 0,
        // undefined for anything whose definition does not say how much it can
        // take - and that is exactly what makes it unkillable. See wound().
        hp: def.hp,
      });
    }
    return sprite;
  }

  isWalkable(tx, ty) {
    const [cols, rows] = this.map.size;
    if (tx < 0 || ty < 0 || tx >= cols || ty >= rows) return false;
    if (!M.tiles[this.map.legend[this.map.ground[ty][tx]]].walkable) return false;
    return !this.blocked.has(`${tx},${ty}`);
  }

  /** The tiles a wanderer would stand on with its anchor tile at (tx, ty). */
  cellsAt(w, tx, ty) {
    return footprintOf(w.def).map(([dx, dy]) => `${tx + dx},${ty + dy}`);
  }

  /** Whether it may: every tile it would cover has to be walkable, and none
   *  of them may be spoken for by another solid animal. Its own tiles are not
   *  in its way, which matters the moment something stands on more than one. */
  canStandAt(w, tx, ty) {
    const cells = this.cellsAt(w, tx, ty);
    if (cells.some((k) => !this.isWalkable(...k.split(',').map(Number)))) return false;
    if (!w.def.blocks) return true;
    const own = new Set(this.cellsAt(w, w.tile[0], w.tile[1]));
    return !cells.some((k) => !own.has(k) && this.penned.has(k));
  }

  /** Move its claim from where it stands to where it is going. */
  claim(w, tx, ty) {
    if (!w.def.blocks) return;
    for (const k of this.cellsAt(w, w.tile[0], w.tile[1])) this.penned.delete(k);
    for (const k of this.cellsAt(w, tx, ty)) this.penned.add(k);
  }

  /** Pick what an animal does next: graze, stand, or step to a neighbour tile. */
  pickWanderAction(w) {
    const cfg = w.def.wander;
    const rand = ([lo, hi]) => lo + Math.random() * (hi - lo);
    const roll = Math.random();

    if (roll < cfg.graze_chance) {
      w.state = 'graze';
      w.timer = rand(cfg.graze_ms);
      return;
    }
    if (roll < cfg.graze_chance + 0.15) {
      w.state = 'idle';
      w.timer = rand(cfg.idle_ms);
      return;
    }
    const dirs = [[0, -1, 'up'], [0, 1, 'down'], [-1, 0, 'left'], [1, 0, 'right']];
    for (let i = dirs.length - 1; i > 0; i--) {          // shuffle
      const j = Math.floor(Math.random() * (i + 1));
      [dirs[i], dirs[j]] = [dirs[j], dirs[i]];
    }
    for (const [dx, dy, facing] of dirs) {
      const nx = w.tile[0] + dx;
      const ny = w.tile[1] + dy;
      if (Math.abs(nx - w.home[0]) > cfg.radius) continue;   // stay near home
      if (Math.abs(ny - w.home[1]) > cfg.radius) continue;
      if (!this.canStandAt(w, nx, ny)) continue;
      const c = this.tileCentre(nx, ny);
      this.claim(w, nx, ny);
      w.tile = [nx, ny];
      w.goalX = c.x;
      w.goalY = c.y;
      w.facing = facing;
      w.state = 'walk';
      return;
    }
    w.state = 'idle';                                    // hemmed in; wait
    w.timer = rand(cfg.idle_ms);
  }

  /** A hostile animal, while it can see you. Returns false when it cannot, and
   *  the caller falls back to ordinary wandering - so "hostile" is a mode a
   *  wanderer drops into and out of, not a second kind of creature with its
   *  own movement code to keep in step with this one.
   *
   *  It chases by heading straight at the hero rather than tile by tile: a
   *  charge that stopped to line itself up with the grid would be a patrol.
   *  Losing sight is a wider radius than gaining it, or the boar flickers in
   *  and out of the chase at exactly the distance you stand at. */
  /** Set an animal's velocity without letting it walk into a wall. Anything
   *  that moves freely rather than tile by tile needs this: its body is
   *  immovable, so the physics will not stop it, and the first thing a player
   *  would see of the whole chase is a boar coming out of the rock. Each axis
   *  is tested on its own, which also makes it slide along an obstacle rather
   *  than sticking to it. */
  driveAvoidingWalls(w, vx, vy) {
    const look = this.ts * 0.6;
    const solid = (px, py) => !this.isWalkable(Math.floor(px / this.ts),
                                               Math.floor(py / this.ts));
    if (vx && solid(w.sprite.x + Math.sign(vx) * look, w.sprite.y)) vx = 0;
    if (vy && solid(w.sprite.x, w.sprite.y + Math.sign(vy) * look)) vy = 0;
    w.sprite.body.setVelocity(vx, vy);
  }

  stepHostile(w, dt) {
    const cfg = w.def.hostile;
    // "provoked" is the difference between a boar and an elk, and it is one
    // field rather than a second kind of creature: the elk carries the whole
    // hostile block from the start and simply does not use it until something
    // hits it. See provoke() - which is also the only thing that sets the flag,
    // so nothing in here needs to know what an elk is.
    if (!cfg || (cfg.provoked && !w.angered)) return false;
    const home = this.tileCentre(w.home[0], w.home[1]);

    // Going home. It has broken off and walks back at its own speed, not the
    // charge: the whole point of a leash is that you can get away, and a boar
    // that jogged home at charging speed would still be on top of you. It does
    // not notice the hero again until it is back, so leading it away and then
    // standing next to it cannot keep it out indefinitely.
    if (w.returning) {
      const hx = home.x - w.sprite.x;
      const hy = home.y - w.sprite.y;
      const d = Math.hypot(hx, hy);
      // Home, or as near as it is going to get. The second case matters: it
      // walks back in a straight line and can wedge on a trunk it went round
      // on the way out, and an animal pushing into a tree for ever is worse
      // than one that settles for where it stands.
      if (d < (w.homeBest === undefined ? Infinity : w.homeBest) - 1) {
        w.homeBest = d;
        w.stuck = 0;
      } else {
        w.stuck = (w.stuck || 0) + dt;
      }
      if (d <= Math.max(2, (w.def.speed * dt) / 1000) || w.stuck > 2500) {
        const at = w.stuck > 2500 ? { x: w.sprite.x, y: w.sprite.y } : home;
        w.sprite.body.reset(at.x, at.y);
        w.returning = false;
        w.angered = false;        // home, and no longer holding the grudge
        w.homeBest = undefined;
        w.stuck = 0;
        w.tile = [Math.floor(at.x / this.ts), Math.floor(at.y / this.ts)];
        this.pickWanderAction(w);
        return false;                                 // back to plain wandering
      }
      w.state = 'walk';
      w.facing = Math.abs(hx) > Math.abs(hy)
        ? (hx < 0 ? 'left' : 'right') : (hy < 0 ? 'up' : 'down');
      this.driveAvoidingWalls(w, (hx / d) * w.def.speed, (hy / d) * w.def.speed);
      return true;
    }

    // A blow in progress owns the creature until it has finished throwing it.
    // Something this slow has to plant its feet to hit you - that pause is
    // what makes a troll's punch a thing you can see coming and walk out of,
    // rather than damage that simply happens as it touches you.
    w.swing = Math.max(0, (w.swing || 0) - dt);
    if (w.swing > 0) {
      w.sprite.body.setVelocity(0, 0);
      return true;
    }

    const dx = this.hero.x - w.sprite.x;
    const dy = this.hero.y - w.sprite.y;
    const dist = Math.hypot(dx, dy);
    // It hunts its own patch, not the whole map: once it has been drawn
    // `leash` away from where it lives it breaks off, whatever it can see.
    const strayed = Math.hypot(w.sprite.x - home.x, w.sprite.y - home.y) > cfg.leash;
    const sees = dist <= (w.chasing ? cfg.lose : cfg.sight) && this.invuln <= 1200;
    if (!sees || strayed) {
      if (!w.chasing) return false;                   // it was only ever grazing
      w.chasing = false;
      w.returning = true;
      w.homeBest = undefined;
      w.stuck = 0;
      return true;                                    // walks home from here
    }
    w.chasing = true;
    w.state = 'walk';
    w.facing = Math.abs(dx) > Math.abs(dy)
      ? (dx < 0 ? 'left' : 'right') : (dy < 0 ? 'up' : 'down');
    if (dist > 0.5) {
      this.driveAvoidingWalls(w, (dx / dist) * cfg.charge_speed,
                              (dy / dist) * cfg.charge_speed);
    }
    // "reach" is centre to centre. Both bodies are solid, so the collider
    // holds those centres about 14px apart side on - a reach below that can
    // never land a hit however close the animal gets, which is the one number
    // here that is easy to set to something quietly impossible.
    w.gore = Math.max(0, (w.gore || 0) - dt);
    if (dist <= cfg.reach && w.gore <= 0) {
      w.gore = cfg.cooldown_ms;
      w.swing = this.swingMs(w);
      this.hurt(cfg.damage);
    }
    return true;
  }

  /** How long a creature's attack animation runs, or 0 if it has none: an
   *  animal that only gores is the boar, and it goes on walking into you. */
  swingMs(w) {
    const a = M.anims[`${w.def.sprite}/attack/${w.facing}`];
    return a ? a.ms * a.frames.length : 0;
  }

  stepWanderers(dt) {
    this.invuln = Math.max(0, (this.invuln || 0) - dt);
    for (const w of this.wanderers) {
      const body = w.sprite.body;
      if (this.stepHostile(w, dt)) {
        const want = `${w.def.sprite}/${w.swing > 0 ? 'attack' : 'walk'}/${w.facing}`;
        if (!w.sprite.anims.currentAnim || w.sprite.anims.currentAnim.key !== want) {
          w.sprite.play(want, true);
        }
        w.sprite.setDepth(w.sprite.y + 0.5);
        continue;
      }
      if (w.state === 'walk') {
        const dx = w.goalX - w.sprite.x;
        const dy = w.goalY - w.sprite.y;
        const dist = Math.hypot(dx, dy);
        const speed = w.def.speed * (w.bolt || 1);
        if (dist <= Math.max(1, (speed * dt) / 1000)) {
          body.reset(w.goalX, w.goalY);      // land on the tile and stop dead
          w.bolt = 0;
          this.pickWanderAction(w);
        } else {
          body.setVelocity((dx / dist) * speed, (dy / dist) * speed);
        }
      } else {
        body.setVelocity(0, 0);
        w.timer -= dt;
        if (w.timer <= 0) this.pickWanderAction(w);
      }
      const want = `${w.def.sprite}/${w.state}/${w.facing}`;
      const cur = w.sprite.anims.currentAnim && w.sprite.anims.currentAnim.key;
      if (cur !== want) w.sprite.play(want, true);
      w.sprite.setDepth(w.sprite.y + 0.5);   // same tie-break as the hero
    }
  }

  // --- actions -------------------------------------------------------------
  /** One entry point for keys and touch buttons alike. */
  act(name) {
    if (name === 'bag') {
      if (this.dialogue || this.busy) return;
      this.bagOpen = !this.bagOpen;
      if (this.bagOpen) {
        this.sheetOpen = this.questOpen = false;
        this.hero.setVelocity(0, 0);
      }
      this.pushSheet();
      this.pushQuests();
      return this.pushInventory();
    }
    if (name === 'sheet') {
      if (this.dialogue || this.busy) return;
      this.sheetOpen = !this.sheetOpen;
      if (this.sheetOpen) {
        this.bagOpen = this.questOpen = false;
        this.hero.setVelocity(0, 0);
      }
      this.pushInventory();
      this.pushQuests();
      return this.pushSheet();
    }
    if (name === 'journal') {
      if (this.dialogue || this.busy) return;
      this.questOpen = !this.questOpen;
      if (this.questOpen) {
        this.bagOpen = this.sheetOpen = false;
        this.hero.setVelocity(0, 0);
      }
      this.pushInventory();
      this.pushSheet();
      return this.pushQuests();
    }
    if (this.questOpen) {                  // read-only: anything shuts it again
      if (name === 'talk') return this.act('journal');
      return;
    }
    if (this.sheetOpen) {                  // the sheet has the keys while open
      if (name === 'talk') return this.useGearSlot(this.sheetCursor);
      if (name === 'swap') return this.cycleWeapon();
      return;
    }
    if (this.bagOpen) {                    // the panel has the keys while open
      if (name === 'talk') return this.useSlot(this.cursor);
      if (name === 'swap') return this.cycleWeapon();
      return;
    }
    if (name === 'talk') {
      if (this.dialogue) return this.advanceDialogue();
      if (this.busy) return;
      if (this.nearest && this.nearest.item) return this.gather(this.nearest);
      return this.advanceDialogue();
    }
    if (name === 'slash') {
      if (this.dialogue) return this.advanceDialogue();
      return this.slash();
    }
    if (name === 'swap') return this.cycleWeapon();
  }

  gather(pick) {
    if (!this.canTake(pick.id)) return;           // bag full: the prompt says so
    this.busy = true;
    this.pending = pick;
    this.hero.setVelocity(0, 0);
    this.hero.anims.play(`${this.heroSprite}/gather/${this.facing}`);
  }

  slash() {
    if (this.busy || !this.weapon) return;
    this.busy = true;
    this.hero.setVelocity(0, 0);
    this.hero.anims.play(`${this.heroSprite}/slash/${this.facing}`);
  }

  onAnimFrame(anim, frame) {
    // the strike lands on the second frame of the swing, not at its end
    if (anim.key.split('/')[1] === 'slash' && frame.index === 2) this.strike();
  }

  onAnimDone(anim) {
    const state = anim.key.split('/')[1];
    if (state === 'gather' && this.pending) {
      const pick = this.pending;
      this.pending = null;
      this.collect(pick);
    }
    if (state === 'gather' || state === 'slash') this.busy = false;
  }

  collect(pick) {
    this.pickups = this.pickups.filter((p) => p !== pick);
    this.interactables = this.interactables.filter((p) => p !== pick);
    if (this.nearest === pick) this.nearest = null;
    this.tweens.killTweensOf(pick.sprite);
    pick.sprite.destroy();
    this.addItem(pick.id);
  }

  /** Can this be picked up at all? Gear going straight onto an empty body
   *  slot needs no bag room, which is why a full bag does not block it. */
  canTake(id) {
    const kind = M.items[id].slot;
    if (kind && !this.gearIn(kind)) return true;
    return this.inventory.includes(null);
  }

  gearIn(kind) {
    return kind === 'weapon' ? this.weapon : this.armor;
  }

  /** Put one thing away. Gear goes to the body when that slot is free. */
  addItem(id) {
    const kind = M.items[id].slot;
    if (kind && !this.gearIn(kind)) {
      if (kind === 'weapon') this.weapon = id; else this.armor = id;
      this.refreshLook();
      return true;
    }
    const slot = this.inventory.indexOf(null);
    if (slot < 0) return false;
    this.inventory[slot] = id;
    this.pushInventory();
    this.afterQuestChange();          // a fetch is counted off the bag
    return true;
  }

  /** Move gear between the bag and the body. The two trade places, so putting
   *  something on never needs a free slot - only taking something off does,
   *  and then only because it has to land somewhere. */
  setGear(kind, id) {
    const cur = this.gearIn(kind);
    if (id === cur) return true;
    if (id) {
      const slot = this.inventory.indexOf(id);
      if (slot < 0) return false;
      this.inventory[slot] = cur;            // what was worn drops into its place
    } else {
      const free = this.inventory.indexOf(null);
      if (free < 0) return false;            // bag full: it stays on
      this.inventory[free] = cur;
    }
    if (kind === 'weapon') this.weapon = id; else this.armor = id;
    this.refreshLook();
    return true;
  }

  /** E on a slot in the open bag: put that piece of gear on. */
  useSlot(slot) {
    const id = this.inventory[slot];
    if (!id) return;
    const kind = M.items[id].slot;
    if (kind) this.setGear(kind, id);
  }

  /** E on a slot in the open sheet: take that piece of gear off. */
  useGearSlot(i) {
    const kind = ['weapon', 'armor'][i];
    if (this.gearIn(kind)) this.setGear(kind, null);
  }

  /** The hero's look is one baked frame set per weapon-and-armour pair; the
   *  actor's record maps "<weapon>|<armor>" to it. */
  refreshLook() {
    this.heroSprite = this.heroDef.looks[`${this.weapon || ''}|${this.armor || ''}`];
    this.pushInventory();
    this.pushSheet();
  }

  /** Every weapon to hand: the drawn one, plus any in the bag. */
  weaponsHeld() {
    const seen = new Set();
    if (this.weapon) seen.add(this.weapon);
    for (const id of this.inventory) {
      if (id && M.items[id].slot === 'weapon') seen.add(id);
    }
    return [...seen];
  }

  cycleWeapon() {
    const held = this.weaponsHeld();
    if (!held.length) return;
    const ring = [null, ...held];
    this.setGear('weapon', ring[(ring.indexOf(this.weapon) + 1) % ring.length]);
  }

  // --- the character sheet ---------------------------------------------------
  /** What the next level costs. A curve, not a table, so levels past the ones
   *  anyone has reached still have a number. */
  xpToNext(level = this.level) {
    const { base, growth } = this.heroDef.xp_curve;
    return Math.round(base * Math.pow(level, growth));
  }

  damageDealt() {
    return this.heroDef.base_damage
         + (this.weapon ? M.items[this.weapon].damage : 0);
  }

  armorWorn() {
    return this.armor ? M.items[this.armor].defense : 0;
  }

  /** Landing a blow is worth what it took off. Levels roll over, carrying the
   *  remainder, so a big hit can never strand you a point short. */
  addXp(n) {
    this.xp += n;
    while (this.xp >= this.xpToNext()) {
      this.xp -= this.xpToNext();
      this.level += 1;
      this.hpMax += this.heroDef.hp_per_level;
      this.hp = this.hpMax;
      if (window.__levelUp) window.__levelUp(this.level);
    }
    this.pushSheet();
  }

  pushSheet() {
    if (!window.__sheet) return;
    const gear = (kind) => {
      const id = this.gearIn(kind);
      if (!id) return null;
      const d = M.items[id];
      return {
        id, name: d.name, index: M.sprites[d.sprite].index,
        stat: kind === 'weapon' ? `+${d.damage} damage` : `+${d.defense} armour`,
      };
    };
    window.__sheet({
      open: this.sheetOpen,
      name: this.who,
      level: this.level,
      hp: this.hp,
      hpMax: this.hpMax,
      xp: this.xp,
      xpNext: this.xpToNext(),
      damage: this.damageDealt(),
      armor: this.armorWorn(),
      cursor: this.sheetCursor,
      slots: [
        { kind: 'weapon', label: 'Weapon', item: gear('weapon') },
        { kind: 'armor', label: 'Armour', item: gear('armor') },
      ],
      bagFull: !this.inventory.includes(null),
    });
  }

  moveGearCursor(dx) {
    if (!dx) return;
    this.sheetCursor = Math.max(0, Math.min(1, this.sheetCursor + dx));
    this.pushSheet();
  }

  /** What the swing reaches: a tile ahead, a tile and a bit either side. */
  strike() {
    const dir = DIR[this.facing];
    const cx = this.hero.x + dir[0] * this.ts;
    const cy = this.hero.y - 6 + dir[1] * this.ts;     // the anchor is at the feet
    const reach = this.ts * 1.25;
    const inArc = (s) => Math.abs(s.x - cx) <= reach && Math.abs(s.y - cy) <= reach;
    // Over a copy: a blow that kills takes its target out of this.wanderers,
    // and a list being edited under a for..of quietly skips the next animal.
    for (const w of [...this.wanderers]) {
      if (!inArc(w.sprite)) continue;
      this.flinch(w.sprite);
      const n = this.floatDamage(w.sprite);
      if (this.wound(w, n)) continue;              // that was the last of it
      if (!this.provoke(w)) this.startle(w, dir);  // it turns, or it bolts
    }
    for (const h of this.hittable) {
      if (!inArc(h.sprite)) continue;
      this.flinch(h.sprite, true);
      this.floatDamage(h.sprite);
    }
  }

  /** A blow lands on something that can fight back. Anything carrying a
   *  "hostile" block turns on the hero when struck instead of bolting - it
   *  knows exactly who hit it, so it does not have to see them first - and
   *  something marked "provoked" has been waiting for exactly this: it grazed
   *  like a sheep until now and is a boar with antlers from here on, until it
   *  gets back to where it lives. Returns whether the blow angered it, because
   *  a creature that turns on you must not also run away from you. */
  provoke(w) {
    if (!w.def.hostile) return false;
    w.angered = true;
    w.chasing = true;
    w.returning = false;
    return true;
  }

  /** A blow's worth: the weapon's damage, give or take a fifth. */
  rollDamage() {
    const base = this.damageDealt();
    return Math.max(1, Math.round(base * (0.8 + Math.random() * 0.4)));
  }

  /** A hit the hero landed: roll it, take the xp, show it, and hand back what
   *  it was worth so the caller can take it off something's hp. */
  floatDamage(target) {
    const n = this.rollDamage();
    this.addXp(n);
    this.hits = (this.hits || 0) + 1;
    this.showDamage(target, n);
    return n;
  }

  /** Take a blow off a creature. Returns whether that killed it.
   *
   *  A creature dies only if its definition says how much it can take, which
   *  is the whole rule: the sheep and the goat carry no "hp" and can be hit
   *  all day, and nothing in here knows which animals those are. */
  wound(w, n) {
    if (!w.def.hp) return false;
    w.hp -= n;
    if (w.hp > 0) return false;
    this.kill(w);
    return true;
  }

  /** Take a creature out of the world. Everything it was in has to let go of
   *  it - the lists it is stepped through, the tiles it reserved, the thing
   *  the player is standing next to - or it goes on blocking ground and
   *  offering conversation from behind a sprite that is no longer drawn. */
  kill(w) {
    this.wanderers = this.wanderers.filter((x) => x !== w);
    this.interactables = this.interactables.filter((it) => it.sprite !== w.sprite);
    if (this.nearest && this.nearest.sprite === w.sprite) this.nearest = null;
    for (const k of this.cellsAt(w, w.tile[0], w.tile[1])) this.penned.delete(k);
    // Spliced, not reassigned: the collider holds this very array, so handing
    // it a new one would leave the hero colliding with the dead.
    const i = this.livestock.indexOf(w.sprite);
    if (i >= 0) this.livestock.splice(i, 1);
    w.sprite.body.setVelocity(0, 0);
    w.sprite.body.enable = false;
    this.showDeath(w.sprite);
    this.noteKill(w.def.id);
  }

  /** It stiffens white, tips over and goes. Short, because a sandbox where
   *  things can be killed should not stop for half a second every time. */
  showDeath(sprite) {
    sprite.anims.stop();
    sprite.setTintFill(0xffffff);
    this.tweens.add({
      targets: sprite, alpha: 0, angle: 18, y: sprite.y + 3,
      duration: 420, ease: 'Quad.in', onComplete: () => sprite.destroy(),
    });
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI * 2 * i) / 6 + Math.random() * 0.7;
      const s = this.add.sprite(sprite.x, sprite.y - 8, 'fx', M.sprites['fx.spark'].index)
        .setScale(1.5).setDepth(sprite.y + 1000);
      this.tweens.add({ targets: s, x: sprite.x + Math.cos(a) * 12,
                        y: sprite.y - 8 + Math.sin(a) * 10, alpha: 0, scale: 0.4,
                        duration: 400, ease: 'Quad.out',
                        onComplete: () => s.destroy() });
    }
  }

  /** The number drifts up off the thing that was hit and fades, with a few
   *  sparks thrown out round it. Digits are sprites from the fx atlas, so
   *  they are pixels of the same size as everything else, not blurred text.
   *  Separate from the roll above because damage now goes both ways, and a
   *  boar goring the hero should not award the hero xp for being gored. */
  showDamage(target, n) {
    const scale = 2;                                  // 3x5 glyphs are too shy at 1x
    const advance = 5 * scale;                        // outlined glyph is 5 wide
    const digits = [...String(n)];
    const x0 = target.x - ((digits.length - 1) * advance) / 2;
    const y0 = target.y - 22;
    const depth = target.y + 1000;
    const parts = digits.map((d, i) => this.add
      .sprite(x0 + i * advance, y0, 'fx', M.sprites[`fx.${d}`].index)
      .setScale(scale).setDepth(depth));
    this.tweens.add({ targets: parts, y: y0 - 14, duration: 900, ease: 'Cubic.out' });
    this.tweens.add({ targets: parts, alpha: 0, delay: 550, duration: 400,
                      onComplete: () => parts.forEach((p) => p.destroy()) });
    for (let i = 0; i < 5; i++) {
      const a = (Math.PI * 2 * i) / 5 + Math.random() * 0.8;
      const r = 7 + Math.random() * 7;
      const s = this.add.sprite(target.x, y0 + 4, 'fx', M.sprites['fx.spark'].index)
        .setScale(1.5).setDepth(depth);
      this.tweens.add({ targets: s, x: target.x + Math.cos(a) * r,
                        y: y0 + 4 + Math.sin(a) * r - 6, alpha: 0, scale: 0.5,
                        duration: 320 + Math.random() * 200, ease: 'Quad.out',
                        onComplete: () => s.destroy() });
    }
  }

  /** Damage coming the other way. Armour is subtracted but never all of it:
   *  a hit that lands should always cost something, or a well-armoured player
   *  cannot tell whether the boar reached them. */
  hurt(n) {
    if (this.invuln > 0) return;
    const taken = Math.max(1, n - this.armorWorn());
    this.hp = Math.max(0, this.hp - taken);
    this.invuln = 900;                     // long enough to back out of reach
    this.showDamage(this.hero, taken);
    this.flinch(this.hero, true);
    this.cameras.main.shake(120, 0.006);
    if (this.hp <= 0) this.blackOut();
    this.pushSheet();
  }

  /** Nothing in this sandbox kills you. Running out of hp puts you back where
   *  the map started you, whole - which keeps a wandering boar a hazard to
   *  respect rather than a way to lose an hour of picking things up. */
  blackOut() {
    this.hp = this.hpMax;
    this.invuln = 1400;
    const back = this.map.spawn.tile;
    const p = this.tileCentre(back[0], back[1]);
    this.hero.body.reset(p.x, p.y);
    this.cameras.main.flash(260, 0, 0, 0);
    for (const w of this.wanderers) {
      if (w.chasing) { w.chasing = false; w.returning = true; }
    }
  }

  flinch(sprite, shake = false) {
    sprite.setTintFill(0xffffff);                        // a white hit flash
    this.time.delayedCall(70, () => sprite.clearTint());
    if (!shake) return;
    const x0 = sprite.x;
    this.tweens.add({ targets: sprite, x: x0 + 2, duration: 40, yoyo: true,
                      repeat: 2, onComplete: () => { sprite.x = x0; } });
  }

  /** An animal that is hit bolts a tile or two away from the blow, at speed,
   *  then goes back to being an animal. */
  startle(w, dir) {
    const cfg = w.def.wander;
    for (const n of [2, 1]) {
      const nx = w.tile[0] + dir[0] * n;
      const ny = w.tile[1] + dir[1] * n;
      if (Math.abs(nx - w.home[0]) > cfg.radius + 2) continue;
      if (Math.abs(ny - w.home[1]) > cfg.radius + 2) continue;
      if (!this.canStandAt(w, nx, ny)) continue;
      const c = this.tileCentre(nx, ny);
      this.claim(w, nx, ny);              // a bolt is still a step: it has to
      w.tile = [nx, ny];                  // take its claim with it
      w.goalX = c.x;
      w.goalY = c.y;
      w.facing = facingOf(dir);
      w.state = 'walk';
      w.bolt = 2.5;
      return;
    }
  }

  pushInventory() {
    if (!window.__inventory) return;
    const slots = this.inventory.map((id) => {
      if (!id) return null;
      const def = M.items[id];
      return { id, name: def.name, index: M.sprites[def.sprite].index,
               gear: def.slot || null,
               equipped: id === this.weapon || id === this.armor };
    });
    window.__inventory({
      slots, cols: BAG_COLS, cursor: this.cursor, open: this.bagOpen,
      weapon: this.weapon ? M.items[this.weapon].name : null,
      armor: this.armor ? M.items[this.armor].name : null,
    });
  }

  /** Arrow keys walk the cursor round the grid while the bag is open. */
  moveCursor(dx, dy) {
    const col = (this.cursor % BAG_COLS + dx + BAG_COLS) % BAG_COLS;
    const rows = BAG_SLOTS / BAG_COLS;
    const row = (Math.floor(this.cursor / BAG_COLS) + dy + rows) % rows;
    this.cursor = row * BAG_COLS + col;
    this.pushInventory();
  }

  // --- quests --------------------------------------------------------------
  // The engine knows four kinds of objective - fetch, kill, talk, go - and
  // nothing about any particular errand. Which quests exist, what they ask for
  // and what they pay is content/quests/; a conversation starts and finishes
  // them by id, the same way it sets a flag.
  //
  // A quest is in exactly one of four states, and those four words are the
  // whole language a conversation has for asking about one:
  //
  //     none    never taken
  //     active  taken, something still to do
  //     ready   taken, every objective met, not yet handed in
  //     done    handed in and paid
  //
  // "ready" is worth being its own state rather than a flag on "active": it is
  // the difference between the reply "still picking" and "here are your
  // berries", and the alternative is every hand-in choice re-deriving it.

  questState(id) {
    const st = this.quests[id];
    if (!st) return 'none';
    if (st.state === 'done') return 'done';
    return this.questProgress(id).every((o) => o.met) ? 'ready' : 'active';
  }

  /** How many of one item the player has, bag and body together. */
  countItem(id) {
    let n = this.inventory.filter((x) => x === id).length;
    if (this.weapon === id) n += 1;
    if (this.armor === id) n += 1;
    return n;
  }

  /** Every objective of a quest, with the progress made against it.
   *
   *  A fetch is counted off the bag each time rather than remembered, so
   *  putting a berry down takes the tick away again and no bookkeeping can
   *  drift out of step with what the player is actually carrying. The other
   *  three kinds are things that happened, so they are what the record holds. */
  questProgress(id) {
    const q = M.quests[id];
    if (!q) return [];
    const st = this.quests[id];
    // Once it is handed in it stays handed in. Counting a fetch off the bag is
    // what keeps it honest while the errand is live, but the berries are in
    // Arne's hands afterwards, and a finished quest that reads 0/3 looks like
    // something went wrong rather than like something was finished.
    const over = st && st.state === 'done';
    return (q.objectives || []).map((ob) => {
      const need = ob.count || 1;
      const have = over ? need : (ob.kind === 'collect'
        ? this.countItem(ob.target)
        : ((st && st.ticks[ob.id]) || 0));
      return { id: ob.id, kind: ob.kind, target: ob.target, text: ob.text,
               have: Math.min(have, need), need, met: have >= need };
    });
  }

  startQuest(id) {
    if (this.quests[id] || !M.quests[id]) return;
    this.quests[id] = { state: 'active', ticks: {} };
    this.toast('Quest taken', M.quests[id].name);
    this.noteVisit();            // already standing where it sends you: done
    this.afterQuestChange();
  }

  /** Hand one in: take what it asked for, pay what it promised.
   *
   *  The collect objectives are the receipt, so no content has to say twice
   *  what three berries means. An objective marked "keep" is one the player
   *  was only ever asked to have. */
  finishQuest(id) {
    if (this.questState(id) !== 'ready') return false;
    const q = M.quests[id];
    for (const ob of q.objectives || []) {
      if (ob.kind !== 'collect' || ob.keep) continue;
      for (let i = 0; i < (ob.count || 1); i++) this.dropItem(ob.target);
    }
    this.quests[id].state = 'done';
    const r = q.reward || {};
    if (r.xp) this.addXp(r.xp);
    if (r.give) this.giveItem(r.give);
    if (r.set) this.flags.add(r.set);
    this.toast('Quest complete', q.name);
    this.afterQuestChange();
    return true;
  }

  /** Mark progress on every active quest with an objective that matches.
   *  `add` counts up (a kill); without it the objective is simply met. */
  tick(matches, add = 0) {
    let moved = false;
    for (const [id, st] of Object.entries(this.quests)) {
      if (st.state !== 'active' || !M.quests[id]) continue;
      for (const ob of M.quests[id].objectives || []) {
        if (!matches(ob)) continue;
        const was = st.ticks[ob.id] || 0;
        const now = add ? was + add : 1;
        if (now === was) continue;
        st.ticks[ob.id] = now;
        moved = true;
      }
    }
    if (moved) this.afterQuestChange();
  }

  noteKill(defId) {
    this.tick((ob) => ob.kind === 'kill' && ob.target === defId, 1);
  }

  noteTalk(defId) {
    if (defId) this.tick((ob) => ob.kind === 'talk' && ob.target === defId);
  }

  /** Where the hero is standing. A map-wide objective is met by being on the
   *  map at all; one with a "tile" wants the player within a few of it. */
  noteVisit() {
    const [tx, ty] = this.heroTile();
    this.tick((ob) => ob.kind === 'visit' && ob.target === this.mapId
      && (!ob.tile || Math.hypot(ob.tile[0] - tx, ob.tile[1] - ty) <= (ob.radius || 2)));
  }

  /** Everything that moves a quest forward ends up here. It finishes anything
   *  that finishes itself, and says out loud what just changed - because by
   *  the time an objective is met the player is usually somewhere else, and a
   *  log you have to open to find out is a log nobody opens. */
  afterQuestChange() {
    for (const id of Object.keys(this.quests)) {
      const q = M.quests[id];
      const st = this.quests[id];
      if (!q) continue;
      if (q.auto && this.questState(id) === 'ready') this.finishQuest(id);
      const told = st.metIds || [];
      const progress = this.questProgress(id);
      if (st.state === 'active') {
        for (const o of progress) {
          if (o.met && !told.includes(o.id)) this.toast('Objective done', o.text);
        }
      }
      st.metIds = progress.filter((o) => o.met).map((o) => o.id);
      const now = this.questState(id);
      if (now === 'ready' && st.told !== 'ready') {
        this.toast('Ready to hand in', q.name);
      }
      st.told = now;
    }
    this.pushQuests();
  }

  /** What a quest pays, as one line. */
  rewardLine(q) {
    const r = q.reward || {};
    const bits = [];
    if (r.xp) bits.push(`${r.xp} xp`);
    if (r.give && M.items[r.give]) bits.push(M.items[r.give].name);
    return bits.join(' + ');
  }

  pushQuests() {
    if (!window.__quests) return;
    const rank = { ready: 0, active: 1, done: 2 };
    const list = Object.keys(this.quests)
      .filter((id) => M.quests[id])
      .map((id) => {
        const q = M.quests[id];
        return {
          id, name: q.name, summary: q.summary, state: this.questState(id),
          giver: (q.giver && M.actors[q.giver] && M.actors[q.giver].name) || null,
          reward: this.rewardLine(q),
          objectives: this.questProgress(id),
        };
      })
      .sort((a, b) => rank[a.state] - rank[b.state] || a.name.localeCompare(b.name));
    window.__quests({
      open: this.questOpen,
      quests: list,
      open_count: list.filter((q) => q.state !== 'done').length,
    });
  }

  toast(title, text) {
    if (window.__toast) window.__toast({ title, text });
  }

  // --- dialogue ------------------------------------------------------------
  // A conversation is a graph: nodes of text joined by the choices the player
  // is offered. What is offered depends on flags this scene remembers and on
  // what is in the bag, so an NPC can know it has met you before and a branch
  // can open only once you are carrying the right thing.

  /** One condition from a "when" clause. `all` nests; everything else is a
   *  single test, which keeps the little language checkable by a gate. */
  test(cond) {
    if (!cond) return true;
    if (cond.all) return cond.all.every((c) => this.test(c));
    if (cond.flag) return this.flags.has(cond.flag);
    if (cond.noflag) return !this.flags.has(cond.noflag);
    if (cond.has) return this.inventory.includes(cond.has);
    if (cond.nothas) return !this.inventory.includes(cond.nothas);
    // One key for a quest rather than four: the state is a word, and a
    // condition names the word - or the words - it will accept. That is also
    // how "taken but not finished" is said without a negation.
    if (cond.quest) {
      const want = cond.quest.is || 'active';
      const now = this.questState(cond.quest.id);
      return Array.isArray(want) ? want.includes(now) : want === now;
    }
    return true;
  }

  /** Entry rules pick where a conversation starts: the first whose condition
   *  holds. A plain string is the common case - always start here. */
  entryNode(dlg) {
    if (typeof dlg.start === 'string') return dlg.start;
    const rule = (dlg.start || []).find((r) => this.test(r.when));
    return rule ? rule.goto : null;
  }

  /** `withId` is what is being talked to, which the dialogue itself does not
   *  know - two things can share a conversation - and a quest may be waiting
   *  on having spoken to exactly that one. */
  openDialogue(id, withId) {
    const dlg = M.dialogue[id];
    const node = this.entryNode(dlg);
    if (!node) return;
    this.noteTalk(withId);
    this.hero.setVelocity(0, 0);
    this.dialogue = { dlg, node: null, line: 0, choices: [], pick: 0 };
    this.gotoNode(node);
  }

  gotoNode(id) {
    const d = this.dialogue;
    d.node = d.dlg.nodes[id];
    d.line = 0;
    d.pick = 0;
    // Only the choices whose conditions hold are offered - the rest are not
    // greyed out, they are simply not things you could say.
    d.choices = (d.node.choices || []).filter((c) => this.test(c.when));
    this.renderDialogue();
  }

  /** E, or a tap: run out the node's lines, then take the chosen branch. */
  advanceDialogue() {
    const d = this.dialogue;
    if (!d) {
      if (this.nearest && this.nearest.def.interact) {
        this.openDialogue(this.nearest.def.interact, this.nearest.id);
      }
      return;
    }
    if (d.line < d.node.text.length - 1) {       // still reading
      d.line += 1;
      return this.renderDialogue();
    }
    if (!d.choices.length) return this.closeDialogue();
    this.choose(d.pick);
  }

  choose(i) {
    const d = this.dialogue;
    if (!d || !d.choices.length || d.line < d.node.text.length - 1) return;
    const choice = d.choices[i];
    if (!choice) return;
    // Handing a quest in first, because that is the effect that empties the
    // bag: it takes what the quest asked for before anything else tries to put
    // something in. Then take before give, so trading the last thing in a full
    // bag still works, and start last - a quest taken here has nothing to do
    // with what this choice just handed over.
    if (choice.finish) this.finishQuest(choice.finish);
    if (choice.take) this.dropItem(choice.take);
    if (choice.give) this.giveItem(choice.give);
    if (choice.set) {
      this.flags.add(choice.set);
      this.pushInventory();                      // a flag can change a look
    }
    if (choice.start) this.startQuest(choice.start);
    if (!choice.goto) return this.closeDialogue();
    this.gotoNode(choice.goto);
  }

  moveChoice(dy) {
    const d = this.dialogue;
    if (!d || !d.choices.length || d.line < d.node.text.length - 1) return;
    d.pick = (d.pick + dy + d.choices.length) % d.choices.length;
    this.renderDialogue();
  }

  /** Remove one of an item from the bag.
   *
   *  The bag only: what is worn is not in it, and carrying a second sword
   *  while one is drawn is the case that matters - handing that one over must
   *  not take the drawn one out of the hero's hand as well. */
  dropItem(id) {
    const slot = this.inventory.indexOf(id);
    if (slot < 0) return;
    this.inventory[slot] = null;
    this.pushInventory();
    this.afterQuestChange();          // and un-counted when it leaves again
  }

  /** Hand something over. A full bag must not swallow it, so it lands at the
   *  hero's feet instead and can be picked up in the usual way. */
  giveItem(id) {
    if (this.addItem(id)) return;
    const tx = Math.floor(this.hero.x / this.ts);
    const ty = Math.floor(this.hero.y / this.ts);
    this.spawn(id, tx, ty);
  }

  renderDialogue() {
    const d = this.dialogue;
    if (!window.__dialogue) return;
    const reading = d.line < d.node.text.length - 1;
    window.__dialogue({
      speaker: d.dlg.speaker,
      text: d.node.text[d.line],
      more: reading,
      choices: reading ? [] : d.choices.map((c) => c.text),
      pick: d.pick,
    });
  }

  closeDialogue() {
    this.dialogue = null;
    if (window.__dialogue) window.__dialogue(null);
  }

  update(time, delta) {
    this.stepWanderers(delta);

    const k = this.keys;
    const pad = window.__pad || {};
    const talking = !!this.dialogue;
    const locked = talking || this.busy || this.bagOpen || this.sheetOpen
      || this.questOpen;

    if (this.sheetOpen && (pad.left || pad.right)) {
      this.moveGearCursor((pad.right ? 1 : 0) - (pad.left ? 1 : 0));
      window.__pad = {};
    }
    if (this.bagOpen && (pad.left || pad.right || pad.up || pad.down)) {
      // the touch d-pad drives the cursor too; one tap is one slot
      this.moveCursor((pad.right ? 1 : 0) - (pad.left ? 1 : 0),
                      (pad.down ? 1 : 0) - (pad.up ? 1 : 0));
      window.__pad = {};
    }

    const left = !locked && (k.left.isDown || k.a.isDown || !!pad.left);
    const right = !locked && (k.right.isDown || k.d.isDown || !!pad.right);
    const up = !locked && (k.up.isDown || k.w.isDown || !!pad.up);
    const down = !locked && (k.down.isDown || k.s.isDown || !!pad.down);

    let vx = (right ? 1 : 0) - (left ? 1 : 0);
    let vy = (down ? 1 : 0) - (up ? 1 : 0);
    if (vx && vy) { vx *= Math.SQRT1_2; vy *= Math.SQRT1_2; }
    this.hero.setVelocity(vx * this.speed, vy * this.speed);

    const moving = vx !== 0 || vy !== 0;
    if (moving) {
      const horizontal = vx !== 0 && (vy === 0 || this.lastAxis === 'x');
      this.facing = horizontal ? (vx < 0 ? 'left' : 'right')
                               : (vy < 0 ? 'up' : 'down');
    }
    const cur = this.hero.anims.currentAnim && this.hero.anims.currentAnim.key;
    const want = `${this.heroSprite}/${moving ? 'walk' : 'idle'}/${this.facing}`;
    if (!this.busy && cur !== want) this.hero.anims.play(want, true);
    const shown = this.busy && cur ? cur : want;

    // Anchor is at the feet, so y sorts. The half is for props on the same tile
    // row: they share the hero's y exactly, and a tie let a bench draw over
    // the sword. A moving thing wins a tie with a thing that stands still.
    this.hero.setDepth(this.hero.y + 0.5);

    // nearest thing worth pressing E at
    let best = null;
    let bestD = 26;
    for (const it of this.interactables) {
      const d = Phaser.Math.Distance.Between(
        this.hero.x, this.hero.y, it.sprite.x, it.sprite.y);
      if (d < bestD) { bestD = d; best = it; }
    }
    this.nearest = best;

    // Standing somewhere can be the errand. Only when the tile changes, which
    // is also the only time the answer can have changed.
    const at = this.heroTile();
    if (!this.lastTile || this.lastTile[0] !== at[0] || this.lastTile[1] !== at[1]) {
      this.lastTile = at;
      this.noteVisit();
    }
    this.checkExit();
    if (this.travelling) return;          // the scene is on its way out

    if (window.__hud) {
      window.__hud({
        anim: shown.split('/').slice(1).join('-'),
        tile: at,
        prompt: !talking && best ? (best.def.name || best.id.split('.')[1]) : null,
        verb: best && best.item ? 'take' : 'talk',
        bagFull: !this.inventory.includes(null),
        talking,
        quests: Object.keys(this.quests)
          .filter((id) => this.questState(id) !== 'done').length,
      });
    }
  }
}

window.game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: VIEW_W,
  height: VIEW_H,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#2f3b2a',
  physics: { default: 'arcade', arcade: { debug: false } },
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: World,
});

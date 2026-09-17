/* Milestone 5: things to pick up, a bag to keep them in, a weapon in hand.
 *
 * This scene knows no art and no content. Every sprite, animation, tile, prop,
 * actor, item, dialogue line and map comes from window.ART.manifest, which
 * tools/build.py assembles from content/*.json and the generators. Nothing here
 * hardcodes a frame number, a tile index or a piece of text - which is also why
 * this file would port to another engine without touching content/.
 *
 * Arming the hero is a sprite swap: the manifest's actor record carries a map
 * from weapon item to a frame set with the weapon baked into every pose, so
 * the walk, the gather and the slash all just work with a different base key.
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
      this.refreshLook();
    }

    // --- the ways out ------------------------------------------------------
    // An exit is authored in content/maps/: which tiles are the doorway, where
    // they lead, and where you come in at the other end. Arriving next to the
    // way back must not throw you straight through it, so exits stay locked
    // until the hero has stepped clear of every one of them.
    this.exits = new Map();
    for (const ex of map.exits || []) {
      for (const t of ex.tiles) this.exits.set(`${t[0]},${t[1]}`, ex);
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
    this.keys.esc.on('down', () => {
      if (this.sheetOpen) return this.act('sheet');
      if (this.bagOpen) return this.act('bag');
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
    if (isActor) sprite.play(`${def.sprite}/idle/${def.facing || 'down'}`);

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
      sprite.body.setSize(16, 8).setOffset(8, 21);   // feet, not the frame
      sprite.body.setImmovable(!!def.blocks);
      if (def.blocks) {
        // Two immovable bodies do not push each other apart, so without a
        // claim on the tile a pair of sheep would walk into one spot and stay
        // there as one four-legged smear. They reserve where they stand and
        // where they are heading instead.
        this.livestock.push(sprite);
        this.penned.add(`${tx},${ty}`);
      }
      this.wanderers.push({
        def, sprite, home: [tx, ty], tile: [tx, ty],
        facing: def.facing || 'down', state: 'idle', timer: 0,
        goalX: p.x, goalY: p.y, bolt: 0,
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
      if (!this.isWalkable(nx, ny)) continue;
      if (w.def.blocks && this.penned.has(`${nx},${ny}`)) continue;   // taken
      const c = this.tileCentre(nx, ny);
      if (w.def.blocks) {
        this.penned.delete(`${w.tile[0]},${w.tile[1]}`);
        this.penned.add(`${nx},${ny}`);
      }
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

  stepWanderers(dt) {
    for (const w of this.wanderers) {
      const body = w.sprite.body;
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
      if (this.bagOpen) { this.sheetOpen = false; this.hero.setVelocity(0, 0); }
      this.pushSheet();
      return this.pushInventory();
    }
    if (name === 'sheet') {
      if (this.dialogue || this.busy) return;
      this.sheetOpen = !this.sheetOpen;
      if (this.sheetOpen) { this.bagOpen = false; this.hero.setVelocity(0, 0); }
      this.pushInventory();
      return this.pushSheet();
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
    for (const w of this.wanderers) {
      if (!inArc(w.sprite)) continue;
      this.flinch(w.sprite);
      this.startle(w, dir);
      this.floatDamage(w.sprite);
    }
    for (const h of this.hittable) {
      if (!inArc(h.sprite)) continue;
      this.flinch(h.sprite, true);
      this.floatDamage(h.sprite);
    }
  }

  /** A blow's worth: the weapon's damage, give or take a fifth. */
  rollDamage() {
    const base = this.damageDealt();
    return Math.max(1, Math.round(base * (0.8 + Math.random() * 0.4)));
  }

  /** The number drifts up off the thing that was hit and fades, with a few
   *  sparks thrown out round it. Digits are sprites from the fx atlas, so
   *  they are pixels of the same size as everything else, not blurred text. */
  floatDamage(target) {
    const n = this.rollDamage();
    this.addXp(n);
    this.hits = (this.hits || 0) + 1;
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
      if (!this.isWalkable(nx, ny)) continue;
      const c = this.tileCentre(nx, ny);
      w.tile = [nx, ny];
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
    return true;
  }

  /** Entry rules pick where a conversation starts: the first whose condition
   *  holds. A plain string is the common case - always start here. */
  entryNode(dlg) {
    if (typeof dlg.start === 'string') return dlg.start;
    const rule = (dlg.start || []).find((r) => this.test(r.when));
    return rule ? rule.goto : null;
  }

  openDialogue(id) {
    const dlg = M.dialogue[id];
    const node = this.entryNode(dlg);
    if (!node) return;
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
        this.openDialogue(this.nearest.def.interact);
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
    // take before give, so trading the last thing in a full bag still works
    if (choice.take) this.dropItem(choice.take);
    if (choice.give) this.giveItem(choice.give);
    if (choice.set) {
      this.flags.add(choice.set);
      this.pushInventory();                      // a flag can change a look
    }
    if (!choice.goto) return this.closeDialogue();
    this.gotoNode(choice.goto);
  }

  moveChoice(dy) {
    const d = this.dialogue;
    if (!d || !d.choices.length || d.line < d.node.text.length - 1) return;
    d.pick = (d.pick + dy + d.choices.length) % d.choices.length;
    this.renderDialogue();
  }

  /** Remove one of an item from the bag, unequipping it if it was in use. */
  dropItem(id) {
    const slot = this.inventory.indexOf(id);
    if (slot < 0) return;
    this.inventory[slot] = null;
    if (this.weapon === id) this.equip(null);
    else if (this.armor === id) this.wear(null);
    else this.pushInventory();
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
    const locked = talking || this.busy || this.bagOpen || this.sheetOpen;

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
    this.checkExit();
    if (this.travelling) return;          // the scene is on its way out

    if (window.__hud) {
      window.__hud({
        anim: shown.split('/').slice(1).join('-'),
        tile: this.heroTile(),
        prompt: !talking && best ? (best.def.name || best.id.split('.')[1]) : null,
        verb: best && best.item ? 'take' : 'talk',
        bagFull: !this.inventory.includes(null),
        talking,
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

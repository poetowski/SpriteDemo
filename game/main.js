/* Milestone 4: a real map, entities spawned from content definitions, and an
 * NPC you can talk to.
 *
 * This scene knows no art and no content. Every sprite, animation, tile, prop,
 * actor, dialogue line and map comes from window.ART.manifest, which
 * tools/build.py assembles from content/*.json and the generators. Nothing here
 * hardcodes a frame number, a tile index or a piece of text - which is also why
 * this file would port to another engine without touching content/.
 */

const M = ART.manifest;
const MAP_ID = 'map.riverside';
const VIEW_W = 320;
const VIEW_H = 240;

/** Origin that puts a sprite's authored anchor on its world position. */
function originOf(spriteKey) {
  const rec = M.sprites[spriteKey];
  const [fw, fh] = M.atlases[rec.atlas].frame;
  return { ox: rec.anchor[0] / fw, oy: rec.anchor[1] / fh, rec };
}

function defOf(id) {
  return M.props[id] || M.actors[id] || null;
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

  create() {
    const map = M.maps[MAP_ID];
    this.map = map;
    this.ts = map.tile_size;
    const [cols, rows] = map.size;

    for (const [key, a] of Object.entries(M.anims)) {
      this.anims.create({
        key,
        frames: a.frames.map((f) => ({ key: a.atlas, frame: f })),
        frameRate: 1000 / a.ms,
        repeat: -1,
      });
    }

    // --- ground ---------------------------------------------------------
    const grid = map.ground.map((row) =>
      [...row].map((ch) => M.tiles[map.legend[ch]].index));
    const tilemap = this.make.tilemap({
      data: grid, tileWidth: this.ts, tileHeight: this.ts,
    });
    const layer = tilemap.createLayer(0, tilemap.addTilesetImage('tileset'), 0, 0);
    layer.setDepth(-1000);
    const blocking = Object.values(M.tiles)
      .filter((t) => !t.walkable).map((t) => t.index);
    layer.setCollision(blocking);

    const worldW = cols * this.ts;
    const worldH = rows * this.ts;
    this.physics.world.setBounds(0, 0, worldW, worldH);
    this.cameras.main.setBounds(0, 0, worldW, worldH);

    // --- entities from the map's placement list --------------------------
    this.solid = this.physics.add.staticGroup();
    this.interactables = [];
    this.wanderers = [];
    this.blocked = new Set();
    for (const e of map.entities) {
      this.spawn(e.def, e.tile[0], e.tile[1]);
    }

    // --- player ----------------------------------------------------------
    const hero = M.actors['actor.hero'];
    const { ox, oy } = originOf(`${hero.sprite}/idle/down/0`);
    const p = this.tileCentre(map.spawn.tile[0], map.spawn.tile[1]);
    this.hero = this.physics.add.sprite(p.x, p.y, 'actors').setOrigin(ox, oy);
    this.hero.body.setSize(12, 8).setOffset(10, 21);   // feet, not the whole frame
    this.hero.setCollideWorldBounds(true);
    this.heroSprite = hero.sprite;
    this.speed = hero.speed;
    this.facing = map.spawn.facing;
    this.hero.anims.play(`${hero.sprite}/idle/${this.facing}`);

    this.physics.add.collider(this.hero, layer);
    this.physics.add.collider(this.hero, this.solid);
    this.cameras.main.startFollow(this.hero, true, 0.16, 0.16);

    // --- input ------------------------------------------------------------
    this.keys = this.input.keyboard.addKeys({
      up: 'UP', down: 'DOWN', left: 'LEFT', right: 'RIGHT',
      w: 'W', a: 'A', s: 'S', d: 'D', talk: 'E', space: 'SPACE', esc: 'ESC',
    });
    const axisOf = { up: 'y', down: 'y', w: 'y', s: 'y',
                     left: 'x', right: 'x', a: 'x', d: 'x' };
    this.lastAxis = 'y';
    for (const [name, key] of Object.entries(this.keys)) {
      if (axisOf[name]) key.on('down', () => { this.lastAxis = axisOf[name]; });
    }
    this.keys.talk.on('down', () => this.advanceDialogue());
    this.keys.space.on('down', () => this.advanceDialogue());
    this.keys.esc.on('down', () => this.closeDialogue());

    this.dialogue = null;
    this.nearest = null;
  }

  tileCentre(tx, ty) {
    return { x: tx * this.ts + this.ts / 2, y: ty * this.ts + this.ts / 2 };
  }

  /** Create one entity from its definition id, at a tile. */
  spawn(defId, tx, ty) {
    const def = defOf(defId);
    const isActor = !!M.actors[defId];
    const key = isActor ? `${def.sprite}/idle/${def.facing || 'down'}/0` : def.sprite;
    const { ox, oy, rec } = originOf(key);
    const p = this.tileCentre(tx, ty);

    const sprite = this.add.sprite(p.x, p.y, rec.atlas, rec.index).setOrigin(ox, oy);
    sprite.setDepth(p.y);
    if (isActor) sprite.play(`${def.sprite}/idle/${def.facing || 'down'}`);

    if (def.blocks) {
      const body = this.add.zone(p.x, p.y, this.ts, this.ts);
      this.physics.add.existing(body, true);
      this.solid.add(body);
      this.blocked.add(`${tx},${ty}`);
    }
    if (def.interact) {
      // position is read from the sprite, so a wandering animal stays talkable
      this.interactables.push({ id: defId, def, sprite });
    }
    if (def.wander) {
      this.wanderers.push({
        def, sprite, home: [tx, ty], tile: [tx, ty],
        facing: def.facing || 'down', state: 'idle', timer: 0,
        goalX: p.x, goalY: p.y,
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
      const c = this.tileCentre(nx, ny);
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
      if (w.state === 'walk') {
        const dx = w.goalX - w.sprite.x;
        const dy = w.goalY - w.sprite.y;
        const dist = Math.hypot(dx, dy);
        const step = (w.def.speed * dt) / 1000;
        if (dist <= step || dist === 0) {
          w.sprite.setPosition(w.goalX, w.goalY);
          this.pickWanderAction(w);
        } else {
          w.sprite.x += (dx / dist) * step;
          w.sprite.y += (dy / dist) * step;
        }
      } else {
        w.timer -= dt;
        if (w.timer <= 0) this.pickWanderAction(w);
      }
      const want = `${w.def.sprite}/${w.state}/${w.facing}`;
      const cur = w.sprite.anims.currentAnim && w.sprite.anims.currentAnim.key;
      if (cur !== want) w.sprite.play(want, true);
      w.sprite.setDepth(w.sprite.y);
    }
  }

  // --- dialogue ----------------------------------------------------------
  advanceDialogue() {
    if (this.dialogue) {
      this.dialogue.line += 1;
      if (this.dialogue.line >= this.dialogue.lines.length) return this.closeDialogue();
      return this.renderDialogue();
    }
    if (!this.nearest) return;
    const dlg = M.dialogue[this.nearest.def.interact];
    this.dialogue = { speaker: dlg.speaker, lines: dlg.lines, line: 0 };
    this.hero.setVelocity(0, 0);
    this.renderDialogue();
  }

  renderDialogue() {
    const d = this.dialogue;
    if (window.__dialogue) {
      window.__dialogue({
        speaker: d.speaker,
        text: d.lines[d.line],
        more: d.line < d.lines.length - 1,
      });
    }
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

    const left = !talking && (k.left.isDown || k.a.isDown || !!pad.left);
    const right = !talking && (k.right.isDown || k.d.isDown || !!pad.right);
    const up = !talking && (k.up.isDown || k.w.isDown || !!pad.up);
    const down = !talking && (k.down.isDown || k.s.isDown || !!pad.down);

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
    const want = `${this.heroSprite}/${moving ? 'walk' : 'idle'}/${this.facing}`;
    const cur = this.hero.anims.currentAnim && this.hero.anims.currentAnim.key;
    if (cur !== want) this.hero.anims.play(want, true);

    this.hero.setDepth(this.hero.y);        // anchor is at the feet, so y sorts

    // nearest thing worth pressing E at
    let best = null;
    let bestD = 26;
    for (const it of this.interactables) {
      const d = Phaser.Math.Distance.Between(
        this.hero.x, this.hero.y, it.sprite.x, it.sprite.y);
      if (d < bestD) { bestD = d; best = it; }
    }
    this.nearest = best;

    if (window.__hud) {
      window.__hud({
        anim: want.split('/').slice(1).join('-'),
        tile: [Math.floor(this.hero.x / this.ts), Math.floor(this.hero.y / this.ts)],
        prompt: !talking && best ? (best.def.name || best.id.split('.')[1]) : null,
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

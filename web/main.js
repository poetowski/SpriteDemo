/* Phaser 3 demo for the generated art.
 *
 * Everything the sprite needs - frame size, animation ranges and frame rates -
 * comes from window.ART in art-embed.js, which tools/build.py emits alongside
 * the .aseprite files. Re-running the build updates this scene; no frame index
 * is hand-copied into the game code.
 */

const WORLD_W = 320;
const WORLD_H = 240;
const SPEED = 70;              // world px per second

class DemoScene extends Phaser.Scene {
  preload() {
    // Data URIs, so the page also runs straight from file:// with no server.
    this.load.spritesheet('hero', ART.hero.image, {
      frameWidth: ART.hero.frameWidth,
      frameHeight: ART.hero.frameHeight,
    });
    Object.entries(ART.props).forEach(([name, uri]) => this.load.image(name, uri));
  }

  create() {
    this.add.tileSprite(0, 0, WORLD_W, WORLD_H, 'ground').setOrigin(0);

    ART.hero.anims.forEach((a) => {
      this.anims.create({
        key: a.key,
        // Per-frame `duration` is extra hold time on top of frameRate, which is
        // how a frame held longer in Aseprite survives into the game.
        frames: a.frames.map((f) => ({ key: 'hero', frame: f.frame, duration: f.duration })),
        frameRate: a.frameRate,
        repeat: a.repeat,
      });
    });

    this.bushes = this.physics.add.staticGroup();
    [[54, 70], [250, 62], [96, 186], [214, 170], [160, 110]].forEach(([x, y]) => {
      const b = this.bushes.create(x, y, 'bush');
      b.body.setSize(18, 7).setOffset(7, 23);   // only the base blocks movement
      b.setDepth(y);
    });

    this.hero = this.physics.add.sprite(160, 160, 'hero');
    this.hero.body.setSize(12, 8).setOffset(10, 21);   // feet box, not the head
    this.hero.setCollideWorldBounds(true);
    this.physics.add.collider(this.hero, this.bushes);

    this.facing = 'down';
    this.lastAxis = 'y';
    this.hero.anims.play('idle-down');

    this.keys = this.input.keyboard.addKeys({
      up: 'UP', down: 'DOWN', left: 'LEFT', right: 'RIGHT',
      w: 'W', a: 'A', s: 'S', d: 'D',
    });
    // Remember which axis was pressed last so diagonals keep a sensible facing.
    const axisOf = { up: 'y', down: 'y', w: 'y', s: 'y',
                     left: 'x', right: 'x', a: 'x', d: 'x' };
    Object.entries(this.keys).forEach(([name, key]) => {
      key.on('down', () => { this.lastAxis = axisOf[name]; });
    });
  }

  update() {
    const k = this.keys;
    const pad = window.__pad || {};        // on-screen d-pad, for touch
    const left = k.left.isDown || k.a.isDown || !!pad.left;
    const right = k.right.isDown || k.d.isDown || !!pad.right;
    const up = k.up.isDown || k.w.isDown || !!pad.up;
    const down = k.down.isDown || k.s.isDown || !!pad.down;

    let vx = (right ? 1 : 0) - (left ? 1 : 0);
    let vy = (down ? 1 : 0) - (up ? 1 : 0);
    if (vx && vy) {                       // keep diagonal speed equal to axial
      vx *= Math.SQRT1_2;
      vy *= Math.SQRT1_2;
    }
    this.hero.setVelocity(vx * SPEED, vy * SPEED);

    const moving = vx !== 0 || vy !== 0;
    if (moving) {
      const horizontal = vx !== 0 && (vy === 0 || this.lastAxis === 'x');
      this.facing = horizontal ? (vx < 0 ? 'left' : 'right')
                               : (vy < 0 ? 'up' : 'down');
    }
    const want = `${moving ? 'walk' : 'idle'}-${this.facing}`;
    const current = this.hero.anims.currentAnim && this.hero.anims.currentAnim.key;
    if (current !== want) this.hero.anims.play(want, true);

    this.hero.setDepth(this.hero.y);      // walk in front of / behind bushes
    if (window.__hud) {
      window.__hud({ anim: want, facing: this.facing, moving,
                     frame: Number(this.hero.frame.name) });
    }
  }
}

window.game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: WORLD_W,
  height: WORLD_H,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#4e7a3a',
  physics: { default: 'arcade', arcade: { debug: false } },
  scale: {
    mode: Phaser.Scale.FIT,        // the parent div caps the size; FIT keeps 4:3
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: DemoScene,
});

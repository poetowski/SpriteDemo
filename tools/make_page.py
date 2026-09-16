"""Bundle the demo into one self-contained HTML page.

    python tools/make_page.py        (also run at the end of tools/build.py)

Writes web/page.html: the same scene as web/index.html, but with the art, the
palette metadata and the scene code inlined, so the file can be hosted or shared
on its own. Phaser is the only external dependency, pinned on a CDN.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hero

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

TEMPLATE = r"""<title>Fourway Hero</title>
<meta name="description" content="A 32x32 pixel hero with four-direction walk and idle animations, generated from a parametric rig.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;450;600&family=Silkscreen:wght@400;700&display=swap">
<style>
  :root {
    --ground: #e9e6ee;
    --surface: #f8f6fb;
    --sunken: #ddd7e7;
    --ink: #241a2e;
    --muted: #6b6278;
    --line: #cdc6da;
    --accent: #3c7f41;
    --accent-bright: #4fa555;
    --blue: #3d5d94;
    --shadow: 0 1px 2px #241a2e14;
  }
  :root:not([data-theme="light"]) {
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground: #15111c;
      --surface: #241a2e;
      --sunken: #1c1526;
      --ink: #ece8f3;
      --muted: #9b92ab;
      --line: #3b3049;
      --accent: #74c46b;
      --accent-bright: #74c46b;
      --blue: #7d9bd3;
      --shadow: 0 1px 2px #0000003d;
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --ground: #15111c;
    --surface: #241a2e;
    --sunken: #1c1526;
    --ink: #ece8f3;
    --muted: #9b92ab;
    --line: #3b3049;
    --accent: #74c46b;
    --accent-bright: #74c46b;
    --blue: #7d9bd3;
    --shadow: 0 1px 2px #0000003d;
    color-scheme: dark;
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font: 450 15px/1.55 "IBM Plex Sans", system-ui, sans-serif;
  }
  .page {
    max-width: 1080px;
    margin: 0 auto;
    padding: 30px 20px 44px;
    display: flex;
    flex-direction: column;
    gap: 22px;
  }

  header { display: flex; flex-direction: column; gap: 7px; }
  .eyebrow {
    font-family: Silkscreen, "IBM Plex Mono", monospace;
    font-size: 10px;
    letter-spacing: .14em;
    color: var(--accent);
  }
  h1 {
    font-family: Silkscreen, "IBM Plex Mono", monospace;
    font-size: clamp(23px, 3.6vw, 33px);
    font-weight: 400;
    line-height: 1.15;
    margin: 0;
    text-wrap: balance;
  }
  .dek { max-width: 60ch; color: var(--muted); margin: 0; }

  .main {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(250px, 1fr);
    gap: 18px;
    align-items: start;
  }
  .stage-wrap { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
  .stage {
    position: relative;
    border: 1px solid var(--line);
    border-radius: 5px;
    overflow: hidden;
    background: #3f6330;
    box-shadow: var(--shadow);
  }
  #game { width: 100%; aspect-ratio: 4 / 3; }
  #game canvas { display: block; }

  .overlay {
    position: absolute;
    inset: 0;
    display: none;
    place-items: center;
    background: #150f1cb8;
    cursor: pointer;
  }
  .overlay.show { display: grid; }
  .overlay span {
    font-family: Silkscreen, monospace;
    font-size: 13px;
    color: #f2eff6;
    border: 1px solid #f2eff64d;
    border-radius: 4px;
    padding: 9px 15px;
    background: #241a2ecc;
  }

  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 14px;
    align-items: center;
    justify-content: space-between;
  }
  .keys { color: var(--muted); font-size: 13px; }
  kbd {
    font: 500 12px/1 "IBM Plex Mono", monospace;
    background: var(--surface);
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: 3px;
    padding: 3px 5px;
    color: var(--ink);
  }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip {
    display: flex;
    align-items: baseline;
    gap: 6px;
    border: 1px solid var(--line);
    background: var(--surface);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 10px;
    letter-spacing: .09em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .chip b {
    font: 400 12px/1 Silkscreen, monospace;
    letter-spacing: 0;
    text-transform: none;
    color: var(--accent);
  }

  .dpad { display: none; grid-template-columns: repeat(3, 42px); gap: 4px; }
  @media (pointer: coarse) { .dpad { display: grid; } }
  .dpad button {
    height: 42px;
    font-size: 15px;
    color: var(--ink);
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 4px;
    cursor: pointer;
    touch-action: none;
  }
  .dpad button.on { background: var(--accent-bright); color: #fff; }
  .dpad .sp { visibility: hidden; }

  .panel {
    border: 1px solid var(--line);
    background: var(--surface);
    border-radius: 5px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 11px;
    box-shadow: var(--shadow);
    min-width: 0;
  }
  .panel h2 {
    margin: 0;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .panel p { margin: 0; font-size: 13px; color: var(--muted); }

  .sheet {
    position: relative;
    width: 100%;
    aspect-ratio: 192 / 128;
    background: var(--sunken);
    border-radius: 3px;
  }
  .sheet img {
    width: 100%;
    height: 100%;
    display: block;
    image-rendering: pixelated;
  }
  #cursor {
    position: absolute;
    border: 2px solid var(--accent-bright);
    border-radius: 2px;
    box-shadow: 0 0 0 1px #241a2e66;
    transition: left .07s linear, top .07s linear;
  }
  @media (prefers-reduced-motion: reduce) { #cursor { transition: none; } }

  .details { display: grid; grid-template-columns: 1.15fr 1fr; gap: 18px; }
  @media (max-width: 880px) {
    .main, .details { grid-template-columns: 1fr; }
  }

  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th {
    text-align: left;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0 12px 6px 0;
    border-bottom: 1px solid var(--line);
  }
  td { padding: 5px 12px 5px 0; border-bottom: 1px solid var(--line); }
  tr:last-child td { border-bottom: 0; }
  .mono { font-family: "IBM Plex Mono", monospace; font-size: 12px; }
  .num { font-variant-numeric: tabular-nums; color: var(--muted); }
  td.tag { color: var(--accent); }

  .pal { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 7px 10px; }
  .sw { display: flex; align-items: center; gap: 7px; min-width: 0; }
  .sw i {
    flex: none;
    width: 15px;
    height: 15px;
    border-radius: 2px;
    /* neutral ring, so the near-black outline colour still reads as a chip
       on the dark panel and the pale skin tones read on the light one */
    box-shadow: 0 0 0 1px #8a829680;
  }
  .sw span { display: flex; flex-direction: column; min-width: 0; }
  .sw b { font-weight: 450; font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sw em {
    font: 400 10px/1.3 "IBM Plex Mono", monospace;
    font-style: normal;
    color: var(--muted);
  }

  footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 14px; }
  footer code { font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--ink); }
  a { color: var(--accent); }
  button:focus-visible, .overlay:focus-visible { outline: 2px solid var(--accent-bright); outline-offset: 2px; }
</style>

<div class="page">
  <header>
    <div class="eyebrow">32&times;32 &middot; 24 frames &middot; 8 tags &middot; 20 colours</div>
    <h1>Fourway Hero</h1>
    <p class="dek">A pixel hero with four-direction walk and idle cycles. Every
    frame is drawn by the same parametric rig, exported to a layered
    <code>.aseprite</code> file and a spritesheet, and played here by Phaser 3
    straight from that export.</p>
  </header>

  <div class="main">
    <div class="stage-wrap">
      <div class="stage">
        <div id="game"></div>
        <div class="overlay" id="overlay"><span>Click to play</span></div>
      </div>
      <div class="bar">
        <div class="keys">
          <kbd>&larr;</kbd> <kbd>&uarr;</kbd> <kbd>&darr;</kbd> <kbd>&rarr;</kbd>
          or <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> to move
        </div>
        <div class="chips">
          <div class="chip">facing <b id="st-facing">down</b></div>
          <div class="chip">clip <b id="st-anim">idle-down</b></div>
          <div class="chip">frame <b id="st-frame">04</b></div>
        </div>
      </div>
      <div class="dpad">
        <button class="sp" tabindex="-1"></button>
        <button data-dir="up" aria-label="Move up">&uarr;</button>
        <button class="sp" tabindex="-1"></button>
        <button data-dir="left" aria-label="Move left">&larr;</button>
        <button data-dir="down" aria-label="Move down">&darr;</button>
        <button data-dir="right" aria-label="Move right">&rarr;</button>
      </div>
    </div>

    <div class="panel">
      <h2>Sheet cursor</h2>
      <div class="sheet">
        <img id="sheet-img" alt="Hero spritesheet: one row per direction, walk then idle">
        <div id="cursor"></div>
      </div>
      <p>The box tracks the frame being drawn right now. One row per direction
      &mdash; down, left, right, up &mdash; four walk frames then two idle.</p>
    </div>
  </div>

  <div class="details">
    <div class="panel">
      <h2>Frame tags</h2>
      <div class="scroll">
        <table>
          <thead>
            <tr><th>Tag</th><th>Frames</th><th>Hold</th><th>Cycle</th></tr>
          </thead>
          <tbody id="tags"></tbody>
        </table>
      </div>
    </div>
    <div class="panel">
      <h2>Palette</h2>
      <div class="pal" id="palette"></div>
    </div>
  </div>

  <footer>
    Generated by a parametric rig: <code>draw_hero(direction, bob, leg, swing)</code>
    composes the same body-part functions for all 24 frames, so the character
    cannot drift between directions. Silhouette outlines are computed, not drawn.
  </footer>
</div>

<script src="https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"></script>
<script>/*__META__*/</script>
<script>/*__ART__*/</script>
<script>
(function () {
  const $ = (sel) => document.querySelector(sel);

  $('#sheet-img').src = ART.hero.image;
  const cursor = $('#cursor');
  cursor.style.width = (100 / META.cols) + '%';
  cursor.style.height = (100 / META.rows) + '%';

  const hold = {};
  ART.hero.anims.forEach((a) => { hold[a.key] = Math.round(1000 / a.frameRate); });
  $('#tags').innerHTML = META.tags.map((t) => {
    const n = t.to - t.from + 1;
    const kind = t.name.startsWith('walk')
      ? n + '-frame contact/passing' : n + '-frame breath';
    return '<tr><td class="mono tag">' + t.name + '</td>'
      + '<td class="mono num">' + t.from + '–' + t.to + '</td>'
      + '<td class="mono num">' + hold[t.name] + ' ms</td>'
      + '<td>' + kind + '</td></tr>';
  }).join('');

  $('#palette').innerHTML = META.palette.map((c) =>
    '<div class="sw"><i style="background:' + c.hex + ';opacity:' + c.alpha + '"></i>'
    + '<span><b>' + c.name + '</b><em>' + c.hex
    + (c.alpha < 1 ? ' · ' + Math.round(c.alpha * 100) + '%' : '')
    + '</em></span></div>').join('');

  // Live readout, called by the scene every frame.
  const facingEl = $('#st-facing'), animEl = $('#st-anim'), frameEl = $('#st-frame');
  window.__hud = ({ anim, facing, frame }) => {
    if (facingEl.textContent !== facing) facingEl.textContent = facing;
    if (animEl.textContent !== anim) animEl.textContent = anim;
    const n = String(frame).padStart(2, '0');
    if (frameEl.textContent !== n) {
      frameEl.textContent = n;
      cursor.style.left = ((frame % META.cols) * 100 / META.cols) + '%';
      cursor.style.top = (Math.floor(frame / META.cols) * 100 / META.rows) + '%';
    }
  };

  // On-screen pad, so the page is playable without a keyboard.
  window.__pad = {};
  document.querySelectorAll('.dpad button[data-dir]').forEach((b) => {
    const dir = b.dataset.dir;
    const set = (v) => (e) => {
      e.preventDefault();
      window.__pad[dir] = v;
      b.classList.toggle('on', v);
    };
    b.addEventListener('pointerdown', set(true));
    ['pointerup', 'pointerleave', 'pointercancel'].forEach((ev) =>
      b.addEventListener(ev, set(false)));
  });

  // Keyboard only reaches the game once this frame has focus.
  const overlay = $('#overlay');
  const hide = () => overlay.classList.remove('show');
  if (!document.hasFocus()) overlay.classList.add('show');
  document.addEventListener('pointerdown', hide);
  window.addEventListener('focus', hide);
  window.addEventListener('blur', () => overlay.classList.add('show'));
})();
</script>
<script>/*__SCENE__*/</script>
"""


def build():
    frames = hero.build_frames()
    meta = {
        "cols": hero.COLS,
        "rows": -(-len(frames) // hero.COLS),
        "tags": [{"name": n, "from": f, "to": t} for n, f, t in hero.build_tags()],
        "palette": [{
            "name": name,
            "hex": "#%02x%02x%02x" % rgba[:3],
            "alpha": round(rgba[3] / 255, 2),
        } for rgba, name in hero.PALETTE.values()],
    }
    with open(os.path.join(WEB, "art-embed.js"), encoding="utf-8") as fh:
        art = fh.read()
    with open(os.path.join(WEB, "main.js"), encoding="utf-8") as fh:
        scene = fh.read()

    html = (TEMPLATE
            .replace("/*__META__*/", "window.META = " + json.dumps(meta) + ";")
            .replace("/*__ART__*/", art)
            .replace("/*__SCENE__*/", scene))
    out = os.path.join(WEB, "page.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out, len(html.encode("utf-8"))


if __name__ == "__main__":
    path, size = build()
    print(f"web/page.html  {size:>8} B  (self-contained; Phaser from CDN)")

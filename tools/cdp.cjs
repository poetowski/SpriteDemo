/* A stand-in for Playwright's `chromium`, on top of an installed Chrome.
 *
 * tools/shot.cjs was written against Playwright. On a machine without it - a
 * developer's Windows box, say - this adapter drives whatever Chrome or Edge
 * is installed over the DevTools protocol and offers the slice of the
 * Playwright page API the script uses: goto, evaluate, waitForFunction,
 * waitForTimeout, keyboard.press, locator().screenshot, screenshot, and the
 * console / pageerror events. Nothing to install: Node 22+ has fetch and
 * WebSocket built in.
 *
 *   const { chromium } = require('./cdp.cjs');
 *   const browser = await chromium.launch();
 *   const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
 *
 * Set CHROME_PATH to point at a browser if the usual places do not have one.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function findChrome() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) {
    return process.env.CHROME_PATH;
  }
  const pf = process.env.ProgramFiles || 'C:/Program Files';
  const pf86 = process.env['ProgramFiles(x86)'] || 'C:/Program Files (x86)';
  const local = process.env.LOCALAPPDATA || '';
  const candidates = [
    path.join(pf, 'Google/Chrome/Application/chrome.exe'),
    path.join(pf86, 'Google/Chrome/Application/chrome.exe'),
    path.join(local, 'Google/Chrome/Application/chrome.exe'),
    path.join(pf86, 'Microsoft/Edge/Application/msedge.exe'),
    path.join(pf, 'Microsoft/Edge/Application/msedge.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium',
  ];
  const hit = candidates.find((p) => p && fs.existsSync(p));
  if (!hit) {
    throw new Error('no Chrome or Edge found; set CHROME_PATH to the browser executable');
  }
  return hit;
}

// Playwright key names -> DevTools key events. Letters and digits are derived.
const KEYS = {
  Space: { key: ' ', code: 'Space', vk: 32 },
  Enter: { key: 'Enter', code: 'Enter', vk: 13 },
  Escape: { key: 'Escape', code: 'Escape', vk: 27 },
  ArrowLeft: { key: 'ArrowLeft', code: 'ArrowLeft', vk: 37 },
  ArrowUp: { key: 'ArrowUp', code: 'ArrowUp', vk: 38 },
  ArrowRight: { key: 'ArrowRight', code: 'ArrowRight', vk: 39 },
  ArrowDown: { key: 'ArrowDown', code: 'ArrowDown', vk: 40 },
};

function keyOf(name) {
  if (KEYS[name]) return KEYS[name];
  if (/^Key[A-Z]$/.test(name)) {
    const ch = name[3];
    return { key: ch.toLowerCase(), code: name, vk: ch.charCodeAt(0) };
  }
  if (/^Digit[0-9]$/.test(name)) {
    const ch = name[5];
    return { key: ch, code: name, vk: ch.charCodeAt(0) };
  }
  return { key: name, code: name, vk: 0 };
}

class Page {
  constructor(send, events) {
    this.send = send;
    this.events = events;
    this.keyboard = {
      press: (k) => this.press(k),
      down: (k) => this.key('keyDown', k),      // held, for walking into things
      up: (k) => this.key('keyUp', k),
    };
  }

  on(event, cb) {
    (this.events[event] = this.events[event] || []).push(cb);
  }

  async goto(url) {
    const loaded = new Promise((r) => { this.events.__load = r; });
    await this.send('Page.navigate', { url });
    await Promise.race([loaded, sleep(8000)]);
  }

  async evaluate(fn, arg) {
    const src = typeof fn === 'function' ? fn.toString() : `() => (${fn})`;
    const expression = `(${src})(${arg === undefined ? '' : JSON.stringify(arg)})`;
    const r = await this.send('Runtime.evaluate', {
      expression, awaitPromise: true, returnByValue: true,
    });
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error((d.exception && d.exception.description) || d.text || 'evaluate failed');
    }
    return r.result ? r.result.value : undefined;
  }

  async waitForFunction(fn, arg, opts = {}) {
    const deadline = Date.now() + (opts.timeout || 30000);
    while (Date.now() < deadline) {
      if (await this.evaluate(fn, arg)) return true;
      await sleep(100);
    }
    throw new Error('waitForFunction: timed out');
  }

  waitForTimeout(ms) { return sleep(ms); }

  async key(type, name) {
    const k = keyOf(name);
    await this.send('Input.dispatchKeyEvent', {
      type, key: k.key, code: k.code,
      windowsVirtualKeyCode: k.vk, nativeVirtualKeyCode: k.vk,
    });
  }

  async press(name) {
    await this.key('keyDown', name);
    await sleep(40);
    await this.key('keyUp', name);
  }

  locator(selector) {
    return {
      screenshot: async ({ path: out }) => {
        const rect = await this.evaluate((sel) => {
          const el = document.querySelector(sel);
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { x: r.x, y: r.y, width: r.width, height: r.height };
        }, selector);
        if (!rect) throw new Error(`locator: nothing matches ${selector}`);
        await this.capture(out, { clip: { ...rect, scale: 1 } });
      },
    };
  }

  async screenshot({ path: out, fullPage } = {}) {
    if (!fullPage) return this.capture(out, {});
    const m = await this.send('Page.getLayoutMetrics');
    const size = m.cssContentSize || m.contentSize;
    await this.capture(out, {
      clip: { x: 0, y: 0, width: Math.ceil(size.width), height: Math.ceil(size.height), scale: 1 },
      captureBeyondViewport: true,
    });
  }

  async capture(out, params) {
    const shot = await this.send('Page.captureScreenshot', { format: 'png', ...params });
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));
  }
}

class Browser {
  constructor(proc, ws, profile) {
    this.proc = proc;
    this.ws = ws;
    this.profile = profile;
    this.nextId = 0;
    this.pending = new Map();
    this.events = {};
    ws.onmessage = (e) => this.dispatch(JSON.parse(e.data));
  }

  dispatch(m) {
    if (m.id && this.pending.has(m.id)) {
      const { resolve, reject } = this.pending.get(m.id);
      this.pending.delete(m.id);
      if (m.error) reject(new Error(m.error.message));
      else resolve(m.result || {});
      return;
    }
    if (m.method === 'Page.loadEventFired' && this.events.__load) {
      this.events.__load();
      delete this.events.__load;
    }
    if (m.method === 'Runtime.consoleAPICalled' && this.events.console) {
      const text = (m.params.args || []).map((a) => a.value !== undefined
        ? String(a.value) : (a.description || a.type)).join(' ');
      const msg = { type: () => m.params.type, text: () => text };
      this.events.console.forEach((cb) => cb(msg));
    }
    if (m.method === 'Runtime.exceptionThrown' && this.events.pageerror) {
      const d = m.params.exceptionDetails;
      const text = (d.exception && d.exception.description) || d.text;
      this.events.pageerror.forEach((cb) => cb(text));
    }
  }

  send(method, params = {}) {
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async newPage({ viewport } = {}) {
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    if (viewport) {
      await this.send('Emulation.setDeviceMetricsOverride', {
        width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: false,
      });
    }
    return new Page((m, p) => this.send(m, p), this.events);
  }

  async close() {
    try { this.ws.close(); } catch (e) { /* already gone */ }
    this.proc.kill();
    await sleep(150);
    fs.rmSync(this.profile, { recursive: true, force: true });
  }
}

const chromium = {
  async launch() {
    const exe = findChrome();
    const port = 9400 + Math.floor(Math.random() * 500);
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
    const proc = spawn(exe, [
      '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
      '--allow-file-access-from-files', '--window-size=1100,1000',
      `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
    ], { stdio: 'ignore' });
    let target = null;
    for (let i = 0; i < 80 && !target; i++) {
      await sleep(250);
      try {
        const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
        target = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      } catch (e) { /* not listening yet */ }
    }
    if (!target) {
      proc.kill();
      throw new Error(`Chrome at ${exe} never exposed DevTools on port ${port}`);
    }
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((r) => { ws.onopen = r; });
    return new Browser(proc, ws, profile);
  },
};

module.exports = { chromium, findChrome };

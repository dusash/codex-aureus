// CDP 截图工具：精确控制视口宽度 + 整页截图
// 用法: node shoot.mjs <fileUrl> <out.png> <w> <h> [view|full] [maxFullHeight]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
const [url, out, W = '1440', H = '1000', mode = 'view', maxFull = '2200'] = argv;
if (!url || !out) { console.error('usage: node shoot.mjs url out w h [view|full]'); process.exit(1); }

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port = 9300 + Math.floor(Math.random() * 600);
const profile = path.join(os.tmpdir(), 'edge-cdp-' + Date.now());

const child = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
  '--disable-extensions', '--disable-sync', '--no-default-browser-check',
  '--force-color-profile=srgb',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  '--window-size=1400,1000',
  url,
], { stdio: 'ignore', detached: false });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function pickTarget() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/list`, { redirect: 'error' });
      const list = await r.json();
      const t = list.find(x => x.type === 'page' && x.webSocketDebuggerUrl && !/^devtools/.test(x.url));
      if (t) return t;
    } catch { /* 还没起来 */ }
    await sleep(250);
  }
  throw new Error('CDP target not found');
}

class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener('message', ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)); } }, 30000);
    });
  }
}

const target = await pickTarget();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.addEventListener('open', res, { once: true });
  ws.addEventListener('error', rej, { once: true });
});
const cdp = new Cdp(ws);

await cdp.send('Page.enable');
await cdp.send('Runtime.enable');

const w = +W, h = +H;
await cdp.send('Emulation.setDeviceMetricsOverride', {
  width: w, height: h, deviceScaleFactor: 1, mobile: w <= 480,
});
// 等字体与图片就绪（Node 侧轮询，避免 awaitPromise 卡死）
let ready = false;
for (let i = 0; i < 60; i++) {
  try {
    const r = await cdp.send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        var im=Array.from(document.images);
        var pend=im.filter(function(x){return !x.complete}).length;
        var f=(document.fonts&&document.fonts.status)||'na';
        return document.readyState+'|'+im.length+'|'+pend+'|'+f;
      })()`,
    });
    const v = String(r.result.value || '');
    if (v.startsWith('complete|') && v.split('|')[2] === '0') { ready = true; break; }
  } catch { /* 继续等 */ }
  await sleep(350);
}
if (!ready) console.error('warn: page not fully ready, shooting anyway');
await sleep(800);

let shot;
if (mode === 'full') {
  // 先滚一遍，触发 IntersectionObserver 出场动画与懒加载图片
  const H = (await cdp.send('Runtime.evaluate', {
    returnByValue: true, expression: 'document.documentElement.scrollHeight',
  })).result.value;
  for (let y = 0; y <= H + 800; y += 620) {
    await cdp.send('Runtime.evaluate', { expression: `window.scrollTo(0,${y})` });
    await sleep(85);
  }
  await cdp.send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)' });
  await sleep(1000);

  const { contentSize } = await cdp.send('Page.getLayoutMetrics');
  const fullH = Math.ceil(contentSize.height);
  const scale = Math.min(1, (+maxFull) / fullH);
  ({ data: shot } = await cdp.send('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: w, height: fullH, scale },
  }));
  console.error(`full page ${w}x${fullH} -> scale ${scale.toFixed(3)}`);
} else {
  ({ data: shot } = await cdp.send('Page.captureScreenshot', { format: 'png' }));
}

fs.writeFileSync(out, Buffer.from(shot, 'base64'));
const info = await cdp.send('Runtime.evaluate', {
  returnByValue: true,
  expression: `JSON.stringify({vw:innerWidth,vh:innerHeight,docW:document.documentElement.scrollWidth,docH:document.documentElement.scrollHeight})`,
});
console.log(info.result.value);

ws.close();
child.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(0);

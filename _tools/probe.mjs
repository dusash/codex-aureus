// 运行时体检：捕获控制台报错/异常，并模拟点击 3 个交互按钮
import { spawn } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';

const url = process.argv[2];
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port = 9700 + Math.floor(Math.random() * 200);
const profile = path.join(os.tmpdir(), 'edge-probe-' + Date.now());
const sleep = ms => new Promise(r => setTimeout(r, ms));

const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
  '--autoplay-policy=no-user-gesture-required',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  '--window-size=1400,1000', url], { stdio: 'ignore' });

let t = null;
for (let i = 0; i < 80 && !t; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`, { redirect: 'error' })).json();
    t = list.find(x => x.type === 'page' && x.webSocketDebuggerUrl);
  } catch {}
  if (!t) await sleep(250);
}
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));

const problems = [];
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') {
    problems.push('EXCEPTION: ' + (m.params.exceptionDetails?.exception?.description ||
      m.params.exceptionDetails?.text));
  }
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) {
    problems.push(m.params.type.toUpperCase() + ': ' +
      m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
  }
});
const send = (method, params = {}) => new Promise(r => {
  const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
});

await send('Runtime.enable');
await send('Page.enable');
await sleep(2500);

const evalJS = async (expr) => (await send('Runtime.evaluate', { returnByValue: true, expression: expr })).result?.value;

const checks = [];
const check = async (name, expression) => {
  const value = await evalJS(expression);
  checks.push({name, passed:value === true, value});
  console.log(name + ':', value);
};
const waitTurn = () => sleep(420);
try {
  await check('仅显示序章', 'document.querySelectorAll(".reader .sheet:not([hidden])").length===1 && !document.getElementById("prologue").hidden');
  for (const width of [1440, 768, 375, 320]) {
    await send('Emulation.setDeviceMetricsOverride', {width, height:900, deviceScaleFactor:1, mobile:false});
    for (const section of ['prologue','relics','chronicle','colophon']) {
      await evalJS(`document.getElementById('tab-${section}').click()`);
      await waitTurn();
      await check(`${width}px ${section} 无溢出`, 'document.documentElement.scrollWidth <= innerWidth');
      await check(`${width}px ${section} 导航选中`, `document.getElementById('tab-${section}').getAttribute('aria-selected')==='true' && !document.getElementById('${section}').hidden`);
      await check(`${width}px ${section} 标题无遮挡`, `document.getElementById('${section}').getBoundingClientRect().top >= document.querySelector('.reader-nav').getBoundingClientRect().bottom - 1`);
    }
  }
  await evalJS("document.getElementById('tab-prologue').click();document.getElementById('tab-relics').click();document.getElementById('tab-chronicle').click();document.getElementById('tab-colophon').click()");
  await waitTurn();
  await check('快速连点保持最后选择', "!document.getElementById('colophon').hidden && document.querySelectorAll('.reader .sheet:not([hidden])').length===1 && document.getAnimations().filter(a=>a.effect.target.classList.contains('sheet')).length===0");
  await evalJS("document.getElementById('tab-prologue').click()"); await waitTurn();
  await evalJS("document.getElementById('tab-relics').click()"); await waitTurn();
  await evalJS('history.back()'); await waitTurn();
  await check('后退恢复序章', "!document.getElementById('prologue').hidden");
  await evalJS('history.forward()'); await waitTurn();
  await check('前进恢复圣物', "!document.getElementById('relics').hidden");
  await evalJS("document.getElementById('tab-relics').focus()");
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight'});
  await waitTurn();
  await check('键盘切换纪年', "!document.getElementById('chronicle').hidden && document.activeElement.id==='tab-chronicle'");
  await evalJS("document.getElementById('nextChapter').click()"); await waitTurn();
  await check('下一章与焦点交接', "document.activeElement.id==='colophon' && document.getElementById('nextChapter').disabled");
  await evalJS("document.getElementById('prevChapter').click()"); await waitTurn();
  await check('上一章', "!document.getElementById('chronicle').hidden");
  await send('Emulation.setEmulatedMedia', {features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await evalJS("document.getElementById('tab-relics').click()"); await sleep(50);
  await check('减少动态效果立即切换', "!document.getElementById('relics').hidden && document.getAnimations().length===0");
  await evalJS("document.querySelector('.relics').focus()");
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight'});
  await sleep(60);
  await check('手机画廊键盘横向浏览', "document.querySelector('.relics').scrollLeft>100");
  await send('Emulation.setEmulatedMedia', {media:'print',features:[]});
  await check('打印包含全部章节', "Array.from(document.querySelectorAll('.reader .sheet')).every(p=>getComputedStyle(p).display!=='none')");
  await send('Emulation.setEmulatedMedia', {media:'',features:[]});
  await evalJS("document.getElementById('tab-colophon').click()"); await waitTurn();
  await evalJS("document.getElementById('seal').click()");
  await check('火漆提示', "document.getElementById('toast').classList.contains('show')");
  await evalJS("document.getElementById('btnCandle').click()");
  await check('烛光反馈', "document.body.classList.contains('candle')");
  await evalJS("document.getElementById('btnCandle').click()");
  await evalJS("document.getElementById('btnChant').click()"); await sleep(100);
  await check('圣咏可开启', "document.getElementById('btnChant').getAttribute('aria-pressed')==='true'");
  await evalJS("document.getElementById('btnChant').click()");
  await check('圣咏可关闭', "document.getElementById('btnChant').getAttribute('aria-pressed')==='false'");
  await send('Page.navigate', {url:url+'#chronicle'}); await sleep(500);
  await check('直达链接显示纪年', "!document.getElementById('chronicle').hidden");
  await send('Emulation.setScriptExecutionDisabled',{value:true});
  await send('Page.navigate', {url}); await sleep(500);
  await check('无脚本保留完整内容', "Array.from(document.querySelectorAll('.reader .sheet')).every(p=>!p.hidden && getComputedStyle(p).display!=='none')");
  await send('Emulation.setScriptExecutionDisabled',{value:false});
  await send('Page.navigate', {url}); await sleep(500);
  const fs = await import('node:fs');
  const out = 'C:/Users/ash/WorkBuddy/2026-10-15-22-48-30/outputs';
  for (const [width,section,name] of [[1440,'prologue','desktop'],[375,'relics','mobile']]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
    await evalJS(`document.getElementById('tab-${section}').click()`); await waitTurn();
    if (width===1440) await evalJS("window.scrollTo({top:0,behavior:'instant'})");
    await sleep(200);
    const image = await send('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync(out+'/'+name+'.png',Buffer.from(image.data,'base64'));
  }
  await check('无运行时异常', problems.length ? 'false' : 'true');
  fs.writeFileSync(out+'/validation.json',JSON.stringify({checks,problems},null,2));
  if(checks.some(c=>!c.passed)) process.exitCode=1;
} finally { ws.close(); child.kill(); }
console.log('检查结果:', checks.filter(c=>c.passed).length+'/'+checks.length);
process.exit(process.exitCode || 0);


// 3D workbench smoke test: plays Blink in real Chrome on the three.js bench —
// drags parts from the tray into exact holes, runs wires from single holes to
// header sockets, presses Check each step, final check (LED must glow),
// hovers a single hole, opens the 3D inspector. Screenshots go to argv[2].
//   npm i puppeteer-core ; CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_3d_smoke.js /tmp/shots
const puppeteer = require('puppeteer-core');
let browserRef = null;
const out = process.argv[2];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = browserRef = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 120000,
    args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  const page = await browser.newPage(); await page.setViewport({width: 1440, height: 900});
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8799) + '/', {waitUntil: 'networkidle0'});
  await page.waitForFunction(() => window.__bench3d, {timeout: 30000, polling: 500});
  await page.evaluate(async () => { const m = await import('/bench/app.js'); await m.bench.start('blink', 'beginner'); document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== 'lessonScreen'); });
  await sleep(2500);
  await page.evaluate(() => window.__bench3d.B.view('top')); await sleep(700);
  const hole = (h) => page.evaluate((h) => window.__bench3d.B.toScreen(window.__bench3d.B.holeWorld(h)), h);
  const pin = (p) => page.evaluate((p) => window.__bench3d.B.toScreen(window.__bench3d.B.boardPinWorld(p)), p);
  const picks = (pt) => page.evaluate((pt) => { const p = window.__bench3d.B.pick(pt.x, pt.y); return p.kind + ':' + (p.hole || p.pin || p.id || ''); }, pt);
  const tray = (id) => page.evaluate((id) => { const it = [...document.querySelectorAll('.tray-item')].find(i => i.dataset.part === id); const r = it.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }, id);
  const dragTo = async (a, b) => { await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, {steps: 6}); await page.mouse.move(b.x, b.y, {steps: 6}); await page.mouse.up(); await sleep(400); };
  const check = async () => { await page.click('#checkBtn'); await sleep(900); return page.evaluate(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ')); };
  const clip = () => page.evaluate(() => document.getElementById('stepClip').innerText.replace(/\s+/g, ' '));
  console.log('tray:', await page.evaluate(() => [...document.querySelectorAll('.tray-item')].map(i => i.dataset.part + (i.querySelector('img') ? '[3d]' : ''))));
  console.log('pick 3b.h ->', await picks(await hole('3b.h')), '| pick 13 ->', await picks(await pin('13')), '| pick 4b.h ->', await picks(await hole('4b.h')));
  // hover one hole: only it lights up
  await page.mouse.move((await hole('12t.c')).x, (await hole('12t.c')).y); await sleep(250);
  console.log('hover tip:', await page.evaluate(() => document.getElementById('tip').innerText.replace(/\s+/g, ' ')));
  await page.screenshot({path: out + '/3d_01_top_hover.png'});
  console.log('STEP:', await clip());
  await dragTo(await tray('r1'), await hole('3b.h'));
  console.log('r1 legs:', await page.evaluate(() => JSON.stringify(window.__bench3d.S.placed.r1 && window.__bench3d.S.placed.r1.legs)));
  console.log('check ->', await check());
  console.log('STEP:', await clip());
  await dragTo(await hole('3b.j'), await pin('13'));
  console.log('wires:', await page.evaluate(() => JSON.stringify(window.__bench3d.S.wires)));
  console.log('check ->', await check());
  console.log('STEP:', await clip());
  const r2 = await page.evaluate(() => window.__bench3d.S.placed.r1.legs['2']);
  const col = parseInt(r2);
  await dragTo(await tray('led1'), await hole(`${col}b.f`));
  console.log('led legs:', await page.evaluate(() => JSON.stringify(window.__bench3d.S.placed.led1 && window.__bench3d.S.placed.led1.legs)));
  console.log('check ->', await check());
  console.log('STEP:', await clip());
  const c = await page.evaluate(() => window.__bench3d.S.placed.led1.legs.C);
  await dragTo(await hole(c.replace(/\.f$/, '.j')), await pin('GND.1'));
  console.log('check ->', await check());
  console.log('STEP:', await clip());
  await page.click('#finishBtn'); await sleep(1400);
  console.log('final ->', await page.evaluate(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ')));
  console.log('LED glowing:', await page.evaluate(() => { let lit = false; window.__bench3d.B.parts.led1.traverse(o => { if (o.isPointLight && o.intensity > 0) lit = true; }); return lit; }));
  await page.evaluate(() => window.__bench3d.B.view('3d')); await sleep(900);
  await page.screenshot({path: out + '/3d_02_done.png'});
  // close-up
  await page.evaluate(() => { const B = window.__bench3d.B; const t = B.holeWorld('5b.f'); B.controls.target.copy(t); B.camera.position.set(t.x + 30, t.y + 45, t.z + 60); }); await sleep(900);
  await page.screenshot({path: out + '/3d_03_closeup.png'});
  await page.evaluate(() => { const B = window.__bench3d.B; const t = B.board.position.clone().add(new window.__bench3d.THREE.Vector3(34, 0, 26)); B.controls.target.copy(t); B.camera.position.set(t.x - 40, t.y + 70, t.z + 80); }); await sleep(900);
  await page.screenshot({path: out + '/3d_04_uno.png'});
  // inspector
  await page.evaluate(() => { document.querySelector('.tray-item[data-part="led1"]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true})); }); await sleep(1500);
  console.log('inspector:', await page.evaluate(() => !document.getElementById('inspector').hidden && document.getElementById('inspInfo').innerText.slice(0, 160).replace(/\s+/g, ' ')));
  await page.screenshot({path: out + '/3d_05_inspector.png'});
  console.log('ERRORS:', errors);
  await browser.close();
})().catch(async (e) => { console.log('TEST ERROR', e); if (browserRef) await browserRef.close().catch(() => {}); process.exit(1); });

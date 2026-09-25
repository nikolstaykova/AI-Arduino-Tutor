// PIR smoke test (real Chrome): plays Motion Alarm on the 3D bench — the PIR
// module goes into three columns, power + OUT wires, then the LED circuit;
// final check; then clicking the sensor's dome ("waving") must make the
// physics read motion on pin 2 for a few seconds.
//   CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_pir_smoke.js /tmp/shots
const puppeteer = require('puppeteer-core');
const out = process.argv[2];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 120000,
    args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  try {
    const page = await browser.newPage(); await page.setViewport({width: 1440, height: 900});
    const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto('http://localhost:' + (process.env.PORT || 8799) + '/', {waitUntil: 'networkidle0'});
    await page.waitForFunction(() => window.__bench3d, {timeout: 30000, polling: 500});
    await page.evaluate(async () => { const m = await import('/bench/app.js'); await m.bench.start('motion-alarm', 'beginner'); document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== 'lessonScreen'); });
    await sleep(2500);
    await page.evaluate(() => window.__bench3d.B.view('top')); await sleep(700);
    const hole = (h) => page.evaluate((h) => window.__bench3d.B.toScreen(window.__bench3d.B.holeWorld(h)), h);
    const pin = (p) => page.evaluate((p) => window.__bench3d.B.toScreen(window.__bench3d.B.boardPinWorld(p)), p);
    const tray = (id) => page.evaluate((id) => { const it = [...document.querySelectorAll('.tray-item')].find(i => i.dataset.part === id); const r = it.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }, id);
    const dragTo = async (a, b) => { await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, {steps: 6}); await page.mouse.move(b.x, b.y, {steps: 6}); await page.mouse.up(); await sleep(500); };
    const check = async () => { await page.click('#checkBtn'); await sleep(900); return page.evaluate(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ')); };
    console.log('tray:', await page.evaluate(() => [...document.querySelectorAll('.tray-item')].map(i => i.dataset.part)));
    await dragTo(await tray('pir1'), await hole('20t.c'));
    console.log('pir legs:', await page.evaluate(() => JSON.stringify(window.__bench3d.S.placed.pir1 && window.__bench3d.S.placed.pir1.legs)));
    console.log('1 ->', await check());
    const picks = (pt) => page.evaluate((pt) => { const p = window.__bench3d.B.pick(pt.x, pt.y); return p.kind + ':' + (p.hole || p.pin || p.id || ''); }, pt);
    // wires via the test hook (dragging wires by hand is covered by ui_3d_smoke; near the screen's
    // edge the camera turns while you drag, which would move the target under a scripted mouse)
    const wire = (a, b) => page.evaluate((a, b) => window.__bench3d.addWire(a, b), a, b);
    await wire('bb:20t.e', 'uno:5V'); console.log('2 ->', await check());
    await wire('bb:22t.e', 'uno:GND.2'); console.log('3 ->', await check());
    await wire('bb:21t.d', 'uno:2'); console.log('4 ->', await check());
    await dragTo(await tray('r1'), await hole('3b.h')); console.log('5 ->', await check());
    await wire('bb:3b.j', 'uno:13'); console.log('6 ->', await check());
    const col = parseInt(await page.evaluate(() => window.__bench3d.S.placed.r1.legs['2']));
    await dragTo(await tray('led1'), await hole(`${col}b.f`)); console.log('7 ->', await check());
    const c = await page.evaluate(() => window.__bench3d.S.placed.led1.legs.C);
    await wire('bb:' + c.replace(/\.f$/, '.j'), 'uno:GND.1'); console.log('8 ->', await check());
    await page.click('#finishBtn'); await sleep(1400);
    console.log('final ->', await page.evaluate(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ').slice(0, 120)));
    const physics = () => page.evaluate(() => (document.getElementById('physicsBody')).innerText.match(/pir1: [^\n]+|uno:2 reads \w+/g));
    console.log('still:', await physics());
    await page.evaluate(() => window.__bench3d.B.view('3d')); await sleep(800);
    // wave: click the dome
    await page.evaluate(() => { const B = window.__bench3d.B; const g = B.parts.pir1; let dome; g.traverse(o => { if (o.userData.kind === 'pir' && o.geometry && o.geometry.type === 'SphereGeometry') dome = o; });
      const v = new window.__bench3d.THREE.Vector3(); dome.getWorldPosition(v); v.y += 6; window.__domePt = B.toScreen(v); });
    const d = await page.evaluate(() => window.__domePt);
    await page.mouse.click(d.x, d.y); await sleep(700);
    console.log('after wave:', await physics(), '| toast:', await page.evaluate(() => document.getElementById('toast').innerText));
    await page.screenshot({path: out + '/pir_wave.png'});
    await sleep(5600);
    console.log('5 s later:', await physics());
    console.log('ERRORS:', errors);
  } catch (e) { console.log('TEST ERROR', e); } finally { await browser.close(); }
})();

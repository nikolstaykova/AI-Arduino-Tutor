// No-breadboard + Learn-map smoke test (real Chrome):
//  1. Home → Learn → the quick parts chat ("No breadboard") → map with coloured levels
//  2. Blink's level card offers every build way; pick "Clip leads"
//  3. Play Blink with parts on the table: legs clipped to header pins / each other → complete, LED glows
//   npm i puppeteer-core ; CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_nobb_smoke.js /tmp/shots
const puppeteer = require('puppeteer-core');
let browserRef = null;
const out = process.argv[2];
const JOIN = process.env.JOIN || 'clips';     // clips | twist | solder
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = browserRef = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 120000, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  const page = await browser.newPage(); await page.setViewport({width: 1440, height: 900});
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8799) + '/', {waitUntil: 'networkidle0'});
  await page.evaluate(() => localStorage.removeItem('cq.parts'));
  await page.reload({waitUntil: 'networkidle0'});
  await page.waitForSelector('.choice', {timeout: 30000, polling: 500}); await sleep(500);
  const pick = (text) => page.evaluate((t) => [...document.querySelectorAll('.choice')].find(c => c.innerText.includes(t)).click(), text);
  await pick('Learn'); await sleep(500);
  console.log('parts question:', await page.evaluate(() => document.getElementById('homeQ').innerText));
  console.log('choices:', await page.evaluate(() => [...document.querySelectorAll('.choice')].map(c => c.innerText.split('\n')[0])));
  await page.screenshot({path: out + '/n1_parts_chat.png'});
  await pick('No breadboard'); await page.waitForFunction(() => document.getElementById('partsDrawer').classList.contains('open'), {polling: 200, timeout: 5000}).catch(() => {});
  console.log('drawer open:', await page.evaluate(() => document.getElementById('partsDrawer').classList.contains('open')), '|', await page.evaluate(() => document.getElementById('drawerNote').innerText.slice(0, 60)));
  for (const want of ['LED', '1kΩ', 'Alligator']) await page.evaluate((w) => { const t = [...document.querySelectorAll('.ptile')].find(t => t.querySelector('.nm').textContent.includes(w)); t && t.click(); }, want);
  await sleep(1400);
  console.log('matches:', await page.evaluate(() => [...document.querySelectorAll('.match')].map(m => m.innerText.replace(/\n/g, ' '))));
  await page.screenshot({path: out + '/n2_drawer.png'});
  await page.click('#closeParts'); await sleep(600);
  console.log('tiles:', await page.evaluate(() => [...document.querySelectorAll('.tile[data-id]')].map(t => t.dataset.id + ':' + [...t.classList].filter(c => ['ready', 'sub', 'need', 'done'].includes(c)).join('') + ' ' + (t.querySelector('.ribbon') || {}).textContent)));
  await page.screenshot({path: out + '/n3_map.png'});
  await page.evaluate(() => document.querySelector('.tile[data-id="blink"]').click()); await sleep(2500);
  const segs = () => page.evaluate(() => [...document.querySelectorAll('#popWays .seg button')].map(b => b.innerText.trim() + (b.getAttribute('aria-pressed') === 'true' ? ' [chosen]' : '') + (b.querySelector('.dot.own') ? ' (have all)' : '')));
  console.log('build choice:', await segs());
  await page.evaluate(() => [...document.querySelectorAll('#segMethod button')].find(b => b.innerText.includes('No breadboard')).click()); await sleep(200);
  await page.evaluate((join) => document.querySelector(`#segJoin button[data-way="${join}"]`).click(), JOIN); await sleep(300);
  console.log('after picking clip leads:', await segs(), '|', await page.evaluate(() => document.querySelector('.way-explain').innerText));
  console.log('plan:', await page.evaluate(() => document.getElementById('popPlan').innerText.replace(/\n+/g, ' | ').slice(0, 400)));
  await page.screenshot({path: out + '/n4_ways.png'});
  await page.click('#popStart'); await sleep(3500);
  console.log('title:', await page.evaluate(() => document.getElementById('brandSub').textContent), '| tray hint:', await page.evaluate(() => document.getElementById('trayTitle').textContent));
  console.log('steps:', await page.evaluate(() => document.getElementById('stepClip').innerText));
  await page.evaluate(() => window.__bench3d.B.view('top')); await sleep(700);
  const T = (js, arg) => page.evaluate(js, arg);
  const tray = (id) => T((id) => { const r = document.querySelector(`.tray-item[data-part="${id}"]`).getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }, id);
  const tableAt = (x, z) => T(([x, z]) => { const W = window.__bench3d; return W.B.toScreen(new W.THREE.Vector3(x, 0, z)); }, [x, z]);
  const pin = (p) => T((p) => window.__bench3d.B.toScreen(window.__bench3d.B.boardPinWorld(p)), p);
  const leg = (id, p) => T(([id, p]) => window.__bench3d.B.toScreen(window.__bench3d.B.partPinWorld(id, p)), [id, p]);
  const drag = async (a, b) => { await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, {steps: 6}); await page.mouse.move(b.x, b.y, {steps: 6}); await page.mouse.up(); await sleep(400); };
  const check = async () => { await page.click('#checkBtn'); await sleep(900); return T(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ')); };
  await drag(await tray('r1'), await tableAt(-20, -30));
  await drag(await tray('led1'), await tableAt(15, -30));
  console.log('placed:', await T(() => Object.keys(window.__bench3d.S.placed)), '| pick r1:1 ->', await T((pt) => { const p = window.__bench3d.B.pick(pt.x, pt.y); return p.kind + ':' + (p.id || '') + ':' + (p.pin || ''); }, await leg('r1', '1')));
  await drag(await leg('r1', '1'), await pin('13'));
  console.log('1 ->', await check(), '|', await T(() => document.getElementById('stepClip').innerText.slice(0, 90)));
  await drag(await leg('led1', 'A'), await leg('r1', '2'));
  console.log('2 ->', await check(), '|', await T(() => document.getElementById('stepClip').innerText.slice(0, 90)));
  await drag(await leg('led1', 'C'), await pin('GND.1'));
  console.log('3 ->', await check());
  console.log('links:', await T(() => JSON.stringify(window.__bench3d.S.wires.map(w => w.a + '~' + w.b + ' [' + w.kind + ']'))));
  await page.click('#finishBtn'); await sleep(1500);
  console.log('final ->', await T(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ').slice(0, 120)));
  console.log('LED glowing:', await T(() => { let lit = false; window.__bench3d.B.parts.led1.traverse(o => { if (o.isPointLight && o.intensity > 0) lit = true; }); return lit; }));
  await sleep(3500); await page.evaluate(() => { document.querySelectorAll('.modal').forEach(m => m.hidden = true); const B = window.__bench3d.B; B.view('3d'); }); await sleep(900);
  await page.screenshot({path: out + '/n5_nobb_done.png'});
  await page.evaluate(() => { const W = window.__bench3d, B = W.B, t = new W.THREE.Vector3(0, 0, -25); B.controls.target.copy(t); B.camera.position.set(25, 45, 40); }); await sleep(900);
  await page.screenshot({path: out + `/n6_nobb_close_${JOIN}.png`});
  console.log('ERRORS:', errors);
  await browser.close();
})().catch(async (e) => { console.log('TEST ERROR', e); if (browserRef) await browserRef.close().catch(() => {}); process.exit(1); });

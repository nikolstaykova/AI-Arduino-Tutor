// "Reveal step" smoke test (real Chrome): Digital Read Serial — reveal before placing the
// button (red dots where its legs go), then on the 5V step (a free hole in the button's
// column + the 5V socket + a dashed wire line), then on the resistor step.
//   CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_reveal_smoke.js /tmp/shots
const puppeteer = require('puppeteer-core');
let browserRef = null;
const out = process.argv[2];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = browserRef = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 120000, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  const page = await browser.newPage(); await page.setViewport({width: 1440, height: 900});
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://localhost:' + (process.env.PORT || 8799) + '/', {waitUntil: 'networkidle0'});
  await page.waitForFunction(() => window.__bench3d, {polling: 300, timeout: 30000});
  await page.evaluate(async () => { const m = await import('/bench/app.js'); await m.bench.start('digital-read-serial', 'beginner'); document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== 'lessonScreen'); });
  await sleep(2500);
  const reveal = async (name) => {
    await page.click('#revealBtn'); await sleep(900);
    const labels = await page.evaluate(() => [...document.querySelectorAll('.reveal-label')].map(l => l.textContent));
    const lines = await page.evaluate(() => window.__bench3d.B.reveal ? window.__bench3d.B.reveal.children.filter(o => o.isLine).length : 0);
    console.log(`${name}: step "${await page.evaluate(() => document.getElementById('stepClip').innerText.slice(0, 60))}" -> markers`, labels, '| wire lines', lines);
    await page.screenshot({path: `${out}/reveal_${name}.png`});
  };
  await page.evaluate(() => window.__bench3d.B.view('top')); await sleep(600);
  await reveal('1_place_button');
  await page.evaluate(() => window.__bench3d.placePart('btn1', '8t.e', 0)); await sleep(400);
  await page.click('#checkBtn'); await sleep(900);
  await reveal('2_wire_5v');
  await page.evaluate(() => window.__bench3d.addWire('bb:10b.h', 'uno:5V')); await page.click('#checkBtn'); await sleep(900);
  await page.evaluate(() => window.__bench3d.addWire('bb:8b.h', 'uno:2')); await page.click('#checkBtn'); await sleep(900);
  await reveal('3_resistor');
  console.log('feedback:', await page.evaluate(() => document.getElementById('feedback').innerText.replace(/\s+/g, ' ').slice(0, 80)));
  console.log('ERRORS:', errors);
  await browser.close();
})().catch(async (e) => { console.log('TEST ERROR', e); if (browserRef) await browserRef.close().catch(() => {}); process.exit(1); });

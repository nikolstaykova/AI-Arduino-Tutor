// Every lesson, played on the real 3D bench (real Chrome): start it, put each
// part where the lesson's own circuit puts it and every wire where it goes,
// then Final check — it must complete. Catches lessons the validator likes but
// the table can't build (holes, rails, board sizes, leg layouts).
//   CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_all_lessons_smoke.js [lesson ids…]
const puppeteer = require('puppeteer-core');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 180000,
    args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  let failed = 0;
  try {
    const errors = [];
    const url = 'http://localhost:' + (process.env.PORT || 8799) + '/';
    let page = await browser.newPage(); await page.goto(url, {waitUntil: 'networkidle0'});
    // default: the lesson-kit lessons (laid out to match the 3D parts' real leg spacing)
    const ids = process.argv.slice(2).length ? process.argv.slice(2) : require('child_process')
      .execSync('python3 -c "from tools.lessons_spec import LESSONS; print(\\" \\".join(m().id for m in LESSONS))"', {cwd: __dirname + '/..'}).toString().trim().split(' ');
    for (const id of ids) {
      // a fresh page per lesson: each one starts from a clean table
      await page.close(); page = await browser.newPage(); await page.setViewport({width: 1280, height: 800});
      page.on('pageerror', e => errors.push(`${id}: ${e.message}`));
      await page.goto(url, {waitUntil: 'networkidle0'});
      await page.waitForFunction(() => window.__bench3d, {timeout: 30000, polling: 500});
      if (process.env.DEBUG_LEGS) await page.evaluate(() => { window.DEBUG_LEGS = true; });
      const verdict = await page.evaluate(async (id) => {
        const m = await import('/bench/app.js'); await m.bench.start(id, 'beginner');
        document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== 'lessonScreen');
        await new Promise(r => setTimeout(r, 1200));
        const T = window.__bench3d, bb = T.G.bbId, board = T.G.boardId, ref = T.S.reference;
        if (!bb) return 'no breadboard (skipped)';
        const holeOf = (end) => { const f = ref.find(([a, b]) => a === end || b === end); if (!f) return null; const o = f[0] === end ? f[1] : f[0]; return o.startsWith(bb + ':') ? o.slice(bb.length + 1) : null; };
        for (const d of T.S.trayParts) {                       // each part: its first leg's hole
          const pins = Object.keys(T.S.placed[d.id] ? T.S.placed[d.id].legs : {});
          const first = (window.__firstPins || {})[d.id];
          const cand = ref.map(([a, b]) => [a, b].find(e => e.startsWith(d.id + ':'))).filter(Boolean);
          let placed = false;
          for (const leg of cand) { const h = holeOf(leg); if (!h) continue;
            for (const rot of [0, 90, 180, 270]) { T.placePart(d.id, h, rot);
              const legs = T.S.placed[d.id] && T.S.placed[d.id].legs;
              if (legs && Object.entries(legs).every(([p, hole]) => { const want = holeOf(`${d.id}:${p}`); return !want || (!!hole && want.replace(/\.\w$/, '') === hole.replace(/\.\w$/, '')); })) { placed = true; break; } }
            if (placed) break; }
          if (!placed) return `couldn't place ${d.id}`;
        }
        for (const [a, b] of ref) {                              // every wire (not part legs)
          const isPart = (e) => !e.startsWith(bb + ':') && !e.startsWith(board + ':');
          if (isPart(a) || isPart(b)) continue;
          const end = (e) => e.startsWith(bb + ':') ? 'bb:' + e.slice(bb.length + 1) : e;
          T.addWire(end(a), end(b));
        }
        // the board is built ahead: Check walks through every step, then Final check
        let text = '';
        for (let i = 0; i < 40; i++) {
          const btn = document.getElementById('finishBtn');
          (btn && !btn.hidden && btn.offsetParent ? btn : document.getElementById('checkBtn')).click();
          await new Promise(r => setTimeout(r, 700));
          text = document.getElementById('feedback').innerText.replace(/\s+/g, ' ');
          if (/COMPLETE|NOT YET|WRONG|⚠|🔌/.test(text)) break;
        }
        if (window.DEBUG_LEGS) text += ' | ' + JSON.stringify(Object.fromEntries(Object.entries(T.S.placed).map(([k, v]) => [k, v.legs]))) + ' | ' + JSON.stringify(T.S.wires.map(w => [w.a, w.b]));
        return text.slice(0, window.DEBUG_LEGS ? 9000 : 140);
      }, id);
      if (process.env.SHOTS) {                                   // SHOTS=dir: a picture of each finished build
        await page.evaluate(() => { const p = document.getElementById('levelPop'); if (p) p.hidden = true; window.__bench3d.B.view('3d'); });
        await sleep(900); await page.screenshot({path: `${process.env.SHOTS}/built_${id}.png`});
      }
      const ok = /COMPLETE|skipped/.test(verdict);
      if (!ok) failed++;
      console.log((ok ? 'OK  ' : 'FAIL') + ' ' + id.padEnd(28) + verdict);
    }
    console.log('ERRORS:', errors.slice(0, 5));
  } catch (e) { console.log('TEST ERROR', e); failed++; } finally { await browser.close(); process.exit(failed ? 1 : 0); }
})();

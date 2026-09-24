// UI flow smoke test: Sparky home → Learn (parts picker, path, lesson card) → Blink on the 3D bench →
// celebrations → Create. Run with a test server: CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & (never your real profile, never a real Claude call).
const puppeteer = require('puppeteer-core');
let browserRef = null;
const out = process.argv[2];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = browserRef = await puppeteer.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', protocolTimeout: 120000, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']});
  const page = await browser.newPage(); await page.setViewport({width:1440, height:900});
  const errors=[]; page.on('pageerror', e=>errors.push(e.message)); page.on('console', m=>{ if(m.type()==='error') errors.push(m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8799) + '/', {waitUntil:'networkidle0'});
  await page.waitForSelector('.choice', {timeout:30000, polling:500}); await sleep(600);
  console.log('HOME:', await page.evaluate(()=>document.getElementById('homeTitle').innerText + ' | ' + document.getElementById('homeSub').innerText));
  console.log('choices:', await page.evaluate(()=>[...document.querySelectorAll('.choice')].map(c=>c.innerText.replace(/\n/g,' '))));
  await page.screenshot({path: out+'/f1_home.png'});
  // Learn
  await page.evaluate(()=>[...document.querySelectorAll('.choice')].find(c=>c.innerText.includes('Learn')).click());
  await sleep(500);   // Sparky asks what's on your desk first
  await page.evaluate(()=>[...document.querySelectorAll('.choice')].find(c=>c.innerText.includes('pick my parts')).click());
  await sleep(1200);
  const tiles = await page.evaluate(()=>[...document.querySelectorAll('.ptile .nm')].map(n=>n.textContent));
  console.log('picker tiles:', tiles.length, tiles.slice(0,10));
  for (const want of ['Arduino Uno R3','USB','Solderless','Jumper','LED','220']) {
    await page.evaluate((w)=>{ const t=[...document.querySelectorAll('.ptile')].find(t=>t.querySelector('.nm').textContent.includes(w)); t && t.click(); }, want);
  }
  await sleep(900);
  console.log('matches:', await page.evaluate(()=>[...document.querySelectorAll('.match')].map(m=>m.innerText.replace(/\n/g,' '))));
  console.log('worlds:', await page.evaluate(()=>[...document.querySelectorAll('.wsign b')].map(b=>b.textContent)));
  console.log('tiles:', await page.evaluate(()=>[...document.querySelectorAll('.tile')].map(t=>(t.querySelector('.lv')||t.querySelector('.face')).textContent+(t.querySelector('.tname')?' '+t.querySelector('.tname').textContent:'')+(t.querySelector('.bdg.tip')?' 💡':'')+(t.querySelector('.bdg.fit')?' 🧰':''))));
  // out of order: level 3-1 before 1-1 — Sparky walks there, the popup tips but doesn't lock
  await page.evaluate(()=>document.querySelector('.tile[data-id="analog-read-serial"]').click()); await sleep(6500);
  console.log('3-1 popup:', await page.evaluate(()=>!document.getElementById('lessonPop').hidden && document.getElementById('lessonPopCard').innerText.replace(/\n+/g,' | ')));
  await page.screenshot({path: out+'/f2b_map_out_of_order.png'});
  await page.evaluate(()=>document.querySelector('#lessonPop [data-close]').click()); await sleep(300);
  await page.screenshot({path: out+'/f2_learn.png'});
  await page.click('#closeParts'); await sleep(500);
  await page.evaluate(()=>document.getElementById('cameraBtn').click()); await sleep(400); await page.screenshot({path: out+'/f3_camera.png'});
  await page.evaluate(()=>document.querySelector('#cameraPop [data-close]').click());
  // lesson popup for blink
  await page.evaluate(()=>document.querySelector('.tile[data-id="blink"]').click()); await sleep(6500);
  console.log('popup:', await page.evaluate(()=>document.getElementById('lessonPopCard').innerText.replace(/\n+/g,' | ')));
  await page.screenshot({path: out+'/f4_popup.png'});
  await page.click('#popStart'); await sleep(1500);
  console.log('lesson screen visible:', await page.evaluate(()=>!document.getElementById('lessonScreen').hidden), '| title:', await page.evaluate(()=>document.getElementById('brandSub').textContent));
  // play Blink quickly with the same moves as the smoke test
  await sleep(1500); await page.evaluate(() => window.__bench3d.B.view('top')); await sleep(600);
  const holeCenter = (h) => page.evaluate((h) => window.__bench3d.B.toScreen(window.__bench3d.B.holeWorld(h)), h);
  const spotCenter = (end) => page.evaluate((p) => window.__bench3d.B.toScreen(window.__bench3d.B.boardPinWorld(p)), end.replace(/^uno:/, ''));
  const trayCenter = (id) => page.evaluate(`(()=>{const it=[...document.querySelectorAll('.tray-item')].find(i=>i.querySelector('.tray-sub').textContent==='${id}');const r=it.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`);
  const dragTo = async (from, to) => { await page.mouse.move(from.x, from.y); await page.mouse.down(); await page.mouse.move(to.x,to.y,{steps:8}); await page.mouse.up(); await sleep(300); };
  const check = async () => { await page.click('#checkBtn'); await sleep(700); return page.evaluate(()=>document.getElementById('feedback').innerText.replace(/\s+/g,' ')); };
  await dragTo(await trayCenter('r1'), await holeCenter('3b.h')); console.log('1a', await check());
  await dragTo(await holeCenter('3b.j'), await spotCenter('uno:13')); console.log('1b', await check());
  await dragTo(await trayCenter('led1'), await holeCenter('7b.f')); console.log('2', await check());
  await dragTo(await holeCenter('6b.j'), await spotCenter('uno:GND.1')); console.log('3', await check());
  await page.click('#finishBtn'); await sleep(1200);
  console.log('final:', await page.evaluate(()=>document.getElementById('feedback').innerText.replace(/\s+/g,' ')));
  await page.screenshot({path: out+'/f5_celebrate.png'});
  await sleep(2200);
  console.log('level-up popup:', await page.evaluate(()=>!document.getElementById('levelPop').hidden && document.getElementById('levelPopCard').innerText.replace(/\n+/g,' ')));
  console.log('header XP:', await page.evaluate(()=>document.getElementById('xpNum').textContent + ' / level ' + document.getElementById('lvlNum').textContent));
  await page.screenshot({path: out+'/f6_levelup.png'});
  // back to the map: the trail draws in, stars pop, Sparky walks on to the next level
  await page.evaluate(()=>{ document.getElementById('levelPop').hidden=true; document.getElementById('backHomeBtn').click(); });
  await sleep(1500); await page.screenshot({path: out+'/f6b_map_celebrate.png'});
  await sleep(3500);
  console.log('after win:', await page.evaluate(()=>({ stars: document.querySelectorAll('.tile[data-id="blink"] .st.on').length, trail: !!document.querySelector('path.trail.on'), beckon: [...document.querySelectorAll('.tile.beckon')].map(t=>t.dataset.id) })));
  await page.screenshot({path: out+'/f6c_map_next.png'});
  // create screen
  await page.evaluate(()=>{ document.getElementById('homeBtn').click(); });
  await sleep(2500);
  await page.evaluate(()=>[...document.querySelectorAll('.choice')].find(c=>c.innerText.includes('Create')).click());
  await sleep(2200);
  await page.type('#createInput', 'a traffic light'); await page.click('#createSend'); await sleep(2500);
  console.log('create chat:', await page.evaluate(()=>[...document.querySelectorAll('#createChat .bubble')].map(b=>b.innerText.replace(/\n+/g,' ').slice(0,160))));
  await page.screenshot({path: out+'/f7_create.png'});
  console.log('ERRORS:', errors);
  await browser.close();
})().catch(async e=>{console.log('TEST ERROR', e); if (browserRef) await browserRef.close().catch(()=>{}); process.exit(1);});

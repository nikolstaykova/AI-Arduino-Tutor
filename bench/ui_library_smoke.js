// Parts & Tools smoke test (real Chrome): home card → parts grid → tools tab → a tool's video → a part's
// 3D viewer → "Used in" opens the level card; a short window still shows the level card's Start button.
//   CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 & ; node bench/ui_library_smoke.js /tmp/shots
const puppeteer=require('puppeteer-core');const sleep=ms=>new Promise(r=>setTimeout(r,ms));const out=process.argv[2];
(async()=>{const b=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new',protocolTimeout:120000,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{const p=await b.newPage();await p.setViewport({width:1280,height:800});const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto('http://localhost:' + (process.env.PORT || 8799) + '/',{waitUntil:'networkidle0'});await p.waitForSelector('.home-card',{timeout:30000});
console.log('cards',await p.evaluate(()=>[...document.querySelectorAll('.home-card b')].map(x=>x.textContent)));
await p.evaluate(()=>[...document.querySelectorAll('.home-card')].find(c=>c.innerText.includes('Parts & Tools')).click());
await sleep(6000);await p.screenshot({path:out+'/lib_parts.png'});
await p.evaluate(()=>document.querySelector('#libTabs [data-kind=tool]').click());await sleep(5000);await p.screenshot({path:out+'/lib_tools.png'});
await p.evaluate(()=>document.querySelector('.lib-tile[data-id=tweezers]').click());await sleep(3000);await p.screenshot({path:out+'/lib_detail_tool.png'});
console.log('video',await p.evaluate(()=>{const v=document.querySelector('.lib-video');return v&&[v.src,v.readyState,v.duration]}));
await p.evaluate(()=>document.querySelector('.lib-close').click());
await p.evaluate(()=>document.querySelector('#libTabs [data-kind=part]').click());await sleep(500);
await p.evaluate(()=>document.querySelector('.lib-tile[data-id=led]').click());await sleep(3000);await p.screenshot({path:out+'/lib_detail_led.png'});
await p.evaluate(()=>document.querySelector('[data-lesson=blink]').click());await sleep(2500);
console.log('lesson pop open',await p.evaluate(()=>!document.getElementById('lessonPop').hidden));
await p.setViewport({width:1280,height:560});await sleep(1500);
await p.screenshot({path:out+'/pop_short.png'});
console.log('start visible',await p.evaluate(()=>{const r=document.getElementById('popStart').getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0}));
console.log('ERRORS',errs);}finally{await b.close();}})();

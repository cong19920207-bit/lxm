// Supplementary desktop measurements only. No production Q201 configuration,
// remote data, phone capability simulation or relative pre-change benefit claim.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {setupNginx,root} = require('./home_nginx_helpers.cjs');
const output = path.join(root,'docs/design/home-redesign/execution/evidence/home-m4');
function observeReadiness() {
  const measured = window.__homeMeasurement = {maskGoneMs:null,entryHitMs:null};
  const observer = new MutationObserver(check);
  function check() {
    if (window.HomeStartup?.phase !== 'ready' || document.getElementById('home-loading-screen')) return;
    if (measured.maskGoneMs == null) measured.maskGoneMs = performance.now();
    const entry = document.querySelector("button[onclick=\"handleHomeQuickAction('more')\"]");
    if (!entry || !document.getElementById('main-content')?.classList.contains('content-loaded')) return;
    const rect = entry.getBoundingClientRect();
    const target = document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
    if (target && entry.contains(target)) {
      measured.entryHitMs = performance.now(); observer.disconnect();
      window.removeEventListener('home-startup-change',check);
      document.removeEventListener('DOMContentLoaded',check);
    }
  }
  observer.observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['class','hidden']});
  document.addEventListener('DOMContentLoaded',check);
  window.addEventListener('home-startup-change',check);
}
(async () => {
  fs.mkdirSync(output,{recursive:true});
  const s = await setupNginx();
  const loads = [],errors = s.errors;
  let page = s.page,context = s.context,cdp = s.cdp;
  try {
    for (const identity of ['visitor','authenticated']) {
      if (identity === 'authenticated') {
        context = await s.context.browser().newContext({viewport:{width:390,height:844},deviceScaleFactor:3});
        page = await context.newPage();
        page.on('pageerror',error => errors.push(error.message));
        cdp = await context.newCDPSession(page);
        await cdp.send('Network.enable');
        await cdp.send('Network.setBlockedURLs',{urls:['https://fonts.googleapis.com/*','https://fonts.gstatic.com/*']});
        await page.addInitScript(() => localStorage.setItem('token','controlled-home-measurement'));
      }
      await page.addInitScript(observeReadiness);
      let entries = new Map();
      cdp.on('Network.requestWillBeSent',event => {
        if (event.request.url.startsWith(s.origin+'/')) entries.set(event.requestId,{path:new URL(event.request.url).pathname,type:event.type,encodedReceivedBytes:0,fromDiskCache:false,fromMemoryCache:false});
      });
      cdp.on('Network.responseReceived',event => {
        const entry = entries.get(event.requestId);
        if (entry) Object.assign(entry,{status:event.response.status,fromDiskCache:!!event.response.fromDiskCache});
      });
      cdp.on('Network.requestServedFromCache',event => { const entry=entries.get(event.requestId);if(entry)entry.fromMemoryCache=true; });
      cdp.on('Network.loadingFinished',event => { const entry=entries.get(event.requestId);if(entry)entry.encodedReceivedBytes=event.encodedDataLength; });
      for (const mode of ['cold','cached-navigation','refresh']) {
        entries = new Map();
        if (mode === 'refresh') await page.reload();
        else await page.goto(s.origin+'/pages/index.html');
        await page.waitForFunction(() => window.__homeMeasurement?.entryHitMs != null,{},{timeout:10000});
        await page.waitForFunction(() => HomeScene.motion.inspect().loaded.length === 5);
        await page.waitForTimeout(150);
        const measured = await page.evaluate(() => ({...window.__homeMeasurement,startup:{skipped:HomeStartup.skipped,phase:HomeStartup.phase},resources:performance.getEntriesByType('resource').filter(entry=>entry.name.startsWith(location.origin+'/')).map(entry=>({path:new URL(entry.name).pathname,transferSize:entry.transferSize,encodedBodySize:entry.encodedBodySize,decodedBodySize:entry.decodedBodySize}))}));
        assert.equal(measured.startup.phase,'ready');
        assert.ok(measured.maskGoneMs < 8500 && measured.entryHitMs < 8500);
        if (mode === 'cached-navigation') assert.ok(measured.maskGoneMs < 1000,'Session navigation skips the presentation');
        else assert.ok(measured.maskGoneMs >= 4000,'Cold/refresh retains the approved presentation timing');
        const requests = [...entries.values()];
        const imageRequests = requests.filter(entry => entry.type === 'Image');
        assert.ok(imageRequests.every(entry=>!entry.path.endsWith('/Index.png')),'Default scene never preheats the old large background');
        assert.equal(imageRequests.filter(entry=>entry.path.includes('/home-scene/v4/')).length,7);
        if (mode !== 'cold') assert.ok(imageRequests.some(entry=>entry.fromMemoryCache||entry.fromDiskCache),'Native image cache is exercised');
        loads.push({identity,mode,...measured,requests,totalCDPEncodedReceivedBytes:requests.reduce((sum,entry)=>sum+entry.encodedReceivedBytes,0)});
        console.log('MEASURE '+identity+' '+mode+' mask='+Math.round(measured.maskGoneMs)+'ms');
      }
    }
    const begin = await page.evaluate(() => ({at:performance.now(),owner:HomeScene.current.inspect(),quality:HomeScene.quality.inspect(),motion:HomeScene.motion.inspect()}));
    const samples = [begin];
    for (let i=0;i<6;i++) {
      await page.waitForTimeout(5000);
      samples.push(await page.evaluate(() => ({at:performance.now(),owner:HomeScene.current.inspect(),quality:HomeScene.quality.inspect(),motion:HomeScene.motion.inspect()})));
      console.log('SAMPLE steady '+(i+1)*5+'s');
    }
    const final = samples.at(-1);
    const frames = final.quality.metrics.frames-begin.quality.metrics.frames;
    const elapsed = final.quality.metrics.elapsedMs-begin.quality.metrics.elapsedMs;
    assert.equal(final.quality.calibrated,false,'Desktop observation must not select production Q201 parameters');
    assert.ok(final.owner.running && frames > 0);
    const responses = [];
    for (let i=0;i<5;i++) {
      // The real target moves with breathing. A physical pointer click should
      // not wait for Playwright's stationary-element assumption.
      const hit = await page.getByRole('button',{name:'轻触林小梦'}).boundingBox();
      assert.ok(hit);
      const point={x:hit.x+hit.width/2,y:hit.y+hit.height/2};
      assert.equal(await page.evaluate(point => document.elementFromPoint(point.x,point.y)?.closest('.home-scene-hit') != null,point),true);
      await page.mouse.click(point.x,point.y);
      await page.waitForFunction(() => HomeScene.motion.inspect().action === 'response');
      await page.waitForFunction(() => HomeScene.motion.inspect().action !== 'response');
      responses.push(await page.evaluate(() => HomeScene.motion.inspect().responseLatencyMs));
    }
    const modalCycles = [];
    for (let i=0;i<10;i++) {
      await page.locator("button[onclick=\"handleHomeQuickAction('more')\"]").click();
      await page.keyboard.press('Escape');
      modalCycles.push(await page.evaluate(() => HomeScene.current.inspect()));
    }
    for (const sample of modalCycles) {
      assert.equal(sample.id,final.owner.id);assert.equal(sample.effects,final.owner.effects);
      assert.equal(sample.subscriptions,final.owner.subscriptions);assert.equal(sample.timers,final.owner.timers);
    }
    const running = {durationMs:final.at-begin.at,frames,meanMainFrameFps:frames*1000/elapsed,
      longTaskCount:final.quality.metrics.longTasks-begin.quality.metrics.longTasks,
      longTaskMs:final.quality.metrics.longTaskMs-begin.quality.metrics.longTaskMs,
      responseFirstFrameLatencyMs:responses,samples,modalCycles};
    assert.deepEqual(errors,[]);
    const files=['frontend/pages/index.html','frontend/static/js/home-scene.js','nginx/nginx.conf'];
    const sourceSha256=Object.fromEntries(files.map(file=>[file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
    fs.writeFileSync(path.join(output,'step-015-016-desktop-measurements.json'),JSON.stringify({scope:'Supplementary actual desktop Chrome on isolated Linux Nginx/local HTTP, controlled API, 390x844 DPR3. External fonts blocked with CDP; native HTTP cache retained. No phone/HTTPS/real audio/low-device target/pre-change comparison or Q201 selection claim.',environment:{browser:await context.browser().version(),platform:process.platform,viewport:{width:390,height:844},deviceScaleFactor:3,network:'localhost Docker forwarding, no throttling'},method:{timing:'performance.now since navigation; mask absent and real more-button hit test',wireBytes:'CDP loadingFinished.encodedDataLength; protocol accounting, not pure asset bytes',resourceBytes:'Resource Timing transferSize/encodedBodySize separately; cache has zero transfer',memory:'Chrome performance.memory.usedJSHeapSize sampled without forced GC; JS heap only, not whole-browser peak or leak verdict'},loads,running,errors,sourceSha256},null,2)+'\n');
    console.log('PASS six native-cache visits and supplementary 30s desktop measurement; '+running.meanMainFrameFps.toFixed(2)+' main-frame fps');
  } finally { await s.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });

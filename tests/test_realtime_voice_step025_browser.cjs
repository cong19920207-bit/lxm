const assert=require('node:assert/strict'),fs=require('node:fs'),http=require('node:http');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const evidence='docs/design/realtime_voice/P1/execution/evidence/m6-20260913/';
const banner='如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。';
const resource='如果你可能马上伤害自己，请立即拨打 110/120，并请一位可信任的人来到你身边；也可以拨打 12356 心理援助热线。';
(async()=>{
 const server=http.createServer((req,res)=>{
  if(req.url.startsWith('/static/')&&!req.url.includes('..')){
   const file='frontend'+req.url;if(fs.existsSync(file)){res.setHeader('Content-Type',req.url.endsWith('.js')?'text/javascript':req.url.endsWith('.css')?'text/css':'image/png');return res.end(fs.readFileSync(file));}
  }
  res.setHeader('Content-Type','text/html');res.end('<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/voice-entry.css"><link rel="stylesheet" href="/static/css/voice-call-cards.css"><button id="start" onclick="VoiceEntry.begin()">发起通话</button><main id="cards"></main><script src="/static/js/voice-entry.js"></script><script src="/static/js/voice-call-cards.js"></script>');
 });await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage({viewport:{width:390,height:844}});await page.emulateMedia({reducedMotion:'reduce'});
  const errors=[],responses=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',async r=>{if(r.url().includes('/api/'))responses.push(await r.text());});
  await page.addInitScript(()=>{
   navigator.permissions.query=async()=>({state:'granted'});
   window.testSockets=[];window.AudioWorkletNode=class{};
   window.AudioContext=class{constructor(){this.audioWorklet={};}async resume(){}async close(){}};
   navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop(){}}]});
   window.VoiceAudioTransport=class{constructor(options){window.testAudio=this;this.options=options;this.track={readyState:'live'};}async start(){}resumeTransport(){}pause(){}frame(){}isPlaying(){return false;}supportsOutputSelection(){return false;}async close(){}setMuted(value){return this.muted=value;}};
   window.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;testSockets.push(this);queueMicrotask(()=>this.onopen?.());}send(){}close(){this.readyState=3;}};
  });
  let hit=false,ended=false;
  const callId='11111111-1111-4111-8111-111111111111';
  const crisis={banner,resource,expires_at:new Date(Date.now()+86400000).toISOString()};
  await page.route('**/api/**',async route=>{
   const req=route.request();let data;
   if(req.url().endsWith('/calls')&&req.method()==='POST')data={call_id:callId,call_ticket:'test'};
   else if(req.url().endsWith('/end')){ended=true;data={changed:true,cleanup_pending:false};}
   else data={call_id:callId,status:ended?'ended':'connected',has_connected:true,duration_seconds:30,show_end_page:true,crisis:hit?crisis:null};
   await route.fulfill({json:{code:0,data},headers:{'Cache-Control':'no-store'}});
  });
  const send=frame=>page.evaluate(frame=>testSockets.at(-1).onmessage({data:JSON.stringify({v:1,...frame})}),frame);
  await page.goto('http://127.0.0.1:'+server.address().port);await page.locator('#start').click();
  await page.waitForFunction(()=>testSockets.length===1);
  await send({type:'state',status:'connected',reconnect_timeout_ms:5000});await page.locator('.is-in-call').waitFor();
  assert.equal(await page.locator('.voice-crisis-banner').isVisible(),false);
  hit=true;await send({type:'crisis_detected',call_id:callId,banner});await page.locator('.voice-crisis-banner').waitFor();
  await send({type:'crisis_detected',call_id:callId,banner});
  for(const width of [390,320]){
   await page.setViewportSize({width,height:width===320?568:844});
   await page.waitForFunction(()=>Math.abs(parseFloat(document.querySelector('.voice-entry').style.getPropertyValue('--voice-crisis-height'))-document.querySelector('.voice-crisis-banner').getBoundingClientRect().height)<.01);
   for(const state of ['listening','thinking','speaking','reconnecting']){
    await page.evaluate(state=>testAudio.options.onState(state),state);
    assert.equal(await page.locator('.voice-crisis-banner').count(),1);
    assert.equal(await page.locator('.voice-crisis-banner').innerText(),banner);
    const box=await page.locator('.voice-crisis-banner').boundingBox(),controls=await page.locator('.voice-call-controls').boundingBox();
    assert.ok(controls.y+controls.height<=box.y,JSON.stringify({width,state,box,controls}));
    assert.equal(await page.locator('.voice-call-hangup').isEnabled(),true);
    assert.equal(await page.locator('.voice-crisis-banner').evaluate(n=>getComputedStyle(n).animationName),'none');
   }
  }
  await page.screenshot({path:evidence+'step025-banner-mobile.png'});
  await send({type:'crisis_detected',call_id:callId,banner:'请联系身边可信任的人。'.repeat(10)+'12356。'});
  await page.waitForFunction(()=>{const b=document.querySelector('.voice-crisis-banner').getBoundingClientRect(),c=document.querySelector('.voice-call-controls').getBoundingClientRect();return c.bottom<=b.top;});
  await send({type:'crisis_detected',call_id:callId,banner});
  await page.locator('.voice-call-hangup').click();await page.getByRole('heading',{name:'通话已结束'}).waitFor();
  assert.equal(await page.locator('.voice-crisis-banner').isVisible(),false);
  await page.getByRole('button',{name:'关闭通话'}).click();
  await page.evaluate(({crisis,callId})=>document.querySelector('#cards').append(VoiceCallCards.render({source:'call',call_id:callId,call_status:'ended',summary_status:'not_applicable',duration_seconds:30,crisis_resource:crisis},Date.now())),{crisis,callId});
  const card=page.locator('.voice-crisis-resource');assert.equal(await card.innerText(),resource);
  assert.equal(await card.locator('button,a,h1,h2,h3').count(),0);
  assert.equal(await card.evaluate(n=>n.closest('.voice-call-card,.ai')===null),true);
  const storage=await page.evaluate(async()=>({local:{...localStorage},session:{...sessionStorage},caches:await caches.keys(),dbs:await indexedDB.databases()}));
  for(const text of [JSON.stringify(storage),await page.content(),...responses])assert.ok(!text.includes('CRISIS-RAW-025-NEVER-PUBLIC'));
  assert.deepEqual(storage.caches,[]);assert.deepEqual(storage.dbs,[]);
  await page.screenshot({path:evidence+'step025-resource-mobile.png'});
  await page.evaluate(()=>VoiceCallCards.configureResourceRefresh(async id=>{const r=await fetch('/api/voice/calls/'+id,{cache:'no-store'});return (await r.json()).data.crisis;}));
  await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));assert.equal(await card.count(),0);
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));await card.waitFor();
  await page.evaluate(()=>window.dispatchEvent(new Event('offline')));assert.equal(await card.count(),0);
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));await card.waitFor();
  hit=false;await page.evaluate(()=>window.dispatchEvent(new Event('offline')));
  const refreshed=page.waitForResponse(r=>r.url().includes('/api/voice/calls/'));
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));await refreshed;
  assert.equal(await card.count(),0);
  await page.reload();assert.equal(await card.count(),0);
  await page.evaluate(({crisis,callId})=>document.querySelector('#cards').append(VoiceCallCards.render({call_id:callId,call_status:'ended',crisis_resource:{...crisis,expires_at:'2000-01-01T00:00:00Z'}},Date.now())),{crisis,callId});
  assert.equal(await card.count(),0);assert.deepEqual(errors,[]);
  fs.writeFileSync(evidence+'step025-browser.json',JSON.stringify({passed:true,widths:[390,320],states:['listening','thinking','speaking','reconnecting'],storage},null,2));
  console.log('STEP025 controlled browser passed: four states, duplicate, layout, resource copy, storage, expiry/pagehide. Physical device not tested.');
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});

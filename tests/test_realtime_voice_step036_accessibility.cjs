const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const evidence='docs/design/realtime_voice/P1/execution/evidence/m6-20260913/';
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage({viewport:{width:402,height:874},reducedMotion:'reduce'}),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  navigator.permissions.query=async()=>({state:'granted'});
  window.testSockets=[];window.AudioWorkletNode=class{};
  window.AudioContext=class{constructor(){this.audioWorklet={};}async resume(){}async close(){}};
  navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop(){}}]});
  window.VoiceAudioTransport=class{constructor(options){window.testAudio=this;this.options=options;this.track={readyState:'live'};}async start(){}resumeTransport(){}pause(){}frame(){}isPlaying(){return false;}supportsOutputSelection(){return false;}async close(){}setMuted(v){return this.muted=v;}};
  window.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;testSockets.push(this);queueMicrotask(()=>this.onopen?.());}send(){}close(){this.readyState=3;}};
 });
 const banner='如果你有伤害自己的念头，请先联系身边可信任的人，或拨打 12356。';
 let ended=false;
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.origin!=='http://127.0.0.1:54321')return route.abort();
  if(url.pathname.startsWith('/api/')) {
   const data=url.pathname.endsWith('/calls')?{call_id:'11111111-1111-4111-8111-111111111111',call_ticket:'test'}:
    url.pathname.endsWith('/end')?(ended=true,{changed:true,cleanup_pending:false}):{status:ended?'ended':'connected',has_connected:true,duration_seconds:30,show_end_page:true,end_message:'就先聊到这'};
   return route.fulfill({json:{code:0,data}});
  }
  if(url.pathname.startsWith('/static/'))return route.fulfill({path:'frontend'+url.pathname});
  return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="stylesheet" href="/static/css/voice-entry.css"><button id="start" onclick="VoiceEntry.begin()">发起通话</button><button id="outside">页面其他操作</button><script src="/static/js/voice-entry.js"></script>'});
 });
 await page.goto('http://127.0.0.1:54321/?flow=ended');
 assert.equal(await page.locator('.voice-entry:visible').count(),0);
 assert.equal(await page.evaluate(()=>testSockets.length),0);
 assert.equal(await page.getByRole('heading',{name:'通话已结束'}).count(),0);
 await page.locator('#start').focus();await page.keyboard.press('Enter');
 await page.waitForFunction(()=>testSockets.length===1);
 const send=frame=>page.evaluate(frame=>testSockets.at(-1).onmessage({data:JSON.stringify({v:1,...frame})}),frame);
 await send({type:'state',status:'connected',reconnect_timeout_ms:5000});
 await page.locator('.is-in-call').waitFor();
 assert.equal(await page.locator('[role=dialog]').getAttribute('aria-modal'),'true');
 await send({type:'provider_event',metadata:{kind:'asr_final'},data:{text:'PRIVATE-TRANSCRIPT-036'}});
 await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='thinking');
 assert.ok(!(await page.locator('[role=dialog]').ariaSnapshot()).includes('PRIVATE-TRANSCRIPT-036'));
 await send({type:'crisis_detected',call_id:'11111111-1111-4111-8111-111111111111',banner});
 await page.locator('.voice-crisis-banner').waitFor();
 await page.waitForFunction(()=>parseFloat(document.querySelector('.voice-entry').style.getPropertyValue('--voice-crisis-height'))>0);
 for(const [width,height] of [[402,874],[874,402],[320,480]]){
  await page.setViewportSize({width,height});
  await page.waitForFunction(()=>Math.abs(parseFloat(document.querySelector('.voice-entry').style.getPropertyValue('--voice-crisis-height'))-document.querySelector('.voice-crisis-banner').getBoundingClientRect().height)<.01);
  for(const state of ['listening','thinking','speaking','reconnecting']){
   await page.evaluate(state=>testAudio.options.onState(state),state);
   assert.equal(await page.locator('.voice-entry').getAttribute('data-call-state'),state);
   assert.equal(await page.locator('.voice-entry-description').innerText(),{listening:'在听',thinking:'想一下',speaking:'正在说',reconnecting:'正在重新连接…'}[state]);
   assert.equal(await page.locator('.voice-call-mute').isVisible(),state!=='reconnecting');
   assert.equal(await page.locator('.voice-call-output').isVisible(),state!=='reconnecting');
   if(state==='reconnecting'){
    const hangup=await page.locator('.voice-call-hangup').boundingBox();assert.ok(Math.abs(hangup.x+hangup.width/2-width/2)<1);
   }
   const layout=await page.evaluate(()=>{
    const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,b:r.bottom};};
    const buttons=[...document.querySelectorAll('.voice-entry button')].filter(n=>n.getClientRects().length&&!n.hidden);
    return {buttons:buttons.map(n=>({label:n.textContent,disabled:n.disabled,...rect(n)})),
      controls:rect(document.querySelector('.voice-call-controls')),banner:rect(document.querySelector('.voice-crisis-banner')),
      title:rect(document.querySelector('.voice-entry-card')),scroll:document.querySelector('.voice-entry').scrollWidth};
   });
   for(const b of layout.buttons){assert.ok(b.w>=44&&b.h>=44,JSON.stringify(b));assert.ok(b.x>=0&&b.y>=0&&b.x+b.w<=width&&b.b<=height,JSON.stringify({width,height,state,b}));}
   assert.ok(layout.controls.b<=layout.banner.y,JSON.stringify(layout));
   assert.ok(layout.title.y>=0&&layout.title.b<=layout.controls.y,JSON.stringify(layout));
   assert.ok(layout.scroll<=width);
   assert.equal(await page.locator('.voice-entry-description').evaluate(n=>getComputedStyle(n,'::before').animationName),'none');
   checks.push({width,height,state});
  }
  await page.screenshot({path:evidence+`step036-${width}x${height}.png`});
 }
 await page.evaluate(()=>testAudio.options.onState('listening'));
 await page.locator('.voice-entry-close').focus();await page.keyboard.press('Shift+Tab');
 assert.equal(await page.locator('.voice-call-hangup').evaluate(n=>n===document.activeElement),true);
 await page.keyboard.press('Tab');assert.equal(await page.locator('.voice-entry-close').evaluate(n=>n===document.activeElement),true);
 await page.keyboard.press('Tab');assert.equal(await page.locator('.voice-call-mute').evaluate(n=>n===document.activeElement),true);
 await page.keyboard.press('Space');assert.equal(await page.locator('.voice-call-mute').getAttribute('aria-pressed'),'true');
 await page.evaluate(()=>testAudio.options.onState('reconnecting'));
 assert.equal(await page.locator('.voice-call-mute').isVisible(),false);
 assert.equal(await page.locator('.voice-call-hangup').evaluate(n=>n===document.activeElement),true);
 await page.evaluate(()=>testAudio.options.onState('listening'));
 assert.equal(await page.locator('.voice-call-mute').getAttribute('aria-pressed'),'true');
 await page.locator('.voice-call-hangup').focus();await page.keyboard.press('Enter');
 await page.getByRole('heading',{name:'通话已结束'}).waitFor();
 await page.locator('.voice-entry-close').focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('#start').evaluate(n=>n===document.activeElement),true);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(evidence+'step036-accessibility.json',JSON.stringify({passed:true,checks,keyboard:true,reducedMotion:true,scope:'production components; controlled media/API/socket; desktop Chrome'},null,2));
 console.log('PASS STEP036: 12 layout states, keyboard loop/mute/hangup/restore, reduced motion, no transcript accessibility text, flow=ended does not trigger initial UI or call');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

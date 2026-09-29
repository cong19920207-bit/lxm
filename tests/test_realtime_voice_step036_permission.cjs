const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const evidence='docs/design/realtime_voice/P1/execution/evidence/m6-20260913/';
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const checks=[];
try{
 for(const mode of ['prompt','query_unavailable','cancel_before_permission','cancel_during_permission','cancel_during_query','pagehide','deny','known_denied','granted']){
  const page=await browser.newPage({viewport:{width:402,height:874}}),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(mode=>{
   window.micRequests=0;window.stopped=0;window.testSockets=[];
   let queries=0;
   navigator.permissions.query=async()=>{if(mode==='query_unavailable')throw new TypeError('unsupported permission');if(mode==='cancel_during_query'&&++queries===1)return new Promise(resolve=>{window.finishQuery=()=>resolve({state:'granted'});});return {state:mode==='granted'?'granted':mode==='known_denied'?'denied':'prompt'};};
   window.AudioWorkletNode=class{};window.AudioContext=class{constructor(){this.audioWorklet={};}async resume(){}async close(){}};
   navigator.mediaDevices.getUserMedia=()=>{micRequests++;return new Promise((resolve,reject)=>{
    window.finishPermission=()=>resolve({getTracks:()=>[{stop(){stopped++;}}]});
    window.denyPermission=()=>reject(new DOMException('Denied','NotAllowedError'));
   });};
   window.VoiceAudioTransport=class{async close(){}};
   window.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;testSockets.push(this);queueMicrotask(()=>this.onopen?.());}send(){}close(){this.readyState=3;}};
  },mode);
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());if(url.origin!=='http://127.0.0.1:54321')return route.abort();
   if(url.pathname.startsWith('/api/')){requests.push(url.pathname);return route.fulfill({json:{code:0,data:{call_id:'11111111-1111-4111-8111-111111111111',call_ticket:'test'}}});}
   if(url.pathname.startsWith('/static/'))return route.fulfill({path:'frontend'+url.pathname});
   return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/voice-entry.css"><button id="start" onclick="VoiceEntry.begin()">发起通话</button><script src="/static/js/voice-entry.js"></script>'});
  });
  await page.goto('http://127.0.0.1:54321');await page.locator('#start').click();
  if(mode==='known_denied'){
   await page.getByRole('heading',{name:'还听不见你的声音',exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>micRequests),0);assert.equal(requests.length,0);
   assert.equal(await page.getByRole('button',{name:'查看开启方法'}).isEnabled(),true);
   assert.deepEqual(errors,[]);checks.push(mode);await page.close();continue;
  }
  if(mode==='cancel_during_query'){
   await page.waitForFunction(()=>typeof finishQuery==='function');
   await page.getByRole('button',{name:'关闭通话'}).click();await page.locator('#start').click();await page.evaluate(()=>finishQuery());
  }
  if(mode!=='granted'){
   await page.getByRole('heading',{name:'打开麦克风，她才能听见你',exact:true}).waitFor({timeout:3000});
   assert.equal(await page.locator('.voice-entry-description').innerText(),'麦克风仅在通话中启用。通话会生成文字记录和摘要，用来延续聊天。');
   assert.equal(await page.evaluate(()=>micRequests),0);assert.equal(requests.length,0);
   for(const [width,height] of [[402,874],[874,402],[320,480]]){
    await page.setViewportSize({width,height});
    for(const name of ['允许麦克风','先不打了','关闭通话']){const b=page.getByRole('button',{name,exact:true});assert.equal(await b.isVisible(),true);const r=await b.boundingBox();assert.ok(r.width>=44&&r.height>=44&&r.x>=0&&r.y>=0&&r.x+r.width<=width&&r.y+r.height<=height);}
   }
   if(mode==='prompt')await page.screenshot({path:evidence+'step036-permission-prompt.png'});
   if(mode==='pagehide'){
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
    assert.equal(await page.locator('.voice-entry').isVisible(),false);
    await page.locator('#start').click();await page.getByRole('button',{name:'允许麦克风',exact:true}).waitFor();
   }
   if(mode==='cancel_before_permission'){
    await page.getByRole('button',{name:'先不打了',exact:true}).click();
    assert.equal(await page.locator('.voice-entry').isVisible(),false);assert.equal(await page.evaluate(()=>micRequests),0);
    assert.equal(await page.locator('#start').evaluate(n=>n===document.activeElement),true);
    await page.locator('#start').click();await page.getByRole('button',{name:'允许麦克风',exact:true}).waitFor();
   }
   // Two synchronous clicks must initiate only one browser permission request.
   await page.getByRole('button',{name:'允许麦克风',exact:true}).evaluate(n=>{n.click();n.click();});
  }
  await page.waitForFunction(()=>micRequests===1);assert.equal(requests.length,0);
  if(mode==='cancel_during_permission'){
   await page.getByRole('button',{name:'关闭通话',exact:true}).click();await page.evaluate(()=>finishPermission());
   await page.waitForFunction(()=>stopped===1);assert.equal(requests.length,0);assert.equal(await page.evaluate(()=>testSockets.length),0);
   await page.locator('#start').click();await page.getByRole('button',{name:'允许麦克风',exact:true}).waitFor();
  }else if(mode==='deny'){
   await page.evaluate(()=>denyPermission());await page.getByRole('heading',{name:'还听不见你的声音',exact:true}).waitFor();
   assert.equal(requests.length,0);assert.equal(await page.getByRole('button',{name:'查看开启方法'}).isEnabled(),true);
  }else{
   await page.evaluate(()=>finishPermission());await page.waitForFunction(()=>testSockets.length===1);
   assert.deepEqual(requests,['/api/voice/calls']);assert.equal(await page.evaluate(()=>micRequests),1);
  }
  assert.deepEqual(errors,[]);checks.push(mode);await page.close();
 }
 fs.writeFileSync(evidence+'step036-permission.json',JSON.stringify({passed:true,checks,scope:'production component; controlled browser permission/media/API; desktop Chrome'},null,2));
 console.log('PASS STEP036 permission: '+checks.join(', '));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

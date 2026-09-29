// Production DOM/styles and real browser audio; controlled HTTP/socket/media input.
const assert=require('node:assert/strict');const fs=require('node:fs');const http=require('node:http');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
const evidence=process.env.VOICE_EVIDENCE_DIR || 'docs/design/realtime_voice/P1/execution/evidence/';
(async()=>{
 const server=http.createServer((req,res)=>{
  const assets={
   '/static/js/voice-entry.js':'frontend/static/js/voice-entry.js',
   '/static/js/voice-playback.js':'frontend/static/js/voice-playback.js',
   '/static/js/voice-audio-transport.js':'frontend/static/js/voice-audio-transport.js',
   '/static/js/voice-microphone-worklet.js':'frontend/static/js/voice-microphone-worklet.js',
   '/static/css/voice-entry.css':'frontend/static/css/voice-entry.css',
   '/static/images/Index/Index.png':'frontend/static/images/Index/Index.png'};
  if(assets[req.url]){res.setHeader('Content-Type',req.url.endsWith('.js')?'text/javascript':req.url.endsWith('.css')?'text/css':'image/png');res.end(fs.readFileSync(assets[req.url]));return;}
  res.setHeader('Content-Type','text/html');res.end('<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="stylesheet" href="/static/css/voice-entry.css"><button onclick="VoiceEntry.begin()">发起通话</button><script src="/static/js/voice-playback.js"></script><script src="/static/js/voice-audio-transport.js"></script><script src="/static/js/voice-entry.js"></script>');
 });await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:'chrome',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage({viewport:{width:402,height:874}});await page.emulateMedia({reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   navigator.permissions.query=async()=>({state:'granted'});
   window.testSockets=[];window.testStreams=[];
   window.WebSocket=class{static OPEN=1;constructor(url){this.url=String(url);this.readyState=1;this.sent=[];testSockets.push(this);queueMicrotask(()=>this.onopen?.());}send(raw){this.sent.push(JSON.parse(raw));}close(){this.readyState=3;queueMicrotask(()=>this.onclose?.());}};
   navigator.mediaDevices.getUserMedia=async()=>{
    const context=new AudioContext();await context.resume();const oscillator=context.createOscillator();
    const dest=context.createMediaStreamDestination();oscillator.connect(dest);oscillator.start();
    const track=dest.stream.getAudioTracks()[0];track.addEventListener('ended',()=>{oscillator.stop();context.close();});
    window.testStreams.push(dest.stream);return dest.stream;
   };
   navigator.mediaDevices.selectAudioOutput=async()=>{throw new Error('controlled device failure');};
  });
  let endRequests=0, createRequests=0,reconnectRequests=0;
  let result={call_id:'11111111-1111-4111-8111-111111111111',status:'ended',end_reason:'user_hangup',has_connected:true,duration_seconds:73,end_message:'就先聊到这',show_end_page:true};
  const requests=[];
  await page.route('**/api/**',async route=>{
   const req=route.request();requests.push(req.url());let data;
   if(req.url().endsWith('/calls')&&req.method()==='POST'){createRequests++;data={call_id:result.call_id,call_ticket:'controlled-ticket'};}
   else if(req.url().endsWith('/reconnect')){reconnectRequests++;data={call_id:result.call_id,call_ticket:'controlled-reconnect-ticket'};}
   else if(req.url().endsWith('/end')){endRequests++;data={changed:true,cleanup_pending:false};}
   else data=result;
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:0,data})});
  });
  const send=frame=>page.evaluate(frame=>testSockets.at(-1).onmessage({data:JSON.stringify({v:1,...frame})}),frame);
  await page.goto('http://127.0.0.1:'+server.address().port);await page.getByRole('button',{name:'发起通话'}).click();
  await page.waitForFunction(()=>testSockets.length===1);
  await send({type:'state',status:'connected',reconnect_timeout_ms:5000});
  await page.locator('.voice-entry.is-in-call').waitFor();
  assert.equal(await page.locator('.voice-entry-description').innerText(),'在听');
  await send({type:'clock',duration_seconds:65});assert.equal(await page.locator('.voice-call-clock').innerText(),'01:05');
  await page.locator('.voice-call-mute').click();
  assert.equal(await page.locator('.voice-call-mute').getAttribute('aria-pressed'),'true');
  assert.equal(await page.evaluate(()=>testStreams[0].getAudioTracks()[0].enabled),false);
  await page.locator('.voice-call-output').click();
  assert.equal(await page.locator('.voice-call-output').getAttribute('aria-pressed'),'false');
  await page.locator('.voice-call-mute').click();
  await send({type:'provider_event',metadata:{kind:'asr_final',reply_id:null},data:{text:'不应出现在页面上的转写'}});
  await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='thinking');
  assert.equal(await page.evaluate(()=>getComputedStyle(document.querySelector('.voice-entry-description'),'::before').animationName),'none');
  assert.ok(!(await page.locator('body').innerText()).includes('不应出现在页面上的转写'));
  await page.screenshot({path:evidence+'step020-thinking.png'});
  await send({type:'audio',pcm_base64:Buffer.alloc(48000).toString('base64'),metadata:{reply_id:'r1'}});
  await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='speaking');
  await page.screenshot({path:evidence+'step020-speaking.png'});
  await send({type:'stop_playback',reply_id:'r1'});
  await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='listening');
  assert.ok(await page.evaluate(()=>testSockets[0].sent.some(f=>f.type==='client_barge_in')));
  assert.ok(!await page.evaluate(()=>testSockets[0].sent.some(f=>f.type==='client_reply_playback_completed')));
  await page.locator('.voice-call-mute').click();
  await page.evaluate(()=>{testSockets[0].readyState=3;testSockets[0].onclose();});
  await page.waitForFunction(()=>testSockets.length===2);
  assert.ok(await page.evaluate(()=>testSockets[1].url.endsWith('/reconnect-stream')));
  await send({type:'state',status:'connected',reconnected:true,reconnect_timeout_ms:5000});
  await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='listening');
  assert.equal(await page.locator('.voice-call-mute').getAttribute('aria-pressed'),'true');
  assert.equal(await page.evaluate(()=>testStreams.length),1);assert.equal(createRequests,1);assert.equal(reconnectRequests,1);
  const bounds=await page.locator('.voice-call-controls').boundingBox();assert.ok(bounds.y+bounds.height<=874-20);
  await page.screenshot({path:evidence+'step020-listening.png'});
  await page.locator('.voice-call-hangup').dblclick();
  await page.getByRole('heading',{name:'通话已结束'}).waitFor();
  assert.equal(endRequests,1);assert.equal(await page.locator('.voice-call-clock').innerText(),'01:13');
  assert.equal(await page.locator('.voice-entry-description').innerText(),'就先聊到这');
  assert.equal(await page.locator('.voice-call-controls').isVisible(),false);
  await page.screenshot({path:evidence+'step020-ended.png'});
  // A fresh call clears controls; pre/post connection failures use authoritative copy.
  for (const [connected,status,reason,copy] of [
    [false,'failed','provider_error','暂时无法接通'],
    [false,'failed','system_error','暂时无法接通'],
    [true,'ended','provider_error','通话暂时中断，请稍后再试'],
    [true,'ended','system_error','通话暂时中断，请稍后再试'],
    [false,'missed','character_missed','她现在可能不方便']]) {
    await page.getByRole('button',{name:'关闭通话'}).click();
    result={...result,status,end_reason:reason,has_connected:connected,duration_seconds:connected?7:0,end_message:copy};
    const previous=await page.evaluate(()=>testSockets.length);
    await page.getByRole('button',{name:'发起通话'}).click();
    await page.waitForFunction(n=>testSockets.length>n,previous);
    if(connected){await send({type:'state',status:'connected',reconnect_timeout_ms:5000});
      await page.locator('.voice-entry.is-in-call').waitFor();
      assert.equal(await page.locator('.voice-call-mute').getAttribute('aria-pressed'),'false');
      assert.equal(await page.evaluate(()=>testStreams.at(-1).getAudioTracks()[0].enabled),true);
    }
    if(!connected&&reason==='provider_error')await page.evaluate(()=>testSockets.at(-1).onclose());
    else await send({type:'state',status});
    await page.getByRole('heading',{name:status==='missed'?'她这次没有接听':connected?'通话已结束':'暂时无法接通'}).waitFor();
    assert.equal(await page.locator('.voice-entry-description').innerText(),copy);
    assert.equal(await page.locator('.voice-call-clock').isVisible(),connected);
  }
  await page.getByRole('button',{name:'关闭通话'}).click();
  result={...result,status:'cancelled',end_reason:'user_cancel',show_end_page:false,has_connected:false};
  const previous=await page.evaluate(()=>testSockets.length);
  await page.getByRole('button',{name:'发起通话'}).click();await page.waitForFunction(n=>testSockets.length>n,previous);
  await send({type:'state',status:'ringing'});
  await page.getByRole('button',{name:'取消',exact:true}).click();
  assert.equal(await page.locator('.voice-entry').isVisible(),false);
  assert.ok(page.url().startsWith('http://127.0.0.1:'));
  assert.equal(requests.some(u=>u.includes('/chat')||u.includes('/messages')),false);
  // Hold navigation so processing feedback and duplicate suppression are observable.
  result={...result,status:'missed',end_reason:'character_missed',show_end_page:true,
    end_message:'她现在可能不方便'};
  const beforeReturn=await page.evaluate(()=>testSockets.length);
  await page.getByRole('button',{name:'发起通话'}).click();
  await page.waitForFunction(n=>testSockets.length>n,beforeReturn);
  await send({type:'state',status:'missed'});
  await page.getByRole('heading',{name:'她这次没有接听'}).waitFor();
  let navigationCount=0, releaseNavigation;
  const navigationGate=new Promise(resolve=>{releaseNavigation=resolve;});
  await page.route('**/pages/chat.html',async route=>{
    navigationCount++; await navigationGate;
    await route.fulfill({status:200,contentType:'text/html',body:'<meta charset="UTF-8"><h1>聊天时间线</h1>'});
  });
  const processing=await page.evaluate(()=>{
    const button=document.querySelector('.voice-entry-primary'), action=button.onclick;
    action(); action(); action();
    return {disabled:button.disabled,busy:button.getAttribute('aria-busy'),
      visible:!document.querySelector('.voice-entry').hidden,text:button.textContent,
      retryDisabled:document.querySelector('.voice-entry-secondary').disabled};
  });
  try {
    assert.deepEqual(processing,{disabled:true,busy:'true',visible:true,text:'正在返回聊天…',retryDisabled:true});
  } finally { releaseNavigation(); }
  await page.getByRole('heading',{name:'聊天时间线'}).waitFor();
  assert.equal(navigationCount,1);
  await page.goBack();
  const afterBack=await page.evaluate(()=>testSockets.length);
  await page.getByRole('button',{name:'发起通话'}).click();
  await page.waitForFunction(n=>testSockets.length>n,afterBack);
  await page.getByRole('button',{name:'关闭通话'}).click();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'passed',scope:'production H5 + real Chrome audio, controlled media/HTTP/socket',createRequests,reconnectRequests,endRequests,errors}));
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});

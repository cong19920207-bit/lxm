// Production UI with actual Python presentation output; transport and media controlled.
const assert=require('node:assert/strict'),fs=require('node:fs'),{execFileSync}=require('node:child_process');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const evidence=process.env.VOICE_EVIDENCE_DIR || 'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/';
const results=JSON.parse(execFileSync(process.env.VOICE_PYTHON||'.venv-step001/bin/python',['-c',`
import json
from datetime import datetime
from types import SimpleNamespace
from backend.constants.realtime_voice_config import get_default_voice_call_script
from backend.services.realtime_voice_presentation_service import call_presentation
script=get_default_voice_call_script()
rows=[]
for reason in script['end_reason']:
    for connected in ([False,True] if reason in ('provider_error','system_error') else [reason!='user_cancel']):
        row=SimpleNamespace(call_id='11111111-1111-4111-8111-111111111111',status='cancelled' if reason=='user_cancel' else 'ended' if connected else 'failed',end_reason=reason,connected_at=datetime.now() if connected else None,duration_seconds=73,config_snapshot={'resolved_script':script})
        rows.append(call_presentation(row))
row.status='missed';row.connected_at=None;row.end_reason=None
rows.append(call_presentation(row))
print(json.dumps(rows))
`],{encoding:'utf8'}));
const blockedCases={
 microphone_denied:['还听不见你的声音','允许麦克风后，才能继续和她通话。'],
 browser_unsupported:['换个浏览器，再和她说话','请使用 Safari 或 Chrome 打开本页，再试一次。'],
 quota_empty:['今天先聊到这里','今天能聊的时间用完啦，之后再来找她吧。'],
 user_banned:['暂时无法发起通话','当前账号暂时无法使用语音通话。'],
 not_allowlisted:['语音通话暂未开放','这项功能还在逐步准备中，先回聊天找她吧。'],
 disabled:['语音通话暂未开放','这项功能还在逐步准备中，先回聊天找她吧。'],
 soft_stop:['暂时无法接通','通话服务暂时休息一下，请稍后再试。'],
 maintenance:['暂时无法接通','通话服务正在维护，请稍后再试。'],
 capacity_full:['现在有点忙','请稍后再试。'],
 user_busy:['你已有一通进行中的通话','请先结束原来的通话。'],
 dial_cooldown:['稍等一下','上一通刚结束，请稍后再试。'],
 provider_unavailable:['暂时无法接通','通话服务暂时不可用，请稍后再试。'],
};
const endCopy={user_hangup:'就先聊到这',exit_intent:'好，那我们先聊到这',silence_timeout:'好像暂时听不到你，我们下次再聊',quota_exhausted:'今天能聊的时间用完啦，我们下次再聊',hard_limit:'这次聊得有点久，我们先休息一下',reconnect_timeout:'网络没有恢复，我们下次再接着聊'};
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const checks=[];
try{
 async function setup(reason,result,virtualClock=false,responseControl={}){
  const page=await browser.newPage({viewport:{width:402,height:874},reducedMotion:'reduce'}),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(reason=>{
   window.testSockets=[];window.stopped=0;window.AudioWorkletNode=class{};
   navigator.permissions.query=async()=>({state:'granted'});
   window.AudioContext=class{constructor(){this.audioWorklet={};}async resume(){}async close(){}};
   navigator.mediaDevices.getUserMedia=async()=>{if(reason==='microphone_denied')throw new DOMException('Denied','NotAllowedError');return {getTracks:()=>[{stop(){window.stopped++;}}]};};
   window.VoiceAudioTransport=class{constructor(){this.track={readyState:'live'};}async start(){}resumeTransport(){}pause(){}frame(){}isPlaying(){return false;}supportsOutputSelection(){return false;}async close(){}};
   window.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;testSockets.push(this);queueMicrotask(()=>this.onopen?.());}send(){}close(){this.readyState=3;}};
   if(reason==='browser_unsupported')window.AudioWorkletNode=undefined;
  },reason);
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!=='http://127.0.0.1:54321')return route.abort();
   if(url.pathname.startsWith('/api/')){
    requests.push({method:route.request().method(),path:url.pathname,key:route.request().headers()['idempotency-key']});
    if(reason==='network'&&url.pathname==='/api/voice/calls')return route.abort('failed');
    if(url.pathname==='/api/voice/calls')return reason?route.fulfill({status:409,json:{code:409,data:{block_reason:reason}}}):route.fulfill({json:{code:0,data:{call_id:result.call_id,call_ticket:'test'}}});
    if(route.request().method()==='GET'&&responseControl.fault){
     if(responseControl.fault==='network')return route.abort('failed');
     if(responseControl.fault==='http503')return route.fulfill({status:503,json:{code:503}});
     if(responseControl.fault==='invalid_json')return route.fulfill({status:200,contentType:'application/json',body:'{'});
     if(responseControl.fault==='nonterminal')return route.fulfill({json:{code:0,data:{...result,status:'ending'}}});
    }
    return route.fulfill({json:{code:0,data:result}});
   }
   if(url.pathname.startsWith('/static/'))return route.fulfill({path:'frontend'+url.pathname});
   return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/voice-entry.css"><button id="start" onclick="VoiceEntry.begin()">发起通话</button><script src="/static/js/voice-entry.js"></script>'});
  });
  if(virtualClock)await page.clock.install();
  await page.goto('http://127.0.0.1:54321/?flow=ended&review=true');
  assert.equal(await page.locator('.voice-entry:visible').count(),0);assert.equal(requests.length,0);
  await page.locator('#start').click();
  return {page,requests,errors};
 }
 async function layout(page,primaryLabel,secondaryLabel){
  assert.equal(await page.getByRole('button',{name:'关闭通话',exact:true}).isVisible(),true);
  assert.equal(await page.getByRole('button',{name:primaryLabel,exact:true}).isVisible(),true);
  if(secondaryLabel)assert.equal(await page.getByRole('button',{name:secondaryLabel,exact:true}).isVisible(),true);
  for(const [width,height] of [[402,874],[874,402],[320,480]]){
   await page.setViewportSize({width,height});
   const rects=await page.locator('.voice-entry button:visible').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {label:n.textContent,x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};}));
   for(const r of rects)assert.ok(r.w>=44&&r.h>=44&&r.x>=0&&r.y>=0&&r.right<=width&&r.bottom<=height,JSON.stringify({width,height,r}));
   assert.ok(await page.locator('.voice-entry').evaluate(n=>n.scrollWidth<=innerWidth));
  }
 }
 for(const [reason,[title,description]] of Object.entries(blockedCases)){
  const {page,requests,errors}=await setup(reason);
  await page.getByRole('heading',{name:title,exact:true}).waitFor();
  assert.equal(await page.locator('.voice-entry-description').innerText(),description);
  assert.equal(await page.evaluate(()=>testSockets.length),0);
  await page.screenshot({path:evidence+'step036-view-'+reason+'.png'});
  assert.equal(requests.length,['microphone_denied','browser_unsupported'].includes(reason)?0:1);
  if(!['microphone_denied','browser_unsupported'].includes(reason))assert.equal(await page.evaluate(()=>stopped),1);
  if(reason==='microphone_denied'){
   await page.getByRole('button',{name:'查看开启方法'}).click();
   assert.equal(await page.locator('.voice-entry-guide').isVisible(),true);
   assert.equal(await page.getByRole('button',{name:'重新检测'}).isVisible(),true);
  }
  await layout(page,reason==='microphone_denied'?'重新检测':['browser_unsupported','quota_empty'].includes(reason)?'回聊天找她':'稍后重试',reason==='quota_empty'?'稍后再说':['microphone_denied','browser_unsupported'].includes(reason)?'暂时不用':'回聊天找她');assert.deepEqual(errors,[]);
  if(reason==='quota_empty'){
   await page.getByRole('button',{name:'稍后再说',exact:true}).click();
   await page.locator('.voice-entry').waitFor({state:'hidden'});
   assert.equal(await page.locator('#start').evaluate(n=>n===document.activeElement),true);
   assert.equal(requests.length,1);
  }
  if(reason==='microphone_denied')await page.screenshot({path:evidence+'step036-permission-guide.png'});
  checks.push({kind:'blocked',reason,viewports:3});await page.close();
 }
 for(const result of results){
  const {page,requests,errors}=await setup(null,result);
  await page.waitForFunction(()=>testSockets.length===1);
  const send=status=>page.evaluate(status=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status})}),status);
  for(const [state,title] of [['deciding','正在呼叫林小梦'],['ringing','正在等待她接听']]){await send(state);await page.getByRole('heading',{name:title,exact:true}).waitFor();}
  if(result.has_connected){
   await send('connected');
   await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='listening');
   assert.equal(await page.getByRole('button',{name:'挂断',exact:true}).isVisible(),true);
  }
  await send(result.status);
  if(result.status==='cancelled'){
   await page.locator('.voice-entry').waitFor({state:'hidden'});
   assert.equal(await page.getByRole('heading',{name:'通话已结束'}).count(),0);
   assert.equal(await page.locator('#start').evaluate(n=>n===document.activeElement),true);
  }else{
   const title=result.status==='missed'?'她这次没有接听':result.has_connected?'通话已结束':'暂时无法接通';
   await page.getByRole('heading',{name:title,exact:true}).waitFor();
   const expected=endCopy[result.end_reason]||(['provider_error','system_error'].includes(result.end_reason)?result.has_connected?'通话暂时中断，请稍后再试':'暂时无法接通':'她现在可能不方便');
   assert.equal(await page.locator('.voice-entry-description').innerText(),expected);
   assert.equal(await page.locator('.voice-call-clock').isVisible(),result.has_connected);
   if(result.has_connected)assert.equal(await page.locator('.voice-call-clock').innerText(),'01:13');
   await page.screenshot({path:evidence+'step036-view-'+(result.end_reason||'missed')+'-'+result.has_connected+'.png'});
   await layout(page,'返回聊天',result.status==='failed'&&!result.has_connected?'重新尝试':null);
   if(result.status==='missed')assert.equal(await page.locator('.voice-entry-secondary').isVisible(),false);
  }
  assert.equal(requests.filter(r=>r.path==='/api/voice/calls').length,1);
  assert.deepEqual(errors,[]);checks.push({kind:'terminal',reason:result.end_reason,status:result.status,connected:result.has_connected});await page.close();
 }
 for(const fault of ['network','http503','invalid_json','nonterminal']){
  const result=results.find(r=>r.end_reason==='user_hangup'),responseControl={};
  const {page,requests,errors}=await setup(null,result,false,responseControl);
  await page.waitForFunction(()=>testSockets.length===1);
  await page.evaluate(()=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status:'connected',reconnect_timeout_ms:5000})}));
  await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='listening');
  responseControl.fault=fault;
  await page.evaluate(()=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status:'ended'})}));
  await page.getByRole('heading',{name:'正在确认通话结果',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.voice-entry-primary').disabled===false);
  assert.equal(await page.locator('.voice-call-clock').isVisible(),false);
  assert.equal(await page.locator('.voice-call-controls').isVisible(),false);
  assert.equal(await page.evaluate(()=>stopped),1);
  assert.equal(await page.evaluate(()=>testSockets[0].readyState),3);
  await layout(page,'重新检查','返回聊天');
  if(fault==='http503')await page.screenshot({path:evidence+'r06-result-pending.png'});
  delete responseControl.fault;
  await page.getByRole('button',{name:'重新检查',exact:true}).click();
  await page.getByRole('heading',{name:'通话已结束',exact:true}).waitFor();
  assert.equal(await page.locator('.voice-call-clock').innerText(),'01:13');
  assert.equal(requests.filter(r=>r.method==='POST').length,1);
  assert.equal(await page.evaluate(()=>testSockets.length),1);
  assert.deepEqual(errors,[]);checks.push({kind:'terminal_result_retry',fault});await page.close();
 }
 {
  const {page,requests,errors}=await setup('quota_empty');
  await page.getByRole('heading',{name:'今天先聊到这里',exact:true}).waitFor();
  await page.getByRole('button',{name:'回聊天找她',exact:true}).click();
  await page.waitForURL('**/pages/chat.html');
  assert.equal(requests.length,1);assert.deepEqual(errors,[]);
  checks.push({kind:'quota_return_chat'});await page.close();
 }
 {
  const {page,requests,errors}=await setup('network');
  await page.getByRole('heading',{name:'暂时没有收到结果',exact:true}).waitFor();
  assert.equal(await page.locator('.voice-entry-description').innerText(),'可以重新检查，本次请求会沿用原来的编号。');
  await page.getByRole('button',{name:'重新检查',exact:true}).click();
  await page.getByRole('heading',{name:'暂时没有收到结果',exact:true}).waitFor();
  assert.equal(requests.length,2);assert.ok(requests[0].key);assert.equal(requests[0].key,requests[1].key);
  assert.equal(await page.evaluate(()=>testSockets.length),0);await layout(page,'重新检查','回聊天找她');assert.deepEqual(errors,[]);
  checks.push({kind:'network_retry',sameIdempotencyKey:true});await page.close();
 }
 {
  const {page,requests,errors}=await setup(null,results[0],true);
  await page.waitForFunction(()=>testSockets.length===1);
  await page.evaluate(()=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status:'ringing'})}));
  await page.getByRole('heading',{name:'正在等待她接听',exact:true}).waitFor();
  await page.clock.runFor(60000);
  assert.equal(await page.getByRole('heading',{name:'正在等待她接听',exact:true}).isVisible(),true);
  assert.equal(requests.length,1); // Demo query and elapsed time cannot manufacture a transition.
  await page.getByRole('button',{name:'取消',exact:true}).click();
  await page.locator('.voice-entry').waitFor({state:'hidden'});
  await page.waitForFunction(()=>stopped===1);
  assert.equal(await page.locator('#start').evaluate(n=>n===document.activeElement),true);
  assert.equal(await page.evaluate(()=>testSockets[0].readyState),3);
  assert.deepEqual(errors,[]);checks.push({kind:'ringing_cancel',noDemoTransitionAfterMs:60000});await page.close();
 }
 for(const action of ['cancel','connected']){
  const {page,requests,errors}=await setup(null,results[0]);
  await page.waitForFunction(()=>testSockets.length===1);
  await page.evaluate(()=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status:'ringing',phase:'connecting'})}));
  await page.getByRole('heading',{name:'林小梦',exact:true}).waitFor();
  assert.equal(await page.locator('.voice-entry-description').innerText(),'正在接通');
  assert.equal(await page.locator('.voice-call-clock').isVisible(),false);
  assert.equal(await page.locator('.voice-call-controls').isVisible(),false);
  await layout(page,'取消',null);
  if(action==='cancel'){
   await page.screenshot({path:evidence+'step036-connecting.png'});
   await page.getByRole('button',{name:'取消',exact:true}).click();
   await page.locator('.voice-entry').waitFor({state:'hidden'});
   assert.equal(await page.evaluate(()=>stopped),1);
   assert.equal(await page.evaluate(()=>testSockets[0].readyState),3);
  }else{
   await page.evaluate(()=>testSockets[0].onmessage({data:JSON.stringify({v:1,type:'state',status:'connected'})}));
   await page.waitForFunction(()=>document.querySelector('.voice-entry').dataset.callState==='listening');
   assert.equal(await page.locator('.voice-entry-description').innerText(),'在听');
   assert.equal(await page.locator('.voice-call-clock').isVisible(),true);
  }
  assert.equal(requests.filter(r=>r.path==='/api/voice/calls').length,1);
  assert.deepEqual(errors,[]);checks.push({kind:'connecting',action,viewports:3});await page.close();
 }
 fs.writeFileSync(evidence+'step036-states.json',JSON.stringify({passed:true,checks,scope:'desktop Chrome production UI; actual Python presentation; controlled HTTP/media/WebSocket'},null,2));
 console.log('PASS STEP036: '+checks.length+' precheck and terminal cases, 3 viewports, permission guide, authoritative end copy, duration and cancellation');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

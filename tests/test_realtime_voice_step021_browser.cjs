const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async () => {
 const browser = await chromium.launch({channel:'chrome',headless:true});
 try {
  const page = await browser.newPage({viewport:{width:390,height:844},timezoneId:'Asia/Shanghai'});
  await page.setContent('<meta charset="utf-8"><main id="cards"></main>');
  await page.addStyleTag({content:'.msg-row{display:flex;margin:12px 0} body{background:#eee;font-family:sans-serif}'+fs.readFileSync('frontend/static/css/voice-call-cards.css','utf8')});
  await page.addScriptTag({path:'frontend/static/js/voice-call-cards.js'});
  await page.evaluate(() => {
   for (const status of ['pending','ready','failed','not_applicable','missed']) {
    document.querySelector('#cards').append(VoiceCallCards.render({source:'call',call_id:status,call_status:status==='missed'?'missed':'ended',duration_seconds:73,summary_status:status,call_summary:'<img src=x onerror=alert(1)> 今天聊了旅行计划。'.repeat(3)},Date.UTC(2026,8,20,13,48)));
   }
  });
  assert.equal(await page.locator('.voice-call-row').count(),5);
  assert.equal(await page.locator('button').count(),1);
  assert.equal(await page.locator('img').count(),0);
  assert.equal(await page.locator('[data-call-id=pending] .voice-call-summary').innerText(),'摘要整理中');
  assert.equal(await page.locator('[data-call-id=pending] .voice-call-static').innerText(),'刚刚聊了一会儿');
  assert.equal(await page.locator('[data-call-id=missed] .voice-call-title').innerText(),'语音通话 · 未接听');
  assert.equal(await page.locator('[data-call-id=missed] time').innerText(),'21:48');
  assert.equal(await page.locator('[data-call-id=missed] time').getAttribute('datetime'),'2026-09-20T13:48:00.000Z');
  assert.equal(await page.locator('[data-call-id=missed] button, [data-call-id=missed] .voice-call-summary').count(),0);
  assert.equal(await page.evaluate(()=>VoiceCallCards.render({call_status:'missed'},null).querySelector('time')),null);
  for(const status of ['failed','not_applicable']) assert.match(await page.locator(`[data-call-id=${status}]`).innerText(),/01:13\s+刚刚聊了一会儿/);
  const button=page.locator('button.voice-call-card');
  await button.locator('.voice-call-title').click();assert.equal(await button.getAttribute('aria-expanded'),'true');
  await button.locator('.voice-call-summary').click();assert.equal(await button.getAttribute('aria-expanded'),'false');
  const target=await button.boundingBox();assert.ok(target.width>=44&&target.height>=44,JSON.stringify(target));
  await button.focus();await page.keyboard.press('Enter');
  assert.equal(await button.getAttribute('aria-expanded'),'true');
  assert.ok(await page.locator('.is-expanded').count());
  await page.keyboard.press('Space');assert.equal(await button.getAttribute('aria-expanded'),'false');
  await page.keyboard.press('Enter');assert.equal(await button.getAttribute('aria-expanded'),'true');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const result=await page.evaluate(async()=>{
   let callback,delay,requests=1,updates=0,cancelled=0,active=true,requestedContext;
   const pending=[{source:'call',summary_status:'pending'}];
   const refresher=VoiceCallCards.pendingRefresh({schedule:(fn,ms)=>{callback=fn;delay=ms;return 1},cancel:()=>cancelled++,active:()=>active,fetch:async context=>{requestedContext=context;requests++;return pending},update:()=>updates++});
   refresher.observe(pending,'/api/chat/timeline?limit=20&cursor=40');refresher.observe(pending,'ignored');
   await callback();refresher.observe(pending);await Promise.resolve();
   const first={delay,requests,updates};
   refresher.reset();refresher.observe(pending);const stale=callback;refresher.reset();await stale();
   return {first,requests,updates,cancelled,requestedContext};
  });
  assert.deepEqual(result,{first:{delay:3000,requests:2,updates:1},requests:2,updates:1,cancelled:1,requestedContext:'/api/chat/timeline?limit=20&cursor=40'});
  fs.mkdirSync('docs/design/realtime_voice/P1/execution/evidence/m6-20260913',{recursive:true});
  await page.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step021-cards-mobile.png'});
  const chat = await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];chat.on('pageerror',error=>errors.push(error.message));
  await chat.addInitScript(()=>localStorage.setItem('token','local-test-only'));
  await chat.clock.install();
  let timelineRequests=0,olderPage=false,summaryReady=false,invalidMissedTime=false;
  const timelineUrls=[];
  await chat.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!=='http://voice.test')return route.abort();
   if(url.pathname.startsWith('/api/')){
    let data={};
    if(url.pathname==='/api/chat/timeline'){
     timelineRequests++;
     timelineUrls.push(url.pathname+url.search);
     data={has_more:false,next_cursor:null,items:[
      {source:'user',id:1,sort_seq:1,content:'旅行计划',created_at:'2026-09-13T10:00:00Z'},
      {source:'agent',id:2,sort_seq:2,content:'明天再聊',created_at:'2026-09-13T10:00:01Z'},
      {source:'call',id:3,sort_seq:3,call_id:'call-test',call_status:'ended',duration_seconds:73,summary_status:summaryReady?'ready':'pending',call_summary:summaryReady?'今天聊了旅行计划，下次接着聊想去的地方。':null,created_at:'2026-09-13T10:00:02Z'}]};
     if(olderPage && !url.searchParams.has('cursor')){
      data.items=data.items.slice(0,2);data.has_more=true;data.next_cursor=3;
     }else if(olderPage){data.items=data.items.slice(2);}
     if(invalidMissedTime){const call=data.items.find(item=>item.source==='call');call.call_status='missed';call.created_at='invalid';}
    }else if(url.pathname==='/api/agent/messages')data={messages:[]};
    return route.fulfill({json:{code:0,data}});
   }
   const file='frontend'+url.pathname;
   if(!url.pathname.includes('..') && fs.existsSync(file))return route.fulfill({path:file});
   return route.fulfill({status:404,body:''});
  });
  await chat.goto('http://voice.test/pages/chat.html');
  await chat.locator('.voice-call-row').waitFor();
  assert.equal(await chat.locator('.msg-row.user').count(),1);
  assert.equal(await chat.locator('.msg-row.ai').count(),1);
  assert.equal(timelineRequests,1);
  await chat.clock.runFor(2999);assert.equal(timelineRequests,1);
  const refreshResponse=chat.waitForResponse(response=>response.url().includes('/api/chat/timeline'));
  await chat.clock.runFor(1);
  await refreshResponse;
  assert.equal(timelineRequests,2);
  await chat.clock.runFor(9000);assert.equal(timelineRequests,2);
  assert.deepEqual(errors,[]);
  await chat.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step021-chat-mobile.png'});
  olderPage=true;timelineRequests=0;timelineUrls.length=0;
  await chat.addInitScript(()=>{window.IntersectionObserver=class{observe(){}disconnect(){}}});
  await chat.reload();await chat.locator('.msg-row.user').waitFor();
  assert.equal(await chat.locator('.voice-call-row').count(),0);
  await chat.evaluate(()=>loadTimeline(false));
  await chat.locator('.voice-call-row').waitFor();
  assert.equal(timelineRequests,2);
  const olderRefresh=chat.waitForResponse(response=>response.url().includes('/api/chat/timeline'));
  await chat.clock.runFor(3000);await olderRefresh;
  await chat.clock.runFor(9000);
  assert.equal(timelineRequests,3); // Two explicit page reads, one automatic refresh.
  assert.deepEqual(timelineUrls.slice(1),['/api/chat/timeline?limit=20&cursor=3','/api/chat/timeline?limit=20&cursor=3&pending_reload=true']);
  assert.deepEqual(errors,[]);
  summaryReady=true;olderPage=false;timelineRequests=0;
  await chat.reload();
  const readyCard=chat.locator('button.voice-call-card');await readyCard.waitFor();
  await readyCard.locator('.voice-call-title').click();assert.equal(await readyCard.getAttribute('aria-expanded'),'true');
  await readyCard.focus();await chat.keyboard.press('Space');assert.equal(await readyCard.getAttribute('aria-expanded'),'false');
  await chat.clock.runFor(9000);assert.equal(timelineRequests,1);
  assert.equal(await chat.locator('.voice-call-row .msg-bubble').count(),0);
  await chat.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step021-chat-ready.png'});
  assert.deepEqual(errors,[]);
  invalidMissedTime=true;await chat.reload();await chat.locator('.voice-call-card.is-missed').waitFor();
  assert.equal(await chat.locator('.voice-call-card.is-missed time').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: card states, safe text, expansion, mobile overflow, one 3s refresh, stale reset');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});

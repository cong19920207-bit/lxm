const assert=require('node:assert/strict'),fs=require('node:fs');const {setup,artifact}=require('./home_browser_helpers.cjs');
(async()=>{const results=[];let s=await setup();try{
 let held;await s.page.route('**/home-scene.js',r=>{held=r});const navigation=s.page.goto(s.origin+'/pages/index.html',{waitUntil:'domcontentloaded'});await s.page.waitForFunction(()=>HomeStartup.phase==='ready',{},{timeout:8500});assert.equal(await s.page.locator('#home-loading-screen').count(),0);assert.equal(await s.page.locator('.home-cta-btn').evaluate(e=>getComputedStyle(e.closest('.home-enter-item')).opacity),'1');
 while(!held)await new Promise(r=>setTimeout(r,10));await held.fulfill({contentType:'text/javascript',body:fs.readFileSync('frontend/static/js/home-scene.js','utf8')});await navigation;await s.page.waitForFunction(()=>HomeScene.current.running);assert.equal(await s.page.evaluate(()=>HomeScene.current.id),1);await s.page.waitForFunction(()=>getHomeDataController().inspect().batches===0);assert.equal(s.apiRequests.length,1);assert.deepEqual(s.errors,[]);results.push({case:'actual scene script arrives after independent 8s head deadline; ready state read, one scene/data init',pass:true})
 }finally{await s.close()}
 for(const failure of ['ResizeObserver','WAAPI','core','script','background','character']){s=await setup();try{
  await s.page.addInitScript(()=>sessionStorage.setItem('lxm_home_loader_done','1'));
  if(failure==='ResizeObserver')await s.page.addInitScript(()=>window.ResizeObserver=function(){throw Error('controlled observer failure')});
  else if(failure==='WAAPI')await s.page.addInitScript(()=>Element.prototype.animate=function(){throw Error('controlled WAAPI failure')});
  else if(failure==='core'||failure==='script')await s.page.route(failure==='core'?'**/home-scene-core.js':'**/home-scene.js',r=>r.abort());
  else await s.page.route(`**/home-scene/v4/${failure}.*.webp`,r=>r.abort());
  await s.page.goto(s.origin+'/pages/index.html');await s.page.locator("button[onclick=\"handleHomeQuickAction('more')\"]").click();await s.page.waitForSelector('#auth-login-modal.is-open');assert.deepEqual(s.errors,[]);results.push({case:'optional '+failure+' fault isolated from static/business entry',pass:true})
 }finally{await s.close()}}
 fs.writeFileSync(artifact('docs/design/home-redesign/execution/evidence/home-m3/scene-boundaries-results.json'),JSON.stringify({scope:'Actual desktop page, actual delayed external script and controlled optional API/core failures',results},null,2)+'\n');console.log('PASS '+results.length+' late module/optional API scenarios')
})().catch(e=>{console.error(e);process.exitCode=1});

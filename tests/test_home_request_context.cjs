const assert=require('node:assert/strict'),fs=require('node:fs');
const {setup,artifact}=require('./home_browser_helpers.cjs');
async function start(){const s=await setup({token:true});await s.page.addInitScript(()=>{if(!sessionStorage.getItem('__home_context_fixture_seeded')){sessionStorage.setItem('lxm_home_loader_done','1');sessionStorage.setItem('__home_context_fixture_seeded','1')}});await s.page.goto(s.origin+'/pages/index.html');await s.page.waitForFunction(()=>document.getElementById('relationship-level-name').textContent==='亲密');return s;}
(async()=>{const results=[];
 for(const policy of ['legacy-login-page','silent-visitor','protected-home-modal','interactive-modal']){
  const s=await start();try{
   await s.page.route('**/api/controlled401',r=>r.fulfill({status:401,contentType:'application/json',body:'{}'}));
   await s.page.evaluate(policy=>{window.valid401Callback=false;request('GET','/api/controlled401',null,policy==='legacy-login-page'?{}:{authPolicy:policy,onUnauthorized:()=>{window.valid401Callback=true}}).catch(()=>{})},policy);
   if(policy==='legacy-login-page')await s.page.waitForURL('**/pages/login.html');
   else if(policy.includes('modal'))await s.page.waitForSelector('#auth-login-modal.is-open');
   else await s.page.waitForFunction(()=>window.valid401Callback);
   assert.equal(await s.page.evaluate(()=>localStorage.getItem('token')),null);
   assert.equal(await s.page.evaluate(()=>sessionStorage.getItem('lxm_home_loader_done')),null);
   if(policy!=='legacy-login-page')assert.equal(await s.page.evaluate(()=>window.valid401Callback),true);
   assert.deepEqual(s.errors,[]);results.push({case:'effective 401 '+policy,pass:true});console.log('PASS '+policy);
  }finally{await s.close();}
 }
 const s=await start();try{
  let held;await s.page.route('**/api/held401',r=>{held=r});
  await s.page.evaluate(()=>{window.currentContext=true;request('GET','/api/held401',null,{isCurrent:()=>window.currentContext}).then(()=>window.outcome='delivered',e=>window.outcome=e.name)});
  while(!held)await new Promise(r=>setTimeout(r,10));
  await s.page.evaluate(()=>{localStorage.setItem('token','controlled-new-session');window.currentContext=false});
  await held.fulfill({status:401,body:'{}'});await s.page.waitForFunction(()=>window.outcome);
  assert.equal(await s.page.evaluate(()=>window.outcome),'StaleRequestError');assert.equal(await s.page.evaluate(()=>localStorage.getItem('token')==='controlled-new-session'),true);
  results.push({case:'stale 401 before side effects',pass:true});
  // Change context while JSON is still parsing using the real shared request function.
  await s.page.evaluate(()=>{
   window.actualFetch=window.fetch;window.currentContext=true;window.outcome=null;
   window.fetch=async()=>({status:200,json:()=>new Promise(resolve=>window.resolveJSON=resolve)});
   request('GET','/api/parse',null,{isCurrent:()=>window.currentContext}).then(()=>window.outcome='delivered',e=>window.outcome=e.name);
  });
  await s.page.waitForFunction(()=>window.resolveJSON);
  await s.page.evaluate(()=>{window.currentContext=false;window.resolveJSON({code:0,data:{value:'old'}})});
  await s.page.waitForFunction(()=>window.outcome);assert.equal(await s.page.evaluate(()=>window.outcome),'StaleRequestError');
  await s.page.evaluate(()=>window.fetch=window.actualFetch);results.push({case:'context changes during JSON parse',pass:true});
  await s.page.route('**/api/cancel',()=>new Promise(()=>{}));
  const failed=s.page.waitForEvent('requestfailed',{predicate:r=>r.url().includes('/api/cancel')});
  await s.page.evaluate(()=>{window.outcome=null;window.controller=new AbortController();request('GET','/api/cancel',null,{signal:window.controller.signal}).then(()=>window.outcome='delivered',e=>window.outcome=e.name)});
  await s.page.waitForTimeout(50);await s.page.evaluate(()=>window.controller.abort());await failed;
  await s.page.waitForFunction(()=>window.outcome);assert.equal(await s.page.evaluate(()=>window.outcome),'AbortError');
  assert.equal(await s.page.evaluate(()=>localStorage.getItem('token')==='controlled-new-session'),true);results.push({case:'AbortSignal cancels real fetch',pass:true});
  await s.page.route('**/api/offline',r=>r.abort());
  const legacy=await s.page.evaluate(()=>request('GET','/api/offline'));assert.equal(legacy.code,-1);results.push({case:'legacy network error result',pass:true});
  assert.deepEqual(s.errors,[]);
 }finally{await s.close();}
 fs.writeFileSync(artifact('docs/design/home-redesign/execution/evidence/home-m2/step-005-results.json'),JSON.stringify({scope:'Actual api.js in real index.html, desktop Chrome; real fetch cancellation and controlled async responses',results},null,2)+'\n');
 console.log('PASS '+results.length+' request context cases');
})().catch(e=>{console.error(e);process.exitCode=1});

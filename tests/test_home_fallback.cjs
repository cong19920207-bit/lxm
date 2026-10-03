const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup,ready,root}=require('./home_browser_helpers.cjs');
const output=process.env.HOME_REGRESSION_EVIDENCE_DIR||path.join(root,'docs/design/home-redesign/execution/evidence/home-m4');
async function legacy(s){await s.page.route('**/pages/index.html',async route=>{const response=await route.fetch();const html=await response.text();await route.fulfill({response,body:html.replace(/<html\b[^>]*>/,'<html lang="zh-CN" data-home-scene-mode="legacy">')});});}
(async()=>{const results=[];fs.mkdirSync(output,{recursive:true});
 for(const mode of ['dynamic','legacy','legacy-storage-api-fault','legacy-image-fault','both-core-fault','one-core-fault','legacy-preference']){
  const s=await setup({token:mode==='legacy-preference'});try{
   if(mode.startsWith('legacy'))await legacy(s);
   if(!['legacy-storage-api-fault','legacy-image-fault'].includes(mode))await s.page.addInitScript(()=>sessionStorage.setItem('lxm_home_loader_done','1'));
   if(mode==='legacy-storage-api-fault'){await s.page.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw Error('controlled storage fault')}})});await s.page.route('**/api/**',()=>{});}
   if(mode==='legacy-image-fault')await s.page.route('**/static/images/Index/Index.png',route=>route.abort());
   if(mode==='both-core-fault')await s.page.route('**/home-scene/v4/{background,character}.*.webp',route=>route.abort());
   if(mode==='one-core-fault')await s.page.route('**/home-scene/v4/background.*.webp',route=>route.abort());
   if(mode==='legacy-preference')await s.page.addInitScript(()=>localStorage.setItem('lxm_home_motion_enabled','1'));
   const started=Date.now();await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
   const useLegacy=mode.startsWith('legacy')||mode==='both-core-fault';
   if(useLegacy&&mode!=='legacy-image-fault')await s.page.waitForFunction(()=>document.querySelector('.home-scene-background').naturalWidth>0);
   const actual=await s.page.evaluate(()=>({background:document.querySelector('.home-scene-background')?.getAttribute('src'),mode:HomeStartup.sceneMode,scene:HomeScene?.current?.inspect(),releases:HomeStartup.releases,hitEnabled:!document.querySelector('.home-scene-hit').disabled,visible:getComputedStyle(document.querySelector('.home-cta-btn').closest('.home-enter-item')).opacity}));
   assert.equal(actual.background,useLegacy?'/static/images/Index/Index.png':'/static/images/home-scene/v4/background.c094490a4d8e.webp');assert.equal(actual.releases,1);assert.equal(actual.visible,'1');
   if(useLegacy){assert.equal(actual.scene.running,false);assert.ok(actual.scene.reasons.includes('legacy'));assert.equal(actual.hitEnabled,false);assert.equal(s.requests.filter(item=>/home-scene\/v4\/(hair_|blink_|lamp_)/.test(item.path)).length,0);}
   if(mode.startsWith('legacy'))assert.equal(s.requests.filter(item=>item.path.includes('/home-scene/v4/')).length,0,'Configured rollback must not fetch unused new scene');
   if(mode==='dynamic'||mode==='one-core-fault')assert.equal(s.requests.filter(item=>item.path==='/static/images/Index/Index.png').length,0,'Normal new scene must not preheat old large background');
   if(mode==='legacy-preference'){
    await s.page.getByRole('button',{name:'更多互动',exact:true}).click();
    assert.equal(await s.page.locator('.toast-item').last().textContent(),'敬请期待');
    assert.equal(await s.page.evaluate(()=>HomeScene.current.motionEnabled),true);
    assert.equal(await s.page.evaluate(()=>HomeScene.tilt.inspect().state),'legacy');
    assert.equal(await s.page.evaluate(()=>localStorage.getItem('lxm_home_motion_enabled')),'1');
    await s.page.locator('#linxiaomeng-avatar').click();await s.page.waitForURL(s.origin+'/pages/settings.html');
    await s.page.getByRole('switch',{name:'倾斜视差',exact:true}).click();
    assert.equal(await s.page.getByRole('switch',{name:'倾斜视差',exact:true}).getAttribute('aria-checked'),'false');
    assert.match(await s.page.locator('#home-tilt-setting-status').innerText(),/旧背景/);
   }
   if(mode!=='legacy-preference'){await s.page.getByRole('button',{name:'她的日记',exact:false}).click();await s.page.locator('#auth-login-modal.is-open').waitFor({state:'visible'});assert.equal(await s.page.locator('#auth-login-modal.is-open').count(),1);}
   assert.equal(s.errors.length,0);const elapsed=Date.now()-started;assert.ok(elapsed<8500,'Rollback must retain bounded loader despite data/image/storage failures');results.push({case:mode,pass:true,elapsedMs:elapsed,actual,requests:s.requests,errors:s.errors});
   if(mode==='legacy'){await s.page.evaluate(()=>closeLoginModal());await s.page.locator('#auth-login-modal').waitFor({state:'hidden'});await s.page.screenshot({path:path.join(output,'step-014-legacy.png'),fullPage:true});}
  }finally{await s.close()}
 }
 fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'step-014-fallback-results.json'),JSON.stringify({scope:'Actual frontend desktop Chrome with explicitly controlled API/storage/image faults; not phone/HTTPS validation',results},null,2)+'\n');console.log('PASS '+results.length+' rollback and preserved startup/business scenarios');
})().catch(error=>{console.error(error);process.exitCode=1});

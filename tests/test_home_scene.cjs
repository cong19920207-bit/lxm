const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup,ready,evidence}=require('./home_browser_helpers.cjs');
const views=[{width:375,height:667},{width:390,height:844},{width:430,height:932},{width:1280,height:720}];
const manifest=JSON.parse(fs.readFileSync('frontend/static/images/home-scene/v4/manifest.json'));
(async()=>{
 const results=[];
 for(const viewport of views){
  const s=await setup({viewport,dpr:viewport.width<1000?3:1});
  try{
   await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
   assert.equal(await s.page.locator('.home-scene-core').count(),2,'Two full static core layers are required');
   await s.page.waitForFunction(()=>[...document.querySelectorAll('.home-scene-core')].every(i=>i.complete&&i.naturalWidth));
   const measure=await s.page.evaluate(()=>{
    const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
    const rig=rect(document.querySelector('.home-scene-position'));
    const face={x:rig.x+rig.width*.36,y:rig.y+rig.height*.17,right:rig.x+rig.width*.68,bottom:rig.y+rig.height*.33};
    return {rig,face,top:rect(document.querySelector('.home-top-bar')),hero:rect(document.querySelector('.home-hero')),float:rect(document.querySelector('.home-hero-float')),
     controls:[...document.querySelectorAll('.home-quick-btn,.home-intimacy-pill,#linxiaomeng-avatar,.home-preview-card,.home-cta-btn')].map(rect),scene:rect(document.querySelector('.home-scene')),
     zoom:document.querySelector('meta[name=viewport]').content, touch:getComputedStyle(document.querySelector('.home-scene')).touchAction};
   });
   assert.ok(measure.face.x>=0&&measure.face.right<=viewport.width);
   assert.ok(measure.face.y>=measure.top.bottom&&measure.face.bottom<=measure.hero.bottom,'Face clears top bar and business cards');
   assert.ok(measure.face.x>=measure.float.right||measure.face.y>=measure.float.bottom,'Face does not intersect status/clock');
   assert.ok(!measure.zoom.includes('user-scalable=no')&&!measure.zoom.includes('maximum-scale=1'));
   assert.notEqual(measure.touch,'none');
   for(const c of measure.controls)assert.ok(c.width>0&&c.height>0&&c.x>=0&&c.right<=viewport.width);
   await s.page.locator('.home-cta-btn').scrollIntoViewIfNeeded();assert.ok(await s.page.locator('.home-cta-btn').isVisible());
   await s.page.screenshot({path:path.join(evidence,`step-003-${viewport.width}x${viewport.height}.png`)});
   const patches=manifest.assets.filter(a=>a.placement_in_character_canvas);
   for(const a of patches){
    const selector='.home-scene-'+a.role.replace('_','-');
    const actual=await s.page.locator(selector).evaluate(async img=>{
     img.src=img.dataset.src;await img.decode();img.hidden=false;
     const r=img.getBoundingClientRect(),p=img.parentElement.getBoundingClientRect();
     return {left_percent:(r.left-p.left)/p.width*100,top_percent:(r.top-p.top)/p.height*100,width_percent:r.width/p.width*100,height_percent:r.height/p.height*100};
    });
    for(const key of ['left_percent','top_percent','width_percent','height_percent'])assert.ok(Math.abs(actual[key]-a.placement_in_character_canvas[key])<.02,'Patch coordinates match source canvas: '+a.role+' '+key);
   }
   await s.page.locator('.home-scene-blink').evaluate(i=>{i.style.opacity='1'});
   await s.page.screenshot({path:path.join(evidence,`step-003-${viewport.width}-closed.png`)});
   await s.page.locator('.home-scene-blink').evaluate(i=>{i.style.opacity='0'});
   await s.page.locator('.h5-home-page').evaluate(e=>{e.style.setProperty('--home-safe-top','34px');e.style.setProperty('--home-safe-bottom','34px')});
   await s.page.waitForFunction(()=>parseFloat(getComputedStyle(document.querySelector('.home-top-bar')).paddingTop)===66);
   await s.page.locator('.home-cta-btn').scrollIntoViewIfNeeded();
   const safeBottom=await s.page.locator('.action-section').evaluate(e=>parseFloat(getComputedStyle(e).paddingBottom));
   assert.ok(safeBottom>=34,'Bottom control respects inset');
   // Rotation, increased card contents and a keyboard-like narrow visual space.
   await s.page.setViewportSize({width:viewport.height,height:viewport.width});
   await s.page.locator('.home-cta-btn').scrollIntoViewIfNeeded();
   await s.page.locator('.home-diary-card').evaluate(e=>{e.style.minHeight='210px'});
   await s.page.setViewportSize({width:375,height:450});
   await s.page.locator('.home-cta-btn').scrollIntoViewIfNeeded();
   await s.page.locator('.home-diary-card').click();await s.page.waitForSelector('#auth-login-modal.is-open');
   await s.page.locator('#auth-modal-login-username').focus();
   await s.page.evaluate(()=>closeLoginModal());
   await s.page.locator('.home-quick-btn').first().click();
   await s.page.waitForSelector('#auth-login-modal.is-open');
   assert.deepEqual(s.errors,[]);
   results.push({viewport,pass:true,measure});
  }finally{await s.close();}
 }
 for(const fault of ['background','character','optional','script','canvas']){
  const s=await setup();try{
   if(fault==='script')await s.page.route('**/home-scene.js*',r=>r.abort());
   else if(fault==='canvas')await s.page.addInitScript(()=>HTMLCanvasElement.prototype.getContext=function(){throw Error('Canvas unavailable')});
   else await s.page.route('**/home-scene/v4/*',r=>{const p=r.request().url();return (fault==='optional'?/hair_|blink_|lamp_/.test(p):p.includes('/'+fault+'.'))?r.abort():r.continue()});
   await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
   const core=await s.page.locator('.home-scene-core').evaluateAll(images=>images.map(i=>({loaded:i.naturalWidth>0,hidden:i.hidden})));
   if(fault==='background'||fault==='character')assert.equal(core.filter(i=>i.loaded).length,1);
   else assert.equal(core.filter(i=>i.loaded).length,2);
   await s.page.locator('.home-quick-btn').first().click();await s.page.waitForSelector('#auth-login-modal.is-open');
   assert.deepEqual(s.errors,[]);results.push({fault,core,pass:true});
  }finally{await s.close();}
 }
 fs.writeFileSync(path.join(evidence,'step-003-results.json'),JSON.stringify({scope:'Desktop Chrome controlled viewports/faults; real frontend; no real iOS keyboard/safe-area/pinch claims',results},null,2)+'\n');
 console.log('PASS: static scene, 4 viewports, rotation/cards, entry interaction, 5 faults');
})().catch(e=>{console.error(e);process.exitCode=1;});

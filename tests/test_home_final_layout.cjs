const assert=require('node:assert/strict'),fs=require('node:fs');const {setup,artifact}=require('./home_browser_helpers.cjs');
const views=[{width:375,height:667},{width:390,height:844},{width:430,height:932},{width:1280,height:720}];
const assets=JSON.parse(fs.readFileSync('frontend/static/images/home-scene/v4/manifest.json')).assets;
(async()=>{const results=[];for(const viewport of views){const s=await setup({viewport,dpr:viewport.width<1000?3:1});try{
 await s.page.addInitScript(()=>sessionStorage.setItem('lxm_home_loader_done','1'));await s.page.goto(s.origin+'/pages/index.html');await s.page.waitForFunction(()=>HomeScene.motion.inspect().loaded.length===5);await s.page.evaluate(()=>HomeScene.current.pause('layout-check'));
 const measure=await s.page.evaluate(()=>{
  const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
  const rig=rect(document.querySelector('.home-scene-position')),bg=rect(document.querySelector('.home-scene-background')),scale=Math.max(bg.width/853,bg.height/1844);
  // (840,715) is on the lit shade in the source image and stays visible at the approved 12px tilt.
  return{rig,face:{x:rig.x+rig.width*.36,y:rig.y+rig.height*.17,right:rig.x+rig.width*.68,bottom:rig.y+rig.height*.33},lampPoint:{x:bg.x+(bg.width-853*scale)/2+840*scale,y:bg.y+(bg.height-1844*scale)/2+715*scale},top:rect(document.querySelector('.home-top-bar')),hero:rect(document.querySelector('.home-hero')),float:rect(document.querySelector('.home-hero-float')),zoom:document.querySelector('meta[name=viewport]').content,
  controls:[...document.querySelectorAll('.home-quick-btn,.home-intimacy-pill,#linxiaomeng-avatar,.home-preview-card,.home-cta-btn')].map(e=>({...rect(e),opacity:getComputedStyle(e.closest('.home-enter-item')||e).opacity}))}
 });
 assert.ok(measure.face.y>=measure.top.bottom&&measure.face.bottom<=measure.hero.bottom);assert.ok(measure.face.x>=measure.float.right||measure.face.y>=measure.float.bottom);assert.ok(measure.face.x>=0&&measure.face.right<=viewport.width);
 assert.ok(measure.lampPoint.x>measure.rig.right+12,'A bright lamp portion remains beyond the person even with maximum tilt');assert.ok(measure.lampPoint.x<viewport.width&&measure.lampPoint.y>=0&&measure.lampPoint.y<viewport.height);
 for(const c of measure.controls){assert.ok(c.width>0&&c.height>0);assert.equal(c.opacity,'1','Business entries are visible immediately on mask release')}
 for(const asset of assets.filter(a=>a.placement_in_character_canvas)){
  const actual=await s.page.locator('.home-scene-'+asset.role.replace('_','-')).evaluate(img=>{const r=img.getBoundingClientRect(),p=img.parentElement.getBoundingClientRect();return{left_percent:(r.left-p.left)/p.width*100,top_percent:(r.top-p.top)/p.height*100,width_percent:r.width/p.width*100,height_percent:r.height/p.height*100}});
  for(const key of Object.keys(actual))assert.ok(Math.abs(actual[key]-asset.placement_in_character_canvas[key])<.02,'Source patch '+asset.role+' '+key)
 }
 await s.page.screenshot({path:artifact(`docs/design/home-redesign/execution/evidence/home-m3/final-${viewport.width}x${viewport.height}.png`)});await s.page.evaluate(()=>HomeScene.current.pause('layout-check',false));
 await s.page.getByRole('button',{name:'轻触林小梦'}).click();await s.page.waitForFunction(()=>HomeScene.motion.inspect().action==='response');
 await s.page.locator('.home-diary-card').click();await s.page.waitForSelector('#auth-login-modal.is-open');assert.equal(await s.page.evaluate(()=>HomeScene.current.running),false);await s.page.evaluate(()=>closeLoginModal());
 await s.page.setViewportSize({width:viewport.height,height:viewport.width});await s.page.locator('.home-diary-card').evaluate(e=>e.style.minHeight='210px');await s.page.setViewportSize({width:375,height:450});await s.page.locator('.home-cta-btn').scrollIntoViewIfNeeded();assert.equal(await s.page.locator('.home-cta-btn').isVisible(),true);assert.deepEqual(s.errors,[]);results.push({viewport,pass:true,measure})
 }finally{await s.close()}}
 fs.writeFileSync(artifact('docs/design/home-redesign/execution/evidence/home-m3/final-layout-results.json'),JSON.stringify({scope:'Actual desktop Chrome controlled phone/desktop sizes; static source alignment, lamp/face margins and real UI hits. Native device pinch/keyboard pending M4.',results},null,2)+'\n');console.log('PASS final composition, immediate visibility, source patches, input priority, rotation/short space')
})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),fs=require('node:fs');const {setup,artifact}=require('./home_browser_helpers.cjs');
(async()=>{const s=await setup();try{
 await s.page.addInitScript(()=>sessionStorage.setItem('lxm_home_loader_done','1'));await s.page.goto(s.origin+'/pages/index.html');await s.page.waitForFunction(()=>HomeScene.current.running);
 const result=await s.page.evaluate(async()=>{
  const c=HomeScene.current,first=c.inspect();for(let i=0;i<20;i++)HomeScene.mount();
  const same=HomeScene.mount()===c;c.pause('login');c.pause('hidden');c.pause('login',false);const combined=c.inspect();
  await new Promise(r=>setTimeout(r,120));const stopped=c.inspect();c.pause('hidden',false);await new Promise(r=>setTimeout(r,50));const resumed=c.inspect();
  window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));const cached=c.inspect();await new Promise(r=>setTimeout(r,100));window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));await new Promise(r=>setTimeout(r,40));const restored=c.inspect();
  window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false}));const destroyed=c.inspect();return {first,same,combined,stopped,resumed,cached,restored,destroyed}
 });
 assert.equal(result.same,true);assert.equal(result.combined.running,false);assert.deepEqual(result.combined.reasons,['hidden']);assert.equal(result.stopped.frames,result.combined.frames);assert.equal(result.resumed.running,true);assert.ok(result.resumed.time-result.stopped.time<100);assert.equal(result.cached.disposed,false);assert.equal(result.cached.running,false);assert.ok(result.restored.time-result.cached.time<90);assert.equal(result.destroyed.raf,false);assert.equal(result.destroyed.subscriptions,0);assert.equal(result.destroyed.effects,0);assert.equal(result.destroyed.timers,0);assert.deepEqual(s.errors,[]);
 fs.mkdirSync('docs/design/home-redesign/execution/evidence/home-m3',{recursive:true});fs.writeFileSync(artifact('docs/design/home-redesign/execution/evidence/home-m3/step-007-results.json'),JSON.stringify({scope:'Actual page desktop Chrome; controlled lifecycle events (not proof of native bfcache eligibility)',result},null,2)+'\n');console.log('PASS singleton, combined pause, clamped resume, persisted pause, complete destroy')
 }finally{await s.close()}})().catch(e=>{console.error(e);process.exitCode=1});

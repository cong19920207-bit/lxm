const assert=require('node:assert/strict'),fs=require('node:fs');
const {setup,artifact}=require('./home_browser_helpers.cjs');
const cases=[
 {name:'API hang',hang:'api'}, {name:'core hang',hang:'core'}, {name:'core decode hang',decode:true},
 {name:'core error',bad:true}, {name:'local property',fault:['local','property']}, {name:'token read',fault:['local','getItem','token']},
 {name:'session read',fault:['session','getItem','lxm_home_loader_done']}, {name:'session write',fault:['session','setItem','lxm_home_loader_done']},
 {name:'session remove',fault:['session','removeItem','lxm_home_loader_done'],reload:true},
 {name:'relationship write',fault:['local','setItem','relationship_level'],token:true},
 {name:'relationship remove',fault:['local','removeItem','relationship_level']},
 {name:'skip + local property',fault:['local','property'],skip:true}, {name:'skip + token read',fault:['local','getItem','token'],skip:true},
];
(async()=>{const results=[];for(const c of cases){
 const s=await setup({token:c.token});try{
  if(c.hang)await s.page.route(c.hang==='api'?'**/api/**':'**/home-scene/v4/*',r=>new Promise(()=>{}));
  if(c.bad)await s.page.route('**/home-scene/v4/*',r=>r.abort());
  await s.page.addInitScript(c=>{
   if(c.skip)sessionStorage.setItem('lxm_home_loader_done','1');
   if(c.decode)HTMLImageElement.prototype.decode=()=>new Promise(()=>{});
   if(c.fault){const [kind,op,key]=c.fault;
    if(op==='property')Object.defineProperty(window,'localStorage',{get(){throw Error('controlled storage property fault')}});
    else{const object=kind==='local'?localStorage:sessionStorage,native=Storage.prototype[op];Storage.prototype[op]=function(k,...args){if(this===object&&k===key)throw Error('controlled storage operation fault');return native.call(this,k,...args)};}
   }
  },c);
  await s.page.goto(s.origin+'/pages/index.html',{waitUntil:'domcontentloaded'});
  if(c.reload)await s.page.reload({waitUntil:'domcontentloaded'});
  await s.page.waitForFunction(()=>!document.getElementById('home-loading-screen'),null,{timeout:8500});
  const info=await s.page.evaluate(()=>({elapsed:Date.now()-HomeStartup.startedAt,phase:HomeStartup.phase,releases:HomeStartup.releases,auth:HomeStartup.auth().known,relationship:document.getElementById('relationship-level-name').textContent}));
  assert.equal(info.phase,'ready');assert.equal(info.releases,1);assert.ok(info.elapsed<8200);
  if(c.skip)assert.ok(info.elapsed<1000);else if(c.hang==='api')assert.ok(info.elapsed>=3950&&info.elapsed<4700,'Normal timing is independent of API');
  if(c.hang==='core'||c.decode)assert.ok(info.elapsed>=5900&&info.elapsed<6800,'5s core deadline then normal exit');
  if(c.fault?.[2]==='relationship_level'&&c.token)assert.equal(info.relationship,'亲密');
  await s.page.locator('.home-quick-btn').first().click();
  if(!c.token)await s.page.waitForSelector('#auth-login-modal.is-open');
  assert.deepEqual(s.errors,[]);
  results.push({case:c.name,...info,pass:true});console.log('PASS '+c.name+' '+info.elapsed+'ms');
 }finally{await s.close();}
 }
 const s=await setup();try{
  await s.page.goto(s.origin+'/pages/index.html');await s.page.waitForFunction(()=>!document.getElementById('home-loading-screen'));
  await s.page.goto(s.origin+'/pages/index.html');
  const skip=await s.page.evaluate(()=>Date.now()-HomeStartup.startedAt);assert.ok(skip<1000);
  await s.page.reload();await s.page.waitForFunction(()=>!document.getElementById('home-loading-screen'));const refresh=await s.page.evaluate(()=>Date.now()-HomeStartup.startedAt);assert.ok(refresh>=3950);
  results.push({case:'same-tab skip and refresh',skip,refresh,pass:true});
 }finally{await s.close();}
 fs.writeFileSync(artifact('docs/design/home-redesign/execution/evidence/home-m2/step-004-results.json'),JSON.stringify({scope:'Actual index.html, desktop Chrome, controlled storage/network/decode faults',results},null,2)+'\n');
})().catch(e=>{console.error(e);process.exitCode=1});

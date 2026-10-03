const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {setup,ready,root,evidence}=require('./home_browser_helpers.cjs');
const emotions=[['平静','emotion_calm'],['开心','emotion_happy'],['好奇','emotion_curious'],['想念','emotion_miss'],['担心','emotion_worry'],['害羞','emotion_shy'],['困倦','emotion_sleepy']];
(async()=>{
 const results=[];
 const s=await setup();
 try{
  await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
  const initial=await s.page.locator('#linxiaomeng-avatar').getAttribute('src');
  assert.ok(initial.startsWith('/static/images/home-thumbnails/v2/'),'Homepage initial avatar must use a derived small image');
  const originalStatus=await s.page.locator('#status-text').textContent();
  for(const [label,stem] of emotions){
   await s.page.evaluate(label=>updateHomeAvatar(label),label);
   await s.page.waitForFunction(stem=>document.getElementById('linxiaomeng-avatar').src.includes(stem),stem);
   await s.page.waitForFunction(()=>document.getElementById('linxiaomeng-avatar').complete&&document.getElementById('linxiaomeng-avatar').naturalWidth>0);
   assert.ok((await s.page.locator('#linxiaomeng-avatar').getAttribute('src')).includes('/home-thumbnails/'));
   assert.equal(await s.page.locator('#status-text').textContent(),originalStatus,'Image changes do not change status semantics');
  }
  const requests=s.requests.map(r=>r.path);
  assert.ok(!requests.some(p=>p.startsWith('/static/images/avatar/')||p.endsWith('/in_diary/diary_1.png')),'Homepage must not request full avatar/diary images');
  for(const action of ['cached','refresh']){
   s.requests.length=0;if(action==='refresh')await s.page.reload();else await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
   assert.ok(!s.requests.some(r=>r.path.startsWith('/static/images/avatar/')||r.path.endsWith('/in_diary/diary_1.png')));
  }
  results.push({case:'initial/emotions/cache/refresh',pass:true});
  await s.page.goto(s.origin+'/pages/settings.html');
  await s.page.evaluate(()=>updateAvatarEmotion('开心'));
  await s.page.waitForFunction(()=>document.getElementById('linxiaomeng-avatar')?.src.endsWith('/avatar/emotion_happy.png'));
  results.push({case:'settings retains shared default mapping',pass:true});
  assert.deepEqual(s.errors,[]);
 }finally{await s.close();}
 for(const failDefault of [false,true]){
  const f=await setup();const failed=[];
  try{
   await f.page.route('**/home-thumbnails/v2/*',route=>{
    const pathname=new URL(route.request().url()).pathname;
    if(pathname.includes('emotion_happy')||(failDefault&&pathname.includes('/default.'))){failed.push(pathname);return route.abort();}
    return route.continue();
   });
   await f.page.goto(f.origin+'/pages/index.html');await ready(f.page);
   const rejected=f.page.waitForEvent('requestfailed',{predicate:r=>r.url().includes('emotion_happy')});
   await f.page.evaluate(()=>updateHomeAvatar('开心'));
   await rejected;
   await f.page.waitForFunction(()=>document.getElementById('linxiaomeng-avatar').naturalWidth>0);
   const actual=await f.page.locator('#linxiaomeng-avatar').getAttribute('src');
   assert.ok(actual.includes('/home-thumbnails/v2/'));
   assert.ok(!actual.includes('emotion_happy'));
   if(failDefault) assert.ok(actual.includes('loader_avatar'),'A failed default uses the independent small loader portrait');
   assert.ok(!f.requests.some(r=>r.path.startsWith('/static/images/avatar/')));
   // Initial default image plus preload may share a request; never retry it on error.
   assert.ok(failed.filter(p=>p.includes('/default.')).length<=1,JSON.stringify(failed));
   assert.deepEqual(f.errors,[]);
   results.push({case:failDefault?'default+emotion failure':'emotion failure',pass:true,failed,actual});
  }finally{await f.close();}
 }
 for(const all of [false,true]){
  const f=await setup();const failed=[];
  try{
   await f.page.route('**/home-thumbnails/v2/*',route=>{
    const pathname=new URL(route.request().url()).pathname;
    if(pathname.includes('loader_avatar')||(all&&pathname.includes('/default.'))){failed.push(pathname);return route.abort();}
    return route.continue();
   });
   await f.page.goto(f.origin+'/pages/index.html');
   if(!all) await f.page.waitForFunction(()=>document.getElementById('loading-avatar').src.includes('/default.')&&document.getElementById('loading-avatar').naturalWidth>0);
   await ready(f.page);
   if(all)assert.equal(await f.page.locator('#linxiaomeng-avatar').evaluate(i=>getComputedStyle(i).visibility),'hidden');
   assert.deepEqual(f.errors,[]);
   assert.ok(!f.requests.some(r=>r.path.startsWith('/static/images/avatar/')));
   results.push({case:all?'all fallback images fail safely':'loader portrait failure',pass:true,failed});
  }finally{await f.close();}
 }
 fs.mkdirSync(evidence,{recursive:true});
 fs.writeFileSync(path.join(evidence,'step-002-results.json'),JSON.stringify({scope:'Real home/settings frontend; controlled API, desktop Chrome',results},null,2)+'\n');
 console.log('PASS: home derived images, 7 emotions, cache/refresh, failure fallback, shared settings mapping');
})().catch(e=>{console.error(e);process.exitCode=1;});

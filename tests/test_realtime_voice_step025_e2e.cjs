const assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const [origin,callId,clear,pageKind]=process.argv.slice(2);
// Read values, not just database/cache names. Close connections so the probe
// itself cannot interfere with later navigation or database deletion.
async function storageContents(){
 const request=req=>new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
 async function printable(value){
  if(value instanceof Blob)return {blob:await value.text()};
  if(value instanceof ArrayBuffer)return {bytes:new TextDecoder().decode(value)};
  if(ArrayBuffer.isView(value))return {bytes:new TextDecoder().decode(value)};
  if(Array.isArray(value))return Promise.all(value.map(printable));
  if(value&&typeof value==='object'){
   if(value instanceof Map)return {map:await printable([...value])};
   if(value instanceof Set)return {set:await printable([...value])};
   const result={};for(const [key,item] of Object.entries(value))result[key]=await printable(item);return result;
  }
  return typeof value==='bigint'?String(value):value;
 }
 const result={local:{...localStorage},session:{...sessionStorage},caches:[],databases:[]};
 for(const name of await caches.keys()){
  const cache=await caches.open(name),entries=[];
  for(const req of await cache.keys()){
   const response=await cache.match(req);
   entries.push({url:req.url,requestHeaders:[...req.headers],responseHeaders:[...response.headers],body:await response.text()});
  }
  result.caches.push({name,entries});
 }
 for(const {name} of await indexedDB.databases()){
  const db=await request(indexedDB.open(name));
  try{
   const stores=[];
   for(const storeName of db.objectStoreNames){
    const tx=db.transaction(storeName,'readonly'),store=tx.objectStore(storeName);
    const completed=new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error||new Error('IDB scan aborted'));tx.onerror=()=>reject(tx.error);});
    const [keys,values]=await Promise.all([request(store.getAllKeys()),request(store.getAll())]);
    await completed;stores.push({name:storeName,keys:await printable(keys),values:await printable(values)});
   }
   result.databases.push({name,stores});
  }finally{db.close();}
 }
 return result;
}
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true,ignoreDefaultArgs:['--disable-back-forward-cache']});
try {
 const page=await browser.newPage({viewport:{width:390,height:844}}),bodies=[],errors=[];
 if(pageKind.startsWith('full_chat'))await page.addInitScript(()=>{
   localStorage.setItem('token','isolated-test-auth');
   window.__jsonCompleted=[];window.__pageShows=[];window.addEventListener('pageshow',event=>window.__pageShows.push(event.persisted));const original=window.fetch;
   window.fetch=async(...args)=>{
     const response=await original(...args),json=response.json.bind(response);
     response.json=async()=>{try{return await json();}finally{setTimeout(()=>window.__jsonCompleted.push(String(args[0])),0);}};
     return response;
   };
 });
 page.on('pageerror',error=>errors.push(error.message));
 const reads=[];
 page.on('response',response=>{if(response.url().includes('/api/'))reads.push(response.text().then(text=>bodies.push(text)));});
 await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
 await page.goto(origin+(pageKind.startsWith('full_chat')?'/chat.html':''));
 const resource=page.locator('.voice-crisis-resource');
 await resource.waitFor();assert.equal(await resource.count(),1);
 assert.equal(await resource.innerText(),'发布资源：110/120；12356。');
 assert.equal(await resource.locator('a,button,h1,h2,h3').count(),0);
 if(pageKind==='full_chat'&&clear==='expiry')await page.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step025-full-chat.png'});
 const call=await page.request.get(origin+'/api/voice/calls/'+callId);
 assert.equal(call.headers()['cache-control'],'no-store');assert.ok((await call.json()).data.crisis);
 let beforeShows=0;
 if(pageKind==='full_chat_bfcache'){beforeShows=await page.evaluate(()=>window.__pageShows.length);await page.goto(origin+'/away');}
 const mutation=clear==='delete'?await page.request.delete(origin+'/api/admin/voice/calls/'+callId):await page.request.post(origin+'/__test__/expire');
 assert.equal(mutation.status(),200);
 if(pageKind==='full_chat_bfcache'){
   const restored=page.waitForResponse(r=>r.url().includes('/api/voice/calls/'));
   await page.goBack({waitUntil:'commit'});
   await page.waitForFunction(previous=>window.__pageShows.length>previous,beforeShows);
   assert.equal(await page.evaluate(()=>window.__pageShows.at(-1)),true,'Actual BFCache restoration required');
   await restored;
   await page.waitForFunction(()=>window.__jsonCompleted.some(url=>url.includes('/api/voice/calls/')));
   assert.equal(await resource.count(),0);
 }
 const priorReads=pageKind.startsWith('full_chat')?await page.evaluate(id=>window.__jsonCompleted.filter(url=>url.endsWith('/api/voice/calls/'+id)).length,callId):await page.evaluate(()=>window.resourceReadsCompleted);
 await page.evaluate(()=>window.dispatchEvent(new Event('offline')));assert.equal(await resource.count(),0);
 const refreshed=page.waitForResponse(r=>r.url().includes('/api/voice/calls/'));
 await page.evaluate(()=>window.dispatchEvent(new Event('online')));await refreshed;
 if(pageKind.startsWith('full_chat'))await page.waitForFunction(({previous,id})=>window.__jsonCompleted.filter(url=>url.endsWith('/api/voice/calls/'+id)).length>previous,{previous:priorReads,id:callId});
 else await page.waitForFunction(previous=>window.resourceReadsCompleted>previous,priorReads);
 assert.equal(await resource.count(),0);
 const after=await page.request.get(origin+'/api/voice/calls/'+callId);
 assert.equal((await after.json()).data.crisis,null);
 const reloaded=page.waitForResponse(r=>r.url().includes('/api/chat/timeline'));
 await page.reload();await reloaded;if(pageKind.startsWith('full_chat'))await page.waitForFunction(()=>window.__jsonCompleted.some(url=>url.includes('/api/chat/timeline'))&&loadingTimeline===false);
 else await page.waitForFunction(()=>window.timelineLoaded===true);
 assert.equal(await resource.count(),0);
 const timeline=await page.request.get(origin+'/api/chat/timeline?cursor=999999999');
 const timelineData=await timeline.json();assert.ok(timelineData.data.items.every(row=>!row.crisis_resource));
 const storage=JSON.stringify(await page.evaluate(storageContents));
 await Promise.all(reads);
 for(const text of [await page.content(),storage,...bodies,await after.text(),await timeline.text()])assert.ok(!text.includes('CRISIS-RAW-025-NEVER-PUBLIC'));
 // Positive controls use only this disposable browser context, after production
 // assertions: an empty store must not make a broken scanner look successful.
 const probe='STEP037-STORAGE-PROBE',cacheName='step037-scan-cache',dbName='step037-scan-db';
 try{
  await page.evaluate(async({probe,cacheName,dbName})=>{
   const cache=await caches.open(cacheName);await cache.put('/__storage_probe__',new Response(probe));
   const db=await new Promise((resolve,reject)=>{const req=indexedDB.open(dbName,1);req.onupgradeneeded=()=>req.result.createObjectStore('records');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
   try{await new Promise((resolve,reject)=>{const tx=db.transaction('records','readwrite');tx.objectStore('records').put({nested:[probe],blob:new Blob([probe])},'safe-key');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}finally{db.close();}
  },{probe,cacheName,dbName});
  const inspected=await page.evaluate(storageContents);
  assert.equal(inspected.caches.find(x=>x.name===cacheName).entries[0].body,probe);
  const record=inspected.databases.find(x=>x.name===dbName).stores[0].values[0];
  assert.equal(record.nested[0],probe);assert.equal(record.blob.blob,probe);
 }finally{
  await page.evaluate(async({cacheName,dbName})=>{await caches.delete(cacheName);await new Promise((resolve,reject)=>{const req=indexedDB.deleteDatabase(dbName);req.onsuccess=resolve;req.onerror=()=>reject(req.error);req.onblocked=()=>reject(new Error('probe database still open'));});},{cacheName,dbName});
 }
 assert.ok(!JSON.stringify(await page.evaluate(storageContents)).includes(probe));
 assert.deepEqual(errors,[]);console.log('PASS same-instance production route/card '+clear+' '+pageKind);
} finally {await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});

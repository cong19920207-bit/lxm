const fs=require('node:fs'),path=require('node:path');
const {setup,ready,evidence}=require('./home_browser_helpers.cjs');
(async()=>{
 const runs=[];
 for(const token of [false,true]){
  const s=await setup({token});
  try{
   for(const action of ['cold','cached','refresh']){
    s.requests.length=0;
    if(action==='refresh')await s.page.reload();else await s.page.goto(s.origin+'/pages/index.html');
    await ready(s.page);
    const resources=await s.page.evaluate(()=>performance.getEntriesByType('resource').map(r=>({path:new URL(r.name).pathname,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize})));
    runs.push({token,action,requests:[...s.requests],resources,errors:[...s.errors]});
   }
   await s.page.screenshot({path:path.join(evidence,`step-002-${token?'authenticated':'visitor'}.png`)});
  }finally{await s.close();}
 }
 fs.writeFileSync(path.join(evidence,'step-002-requests.json'),JSON.stringify({scope:'Real frontend, controlled API, desktop Chrome, native HTTP cache; no mobile timing claims',runs},null,2)+'\n');
 // Visual reference uses the existing object-fit:cover at the real 42/56px sizes.
 const s=await setup();try{
  await s.page.goto(s.origin+'/pages/index.html');await ready(s.page);
  const manifest=JSON.parse(fs.readFileSync('frontend/static/images/home-thumbnails/v2/manifest.json'));
  await s.page.evaluate(assets=>{
   document.body.innerHTML=''; document.body.style='background:#15121d;color:white;overflow:auto;padding:20px';
   for(const a of assets){
    const row=document.createElement('div');row.style='display:flex;gap:18px;align-items:center;margin:20px';
    row.append(a.role+' 原图 / 派生');
    for(const src of [a.source_url,a.url]){const img=new Image();img.src=src;const size=a.role==='diary_1'?56:a.role==='loader_avatar'?96:42;img.style=`width:${size}px;height:${size}px;object-fit:cover`;row.append(img);}
    document.body.append(row);
   }
  },manifest.assets.map(a=>({...a,role:a.file.split('.')[0],source_url:a.source.replace('frontend','')}))); 
  await s.page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth));
  await s.page.screenshot({path:path.join(evidence,'step-002-quality.png'),fullPage:true});
 }finally{await s.close();}
 console.log('Captured 6 native-cache resource runs and thumbnail display comparison');
})().catch(e=>{console.error(e);process.exitCode=1;});

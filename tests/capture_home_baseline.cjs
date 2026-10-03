const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {setup,ready,root,evidence} = require('./home_browser_helpers.cjs');
(async()=>{
  fs.mkdirSync(path.join(evidence,'baseline'),{recursive:true});
  const snapshots = [];
  for(const file of ['frontend/pages/index.html','frontend/static/js/api.js']){
    const data = fs.readFileSync(path.join(root,file));
    const output = path.join(evidence,'baseline',path.basename(file));
    if(fs.existsSync(output) && !fs.readFileSync(output).equals(data)) throw Error('Baseline already exists with different bytes');
    fs.writeFileSync(output,data);
    snapshots.push({file,sha256:crypto.createHash('sha256').update(data).digest('hex')});
  }
  const runs=[];
  for(const token of [false,true]){
    const s=await setup({baseline:true,token});
    try{
      for(const action of ['cold','cached','refresh']){
        s.requests.length=0;
        const start=Date.now();
        if(action==='refresh')await s.page.reload();else await s.page.goto(s.origin+'/pages/index.html');
        await ready(s.page);
        const resources=await s.page.evaluate(()=>performance.getEntriesByType('resource').map(r=>({path:new URL(r.name).pathname,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize,decodedBodySize:r.decodedBodySize})));
        runs.push({token,action,readyElapsedMs:Date.now()-start,requests:[...s.requests],resources,errors:[...s.errors]});
      }
      await s.page.screenshot({path:path.join(evidence,`baseline-${token?'authenticated':'visitor'}.png`)});
    }finally{await s.close();}
  }
  fs.writeFileSync(path.join(evidence,'baseline-results.json'),JSON.stringify({scope:'Desktop Chrome, local HTTP, fixed visitor/authenticated fixtures; real frontend resources. Not phone or real API/network measurements.',snapshots,runs},null,2)+'\n');
  console.log('Captured immutable pre-change source and 6 controlled cold/cache/refresh resource runs');
})().catch(e=>{console.error(e);process.exitCode=1;});

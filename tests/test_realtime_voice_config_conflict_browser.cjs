const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
try{for(const code of ['VOICE_CONFIG_BASE_VERSION_CONFLICT','VOICE_CONFIG_REVISION_CONFLICT']){
 const page=await browser.newPage(),errors=[],writes=[];let conflict=false,failRead=false;
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{sessionStorage.setItem('admin_token','local-test');sessionStorage.setItem('admin_role','super_admin');});
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.origin!=='http://voice.test')return route.abort();
  if(url.pathname.startsWith('/api/')){
   if(route.request().method()==='PATCH'){writes.push(route.request().postDataJSON());conflict=true;return route.fulfill({status:409,json:{code:409,message:'配置冲突',data:{error_code:code}}});}
   if(url.pathname==='/api/admin/voice/config/config'){
    if(conflict&&failRead)return route.fulfill({status:503,json:{code:503,message:'unavailable'}});
    return route.fulfill({json:{code:0,data:{config:{global:{enabled:false,maintenance_message:conflict?'SERVER_LATEST':'BASE'}},_meta:{base_version:0,draft_revision:conflict?2:1,has_draft:false}}}});
   }
   return route.fulfill({json:{code:0,data:{list:[],calls:[]}}});
  }
  const file=url.pathname.slice(1);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});
 });
 await page.goto('http://voice.test/admin/pages/voice-config.html');
 await page.waitForFunction(()=>document.querySelector('#voice-section-json').value.includes('BASE'));
 await page.locator('#voice-advanced-editor').evaluate(el=>{el.open=true;});
 const local=JSON.stringify({maintenance_message:'<img src=x onerror=alert(1)>LOCAL'});
 await page.locator('#voice-section-json').fill(local);
 await page.locator('#btn-voice-save-section').click();
 await page.getByText('服务器最新内容',{exact:true}).waitFor();
 const comparison=page.locator('#voice-conflict-comparison');
 assert.ok((await comparison.innerText()).includes('SERVER_LATEST'));
 assert.ok((await comparison.innerText()).includes('LOCAL'));
 assert.ok((await comparison.innerText()).includes('差异字段：maintenance_message'));
 assert.equal(await comparison.locator('img').count(),0);
 assert.equal(await page.locator('#voice-section-json').inputValue(),local);
 assert.equal(writes.length,1);assert.equal(writes[0].draft_revision,1);
 failRead=true;await page.locator('#btn-voice-save-section').click();
 await page.getByText('最新内容读取失败，本次编辑仍保留，请稍后重新加载。',{exact:true}).waitFor();
 assert.equal(await page.locator('#voice-section-json').inputValue(),local);
 assert.equal(writes[1].draft_revision,1);assert.equal(writes.length,2);
 assert.deepEqual(errors,[]);await page.close();
}console.log('PASS: both config conflicts show latest diff, preserve local edit and stale revision; failed read preserves edit; safe text');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

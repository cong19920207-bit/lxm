const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true}),results=[];
try{for(const role of ['super_admin','ops_admin','observer']){
  const page=await browser.newPage({viewport:{width:1400,height:900}}),errors=[],writes=[];
  let deleted=false,fail=true,accept=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',async dialog=>{
    assert.equal(dialog.type(),'confirm');
    assert.ok(dialog.message().includes('取消未完成任务'));
    assert.ok(dialog.message().includes('长期记忆、用量账本、成长值和无正文审计不会删除或回滚'));
    if(accept)await dialog.accept();else await dialog.dismiss();
  });
  await page.addInitScript(role=>{sessionStorage.setItem('admin_token','local-test');sessionStorage.setItem('admin_role',role);sessionStorage.setItem('admin_username','test');},role);
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());if(url.origin!=='http://voice.test')return route.abort();
    if(url.pathname.startsWith('/api/')){
      if(route.request().method()==='DELETE'){
        writes.push(url.pathname);assert.equal(url.pathname,'/api/admin/voice/calls/delete-test');
        if(fail)return route.fulfill({status:503,json:{detail:'通话删除未完成，请重试'}});
        deleted=true;return route.fulfill({json:{code:0,data:{call_id:'delete-test'}}});
      }
      const data=url.pathname==='/api/admin/voice/calls'?{items:deleted?[]:[{call_id:'delete-test',user_id:1,status:'ended'}],total:deleted?0:1}:
        {call_id:'delete-test',status:'ended',call_summary:'这段摘要会在删除成功后移除'};
      return route.fulfill({json:{code:0,data}});
    }
    const file=url.pathname.slice(1);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});
  });
  await page.goto('http://voice.test/admin/pages/voice-calls.html');await page.locator('#voice-rows button').click();
  if(role==='super_admin'){
    await page.locator('#voice-delete').click();assert.deepEqual(writes,[]);
    accept=true;await page.locator('#voice-delete').click();
    await page.waitForFunction(()=>document.querySelector('#voice-detail-status').textContent.length>0);
    assert.equal(await page.locator('#voice-delete').isEnabled(),true);
    assert.equal(await page.locator('#voice-dialog').isVisible(),true);
    fail=false;await page.locator('#voice-delete').click();
    await page.getByText('暂无匹配的通话',{exact:true}).waitFor();
    assert.equal(await page.locator('#voice-dialog').isVisible(),false);
    assert.equal(await page.locator('#voice-panel').textContent(),'');
    assert.equal(writes.length,2);
    await page.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step034-delete-browser.png'});
  }else{assert.equal(await page.locator('#voice-delete').isVisible(),false);assert.deepEqual(writes,[]);}
  assert.deepEqual(errors,[]);results.push({role,writes:writes.length,passed:true});await page.close();
}
fs.writeFileSync('docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step034-delete-browser.json',JSON.stringify(results,null,2)+'\n');
console.log('delete UI passed: role visibility, impact confirmation/cancel, failed retry, successful body clearing');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});

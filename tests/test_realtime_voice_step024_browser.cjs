// Production crisis page and scripts; HTTP data is controlled, no live records.
const assert=require('node:assert/strict'), fs=require('node:fs'), http=require('node:http');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async()=>{
 const server=http.createServer((req,res)=>{
  const path=req.url.split('?')[0];
  const file=path.startsWith('/admin/') ? path.slice(1) : 'admin/pages/error.html';
  if(!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');
  res.end(fs.readFileSync(file));
 });await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:'chrome',headless:true});
  for(const role of ['super_admin','observer','tech_ops','ops_admin','ai_trainer']){
   const page=await browser.newPage({viewport:{width:1280,height:900}});const reads=[];
   await page.addInitScript(role=>{sessionStorage.setItem('admin_token','test');sessionStorage.setItem('admin_role',role);},role);
   await page.route('**/api/admin/voice/crisis-records**',async route=>{
    const path=new URL(route.request().url()).pathname;reads.push(path);
    const row={id:1,call_id:'call-example',turn_index:1,direction:'assistant',is_persona_incident:true,match_status:'matched',created_at:'2026-09-13T12:00:00',expired:false};
    const data=path.endsWith('/1')?{...row,content_plaintext:'<img src=x onerror="window.leaked=true">PRIVATE_SENTINEL',matched_keyword:'PRIVATE'}:{items:[row],total:1,page:1,page_size:20};
    await route.fulfill({json:{code:0,data}});
   });
   await page.goto(`http://127.0.0.1:${server.address().port}/admin/pages/voice-crisis.html`);
   if(role==='super_admin'){
    await page.getByRole('button',{name:'查看原文'}).click();
    await page.getByTestId('crisis-detail').getByText(/PRIVATE_SENTINEL/).waitFor();
    assert.equal(await page.evaluate(()=>window.leaked),undefined);
    assert.equal(reads.length,2);
    await page.getByRole('button',{name:'关闭原文'}).click();
    assert.equal(await page.getByTestId('crisis-detail').textContent(),'');
    await page.getByRole('button',{name:'查看原文'}).click();
    await page.getByTestId('crisis-detail').getByText(/PRIVATE_SENTINEL/).waitFor();
    assert.equal(reads.length,3); // Reopening must issue another audited request.
    assert.equal(await page.locator('.menu-item').filter({hasText:'危机记录'}).count(),1);
    fs.mkdirSync('docs/design/realtime_voice/P1/execution/evidence/m4-20260913',{recursive:true});
    await page.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m4-20260913/crisis-admin.png',fullPage:true});
   }else{
    await page.waitForURL('**/error.html?type=403');assert.equal(reads.length,0);
   }
   await page.close();
  }
  console.log('PASS: five-role page access, escaped text, close clears text, every reopen reads, super-admin menu');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});

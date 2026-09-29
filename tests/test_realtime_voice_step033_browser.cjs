const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
try{for(const role of ['super_admin','ops_admin','observer','tech_ops','ai_trainer']){
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
const writes=[],reads=[];
let turnGate=null,turnRequested=null;
const exported={items:[{call_id:'test-call',turn_index:1,user_text_final:'用户最终文字',assistant_text_effective:'实际播放的文字',effective_text_expires_at:'2026-10-01T00:00:00'}],snapshot_at:'2026-09-13T00:00:00'};
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(role=>{sessionStorage.setItem('admin_token','local-test');sessionStorage.setItem('admin_role',role);sessionStorage.setItem('admin_username','test');},role);
await page.route('**/*',async route=>{const url=new URL(route.request().url());if(url.origin!=='http://voice.test')return route.abort();
if(url.pathname.startsWith('/api/')){let data={};
if(url.pathname.endsWith('/turns')&&turnGate){turnRequested();await turnGate;}
if(route.request().method()==='POST')writes.push(url.pathname);else reads.push(url.pathname);
if(url.pathname==='/api/admin/voice/calls')data={items:[{call_id:'test-call',user_id:1,status:'ended',duration_seconds:65,summary_status:'ready',turn_count:1}],total:1};
else if(url.pathname.endsWith('/export')){assert.deepEqual(route.request().postDataJSON(),{call_ids:['test-call']});data=exported;}
else if(url.pathname.endsWith('/debug'))data={items:[{turn_index:1,assistant_text_generated:'完整生成测试文字',generated_text_expires_at:'2026-10-01T00:00:00'}],reasoning:'内部判断测试',next_after:null};
else if(url.pathname.endsWith('/turns'))data={items:[
{turn_index:1,user_text_final:'<img src=x onerror=alert(1)>',assistant_text_effective:'实际播放的文字',memory_status:'success',content_available:true,effective_text_expires_at:new Date(Date.now()+2.5*86400000).toISOString().replace('Z','')},
{turn_index:2,user_text_final:null,assistant_text_effective:null,memory_status:'success',content_available:false,effective_text_expires_at:new Date(Date.now()-86400000).toISOString(),effective_text_cleared_at:'2026-09-01T00:00:00',content_clear_reason:'expired'},
{turn_index:3,user_text_final:null,assistant_text_effective:null,content_available:false,effective_text_expires_at:null,user_crisis_status:'suspected',assistant_crisis_status:'suspected',content_unavailable_reason:'crisis_isolated'}],next_after:null};
else if(url.pathname.endsWith('/jobs'))data={items:[{id:7,kind:'memory',job_type:'memory',status:writes.length?'pending':'failed',attempt_count:2,fail_reason:'write_unavailable',retry_path:writes.length?null:'/jobs/7/retry'}],next_after:null};
else if(url.pathname.endsWith('/audit'))data={items:[],next_after:null};
else if(url.pathname.endsWith('/usage'))data={ledger:[],growth:[]};
else data={call_id:'test-call',status:'ended',call_summary:'聊了旅行计划'};
return route.fulfill({json:{code:0,data}});}
const file=url.pathname.slice(1);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});});
if(['tech_ops','ai_trainer'].includes(role)){
await page.goto('http://voice.test/admin/pages/voice-calls.html');
await page.waitForURL('**/error.html?type=403');
assert.equal(reads.some(path=>path.startsWith('/api/admin/voice/calls')),false);
if(role==='ai_trainer'){
await page.goto('http://voice.test/admin/pages/voice-jobs.html');await page.waitForURL('**/error.html?type=403');
assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);await page.close();continue;}
await page.goto('http://voice.test/admin/pages/voice-jobs.html');
assert.equal(await page.getByRole('link',{name:'查看进行中通话与强制挂断'}).getAttribute('href'),'voice-ops.html');
await page.locator('#job-call').fill('test-call');await page.getByRole('button',{name:'查询',exact:true}).click();
await page.getByRole('button',{name:'补跑一次',exact:true}).click();await page.getByText('pending',{exact:true}).waitFor();
assert.deepEqual(writes,['/api/admin/voice/jobs/7/retry']);assert.equal(await page.getByText('通话记录',{exact:true}).count(),0);
assert.deepEqual(errors,[]);await page.close();continue;}
await page.goto('http://voice.test/admin/pages/voice-calls.html');
await page.locator('#voice-rows button').click();await page.getByRole('button',{name:'逐轮转写',exact:true}).click();
await page.getByText('实际播放的文字',{exact:true}).waitFor();assert.equal(await page.locator('#voice-panel img').count(),0);
const retentionRows=await page.locator('#voice-panel tr').evaluateAll(rows=>rows.map(row=>Array.from(row.children,cell=>cell.textContent)));
const retentionColumn=name=>retentionRows[0].indexOf(name);
for(const name of ['有效文字到期','剩余天数','清理状态','有效文字清理时间','清理原因'])assert.ok(retentionColumn(name)>=0,name);
assert.equal(retentionRows[1][retentionColumn('剩余天数')],'2');
assert.equal(retentionRows[1][retentionColumn('清理状态')],'未清理');
assert.equal(retentionRows[2][retentionColumn('剩余天数')],'0');
assert.equal(retentionRows[2][retentionColumn('清理状态')],'已清理');
assert.equal(retentionRows[2][retentionColumn('清理原因')],'到期清理');
assert.equal(retentionRows[2][retentionColumn('有效文字清理时间')],'2026-09-01T00:00:00');
assert.equal(retentionRows[3][retentionColumn('剩余天数')],'—');
assert.equal(retentionRows[3][retentionColumn('用户危机检测')],'疑似（检测未能可靠完成）');
assert.match(retentionRows[3][retentionColumn('内容说明')],/危机隔离/);
assert.equal(await page.getByRole('columnheader',{name:'危机疑似（方向数）',exact:true}).count(),1);
if(role!=='super_admin')assert.equal(await page.locator('#voice-debug').isVisible(),false);
if(role==='observer'){assert.equal(await page.locator('#voice-export').isVisible(),false);assert.deepEqual(writes,[]);}
else{
const downloaded=page.waitForEvent('download');await page.locator('#voice-export').click();const download=await downloaded;
assert.equal(download.suggestedFilename(),'voice-test-call.json');
assert.deepEqual(JSON.parse(fs.readFileSync(await download.path(),'utf8')),exported);
assert.deepEqual(writes,['/api/admin/voice/calls/export']);}
if(role==='super_admin'){
await page.locator('#voice-debug').click();await page.getByText('完整生成测试文字',{exact:true}).waitFor();
assert.ok((await page.locator('#voice-panel').textContent()).includes('内部判断测试'));}
await page.locator('#voice-close').click();assert.equal(await page.locator('#voice-panel').textContent(),'');
await page.locator('#voice-rows button').click();await page.getByRole('button',{name:'用量与成长',exact:true}).click();await page.getByRole('heading',{name:'成长记录',exact:true}).waitFor();
if(role==='super_admin'){
let release;turnGate=new Promise(resolve=>{release=resolve;});const requested=new Promise(resolve=>{turnRequested=resolve;});
await page.getByRole('button',{name:'逐轮转写',exact:true}).click();await requested;
await page.locator('#voice-close').click();
const responded=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/turns'));release();await responded;
await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
assert.equal(await page.locator('#voice-panel').textContent(),'');assert.equal(await page.locator('#voice-dialog').isVisible(),false);
turnGate=null;
await page.locator('#voice-rows button').click();await page.getByRole('button',{name:'用量与成长',exact:true}).click();await page.getByRole('heading',{name:'成长记录',exact:true}).waitFor();}
assert.deepEqual(errors,[]);if(role==='super_admin')await page.screenshot({path:'/tmp/voice-crisis-step033-browser.png'});await page.close();
}console.log('voice records browser passed: five roles, direct access denial, super debug, super/ops export file and request, observer read-only, tech retry/ops link, tabs, literal text, close clearing including delayed response');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});

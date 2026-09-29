const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
try {for(const role of ['super_admin','ai_trainer','tech_ops','ops_admin','observer']) {
 const page=await browser.newPage({viewport:{width:1280,height:900}}),requests=[],errors=[];let fail=false,truncateAvailable=false;
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(role=>{sessionStorage.setItem('admin_token','test');sessionStorage.setItem('admin_role',role);sessionStorage.setItem('admin_username','test');},role);
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.origin!=='http://voice.test')return route.abort();
  if(url.pathname.startsWith('/api/')) {
   requests.push(route.request().method());
   if(fail)return route.fulfill({json:{code:503,message:'unavailable'}});
   const data=url.pathname.endsWith('/billing-preview')?{start:url.searchParams.get('start'),end:url.searchParams.get('end'),currency:'CNY',billable_seconds:120,estimated_cost:'0.120000',provider_billed_cost:'0.10',difference_amount:'0.020000',difference_rate:'0.2',formula_version:'voice-bill-v1'}:url.pathname.endsWith('/history')?{start:url.searchParams.get('start'),end:url.searchParams.get('end'),days:[
    {date:'2026-09-18',metrics:[{name:'billable_seconds',value:0,status:'measured',computed_at_utc:'2026-09-20T01:00:00+00:00'}]},
    {date:'2026-09-19',metrics:[{name:'billable_seconds',value:null,status:'not_measurable',reason:'not_materialized',computed_at_utc:null}]}]}:url.pathname.endsWith('/daily')?{date:url.searchParams.get('day'),metrics:[
    {name:'daily_call_count',value:0,status:'measured'},
    {name:'connect_rate',value:.5,status:'provisional'},
    {name:'estimated_cost',value:null,status:'not_measurable',reason:'price_unconfigured'}]}:
    {date:url.searchParams.get('day'),capability_metrics:[{name:'truncate_success_rate',value:null,status:'not_measurable',reason:'capability_evidence_unavailable_for_bucket'},{name:'double_reply_count',value:2,status:'measured'},{name:'effective_text_evidence_distribution',value:{exact_played:.5,confirmed_sentences:.25,full:.25,none:0},status:'measured',unit:'text_snapshot',sample_count:4}],
     events:[{name:'<img src=x onerror=alert(1)>',status:'available',samples:[{dimensions:{result:'test'},value:3}]}],
     durations:[{name:'latency',status:'available',groups:[{dimensions:{},status:'available',p50_ms:10,p90_ms:20,p95_ms:30,sample_count:4}]}]};
   if(truncateAvailable&&data.capability_metrics)data.capability_metrics[0]={name:'truncate_success_rate',value:.5,status:'measured'};
   if(url.searchParams.get('simulated_pricing')==='true')data.pricing={data_source:'simulated'};
   return route.fulfill({json:{code:0,data}});
  }
  const file=url.pathname.slice(1);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});
 });
 await page.goto('http://voice.test/admin/pages/voice-metrics.html');
 await page.locator('#daily-rows').getByText('50.00%（暂定）',{exact:true}).waitFor();
 await page.getByRole('tab',{name:'近期观测',exact:true}).click();
 await page.locator('#capability-rows').getByText('不可测',{exact:true}).waitFor();
 await page.locator('#capability-rows').getByText('精确已播 50.00%；已确认句子 25.00%；完整播放 25.00%；无有效文本 0.00%',{exact:true}).waitFor();
 await page.locator('#capability-rows').getByText('文本状态采样 4 次；不代表回复数',{exact:true}).waitFor();
 assert.equal(await page.locator('#capability-rows tr').filter({hasText:'额外回复数（按回复去重）'}).locator('td').nth(1).innerText(),'2');
 assert.ok((await page.locator('#daily-rows').innerText()).includes('尚未配置单价'));
 assert.equal(await page.locator('#daily-rows tr').first().locator('td').nth(1).innerText(),'0');
 await page.locator('summary').click();
 assert.equal(await page.locator('#observation-rows img').count(),0);
 assert.ok((await page.locator('#observation-rows').innerText()).includes('10 / 20 / 30 ms'));
 assert.equal(await page.locator('#sidebar-mount .menu-item.active').filter({hasText:'通话指标'}).count(),1);
 await page.getByRole('tab',{name:'业务日统计',exact:true}).click();
 await page.locator('#daily-date').fill('2026-09-19');await page.getByRole('button',{name:'查询业务日',exact:true}).click();
 await page.getByText('统计日期：2026-09-19（北京时间）；按当前持久化结果计算',{exact:true}).waitFor();
 await page.getByRole('tab',{name:'历史日聚合',exact:true}).click();
 await page.locator('#history-rows').getByText('尚无可用落库值',{exact:true}).waitFor();
 assert.equal(await page.locator('#history-rows tr').first().locator('td').nth(1).innerText(),'0');
 assert.ok((await page.locator('#history-rows').innerText()).includes('2026-09-20T01:00:00+00:00'));
 await page.getByRole('tab',{name:'业务日统计',exact:true}).click();await page.locator('#daily-simulated').check();
 await page.getByRole('button',{name:'查询业务日',exact:true}).click();
 await page.locator('#daily-status').getByText(/模拟估算 CNY 0.06\/分钟/).waitFor();
 await page.getByRole('tab',{name:'历史日聚合',exact:true}).click();await page.locator('#history-simulated').check();
 await page.getByRole('button',{name:'查询历史',exact:true}).click();
 await page.locator('#history-status').getByText(/模拟估算 CNY 0.06\/分钟/).waitFor();
 await page.getByRole('tab',{name:'成本与账单',exact:true}).click();await page.locator('#billing-amount').fill('0.10');
 await page.getByRole('button',{name:'计算模拟差额',exact:true}).click();
 await page.locator('#billing-rows').getByText('20.00%',{exact:true}).waitFor();
 assert.ok((await page.locator('#billing-rows').innerText()).includes('0.120000 CNY'));
 await page.getByRole('tab',{name:'近期观测',exact:true}).click();truncateAvailable=true;await page.getByRole('button',{name:'查询观测',exact:true}).click();
 await page.locator('#capability-rows').getByText('50.00%',{exact:true}).waitFor();
 fail=true;await page.getByRole('tab',{name:'业务日统计',exact:true}).click();await page.getByRole('button',{name:'查询业务日',exact:true}).click();
 await page.locator('#daily-status').getByText('加载失败，请重试',{exact:true}).waitFor();
 assert.equal(await page.locator('#daily-rows tr').count(),0);
 await page.getByRole('tab',{name:'历史日聚合',exact:true}).click();await page.getByRole('button',{name:'查询历史',exact:true}).click();
 await page.locator('#history-status').getByText('加载失败，请检查日期范围（最多31天）后重试',{exact:true}).waitFor();
 assert.equal(await page.locator('#history-rows tr').count(),0);
 await page.getByRole('tab',{name:'成本与账单',exact:true}).click();await page.getByRole('button',{name:'计算模拟差额',exact:true}).click();
 await page.locator('#billing-status').getByText('计算失败，请检查日期范围（最多31天）和金额后重试',{exact:true}).waitFor();
 assert.equal(await page.locator('#billing-rows tr').count(),0);
 assert.ok(requests.every(method=>method==='GET'));assert.deepEqual(errors,[]);
 await page.close();
} console.log('PASS: five roles, readonly requests, null/zero/provisional, UTC/business labels, safe text, error clears stale values');
} finally {await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

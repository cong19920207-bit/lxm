const assert = require('node:assert/strict');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    for (const role of ['tech_ops','observer','ai_trainer','ops_admin','super_admin']) {
      const context = await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1280,height:1100},extraHTTPHeaders:{'x-role':role}});
      const page = await context.newPage(), errors = [], calls = [], network = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('requestfailed', r => network.push({path:new URL(r.url()).pathname,error:r.failure()}));
      page.on('response', r => { if (r.url().includes('/api/')) network.push({path:new URL(r.url()).pathname,status:r.status()}); });
      page.on('console', message => { if (message.type()==='error') network.push({error:message.text()}); });
      page.on('request', r => { if (r.method()==='POST') calls.push(new URL(r.url()).pathname); });
      await page.addInitScript(role => { sessionStorage.setItem('admin_token','isolated-test');sessionStorage.setItem('admin_role',role); },role);
      await page.goto(process.argv[2]+'/admin/pages/voice-master-switch.html');
      await page.waitForFunction(() => document.querySelector('#voice-diag-proxy').textContent.includes('正常'));
      const mayTest = ['tech_ops','super_admin'].includes(role);
      assert.equal(await page.locator('#btn-voice-diag-test').isDisabled(),!mayTest);
      if (role === 'tech_ops') {
        assert.match(await page.locator('#voice-diag-link').innerText(),/尚未检测/);
        await page.locator('#btn-voice-diag-test').click();
        try {
          await page.waitForFunction(() => document.querySelector('#voice-diag-link').textContent.includes('消息往返通过'),null,{timeout:12000});
        } catch (error) {
          console.error('diagnostic UI:', await page.locator('.diagnostic-panel').innerText());
          console.error('page errors:', errors);
          console.error('network:', network);
          throw error;
        }
        assert.deepEqual(calls,['/api/admin/voice/master-switch/diagnostics/probes']);
        assert.equal(await page.locator('#voice-master-enabled').isChecked(),false);
        assert.match(await page.locator('#voice-diag-rejections').innerText(),/不能据此判断没有异常/);
        await page.screenshot({path:process.argv[3],fullPage:true});
        // A broken Upgrade path must not retain an earlier green success.
        let intercepted = 0;
        await page.routeWebSocket(/\/api\/voice\/diagnostics\/stream$/, ws => { intercepted++; ws.close(); });
        await page.reload();
        await page.waitForFunction(() => !document.querySelector('#btn-voice-diag-test').disabled);
        await page.waitForTimeout(3100);
        await page.locator('#btn-voice-diag-test').click();
        await page.waitForFunction(() => document.querySelector('#voice-diag-link').textContent.includes('本次检测未完成'));
        assert.equal(intercepted,1);
        assert.notEqual(await page.locator('#voice-diag-link').getAttribute('data-health'),'ready');
        // Controlled projections exercise unknown/stale/storage failures, not
        // the live proxy success already verified above.
        const snapshot = {mode:'docker_dns',service:'nginx',instance:'test-instance',generation:1,
          status:'ready',discovered_addresses:['172.18.0.4'],trusted_addresses:['172.18.0.4'],
          checked_at:new Date().toISOString(),refresh_seconds:5};
        let projection = {proxy:snapshot,probe_storage:'unavailable',last_probe:null,
          recent_rejections:{status:'unavailable',samples:null},probe_valid_seconds:60};
        await page.route('**/api/admin/voice/master-switch/diagnostics', route => route.fulfill({json:{code:0,data:projection}}));
        await page.locator('#btn-voice-diag-refresh').click();
        await page.waitForFunction(() => document.querySelector('#voice-diag-link').textContent==='诊断记录不可用');
        assert.match(await page.locator('#voice-diag-message').innerText(),/Redis/);
        projection = {...projection,probe_storage:'available',last_probe:{status:'passed',scheme:'wss',
          checked_at:new Date(Date.now()-61000).toISOString(),proxy:{instance:'test-instance',generation:1}}};
        await page.locator('#btn-voice-diag-refresh').click();
        await page.waitForFunction(() => document.querySelector('#voice-diag-link').textContent.includes('过期'));
        assert.notEqual(await page.locator('#voice-diag-link').getAttribute('data-health'),'ready');
        projection = {...projection,proxy:{...snapshot,status:'error',trusted_addresses:[],discovered_addresses:[]},
          last_probe:{status:'failed',reason:'wss_required',checked_at:new Date().toISOString()}};
        await page.locator('#btn-voice-diag-refresh').click();
        await page.waitForFunction(() => document.querySelector('#voice-diag-proxy').textContent.includes('解析失败'));
        assert.match(await page.locator('#voice-diag-message').innerText(),/安全连接/);
      } else {
        await page.locator('#btn-voice-diag-refresh').click();
        assert.equal(calls.length,0);
      }
      assert.deepEqual(errors,[]);
      await context.close();
    }
    console.log('PASS: real TLS roundtrip, failed Upgrade, stale/DNS/Redis failures, five role UI, no call/master-switch writes');
  } finally { await browser.close(); }
})().catch(error => { console.error(error);process.exitCode=1; });

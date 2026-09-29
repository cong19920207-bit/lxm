const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const role of ['super_admin', 'tech_ops', 'ai_trainer', 'ops_admin', 'observer']) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
      const errors = [], writes = [];
      let state = {enabled:false,version:1,updated_by:'test',updated_at:'2026-09-27T00:00:00'};
      let behavior = 'success', release;
      page.on('pageerror', e => errors.push(e.message));
      await page.addInitScript(role => {
        sessionStorage.setItem('admin_token','local-test');sessionStorage.setItem('admin_role',role);
      }, role);
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'http://voice.test') return route.abort();
        if (url.pathname.startsWith('/api/')) {
          const method = route.request().method();
          if (method !== 'GET') writes.push({path:url.pathname,body:route.request().postDataJSON()});
          if (url.pathname === '/api/admin/voice/master-switch/publish') {
            if (behavior === 'failure') return route.fulfill({status:400,json:{code:400,message:'凭据未配置'}});
            if (behavior === 'conflict') { state.version++; return route.fulfill({status:409,json:{code:409,message:'总开关已更新'}}); }
            if (behavior === 'delayed') await new Promise(resolve => release=resolve);
            state = {...state,enabled:route.request().postDataJSON().enabled,version:state.version+1};
            if (behavior === 'lost') return route.abort();
          }
          let data = state;
          if (url.pathname === '/api/admin/voice/config/config') data = {config:{global:{enabled:false,maintenance_mode:false,maintenance_message:'暂时无法接通',rollout:{mode:'allowlist',user_ids:[]},test_user_ids:[]},s2s:{}},_meta:{base_version:1,draft_revision:0,has_draft:false,changed_sections:[]}};
          else if (url.pathname.includes('/history')) data = {list:[]};
          else if (!url.pathname.includes('/master-switch')) data={list:[],calls:[],database_count:0,lease_count:0};
          return route.fulfill({json:{code:0,data}});
        }
        const file = url.pathname.slice(1);
        return fs.existsSync(file) ? route.fulfill({path:file}) : route.fulfill({status:404,body:''});
      });
      await page.goto('http://voice.test/admin/pages/voice-master-switch.html');
      await page.waitForFunction(() => document.querySelector('#voice-master-status').textContent.includes('当前生效'));
      const toggle = page.locator('#voice-master-enabled');
      assert.equal(await toggle.isChecked(),false);
      assert.equal(await toggle.isDisabled(),!['super_admin','tech_ops'].includes(role));
      assert.match(await page.locator('#sidebar-mount').innerText(),/🔘 总开关/);
      if (role==='super_admin') {
        await toggle.click();
        assert.equal(await toggle.isChecked(),false);
        assert.equal(await page.locator('.modal-overlay input').count(),0);
        await page.locator('#__confirm_cancel').click();
        assert.equal(writes.length,0);
        behavior='delayed';
        await toggle.click(); await page.locator('#__confirm_ok').click();
        await page.waitForFunction(() => document.querySelector('#voice-master-status').textContent==='正在处理…');
        assert.equal(await toggle.isChecked(),false);
        assert.equal(await toggle.isDisabled(),true);
        while (!release) await new Promise(r=>setTimeout(r,10));
        assert.deepEqual(writes[0],{path:'/api/admin/voice/master-switch/publish',body:{enabled:true,expected_version:1}});
        release();
        await page.waitForFunction(() => document.querySelector('#voice-master-enabled').checked);
        assert.equal(writes.length,1);
        behavior='failure'; await toggle.click();await page.locator('#__confirm_ok').click();
        await page.waitForFunction(() => !document.querySelector('#voice-master-enabled').disabled);
        assert.equal(await toggle.isChecked(),true);
        assert.match(await page.locator('#voice-master-error').innerText(),/凭据未配置/);
        behavior='conflict'; await toggle.click();await page.locator('#__confirm_ok').click();
        await page.waitForFunction(() => !document.querySelector('#voice-master-enabled').disabled);
        assert.equal(await toggle.isChecked(),true);
        behavior='lost'; await toggle.click();await page.locator('#__confirm_ok').click();
        await page.waitForFunction(() => !document.querySelector('#voice-master-enabled').disabled);
        assert.equal(await toggle.isChecked(),false);
        assert.equal(writes.length,4);
      }
      await page.goto('http://voice.test/admin/pages/voice-config.html');
      await page.waitForFunction(() => document.querySelector('#voice-section-json').value.includes('暂时无法接通'));
      const mayReadOps = ['super_admin', 'tech_ops', 'observer'].includes(role);
      const opsLink = page.getByRole('link', { name: '前往通话运维' });
      assert.equal(await opsLink.count(), mayReadOps ? 1 : 0);
      if (mayReadOps) assert.equal(await opsLink.getAttribute('href'), '/admin/pages/voice-ops.html');
      assert.equal(await page.locator('#sidebar-mount').getByText('通话运维').count(), mayReadOps ? 1 : 0);
      assert.equal(await page.locator('#voice-global-switch-card').count(),0);
      assert.equal('enabled' in JSON.parse(await page.locator('#voice-section-json').inputValue()),false);
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('PASS: independent menu, one confirmation, cancel/no writes, success-only state, failed/conflicting/lost responses, permissions and old entry removed');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});

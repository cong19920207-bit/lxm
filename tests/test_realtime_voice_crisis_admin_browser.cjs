const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    for (const role of ['super_admin','ai_trainer','observer','tech_ops','ops_admin']) {
      const page = await browser.newPage();
      const errors = [], writes = [], reads = [];
      let health = {publication_status:'unpublished', active_version:null, keyword_count:0,
        cache_status:'missing', fallback_ready:false};
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(role => {
        sessionStorage.setItem('admin_token','local-test');
        sessionStorage.setItem('admin_role',role);
      }, role);
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'http://voice.test') return route.abort();
        if (url.pathname.startsWith('/api/')) {
          reads.push(url.pathname);
          if (route.request().method() !== 'GET') writes.push(url.pathname);
          const data = url.pathname.endsWith('/history') ? {list:[],total:0} : {
            banned_keywords:[], persona_boundary_keywords:[], style_violation_keywords:[],
            crisis_keywords:health?.fallback_ready ? ['fixture-policy'] : [], crisis_keywords_status:health};
          return route.fulfill({json:{code:0,data}});
        }
        const file = url.pathname.slice(1);
        return fs.existsSync(file) ? route.fulfill({path:file}) : route.fulfill({status:404,body:''});
      });
      await page.goto('http://voice.test/admin/pages/safety-rules.html#crisis');
      if (['tech_ops','ops_admin'].includes(role)) {
        await page.waitForURL('**/error.html?type=403');
        assert.deepEqual(reads,[]);
      } else {
        await page.getByText(/尚未发布危机词/).waitFor();
        assert.equal(await page.locator('#pane-crisis').isVisible(),true);
        assert.match(await page.locator('#crisis-config-health').innerText(),/新通话会被阻止/);
        if (role === 'observer') assert.equal(await page.locator('#btn-save-crisis').isVisible(),false);
        health = {publication_status:'published',active_version:9,keyword_count:1,
          cache_status:'missing',fallback_ready:true};
        await page.reload();
        await page.getByText(/已发布 · V9/).waitFor();
        assert.match(await page.locator('#crisis-config-health').innerText(),/回退读取数据库/);
        health = undefined;
        await page.reload();
        await page.getByText(/状态暂时无法确认/).waitFor();
      }
      assert.deepEqual(writes,[]);
      assert.deepEqual(errors,[]);
      await page.close();
    }

    // The first approved term can be published directly from the input field.
    const page = await browser.newPage();
    let published = [];
    const publishRequests = [];
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('admin_token','local-test');
      sessionStorage.setItem('admin_role','super_admin');
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://voice.test') return route.abort();
      if (url.pathname === '/api/admin/safety-rules/crisis-keywords' && route.request().method() === 'PUT') {
        const keywords = route.request().postDataJSON().keywords;
        publishRequests.push(keywords);
        if (!Array.isArray(keywords) || keywords.length === 0) {
          return route.fulfill({status:422,json:{code:20076,message:'危机关键词不能为空'}});
        }
        published = keywords;
        return route.fulfill({json:{code:0,data:{version:1}}});
      }
      if (url.pathname.startsWith('/api/')) {
        const data = url.pathname.endsWith('/history') ? {list:[],total:0} : {
          banned_keywords:[], persona_boundary_keywords:[], style_violation_keywords:[],
          crisis_keywords:published,
          crisis_keywords_status:{publication_status:published.length ? 'published' : 'unpublished',
            active_version:published.length ? 1 : null,keyword_count:published.length,
            cache_status:published.length ? 'healthy' : 'missing',fallback_ready:published.length > 0}
        };
        return route.fulfill({json:{code:0,data}});
      }
      const file = url.pathname.slice(1);
      return fs.existsSync(file) ? route.fulfill({path:file}) : route.fulfill({status:404,body:''});
    });
    await page.goto('http://voice.test/admin/pages/safety-rules.html#crisis');
    await page.getByText(/尚未发布危机词/).waitFor();
    await page.locator('#btn-save-crisis').click();
    assert.deepEqual(publishRequests,[]);
    await page.locator('#crisis-inline-error.show').waitFor();
    await page.locator('#input-crisis').fill('  不想活了  ');
    await page.locator('#btn-save-crisis').click();
    await page.waitForFunction(() =>
      document.querySelector('#crisis-config-health').textContent.includes('已发布') ||
      document.querySelector('#crisis-inline-error').classList.contains('show'));
    assert.deepEqual(publishRequests,[['不想活了']]);
    await page.getByText(/已发布 · V1/).waitFor();
    assert.equal(await page.locator('#input-crisis').inputValue(),'');
    assert.equal(await page.locator('#cloud-crisis .safety-kw-tag').count(),1);
    assert.deepEqual(errors,[]);
    await page.close();
    console.log('crisis config page: health, roles, empty rejection and direct input publication');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

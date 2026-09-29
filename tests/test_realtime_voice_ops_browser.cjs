// Real DOM + shared adminRequest; all network traffic is intercepted in this test.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [], writes = [], opsReads = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('admin_token', 'local-test');
      if (!sessionStorage.getItem('admin_role')) sessionStorage.setItem('admin_role', 'tech_ops');
      window.showToast = () => {};
    });
    let active = ['done', 'pending', 'manual'], releaseWrite;
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== 'http://voice.test') return route.abort();
      if (!url.pathname.startsWith('/api/')) {
        const file = url.pathname.slice(1);
        return fs.existsSync(file) ? route.fulfill({path: file}) : route.fulfill({contentType: 'text/html', body: '<html><body></body></html>'});
      }
      if (request.method() === 'GET') {
        if (url.pathname.startsWith('/api/admin/voice/ops/')) opsReads.push(url.pathname);
        return route.fulfill({json: {code: 0, data: {
        calls: active.map(call_id => ({call_id, user_id: 1, status: 'connected'})), database_count: active.length, lease_count: 0}}});
      }
      writes.push(url.pathname);
      if (url.pathname.endsWith('/hard-stop')) {
        await new Promise(resolve => {releaseWrite = resolve;});
        active = ['manual'];
        return route.fulfill({status: 503, json: {code: 503, data: {
          targets: ['done', 'pending', 'manual'], results: [
            {call_id: 'done', changed: true, cleanup_pending: false},
            {call_id: 'pending', changed: true, cleanup_pending: true}], failed: ['pending', 'manual'],
          failure_details: [
            {call_id: 'pending', error_code: 'VOICE_END_CLEANUP_PENDING', retryable: true},
            {call_id: 'manual', error_code: 'VOICE_END_SETTLEMENT_REVIEW_REQUIRED', retryable: false}]
        }}});
      }
      if (url.pathname.endsWith('/pending/force-end')) return route.fulfill({json: {code: 0, data: {call_id: 'pending', changed: false, cleanup_pending: false}}});
      if (url.pathname.endsWith('/manual/force-end')) return route.fulfill({status: 409, json: {code: 409, data: {
        call_id: 'manual', error_code: 'VOICE_END_SETTLEMENT_REVIEW_REQUIRED', retryable: false,
        message: '<img src=x onerror=alert(1)> private server content'}}});
      if (url.pathname.endsWith('/unknown/force-end')) return route.abort('failed');
      return route.fulfill({json: {code: 0, data: {idempotent: false}}});
    });
    const pageResponse = await page.goto('http://voice.test/admin/pages/voice-ops.html');
    assert.equal(pageResponse.status(), 200, 'the independent operations page must load');
    assert.equal(await page.locator('#voice-ops-card').count(), 1, 'operations controls belong on the independent page');
    await page.waitForFunction(() => document.querySelectorAll('#voice-ops-calls tr').length === 3);
    assert.match(await page.locator('#sidebar-mount .menu-item.active').innerText(), /通话运维/);
    await page.locator('#voice-ops-hard').click();
    assert.equal(writes.length, 0, 'exact confirmation is required');
    await page.locator('#voice-ops-confirm').fill('CONFIRM');
    await page.locator('#voice-ops-hard').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-hard').disabled);
    assert.equal(await page.locator('#voice-ops-calls button:enabled').count(), 0, 'duplicate writes are disabled');
    // Synchronize with the intercepted request without a timing assumption.
    while (!releaseWrite) await new Promise(setImmediate);
    releaseWrite();
    await page.waitForFunction(() => document.querySelector('#voice-ops-result').textContent.includes('清理待完成 1'));
    const outcomes = page.locator('#voice-ops-outcomes');
    assert.match(await outcomes.textContent(), /需人工核查/);
    assert.equal(await outcomes.locator('button').count(), 1);
    await page.locator('#voice-ops-refresh').click();
    assert.match(await page.locator('#voice-ops-result').textContent(), /完成 1 通/);
    assert.match(await outcomes.textContent(), /pending/);
    await page.locator('#voice-ops-confirm').fill('CONFIRM');
    await outcomes.locator('button').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-result').textContent.includes('完成 2 通'));
    assert.deepEqual(writes, ['/api/admin/voice/ops/hard-stop', '/api/admin/voice/calls/pending/force-end']);
    await page.locator('#voice-ops-confirm').fill('CONFIRM');
    await page.locator('#voice-ops-calls button').click();
    await page.waitForFunction(() => !document.querySelector('#voice-ops-hard').disabled);
    assert.equal(await outcomes.locator('img').count(), 0);
    assert.doesNotMatch(await outcomes.textContent(), /private server content/);

    active = ['unknown'];
    await page.locator('#voice-ops-refresh').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-calls').textContent.includes('unknown'));
    await page.locator('#voice-ops-confirm').fill('CONFIRM');
    await page.locator('#voice-ops-calls button').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-outcomes').textContent.includes('结果待确认'));
    assert.equal(writes.filter(path => path.endsWith('/unknown/force-end')).length, 1);
    assert.match(await outcomes.textContent(), /unknown/);
    await page.evaluate(() => sessionStorage.setItem('admin_role', 'observer'));
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#voice-ops-state').textContent.includes('进行中'));
    assert.equal(await page.locator('#voice-ops-write').isVisible(), false);
    assert.equal(await page.locator('#voice-ops-calls button').count(), 0);
    for (const role of ['ops_admin', 'ai_trainer']) {
      const readCount = opsReads.length;
      await page.evaluate(roleName => sessionStorage.setItem('admin_role', roleName), role);
      await page.goto('http://voice.test/admin/pages/voice-ops.html');
      await page.waitForURL('**/error.html?type=403');
      assert.equal(opsReads.length, readCount, 'denied roles must not request operations data');
    }
    assert.deepEqual(errors, []);
    console.log('PASS: partial 503 details, fixed-target retries, pending cleanup, manual review, unknown result and observer');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});

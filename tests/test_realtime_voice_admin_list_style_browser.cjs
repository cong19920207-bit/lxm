const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('admin_token', 'local-test');
      sessionStorage.setItem('admin_role', 'super_admin');
      sessionStorage.setItem('admin_username', 'test');
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://voice.test') return route.abort();
      if (url.pathname.startsWith('/api/')) {
        let data = {};
        if (url.pathname === '/api/admin/voice/calls') {
          data = { items: [{ call_id: 'style-call', user_id: 1, status: 'ended' }], total: 45 };
        } else if (url.pathname === '/api/admin/voice/crisis-records') {
          data = { items: [{ id: 1, call_id: 'style-call', turn_index: 1, is_persona_incident: false, created_at: '2026-09-27T00:00:00', expired: false, match_status: 'matched' }], total: 45, page: 1, page_size: 20 };
        } else if (url.pathname.endsWith('/daily')) {
          data = { date: '2026-09-27', metrics: [] };
        } else if (url.pathname.endsWith('/history')) {
          data = { start: '2026-09-20', end: '2026-09-26', days: [] };
        } else if (url.pathname.endsWith('/observations')) {
          data = { date: '2026-09-27', capability_metrics: [], events: [], durations: [] };
        }
        return route.fulfill({ json: { code: 0, data } });
      }
      const file = url.pathname.slice(1);
      return fs.existsSync(file)
        ? route.fulfill({ path: file })
        : route.fulfill({ status: 404, body: '' });
    });

    for (const name of ['voice-calls', 'voice-jobs', 'voice-crisis', 'voice-metrics']) {
      await page.goto('http://voice.test/admin/pages/' + name + '.html');
      await page.locator('.voice-list-page').waitFor();
      assert.equal(await page.locator('link[href*="voice-list-pages.css"]').count(), 1, name + ' uses shared list styles');
      assert.ok(await page.locator('.page-card').count() >= (name === 'voice-metrics' ? 4 : 2), name + ' separates controls and results into cards');
      assert.equal(
        await page.locator('input:not([type="checkbox"]), select').count(),
        await page.locator('input.form-control:not([type="checkbox"]), select.form-control').count(),
        name + ' uses platform form controls'
      );
      assert.equal(
        await page.locator('table').count(),
        await page.locator('.voice-table-wrap table.admin-table').count(),
        name + ' wraps platform tables consistently'
      );
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
        true,
        name + ' does not overflow the page viewport'
      );
    }

    await page.goto('http://voice.test/admin/pages/voice-calls.html');
    await page.locator('.pagination').waitFor();
    await page.goto('http://voice.test/admin/pages/voice-crisis.html');
    await page.locator('.pagination').waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: voice list pages share platform cards, controls, tables and pagination');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

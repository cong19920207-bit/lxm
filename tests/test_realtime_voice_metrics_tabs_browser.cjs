const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
    const apiPaths = [];
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
        apiPaths.push(url.pathname);
        let data = {};
        if (url.pathname.endsWith('/daily')) data = { date: url.searchParams.get('day'), metrics: [] };
        if (url.pathname.endsWith('/history')) data = { start: url.searchParams.get('start'), end: url.searchParams.get('end'), days: [] };
        if (url.pathname.endsWith('/observations')) data = { date: url.searchParams.get('day'), capability_metrics: [], events: [], durations: [] };
        if (url.pathname.endsWith('/billing-preview')) data = {
          start: url.searchParams.get('start'), end: url.searchParams.get('end'), currency: 'CNY',
          billable_seconds: 0, estimated_cost: '0.000000', provider_billed_cost: '1.00',
          difference_amount: '-1.000000', difference_rate: -1, formula_version: 'voice-bill-v1'
        };
        return route.fulfill({ json: { code: 0, data } });
      }
      const file = url.pathname.slice(1);
      return fs.existsSync(file) ? route.fulfill({ path: file }) : route.fulfill({ status: 404, body: '' });
    });

    await page.goto('http://voice.test/admin/pages/voice-metrics.html');
    await page.locator('#daily-status').getByText(/统计日期/).waitFor();
    assert.equal(await page.getByRole('tab').count(), 4, 'four metric modules are exposed as tabs');
    assert.equal(await page.getByRole('tab', { name: '业务日统计' }).getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('.voice-metrics-pane:visible').count(), 1, 'only one metric module is visible');
    assert.match(page.url(), /[?&]tab=daily(?:&|$)/, 'default tab is reflected in the URL');
    assert.deepEqual(apiPaths, ['/api/admin/voice/metrics/daily'], 'only the active tab loads initially');

    await page.locator('#daily-date').fill('2026-09-18');
    await page.getByRole('tab', { name: '历史日聚合' }).click();
    await page.locator('#history-status').getByText(/已落库结果/).waitFor();
    assert.match(page.url(), /[?&]tab=history(?:&|$)/);
    assert.equal(await page.locator('#metrics-pane-history').isVisible(), true);
    assert.equal(apiPaths.filter(path => path.endsWith('/history')).length, 1, 'history loads on first activation');

    await page.locator('#history-start').fill('2026-09-10');
    await page.getByRole('tab', { name: '业务日统计' }).click();
    assert.equal(await page.locator('#daily-date').inputValue(), '2026-09-18', 'each tab keeps its filter values');
    assert.equal(apiPaths.filter(path => path.endsWith('/daily')).length, 1, 'returning to a loaded tab does not reload it');
    await page.goBack();
    await page.getByRole('tab', { name: '历史日聚合' }).waitFor();
    assert.equal(await page.getByRole('tab', { name: '历史日聚合' }).getAttribute('aria-selected'), 'true', 'browser history restores the tab');
    assert.equal(await page.locator('#history-start').inputValue(), '2026-09-10');

    await page.getByRole('tab', { name: '成本与账单' }).focus();
    await page.getByRole('tab', { name: '成本与账单' }).press('ArrowRight');
    await page.locator('#observation-status').getByText(/观测日期/).waitFor();
    assert.equal(await page.getByRole('tab', { name: '近期观测' }).getAttribute('aria-selected'), 'true', 'arrow keys switch tabs');
    assert.equal(apiPaths.filter(path => path.endsWith('/observations')).length, 1);

    await page.getByRole('tab', { name: '成本与账单' }).click();
    await page.locator('#billing-status').getByText(/模拟核对/).waitFor();
    assert.equal(apiPaths.filter(path => path.endsWith('/billing-preview')).length, 1, 'billing loads on first activation');
    assert.deepEqual(errors, []);
    console.log('PASS: metrics tabs use URL state, lazy loading, browser history, keyboard switching and preserved filters');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

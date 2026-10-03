// STEP-001 asset viewer only; this does not load the production home page.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HOME_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.HOME_CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const runs = [];
  try {
    for (const [width, height, dpr] of [[375, 667, 1], [390, 844, 3], [430, 932, 3], [1280, 720, 1]]) {
      const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`http://127.0.0.1:54322/?width=${width}&height=${height}`);
      await page.waitForFunction(() => window.previewReady);
      const results = await page.evaluate(() => window.runChecks());
      assert.equal(results.assets.length, 7);
      assert.ok(results.assets.every(asset => asset.pass), JSON.stringify(results.assets));
      for (const closed of [false, true]) {
        await page.evaluate(closed => window.setEye(closed), closed);
        await page.evaluate(async () => Promise.all([...document.images].map(img => img.decode())));
        await page.locator('.scene').screenshot({
          path: path.join(__dirname, `${width}x${height}-dpr${dpr}-${closed ? 'closed' : 'open'}.png`),
        });
      }
      assert.deepEqual(errors, []);
      runs.push({ requestedViewport: [width, height], requestedDPR: dpr, ...results, errors });
      await context.close();
    }
    fs.writeFileSync(path.join(__dirname, 'browser-results.json'), JSON.stringify({
      scope: 'Desktop Chrome asset viewer. Viewports and DPR are controlled; no mobile device, WeChat, production UI or network-performance claim.',
      browserVersion: browser.version(), runs,
    }, null, 2) + '\n');
    console.log(`PASS: ${runs.length} controlled viewport/DPR runs, ${runs.length * 7} asset decode/composite checks, 8 open/closed screenshots`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

const assert = require('node:assert/strict');
const fs = require('node:fs');
const { setup, artifact, ready } = require('./home_browser_helpers.cjs');
const motionSwitch = page => page.getByRole('switch', { name: '主页动效', exact: true });

async function start(options = {}) {
  const s = await setup({ token: true, ...options });
  await s.page.addInitScript(() => {
    sessionStorage.setItem('lxm_home_loader_done', '1');
    window.preferencePageIdentity = Math.random();
    window.preferencePageShows = [];
    window.addEventListener('pageshow', e => window.preferencePageShows.push(e.persisted));
    window.preferencePermissionCalls = 0;
    if (window.DeviceOrientationEvent) {
      window.DeviceOrientationEvent.requestPermission = () => {
        window.preferencePermissionCalls++;
        return Promise.resolve('granted');
      };
    }
  });
  return s;
}

async function settings(s) {
  await s.page.locator('#linxiaomeng-avatar').click();
  await s.page.waitForURL(s.origin + '/pages/settings.html');
  assert.equal(await motionSwitch(s.page).count(), 1, 'Settings must expose the homepage motion switch');
  await motionSwitch(s.page).waitFor({ state: 'visible' });
}

(async () => {
  const results = [];
  let s = await start({ nativeBfcache: true });
  try {
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    await s.page.waitForFunction(() => HomeScene.current.running);
    const identity = await s.page.evaluate(() => preferencePageIdentity);
    await settings(s);
    assert.equal(await motionSwitch(s.page).getAttribute('aria-checked'), 'true');
    assert.equal(await s.page.getByRole('switch', { name: '倾斜视差', exact: true }).getAttribute('aria-checked'), 'false');
    const styles = await s.page.evaluate(() => {
      const appearance = el => {
        const css = getComputedStyle(el);
        return [css.width, css.height, css.backgroundColor, css.borderRadius];
      };
      return { motion: appearance(document.getElementById('toggle-home-motion')), agent: appearance(document.getElementById('toggle-agent')) };
    });
    assert.deepEqual(styles.motion, styles.agent, 'Homepage motion uses the existing preference switch appearance');
    await motionSwitch(s.page).click();
    assert.equal(await motionSwitch(s.page).getAttribute('aria-checked'), 'false');
    assert.equal(await s.page.evaluate(() => localStorage.getItem('lxm_home_motion_enabled')), '0');
    assert.equal(s.apiRequests.filter(r => r.path === '/api/user/settings' && r.method === 'PUT').length, 0, 'Browser motion preference must not write account settings');
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => window.HomeScene && HomeScene.current.motionEnabled === false);
    assert.equal(await s.page.evaluate(() => preferencePageIdentity), identity, 'Native back restores the original homepage');
    assert.equal(await s.page.evaluate(() => preferencePageShows.includes(true)), true);
    assert.equal(await s.page.evaluate(() => HomeScene.current.running), false, 'Returning from settings applies the saved choice before resuming');
    const optionalBefore = s.requests.filter(r => /hair_|blink_crop|lamp_glow/.test(r.path)).length;
    await s.page.reload();
    await ready(s.page);
    assert.equal(await s.page.evaluate(() => HomeScene.current.running), false);
    assert.equal(s.requests.filter(r => /hair_|blink_crop|lamp_glow/.test(r.path)).length, optionalBefore, 'An initially disabled homepage does not load optional motion layers');
    await settings(s);
    assert.equal(await motionSwitch(s.page).getAttribute('aria-checked'), 'false');
    await s.page.evaluate(() => saveToken('fixture-another-account'));
    await s.page.reload();
    assert.equal(await motionSwitch(s.page).getAttribute('aria-checked'), 'false', 'Changing accounts retains the browser preference');
    await motionSwitch(s.page).focus();
    await s.page.keyboard.press('Space');
    assert.equal(await motionSwitch(s.page).getAttribute('aria-checked'), 'true');
    const otherTab = await s.context.newPage();
    try {
      await otherTab.goto(s.origin + '/pages/settings.html');
      await motionSwitch(otherTab).click();
      await s.page.waitForFunction(() => document.getElementById('toggle-home-motion').getAttribute('aria-checked') === 'false');
      await motionSwitch(otherTab).click();
      await s.page.waitForFunction(() => document.getElementById('toggle-home-motion').getAttribute('aria-checked') === 'true');
    } finally { await otherTab.close(); }
    await s.page.emulateMedia({ reducedMotion: 'reduce' });
    await s.page.waitForFunction(() => document.getElementById('home-motion-setting-desc').textContent.includes('系统已减少动态'));
    assert.match(await s.page.locator('#home-motion-setting-desc').textContent(), /系统已减少动态/);
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => window.HomeScene && HomeScene.current.motionEnabled);
    assert.equal(await s.page.evaluate(() => HomeScene.current.running), false, 'System reduced motion still takes priority');
    await s.page.emulateMedia({ reducedMotion: 'no-preference' });
    await s.page.waitForFunction(() => HomeScene.current.running);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
    assert.equal(await s.page.evaluate(() => preferencePermissionCalls), 0, 'Enabling scene motion never requests sensor permission');
    await s.page.getByRole('button', { name: '更多互动', exact: true }).click();
    assert.equal(await s.page.locator('.toast-item').last().textContent(), '敬请期待');
    assert.equal(await s.page.locator('#home-motion-panel').count(), 0);
    assert.equal(await s.page.locator('#home-motion-enabled').count(), 0, 'Scene motion belongs to settings');
    assert.equal(await s.page.locator('#home-tilt-enabled').count(), 0, 'Tilt control also belongs to settings');
    await settings(s);
    await s.page.screenshot({ path: artifact('reports/home-motion-settings/settings.png'), fullPage: true });
    assert.deepEqual(s.errors, []);
    results.push({ case: 'settings switch appearance, native back, refresh, account change, cross-tab sync, keyboard, reduced motion and separate tilt', pass: true });
  } finally { await s.close(); }

  for (const op of ['getItem', 'setItem']) {
    s = await start();
    try {
      await s.page.addInitScript(op => {
        const native = Storage.prototype[op];
        Storage.prototype[op] = function (key, ...args) {
          if (key === 'lxm_home_motion_enabled') throw Error('controlled preference fault');
          return native.call(this, key, ...args);
        };
      }, op);
      await s.page.goto(s.origin + '/pages/index.html');
      await ready(s.page);
      await settings(s);
      assert.match(await s.page.locator('#home-motion-storage-note').textContent(), op === 'getItem' ? /无法读取/ : /^$/);
      if (op === 'setItem') {
        await motionSwitch(s.page).click();
        assert.match(await s.page.locator('#home-motion-storage-note').textContent(), /仅本次/);
        await s.page.goBack();
        await s.page.waitForFunction(() => HomeScene.current.motionEnabled === false);
        assert.equal(await s.page.evaluate(() => HomeScene.current.running), false, 'A save failure still transfers this visit\'s choice to the homepage');
      }
      assert.deepEqual(s.errors, []);
      results.push({ case: 'actual settings with controlled preference ' + op + ' failure', pass: true });
    } finally { await s.close(); }
  }

  s = await start({ token: false });
  try {
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    assert.equal(await s.page.evaluate(() => HomeScene.current.motionEnabled), true, 'An independent browser enables all scene motion by default');
    await s.page.locator('#linxiaomeng-avatar').click();
    await s.page.waitForURL(s.origin + '/pages/settings.html');
    assert.equal(await s.page.locator('#settings-private-sections').isVisible(), false);
    assert.equal(await s.page.getByRole('button', { name: '点击登录', exact: true }).isVisible(), true);
    assert.equal(s.apiRequests.filter(r => ['/api/user/settings', '/api/relationship/status'].includes(r.path)).length, 0);
    assert.deepEqual(s.errors, []);
    results.push({ case: 'browser default and preserved visitor settings gate', pass: true });
  } finally { await s.close(); }

  fs.writeFileSync(artifact('reports/home-motion-settings/results.json'), JSON.stringify({ scope: 'Real homepage and settings frontend, desktop Chrome, controlled business APIs and storage failures; native back cache exercised', results }, null, 2) + '\n');
  console.log('PASS ' + results.length + ' settings/home preference scenarios');
})().catch(error => { console.error(error); process.exitCode = 1; });

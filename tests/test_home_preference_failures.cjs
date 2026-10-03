// Regression expectations follow the approved F1/F2 fixes, including page-only
// behavior when every preference write is unavailable. Permissions are controlled.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { setup, ready, artifact, root } = require('./home_browser_helpers.cjs');
const motion = page => page.getByRole('switch', { name: '主页动效', exact: true });
const tilt = page => page.getByRole('switch', { name: '倾斜视差', exact: true });

async function start({ startupFailure = false, hidden = false, cold = false } = {}) {
  const s = await setup({ token: true, nativeBfcache: true });
  try {
    await s.page.addInitScript(({ startupFailure, hidden, cold }) => {
      if (!cold) sessionStorage.setItem('lxm_home_loader_done', '1');
      if (startupFailure && !sessionStorage.getItem('__preference_startup_seeded')) {
        sessionStorage.setItem('lxm_home_tilt_enabled', '1');
        sessionStorage.setItem('lxm_home_tilt_permission', 'granted');
        sessionStorage.setItem('__preference_fault', 'tilt-all');
        sessionStorage.setItem('__preference_startup_seeded', '1');
      }
      window.preferencePageIdentity = Math.random();
      window.preferenceFault = sessionStorage.getItem('__preference_fault') || '';
      const native = Storage.prototype.setItem;
      Storage.prototype.setItem = function(key, ...args) {
        const mode = sessionStorage.getItem('__preference_fault') || '';
        if ((mode === 'motion' && ['lxm_home_motion_enabled', 'lxm_home_motion_session'].includes(key)) ||
            (mode === 'tilt-flag' && key === 'lxm_home_tilt_enabled') ||
            (mode === 'tilt-status' && key === 'lxm_home_tilt_status') ||
            (mode === 'tilt-all' && key.startsWith('lxm_home_tilt_'))) {
          throw new DOMException('Controlled preference write failure', 'QuotaExceededError');
        }
        return native.call(this, key, ...args);
      };
      window.DeviceOrientationEvent.requestPermission = () => {
        if (!navigator.userActivation.isActive || location.pathname !== '/pages/settings.html') throw Error('Explicit settings gesture required');
        sessionStorage.setItem('__preference_permission_calls', String(Number(sessionStorage.getItem('__preference_permission_calls')) + 1));
        return Promise.resolve('granted');
      };
      if (startupFailure && location.pathname === '/pages/index.html') {
        window.preferenceOrientation = window.DeviceOrientationEvent;
        Object.defineProperty(window, 'DeviceOrientationEvent', { configurable: true, writable: true, value: undefined });
        window.preferenceHidden = hidden;
        Object.defineProperty(document, 'hidden', { configurable: true, get: () => window.preferenceHidden });
        window.preferenceToasts = [];
        new MutationObserver(records => {
          for (const record of records) for (const node of record.addedNodes) {
            if (node.nodeType === 1 && node.matches('.toast-item')) {
              window.preferenceToasts.push({ text: node.textContent, phase: window.HomeStartup?.phase, hidden: document.hidden });
            }
          }
        }).observe(document, { childList: true, subtree: true });
      }
    }, { startupFailure, hidden, cold });
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    return s;
  } catch (error) { await s.close(); throw error; }
}
async function settings(s) {
  await s.page.locator('#linxiaomeng-avatar').click();
  await s.page.waitForURL(s.origin + '/pages/settings.html');
  await tilt(s.page).waitFor({ state: 'visible' });
}
async function fault(s, mode) {
  await s.page.evaluate(mode => {
    window.preferenceFault = mode;
    sessionStorage.setItem('__preference_fault', mode);
  }, mode);
}
async function resume(s) {
  await s.page.evaluate(() => {
    HomeScene.current.pause('controlled-hidden');
    HomeScene.current.pause('controlled-hidden', false);
  });
}
const cases = {
  async tilt_startup_page_only(s) {
    const messages = await s.page.evaluate(() => preferenceToasts);
    assert.equal(messages.length, 1, 'Initialization closure must show the save-failure warning after the page is ready');
    assert.match(messages[0].text, /当前浏览器不支持倾斜.*本页.*离开页面后/);
    assert.equal(messages[0].phase, 'ready', 'The warning must not expire during the loading screen');
    assert.equal(messages[0].hidden, false);
    await s.page.waitForFunction(() => Number(getComputedStyle(document.querySelector('.toast-item')).opacity) > 0.95);
    assert.equal(await s.page.evaluate(() => HomePreferences.readTilt().enabled), false);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false);
    await s.page.evaluate(() => {
      document.dispatchEvent(new Event('DOMContentLoaded'));
      window.dispatchEvent(new Event('home-startup-change'));
      document.dispatchEvent(new Event('visibilitychange'));
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    });
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 1, 'Repeated lifecycle events must not repeat a delivered warning');
  },
  async tilt_startup_hidden(s) {
    const identity = await s.page.evaluate(() => preferencePageIdentity);
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 0, 'Do not consume a pending warning while hidden');
    await settings(s);
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => window.HomeScene?.current);
    assert.equal(await s.page.evaluate(() => preferencePageIdentity), identity, 'Pending feedback must survive native bfcache');
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 0);
    await s.page.evaluate(() => {
      window.preferenceHidden = false;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 1);
    assert.match(await s.page.locator('.toast-item').textContent(), /当前浏览器不支持倾斜.*离开页面后/);
  },
  async tilt_startup_replaced(s) {
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 0);
    await fault(s, '');
    // Exercise the saved-choice handoff directly; gesture authorization is covered by test_home_tilt.cjs.
    await s.page.evaluate(() => {
      window.DeviceOrientationEvent = window.preferenceOrientation;
      HomePreferences.writeTilt(true, true);
      window.preferenceHidden = false;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    assert.equal(await s.page.evaluate(() => HomePreferences.readTilt().enabled), true);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), true);
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 0, 'A later successful choice must invalidate the old closure warning');
  },
  async tilt_startup_destroyed(s) {
    await s.page.evaluate(() => {
      HomeScene.current.destroy();
      window.preferenceHidden = false;
      document.dispatchEvent(new Event('visibilitychange'));
      document.dispatchEvent(new Event('DOMContentLoaded'));
      window.dispatchEvent(new Event('home-startup-change'));
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    });
    assert.equal(await s.page.evaluate(() => preferenceToasts.length), 0, 'Destroyed pages must never deliver pending feedback');
    assert.equal(await s.page.evaluate(() => HomeScene.current.inspect().subscriptions), 0);
  },
  async motion(s) {
    await settings(s);
    await fault(s, 'motion');
    await motion(s.page).click();
    assert.equal(await motion(s.page).getAttribute('aria-checked'), 'false');
    assert.equal(await s.page.evaluate(() => HomePreferences.readMotion().enabled), false, 'Failed writes must not let a read discard this page\'s choice');
    assert.match(await s.page.locator('#home-motion-storage-note').textContent(), /本页.*离开页面后/);
    await tilt(s.page).click();
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false');
    assert.equal(await s.page.evaluate(() => Number(sessionStorage.getItem('__preference_permission_calls'))), 0, 'Off motion must prevent sensor authorization even when saving failed');
    assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /先开启主页动效/);
    await s.page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })));
    assert.equal(await motion(s.page).getAttribute('aria-checked'), 'false');
    const other = await s.context.newPage();
    try {
      await other.goto(s.origin + '/pages/settings.html');
      await motion(other).click();
      await s.page.waitForFunction(() => document.getElementById('home-motion-storage-note').textContent === '');
      assert.equal(await motion(s.page).getAttribute('aria-checked'), 'false', 'A later saved cross-tab choice clears the page-only override');
    } finally { await other.close(); }
    await fault(s, '');
    await motion(s.page).click();
    assert.equal(await s.page.evaluate(() => localStorage.getItem('lxm_home_motion_enabled')), '1');
    assert.equal(await s.page.locator('#home-motion-storage-note').textContent(), '');
    await fault(s, 'motion');
    await motion(s.page).click();
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => HomeScene.current.running);
    assert.equal(await s.page.evaluate(() => HomeScene.current.motionEnabled), true, 'Unwritable cross-page transfer may restore the saved choice, as explained in settings');
  },
  async tilt_timeout(s) {
    await settings(s);
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    await fault(s, 'tilt-flag');
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().state === 'unavailable', null, { timeout: 9000 });
    assert.equal(await s.page.evaluate(() => HomePreferences.readTilt().enabled), false, 'A failed timeout write must still leave the effective choice off');
    await resume(s);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false, 'Paused/resumed scenes must not revive a timed-out selection');
    await settings(s);
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false', 'The existing status channel must carry the off selection back to settings');
    assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /方向数据/);
    assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /无法保存/);
    await s.page.reload();
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false');
    await fault(s, '');
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    await s.page.evaluate(() => window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', { beta: 0, gamma: 0 })));
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().state === 'enabled');
    await settings(s);
    await fault(s, 'tilt-flag');
    await tilt(s.page).click();
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false', 'Explicit off also wins over the stale stored on value');
    await s.page.goBack({ waitUntil: 'commit' });
    await resume(s);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
  },
  async tilt_page_only(s) {
    await settings(s);
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    await fault(s, 'tilt-all');
    await tilt(s.page).click();
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false', 'Explicit off must take effect in this page despite all preference writes failing');
    assert.equal(await s.page.evaluate(() => HomePreferences.readTilt().enabled), false);
    assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /本页.*离开页面后/);
    await s.page.evaluate(() => syncHomeMotionSetting());
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false');
    await fault(s, '');
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    assert.doesNotMatch(await s.page.locator('#home-tilt-setting-status').textContent(), /无法保存/);
  },
  async tilt_handoff_failure(s) {
    await settings(s);
    await fault(s, 'tilt-status');
    await tilt(s.page).click();
    await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-busy') === 'false');
    assert.equal(await tilt(s.page).getAttribute('aria-checked'), 'false', 'An incomplete preference handoff must not report an enabled choice');
    assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /无法保存/);
    await s.page.goBack({ waitUntil: 'commit' });
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
  },
  async tilt_timeout_page_only(s) {
    const identity = await s.page.evaluate(() => preferencePageIdentity);
    await settings(s);
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    await fault(s, 'tilt-all');
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().state === 'unavailable', null, { timeout: 9000 });
    assert.equal(await s.page.evaluate(() => preferencePageIdentity), identity);
    assert.equal(await s.page.evaluate(() => HomePreferences.readTilt().enabled), false);
    await resume(s);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false);
    assert.match(await s.page.locator('.toast-item').last().textContent(), /本页.*离开页面后/);
    // A later successful explicit choice must replace the old page-only closure.
    await fault(s, '');
    await settings(s);
    if (await tilt(s.page).getAttribute('aria-checked') === 'true') await tilt(s.page).click();
    await tilt(s.page).click();
    await s.page.waitForFunction(() => HomePreferences.readTilt().enabled);
    await s.page.goBack({ waitUntil: 'commit' });
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().listening);
    await s.page.evaluate(() => window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', { beta: 0, gamma: 0 })));
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().state === 'enabled');
  },
};
(async () => {
  const results = [];
  for (const [name, run] of Object.entries(cases)) {
    if (process.env.HOME_PREFERENCE_FAILURE_CASE && process.env.HOME_PREFERENCE_FAILURE_CASE !== name) continue;
    const s = await start({ startupFailure: name.startsWith('tilt_startup_'), hidden: name.startsWith('tilt_startup_') && name !== 'tilt_startup_page_only', cold: name === 'tilt_startup_page_only' });
    try { await run(s); assert.deepEqual(s.errors, []); results.push({ case: name, pass: true }); }
    finally { await s.close(); }
  }
  const files = ['frontend/pages/index.html','frontend/pages/settings.html','frontend/static/js/home-preferences.js','frontend/static/js/home-scene.js','frontend/static/css/home-scene.css'];
  const sourceSha256 = Object.fromEntries(files.map(file => [file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
  fs.writeFileSync(artifact('reports/home-motion-settings/preference-failure-results.json'), JSON.stringify({ scope: 'Actual home/settings frontend and desktop Chrome; controlled storage write failures and orientation permissions; real phone validation remains pending', results, sourceSha256 }, null, 2) + '\n');
  console.log('PASS ' + results.length + ' combined preference failure scenarios');
})().catch(error => { console.error(error); process.exitCode = 1; });

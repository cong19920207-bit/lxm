const assert = require('node:assert/strict');
const fs = require('node:fs');
const { setup, ready, artifact } = require('./home_browser_helpers.cjs');
const tiltSwitch = page => page.getByRole('switch', { name: '倾斜视差', exact: true });

async function start(mode = 'allow') {
  const s = await setup({ token: true, nativeBfcache: true });
  try {
  if (mode === 'reduced') await s.page.emulateMedia({ reducedMotion: 'reduce' });
  await s.page.addInitScript(mode => {
    sessionStorage.setItem('lxm_home_loader_done', '1');
    if (sessionStorage.getItem('__tilt_permission_calls') === null) sessionStorage.setItem('__tilt_permission_calls', '0');
    window.tiltPageIdentity = Math.random();
    window.tiltPageShows = [];
    window.addEventListener('pageshow', e => window.tiltPageShows.push(e.persisted));
    if (mode === 'unsupported') Object.defineProperty(window, 'DeviceOrientationEvent', { value: undefined });
    else if (mode === 'insecure') Object.defineProperty(window, 'isSecureContext', { value: false });
    if (window.DeviceOrientationEvent && mode !== 'implicit') {
      window.DeviceOrientationEvent.requestPermission = () => {
        assertGesture();
        sessionStorage.setItem('__tilt_permission_calls', String(Number(sessionStorage.getItem('__tilt_permission_calls')) + 1));
        if (mode === 'defer') return new Promise(resolve => window.finishTiltPermission = resolve);
        if (mode === 'reject') return Promise.reject(Error('controlled permission failure'));
        return Promise.resolve(mode === 'deny' ? 'denied' : 'granted');
      };
    }
    function assertGesture() {
      if (!navigator.userActivation.isActive || location.pathname !== '/pages/settings.html') throw Error('Permission requires an active user gesture in settings');
    }
    if (mode === 'storage') {
      const native = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, value) {
        if (key === 'lxm_home_tilt_enabled') throw Error('controlled tilt storage fault');
        return native.call(this, key, value);
      };
    }
  }, mode);
  await s.page.goto(s.origin + '/pages/index.html');
  await ready(s.page);
  s.homeIdentity = await s.page.evaluate(() => tiltPageIdentity);
  await s.page.locator('#linxiaomeng-avatar').click();
  await s.page.waitForURL(s.origin + '/pages/settings.html');
  assert.equal(await tiltSwitch(s.page).count(), 1, 'Settings must expose the tilt control beside homepage motion');
  await tiltSwitch(s.page).waitFor({ state: 'visible' });
  return s;
  } catch (error) { await s.close(); throw error; }
}

const calls = s => s.page.evaluate(() => Number(sessionStorage.getItem('__tilt_permission_calls')));
const orient = (s, beta, gamma) => s.page.evaluate(({ beta, gamma }) => window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', { beta, gamma })), { beta, gamma });
async function back(s) {
  await s.page.goBack({ waitUntil: 'commit' });
  await s.page.waitForFunction(() => window.HomeScene?.tilt);
}
async function settings(s) {
  await s.page.locator('#linxiaomeng-avatar').click();
  await s.page.waitForURL(s.origin + '/pages/settings.html');
}

(async () => {
  const results = [];
  let s = await start();
  try {
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false', 'Tilt is off until explicitly enabled');
    assert.equal(await s.page.getByRole('switch', { name: '主页动效', exact: true }).getAttribute('aria-checked'), 'true');
    assert.equal(await calls(s), 0);
    const sizes = await s.page.evaluate(() => ['toggle-home-motion', 'toggle-home-tilt', 'toggle-agent'].map(id => {
      const style = getComputedStyle(document.getElementById(id));
      return [style.width, style.height, style.borderRadius];
    }));
    assert.deepEqual(sizes[0], sizes[1]);
    assert.deepEqual(sizes[1], sizes[2], 'Both new controls use the existing preference switch shape');
    await tiltSwitch(s.page).focus();
    await s.page.keyboard.press('Space');
    await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-checked') === 'true');
    assert.equal(await calls(s), 1);
    await back(s);
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().listening);
    assert.equal(await s.page.evaluate(() => tiltPageIdentity), s.homeIdentity, 'Actual back cache restores the homepage with the new choice');
    assert.equal(await s.page.evaluate(() => tiltPageShows.includes(true)), true);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().state), 'waiting-data');
    assert.equal(await calls(s), 1, 'Returning home never repeats the authorization request');
    await orient(s, null, null);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().state), 'waiting-data', 'Permission alone is not valid sensor data');
    await orient(s, 45, 0);
    await orient(s, 55, 15);
    assert.deepEqual(await s.page.evaluate(() => HomeScene.tilt.inspect().input), { x: 0.75, y: 0.4 });
    // Approved tuning: 15° sideways and 10° forward move the visible layer 9px / 3.2px.
    await s.page.waitForFunction(() => {
      const matrix = new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.home-scene-parallax')).transform);
      return Math.abs(matrix.m41 - 9) < 0.1 && Math.abs(matrix.m42 - 3.2) < 0.1;
    }, null, { timeout: 2000 });
    await s.page.evaluate(() => window.dispatchEvent(new Event('orientationchange')));
    await orient(s, 55, 15);
    assert.deepEqual(await s.page.evaluate(() => HomeScene.tilt.inspect().input), { x: 0, y: 0 });
    await s.page.evaluate(() => { HomeScene.current.pause('test-login'); HomeScene.current.pause('test-hidden'); HomeScene.current.pause('test-login', false); });
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false);
    await s.page.evaluate(() => HomeScene.current.pause('test-hidden', false));
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().listening);
    await orient(s, 45, 0);
    const subscriptions = await s.page.evaluate(() => HomeScene.current.inspect().subscriptions);
    for (let i = 0; i < 6; i++) {
      await s.page.evaluate(() => { HomeScene.current.pause('test-hidden'); HomeScene.current.pause('test-hidden', false); });
      await orient(s, 45, 0);
    }
    assert.equal(await s.page.evaluate(() => HomeScene.current.inspect().subscriptions), subscriptions);
    assert.equal(await calls(s), 1);
    const otherTab = await s.context.newPage();
    try {
      await otherTab.goto(s.origin + '/pages/settings.html');
      assert.equal(await tiltSwitch(otherTab).getAttribute('aria-checked'), 'false', 'A new tab does not inherit active tilt');
    } finally { await otherTab.close(); }
    await settings(s);
    await s.page.getByRole('switch', { name: '主页动效', exact: true }).click();
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'true', 'Pausing motion retains the explicit tilt choice');
    await back(s);
    assert.equal(await s.page.evaluate(() => HomeScene.current.motionEnabled), false);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false);
    await settings(s);
    await s.page.getByRole('switch', { name: '主页动效', exact: true }).click();
    await back(s);
    await s.page.waitForFunction(() => HomeScene.tilt.inspect().listening);
    await orient(s, 45, 0);
    assert.equal(await calls(s), 1, 'Resuming the saved tilt choice does not request new permission');
    await settings(s);
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'true');
    await tiltSwitch(s.page).click();
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false');
    await back(s);
    await s.page.waitForFunction(() => !HomeScene.tilt.inspect().listening);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
    assert.deepEqual(await s.page.evaluate(() => HomeScene.tilt.inspect().input), { x: 0, y: 0 });
    await s.page.getByRole('button', { name: '更多互动', exact: true }).click();
    assert.equal(await s.page.locator('.toast-item').last().textContent(), '敬请期待');
    assert.equal(await s.page.locator('#home-tilt-enabled').count(), 0, 'The actual tilt switch has moved out of More');
    await settings(s);
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false');
    await s.page.screenshot({ path: artifact('reports/home-motion-settings/settings-both-controls.png'), fullPage: true });
    assert.equal(s.apiRequests.filter(r => r.path === '/api/user/settings' && r.method === 'PUT').length, 0);
    assert.deepEqual(s.errors, []);
    results.push({ case: 'settings shape/default, click authorization, real native back, finite data, rotation, combined pause, cleanup and explicit off', pass: true });
  } finally { await s.close(); }

  for (const mode of ['deny', 'unsupported', 'insecure', 'reject', 'storage', 'motion-off', 'reduced', 'defer']) {
    s = await start(mode);
    try {
      if (mode === 'motion-off') await s.page.getByRole('switch', { name: '主页动效', exact: true }).click();
      await tiltSwitch(s.page).click();
      if (mode === 'defer') {
        await s.page.waitForFunction(() => typeof finishTiltPermission === 'function');
        await tiltSwitch(s.page).click();
        await s.page.evaluate(() => window.finishTiltPermission('granted'));
        await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-busy') !== 'true');
      } else {
        const expected = { deny: /未获得/, unsupported: /不支持/, insecure: /连接/, reject: /授权/, storage: /保存/, 'motion-off': /先开启主页动效/, reduced: /减少动态/ }[mode];
        await s.page.waitForFunction(() => document.getElementById('home-tilt-setting-status').textContent !== '正在等待倾斜授权…');
        assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), expected);
      }
      assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false');
      if (['unsupported', 'insecure', 'motion-off', 'reduced'].includes(mode)) assert.equal(await calls(s), 0);
      await back(s);
      assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().listening), false);
      assert.deepEqual(s.errors, []);
      results.push({ case: mode + ' feedback, off state and no hidden activation', pass: true });
    } finally { await s.close(); }
  }

  for (const change of ['departure', 'motion-off', 'reduced']) {
    s = await start('defer');
    try {
    await tiltSwitch(s.page).click();
    await s.page.waitForFunction(() => typeof finishTiltPermission === 'function');
    if (change === 'departure') await s.page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })));
    else if (change === 'motion-off') await s.page.getByRole('switch', { name: '主页动效', exact: true }).click();
    else {
      await s.page.emulateMedia({ reducedMotion: 'reduce' });
      await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-busy') !== 'true');
    }
    await s.page.evaluate(() => window.finishTiltPermission('granted'));
    await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-busy') !== 'true');
    assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false', 'A late permission result cannot override cancellation');
    assert.deepEqual(s.errors, []);
    results.push({ case: change + ' invalidates a late authorization result', pass: true });
    } finally { await s.close(); }
  }

  for (const mode of ['allow', 'implicit']) {
    s = await start(mode);
    try {
      await tiltSwitch(s.page).click();
      await s.page.waitForFunction(() => document.getElementById('toggle-home-tilt').getAttribute('aria-checked') === 'true');
      await back(s);
      await s.page.waitForFunction(() => HomeScene.tilt.inspect().listening);
      if (mode === 'implicit') {
        await orient(s, 45, 0);
        assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().state), 'enabled');
        assert.equal(await calls(s), 0);
      } else {
        await s.page.waitForFunction(() => HomeScene.tilt.inspect().state === 'unavailable', {}, { timeout: 6500 });
        await settings(s);
        assert.equal(await tiltSwitch(s.page).getAttribute('aria-checked'), 'false');
        assert.match(await s.page.locator('#home-tilt-setting-status').textContent(), /方向数据/);
      }
      assert.deepEqual(s.errors, []);
      results.push({ case: mode === 'implicit' ? 'explicit setting with a browser that has no permission method' : 'missing direction data times out and is reflected in settings', pass: true });
    } finally { await s.close(); }
  }
  fs.writeFileSync(artifact('reports/home-motion-settings/tilt-settings-results.json'), JSON.stringify({ scope: 'Real home/settings frontend and desktop Chrome native back cache, controlled DeviceOrientation and permission outcomes; actual phone/HTTPS permission and direction remain pending', results }, null, 2) + '\n');
  console.log('PASS ' + results.length + ' settings tilt scenarios; real phone validation pending');
})().catch(error => { console.error(error); process.exitCode = 1; });

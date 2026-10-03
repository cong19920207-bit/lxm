// Character geometry stays stable through refresh, chat return, and breathing.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { setup, ready, artifact, root } = require('./home_browser_helpers.cjs');

async function entranceGeometry() {
  const s = await setup({ viewport: { width: 560, height: 600 } });
  try {
    await s.page.addInitScript(() => sessionStorage.setItem('lxm_home_loader_done', '1'));
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    const result = await s.page.evaluate(async () => {
      HomeScene.current.pause('geometry-check');
      const rig = document.querySelector('.home-scene-position');
      const bar = document.querySelector('.home-top-bar');
      const sample = () => {
        const r = rig.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height };
      };
      const remeasure = async transform => {
        bar.style.setProperty('transform', transform, 'important');
        window.dispatchEvent(new Event('resize'));
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
        return sample();
      };
      const neutral = await remeasure('none');
      const entrance = await remeasure('translateY(16px)');
      const restored = await remeasure('none');
      bar.style.removeProperty('transform');
      const note = document.createElement('span');
      note.className = 'home-module-note';
      note.innerHTML = '陪伴天数暂时无法加载，请稍后再试。<button type="button">重试</button>';
      bar.querySelector('.home-top-meta').append(note);
      const withNote = await remeasure('none');
      const noteVisible = note.getBoundingClientRect().height > 0;
      note.remove();
      const afterNote = await remeasure('none');
      bar.style.removeProperty('transform');
      return { neutral, entrance, restored, withNote, afterNote, noteVisible };
    });
    assert.equal(result.noteVisible, true, 'Failure note and retry remain visible');
    for (const frame of [result.entrance, result.restored, result.withNote, result.afterNote]) {
      for (const key of Object.keys(result.neutral)) {
        assert.ok(Math.abs(frame[key] - result.neutral[key]) < 0.1,
          'Top-bar entrance or transient note must not change character ' + key);
      }
    }
    assert.deepEqual(s.errors, []);
    return { case: 'entrance and transient failure-note geometry', pass: true, result };
  } finally { await s.close(); }
}

async function refreshBreathing() {
  const s = await setup();
  try {
    await s.page.addInitScript(() => {
      window.characterSamples = [];
      const record = () => {
        if (window.HomeStartup?.phase === 'ready' && window.HomeScene?.current.running) {
          const box = document.querySelector('.home-scene-character').getBoundingClientRect();
          characterSamples.push({ time: HomeScene.current.time, x: box.x, y: box.y,
            width: box.width, height: box.height });
        }
        if (!window.characterSamplesDone) requestAnimationFrame(record);
      };
      requestAnimationFrame(record);
    });
    await s.page.goto(s.origin + '/pages/index.html');
    await ready(s.page);
    await s.page.waitForFunction(() => HomeScene.current.time > 5700);
    const initial = await s.page.evaluate(() => {
      window.characterSamplesDone = true;
      return characterSamples;
    });
    await s.page.reload();
    await ready(s.page);
    await s.page.waitForFunction(() => HomeScene.current.time > 5700);
    const refreshed = await s.page.evaluate(() => {
      window.characterSamplesDone = true;
      return { navigation: performance.getEntriesByType('navigation')[0].type, samples: characterSamples };
    });
    assert.equal(refreshed.navigation, 'reload');
    const results = [];
    for (const [name, samples] of [['initial', initial], ['refresh', refreshed.samples]]) {
      assert.ok(samples.length > 20);
      const range = key => Math.max(...samples.map(s => s[key])) - Math.min(...samples.map(s => s[key]));
      assert.ok(range('height') < 0.1, name + ': breathing must not stretch the whole character');
      assert.ok(range('width') < 0.1, name + ': breathing must not resize the whole character');
      assert.ok(range('y') > 0.5 && range('y') < 2, name + ': preserve gentle breathing movement');
      const maximumStep = Math.max(...samples.slice(1).map((sample, i) => Math.abs(sample.y - samples[i].y)));
      assert.ok(maximumStep < 0.25, name + ': character movement must stay continuous after reveal');
      results.push({ navigation: name, widthRange: range('width'), heightRange: range('height'),
        movementRange: range('y'), maximumStep, first: samples[0], last: samples.at(-1) });
    }
    assert.deepEqual(s.errors, []);
    return { case: 'initial load and refresh breathing', pass: true, results };
  } finally { await s.close(); }
}

async function chatReturn() {
  const results = [];
  for (const viewport of [{ width: 390, height: 844 }, { width: 560, height: 600 }]) {
    const s = await setup({ token: true, nativeBfcache: true, viewport });
    try {
      await s.page.addInitScript(() => {
        window.homeReturnIdentity = Math.random();
        window.homeReturnSamples = [];
        const record = () => {
          if (window.HomeStartup?.phase === 'ready' && window.HomeScene?.current) {
            const r = document.querySelector('.home-scene-position').getBoundingClientRect();
            const p = document.querySelector('.h5-home-page').getBoundingClientRect();
            // A short page scrolls to reveal the chat button; native back restores
            // that scroll position. Compare geometry within the page, not viewport.
            homeReturnSamples.push({ x: r.x - p.x, y: r.y - p.y,
              width: r.width, height: r.height, scrollY: window.scrollY });
          }
          requestAnimationFrame(record);
        };
        requestAnimationFrame(record);
      });
      await s.page.goto(s.origin + '/pages/index.html');
      await ready(s.page);
      await s.page.waitForFunction(() => homeReturnSamples.length > 20);
      const initial = await s.page.evaluate(() => homeReturnSamples.at(-1));
      await s.page.locator('.home-cta-btn').click();
      await s.page.waitForURL(s.origin + '/pages/chat.html');
      await s.page.getByRole('button', { name: '返回', exact: true }).click();
      await s.page.waitForURL(s.origin + '/pages/index.html');
      await ready(s.page);
      await s.page.waitForFunction(() => homeReturnSamples.length > 20);
      const returned = await s.page.evaluate(() => ({ samples: homeReturnSamples,
        releaseMs: HomeStartup.releasedAt - HomeStartup.startedAt, identity: homeReturnIdentity }));
      assert.ok(returned.releaseMs < 3000, 'Chat return keeps the existing skip-loader behavior');
      await s.page.evaluate(() => { homeReturnSamples = []; });
      await s.page.locator('.home-cta-btn').click();
      await s.page.waitForURL(s.origin + '/pages/chat.html');
      await s.page.goBack({ waitUntil: 'commit' });
      await s.page.waitForFunction(() => window.HomeScene?.current && homeReturnSamples.length > 20);
      const cached = await s.page.evaluate(() => ({ identity: homeReturnIdentity, samples: homeReturnSamples }));
      assert.equal(cached.identity, returned.identity, 'Browser back restores the original homepage');
      for (const [navigation, samples] of [['chat return button', returned.samples], ['browser back', cached.samples]]) {
        for (const sample of samples) for (const key of ['x', 'y', 'width', 'height']) {
          assert.ok(Math.abs(sample[key] - initial[key]) < 0.1,
            navigation + ': character ' + key + ' stays stable from its first visible frame; ' +
            JSON.stringify({ viewport, initial, sample }));
        }
      }
      assert.deepEqual(s.errors, []);
      results.push({ viewport, pass: true, initial, returned: returned.samples[0],
        browserBack: cached.samples[0], returnReleaseMs: returned.releaseMs });
    } finally { await s.close(); }
  }
  return { case: 'chat return button and native browser back', pass: true, results };
}

(async () => {
  const cases = { entrance: entranceGeometry, breathing: refreshBreathing, chat_return: chatReturn };
  const results = [];
  for (const [name, run] of Object.entries(cases)) {
    if (!process.env.HOME_STABILITY_CASE || process.env.HOME_STABILITY_CASE === name) results.push(await run());
  }
  const files = ['frontend/pages/index.html', 'frontend/pages/chat.html', 'frontend/static/css/home-scene.css', 'frontend/static/js/home-scene.js'];
  const sourceSha256 = Object.fromEntries(files.map(file => [file,
    crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex')]));
  fs.writeFileSync(artifact('reports/home-motion-settings/character-stability-results.json'),
    JSON.stringify({ scope: 'Actual frontend in desktop Chrome with controlled business APIs; entrance transform, native reload, real chat return button, and native bfcache. Chat-return geometry is relative to the page to preserve normal scroll restoration. Real phone browser chrome changes are not simulated.', results, sourceSha256 }, null, 2) + '\n');
  console.log('PASS ' + results.length + ' character stability groups');
})().catch(error => { console.error(error); process.exitCode = 1; });

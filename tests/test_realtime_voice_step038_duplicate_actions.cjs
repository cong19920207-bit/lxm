// Desktop Chrome acceptance: duplicate retry and cancel during a pending create.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const assets = {
    '/static/js/voice-entry.js': 'frontend/static/js/voice-entry.js',
    '/static/js/voice-playback.js': 'frontend/static/js/voice-playback.js',
    '/static/js/voice-audio-transport.js': 'frontend/static/js/voice-audio-transport.js',
    '/static/js/voice-microphone-worklet.js': 'frontend/static/js/voice-microphone-worklet.js',
    '/static/css/voice-entry.css': 'frontend/static/css/voice-entry.css',
  };
  const server = http.createServer((req, res) => {
    if (assets[req.url]) {
      res.setHeader('Content-Type', req.url.endsWith('.css') ? 'text/css' : 'text/javascript');
      res.end(fs.readFileSync(assets[req.url]));
      return;
    }
    res.setHeader('Content-Type', 'text/html');
    res.end('<meta charset="utf-8"><link rel="stylesheet" href="/static/css/voice-entry.css">' +
      '<button onclick="VoiceEntry.begin()">发起通话</button>' +
      '<script src="/static/js/voice-playback.js"></script>' +
      '<script src="/static/js/voice-audio-transport.js"></script>' +
      '<script src="/static/js/voice-entry.js"></script>');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({channel: 'chrome', headless: true});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      navigator.permissions.query = async () => ({state: 'granted'});
      navigator.mediaDevices.getUserMedia = async () => {
        const context = new AudioContext();
        await context.resume();
        const oscillator = context.createOscillator();
        const destination = context.createMediaStreamDestination();
        oscillator.connect(destination);
        oscillator.start();
        destination.stream.getAudioTracks()[0].addEventListener('ended', () => {
          oscillator.stop();
          context.close();
        });
        return destination.stream;
      };
    });
    let creates = 0, ends = 0, releaseCreate, secondStarted;
    const pendingCreate = new Promise(resolve => { releaseCreate = resolve; });
    const secondRequest = new Promise(resolve => { secondStarted = resolve; });
    const keys = [];
    await page.route('**/api/voice/**', async route => {
      const request = route.request();
      if (request.url().endsWith('/calls') && request.method() === 'POST') {
        creates++;
        keys.push(request.headers()['idempotency-key']);
        if (creates === 1) return route.abort('failed');
        if (creates === 2) {
          secondStarted();
          await pendingCreate;
          return route.fulfill({json: {code: 0, data: {
            call_id: '11111111-1111-4111-8111-111111111111', call_ticket: 'controlled-ticket',
          }}});
        }
        throw new Error('duplicate create request');
      }
      if (request.url().endsWith('/end')) {
        ends++;
        return route.fulfill({json: {code: 0, data: {changed: ends === 1}}});
      }
      return route.fulfill({json: {code: 0, data: {}}});
    });
    await page.goto('http://127.0.0.1:' + server.address().port);
    await page.getByRole('button', {name: '发起通话'}).click();
    await page.getByRole('button', {name: '重新检查'}).waitFor();
    await page.evaluate(() => {
      const retry = document.querySelector('.voice-entry-primary').onclick;
      retry(); retry(); retry();
    });
    await secondRequest;
    assert.equal(creates, 2);
    assert.equal(keys[0], keys[1], 'network retry must retain the idempotency key');
    await page.getByRole('button', {name: '取消'}).waitFor();
    await page.evaluate(() => {
      const cancel = document.querySelector('.voice-entry-primary').onclick;
      cancel(); cancel();
    });
    releaseCreate();
    await page.waitForFunction(() => document.querySelector('.voice-entry')?.hidden === true);
    await page.waitForTimeout(50);
    assert.equal(creates, 2);
    assert.equal(ends, 1, 'pending created call must be ended exactly once');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: 'passed', scope: 'desktop Chrome controlled retry/cancel', creates, ends, sameKey: true, errors}));
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

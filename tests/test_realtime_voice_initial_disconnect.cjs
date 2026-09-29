// Real browser + rejected WebSocket handshake; the HTTP boundary is isolated.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

const assets = {
  '/static/js/voice-entry.js': process.env.VOICE_ENTRY_SCRIPT || 'frontend/static/js/voice-entry.js',
  '/static/js/voice-playback.js': 'frontend/static/js/voice-playback.js',
  '/static/js/voice-audio-transport.js': 'frontend/static/js/voice-audio-transport.js',
  '/static/js/voice-microphone-worklet.js': 'frontend/static/js/voice-microphone-worklet.js',
  '/static/css/voice-entry.css': 'frontend/static/css/voice-entry.css',
};
const html = '<meta charset="utf-8"><link rel="stylesheet" href="/static/css/voice-entry.css">' +
  '<button onclick="VoiceEntry.begin()">发起通话</button>' +
  '<script src="/static/js/voice-playback.js"></script>' +
  '<script src="/static/js/voice-audio-transport.js"></script>' +
  '<script src="/static/js/voice-entry.js"></script>';

async function fixture(browser, options = {}) {
  const state = {calls: [], ends: [], upgrades: 0, reads: 0, busyBlocks: 0,
    cleanupPending: !!options.cleanupPending, failEnd: !!options.failEnd, failRead: !!options.failRead,
    wrongBaseRequests: 0};
  const json = (res, data, status = 200) => {
    res.writeHead(status, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({code: status === 200 ? 0 : status, data}));
  };
  const server = http.createServer(async (req, res) => {
    if (assets[req.url]) {
      res.setHeader('Content-Type', req.url.endsWith('.css') ? 'text/css' : 'text/javascript');
      res.end(fs.readFileSync(assets[req.url]));
      return;
    }
    if (req.url === '/api/voice/calls' && req.method === 'POST') {
      if (state.calls.some(call => ['deciding', 'ringing', 'connected', 'reconnecting'].includes(call.status))) {
        state.busyBlocks++;
        return json(res, {block_reason: 'user_busy'}, 409);
      }
      const call = {call_id: '11111111-1111-4111-8111-' + String(state.calls.length + 1).padStart(12, '0'),
        status: options.initialStatus || 'deciding', has_connected: options.initialStatus === 'connected',
        duration_seconds: 0, end_reason: null, end_message: '暂时无法接通', show_end_page: true};
      state.calls.push(call);
      return json(res, {...call, call_ticket: 'controlled-ticket'});
    }
    const requestUrl = new URL(req.url, 'http://localhost');
    const match = requestUrl.pathname.match(/^\/api\/voice\/calls\/([^/]+)(\/end|\/reconnect)?$/);
    if (match) {
      const call = state.calls.find(item => item.call_id === match[1]);
      if (!call) return json(res, {}, 404);
      if (match[2] === '/end' && req.method === 'POST') {
        state.ends.push(call.call_id);
        if (options.connectBeforeEnd) {
          call.status = 'connected'; call.has_connected = true;
          if (requestUrl.searchParams.get('only_if_unconnected') === 'true') return json(res, {}, 409);
        }
        if (options.waitEnd) await options.waitEnd;
        if (state.failEnd) return json(res, {}, 503);
        call.status = 'cancelled'; call.end_reason = 'user_cancel'; call.show_end_page = false;
        return json(res, {call_id: call.call_id, changed: true, cleanup_pending: state.cleanupPending});
      }
      if (match[2] === '/reconnect') return json(res, {call_id: call.call_id, call_ticket: 'reconnect-ticket'});
      state.reads++;
      if (state.failRead) return json(res, {}, 503);
      return json(res, call);
    }
    res.setHeader('Content-Type', 'text/html');
    res.end(html);
  });
  server.on('upgrade', (req, socket) => {
    state.upgrades++;
    socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const context = await browser.newContext({permissions: ['microphone']});
  const page = await context.newPage();
  if (options.legacyLocalBase) {
    await page.addInitScript(() => { window.API_BASE = 'http://localhost:8000'; });
    await page.route('http://localhost:8000/**', route => { state.wrongBaseRequests++; return route.abort(); });
  }
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.setDefaultTimeout(3500);
  await page.goto('http://' + (options.legacyLocalBase ? 'localhost' : '127.0.0.1') + ':' + server.address().port);
  return {state, page, errors,
    async close() { await context.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }};
}

const primary = page => page.locator('.voice-entry-primary');
const description = page => page.locator('.voice-entry-description');
async function start(page) { await page.getByRole('button', {name: '发起通话', exact: true}).click(); }
async function retryReady(page) {
  await page.waitForFunction(() => document.querySelector('.voice-entry-primary')?.textContent === '重新尝试');
}
async function pending(page) {
  await page.waitForFunction(() => document.querySelector('.voice-entry-primary')?.textContent === '重新检查');
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true,
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']});
  const passed = [], failures = [];
  async function check(name, options, run) {
    const f = await fixture(browser, options);
    try { await run(f); assert.deepEqual(f.errors, []); passed.push(name); }
    catch (error) { failures.push({name, message: error.message, state: f.state}); }
    finally { await f.close(); }
  }
  try {
    await check('same-site voice follows the page port despite legacy localhost API default', {legacyLocalBase: true}, async ({page, state}) => {
      await start(page);
      await retryReady(page);
      assert.equal(state.wrongBaseRequests, 0);
      assert.equal(state.upgrades, 1);
      assert.equal(state.calls[0].status, 'cancelled');
    });
    await check('rejected handshake ends its call and permits a fresh attempt', {}, async ({page, state}) => {
      await start(page);
      await retryReady(page);
      assert.equal(state.upgrades, 1);
      assert.deepEqual(state.ends, [state.calls[0].call_id]);
      assert.equal(state.calls[0].status, 'cancelled');
      assert.doesNotMatch(await description(page).innerText(), /恢复网络/);
      await primary(page).click();
      await retryReady(page);
      assert.equal(state.calls.length, 2);
      assert.deepEqual(state.ends, state.calls.map(call => call.call_id));
      assert.equal(state.busyBlocks, 0);
    });
    await check('failed cleanup retains the same target and blocks duplicate creates', {failEnd: true}, async ({page, state}) => {
      await start(page);
      await pending(page);
      assert.equal(state.ends.length, 1);
      assert.equal(state.calls[0].status, 'deciding');
      await page.evaluate(() => VoiceEntry.begin());
      assert.equal(state.calls.length, 1);
      state.failEnd = false;
      await page.evaluate(() => { const check = document.querySelector('.voice-entry-primary').onclick; check(); check(); check(); });
      await retryReady(page);
      assert.deepEqual(state.ends, [state.calls[0].call_id, state.calls[0].call_id]);
      assert.equal(state.calls.length, 1);
    });
    await check('pending Redis cleanup is confirmed before retry', {cleanupPending: true}, async ({page, state}) => {
      await start(page);
      await pending(page);
      assert.equal(state.ends.length, 1);
      assert.equal(state.calls[0].status, 'cancelled');
      state.cleanupPending = false;
      await primary(page).click();
      await retryReady(page);
      assert.equal(state.ends.length, 2);
      assert.equal(state.calls.length, 1);
    });
    await check('unavailable status does not guess the call state', {failRead: true}, async ({page, state}) => {
      await start(page);
      await pending(page);
      assert.equal(state.ends.length, 0);
      assert.doesNotMatch(await description(page).innerText(), /恢复网络/);
      state.failRead = false;
      await primary(page).click();
      await retryReady(page);
      assert.equal(state.ends.length, 1);
    });
    await check('an already connected server call is not automatically ended', {initialStatus: 'connected'}, async ({page, state}) => {
      await start(page);
      await pending(page);
      assert.equal(state.ends.length, 0);
      await page.evaluate(() => VoiceEntry.begin());
      assert.equal(state.busyBlocks, 0);
      assert.equal(state.calls.length, 1);
    });
    await check('an unconnected ringing attempt is cleaned up', {initialStatus: 'ringing'}, async ({page, state}) => {
      await start(page);
      await retryReady(page);
      assert.equal(state.calls[0].status, 'cancelled');
      assert.deepEqual(state.ends, [state.calls[0].call_id]);
    });
    await check('connection winning cleanup race remains active', {initialStatus: 'ringing', connectBeforeEnd: true}, async ({page, state}) => {
      await start(page);
      await pending(page);
      assert.equal(state.calls[0].status, 'connected');
      assert.equal(state.ends.length, 1);
      await primary(page).click();
      await pending(page);
      assert.equal(state.ends.length, 1);
      assert.equal(state.calls.length, 1);
      state.calls[0].status = 'ended';
      await primary(page).click();
      await page.waitForFunction(() => document.querySelector('.voice-entry h1')?.textContent === '通话已结束');
      assert.equal(state.ends.length, 1);
    });
    let releaseEnd;
    const waitEnd = new Promise(resolve => { releaseEnd = resolve; });
    await check('late cleanup cannot reopen a closed call panel', {waitEnd}, async ({page, state}) => {
      try {
        const requested = page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/end'));
        await start(page);
        await requested;
        await page.getByRole('button', {name: '关闭通话', exact: true}).click();
        await page.locator('.voice-entry').waitFor({state: 'hidden'});
        const finished = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/end'));
        releaseEnd();
        await (await finished).finished();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.equal(await page.locator('.voice-entry').isVisible(), false);
        assert.equal(state.calls.length, 1);
      } finally { releaseEnd(); }
    });
    await check('connected socket loss retains the reconnect flow', {}, async ({page, state}) => {
      let original, reconnected = false;
      await page.routeWebSocket(/\/stream$/, ws => {
        original = ws;
        state.calls[0].status = 'connected'; state.calls[0].has_connected = true;
        ws.send(JSON.stringify({v: 1, type: 'state', status: 'connected', reconnect_timeout_ms: 5000}));
      });
      await page.routeWebSocket(/\/reconnect-stream$/, ws => {
        reconnected = true;
        ws.send(JSON.stringify({v: 1, type: 'state', status: 'connected', reconnect_timeout_ms: 5000}));
      });
      await page.reload();
      await start(page);
      await page.waitForFunction(() => document.querySelector('.voice-entry')?.dataset.callState === 'listening');
      state.calls[0].status = 'reconnecting';
      await original.close({code: 1011, reason: 'controlled disconnect'});
      await page.waitForFunction(() => document.querySelector('.voice-entry')?.dataset.callState === 'listening');
      assert.equal(reconnected, true);
      assert.equal(state.ends.length, 0);
      assert.equal(state.calls.length, 1);
    });
  } finally { await browser.close(); }
  console.log(JSON.stringify({passed, failures}, null, 2));
  assert.equal(failures.length, 0, 'initial connection recovery scenarios failed');
})().catch(error => { console.error(error); process.exitCode = 1; });

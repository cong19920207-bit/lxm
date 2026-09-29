// Controlled transport regressions. Does not claim real microphone/device coverage.
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('frontend/static/js/voice-entry.js', 'utf8');
const tick = () => new Promise(setImmediate);
const ok = data => ({status: 200, ok: true, json: async () => ({code: 0, data})});
const terminal = (status = 'ended') => ({status, has_connected: status === 'ended', duration_seconds: 9, end_message: '结果已确认'});

function harness(handler) {
  const nodes = new Map(), requests = [], sockets = [], tracks = [], storage = new Map();
  const node = () => ({hidden: false, dataset: {}, appendChild() {}, setAttribute() {}, removeAttribute() {},
    addEventListener() {}, focus() {}, classList: {add() {}, remove() {}, toggle() {}, contains: () => false},
    querySelector(key) { if (!nodes.has(key)) nodes.set(key, node()); return nodes.get(key); }, querySelectorAll: () => []});
  let counter = 0;
  const context = {console, URL, performance, setTimeout, clearTimeout, setInterval: () => ++counter, clearInterval() {},
    ResizeObserver: class {observe() {}}, CustomEvent: class {}, location: {origin: 'https://test.example'},
    document: {createElement: node, body: {appendChild() {}}, activeElement: node()},
    localStorage: {getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v)},
    crypto: {randomUUID: () => String(++counter).padStart(36, '0')},
    navigator: {userAgent: 'Chrome', permissions: {async query() {return {state: 'granted'};}},
      mediaDevices: {async getUserMedia() {const track = {stop() {this.stopped = true;}}; tracks.push(track); return {getTracks: () => [track]};}}},
    fetch: async (url, options) => {requests.push({url, ...options}); return handler(url, options, requests);},
  };
  context.window = context; context.isSecureContext = true;
  context.AudioContext = class {constructor() {this.audioWorklet = {};} async resume() {} async close() {}};
  context.AudioWorkletNode = class {};
  context.VoiceAudioTransport = class {async start() {} frame() {} pause() {} resumeTransport() {} async close() {} supportsOutputSelection() {return false;}};
  context.addEventListener = context.dispatchEvent = () => {};
  context.WebSocket = class {static OPEN = 1; constructor(url) {this.url = String(url); this.readyState = 1; sockets.push(this);} send() {} close() {this.readyState = 3;}};
  vm.runInNewContext(source, context);
  return {begin: () => context.VoiceEntry.begin(), nodes, requests, sockets, tracks,
    primary: () => nodes.get('.voice-entry-primary').onclick(),
    hangup: () => nodes.get('.voice-call-hangup').onclick()};
}

(async () => {
  for (const state of ['ended', 'failed', 'missed', 'cancelled']) {
    const h = harness(url => url === '/api/voice/calls'
      ? ok({call_id: 'original', call_ticket: null, status: state}) : ok(terminal(state)));
    await h.begin(); await tick();
    assert.equal(h.sockets.length, 0);
    assert.equal(h.requests.filter(r => r.url === '/api/voice/calls/original').length, 1);
    assert.notEqual(h.nodes.get('h1').textContent, '你已有一通进行中的通话');
    const key = h.requests[0].headers['Idempotency-Key'];
    await h.begin(); await tick();
    assert.notEqual(h.requests.filter(r => r.url === '/api/voice/calls').at(-1).headers['Idempotency-Key'], key);
    assert.equal(h.requests.filter(r => r.url.includes('/end')).length, 0);
  }

  for (const state of ['connected', 'ending']) {
    const h = harness(url => url === '/api/voice/calls' ? ok({call_id: 'original', call_ticket: null}) : ok({status: state, has_connected: true}));
    await h.begin(); await tick(); await h.primary(); await h.begin();
    assert.equal(h.requests.filter(r => r.url === '/api/voice/calls').length, 1);
    assert.equal(h.requests.filter(r => r.url.includes('/end')).length, 0);
    assert.equal(h.nodes.get('.voice-entry-primary').textContent, '重新检查');
  }

  const reconnect = harness(url => url === '/api/voice/calls' ? ok({call_id: 'original', call_ticket: null})
    : url.endsWith('/reconnect') ? ok({call_id: 'original', call_ticket: 'fresh'}) : ok({status: 'reconnecting', has_connected: true}));
  await reconnect.begin(); await tick();
  assert.equal(reconnect.sockets.length, 1);
  assert.match(reconnect.sockets[0].url, /original\/reconnect-stream$/);

  let state = 'ringing', pending = true;
  const cleanup = harness(url => {
    if (url === '/api/voice/calls') return ok({call_id: 'original', call_ticket: null});
    if (url.includes('/end?only_if_unconnected=true')) {state = 'cancelled'; return ok({cleanup_pending: pending});}
    return ok({...terminal(state), has_connected: false});
  });
  await cleanup.begin(); await tick(); await cleanup.begin();
  assert.equal(cleanup.requests.filter(r => r.url === '/api/voice/calls').length, 1);
  assert.equal(cleanup.nodes.get('.voice-entry-primary').textContent, '重新检查');
  pending = false; await cleanup.primary();
  assert.equal(cleanup.nodes.get('.voice-entry-primary').textContent, '重新尝试');
  const originalKey = cleanup.requests[0].headers['Idempotency-Key'];
  await cleanup.primary();
  assert.notEqual(cleanup.requests.filter(r => r.url === '/api/voice/calls').at(-1).headers['Idempotency-Key'], originalKey);

  let won = false;
  const race = harness(url => {
    if (url === '/api/voice/calls') return ok({call_id: 'original', call_ticket: null});
    if (url.includes('/end?')) {won = true; return {status: 409, ok: false, json: async () => ({detail: 'state changed'})};}
    return ok({status: won ? 'connected' : 'ringing', has_connected: won});
  });
  await race.begin(); await tick(); await race.primary();
  assert.equal(race.requests.filter(r => r.url.endsWith('/end')).length, 0);
  assert.equal(race.requests.filter(r => r.url.includes('/end?')).length, 1);
  assert.equal(race.requests.filter(r => r.url === '/api/voice/calls').length, 1);

  let offline = true;
  const network = harness(url => {
    if (offline) {offline = false; throw new Error('lost create response');}
    return url === '/api/voice/calls' ? ok({call_id: 'original', call_ticket: null}) : ok(terminal());
  });
  await network.begin(); await network.primary(); await tick();
  assert.equal(network.requests[0].headers['Idempotency-Key'], network.requests[1].headers['Idempotency-Key']);

  let hangingPending = true;
  const hanging = harness(url => url === '/api/voice/calls' ? ok({call_id: 'original', call_ticket: 'ticket'})
    : url.endsWith('/end') ? ok({cleanup_pending: hangingPending}) : ok(terminal()));
  await hanging.begin(); await hanging.hangup();
  hanging.sockets[0].onmessage({data: JSON.stringify({v: 1, type: 'state', status: 'ended'})});
  await tick(); await hanging.begin();
  assert.equal(hanging.nodes.get('.voice-entry-primary').textContent, '重新检查');
  assert.equal(hanging.requests.filter(r => r.url === '/api/voice/calls').length, 1);
  hangingPending = false; await hanging.primary();
  assert.equal(hanging.nodes.get('h1').textContent, '通话已结束');
  console.log('PASS: replay states, fixed-call cleanup, connection race, network idempotency and pending hangup');
})().catch(error => {console.error(error); process.exitCode = 1;});

// Production entry script; controlled DOM/media/HTTP/socket for deterministic races.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/static/js/voice-entry.js', 'utf8');
const flush = async () => { await new Promise(setImmediate); await new Promise(setImmediate); };
const ok = data => ({status:200, ok:true, json:async () => ({code:0, data})});
const result = (id = 'original', status = 'ended') => ({call_id:id, status,
  end_reason:status === 'failed' ? 'provider_error' : status === 'ended' ? 'user_hangup' : null,
  has_connected:status === 'ended', duration_seconds:status === 'ended' ? 73 : 0,
  end_message:status === 'missed' ? '她现在可能不方便' : '已确认结果', show_end_page:status !== 'cancelled'});
const deferred = () => { let resolve; const promise = new Promise(r => {resolve = r;}); return {promise, resolve}; };

function harness(read, create = () => ok({call_id:'original', call_ticket:'ticket'})) {
  const nodes = new Map(), tracks = [], sockets = [], requests = [], events = new Map(), intervals = new Set();
  let seq = 0, panel, audioCloses = 0, logins = 0;
  const document = {body:{appendChild() {}}, activeElement:null};
  const node = () => {
    const classes = new Set();
    return {hidden:false, disabled:false, dataset:{}, style:{setProperty() {}}, appendChild() {},
      setAttribute() {}, removeAttribute() {}, addEventListener() {},
      focus() {document.activeElement = this;}, getBoundingClientRect() {return {height:0};},
      classList:{add:k=>classes.add(k), remove:k=>classes.delete(k), toggle() {}, contains:k=>classes.has(k)},
      querySelector(key) {if (!nodes.has(key)) nodes.set(key, node()); return nodes.get(key);}, querySelectorAll:() => []};
  };
  const launcher = node(); document.activeElement = launcher;
  document.createElement = tag => {const value = node(); if (tag === 'section') panel = value; return value;};
  const context = {console, document, URL, performance, setTimeout, clearTimeout,
    setInterval:() => {const id = ++seq; intervals.add(id); return id;}, clearInterval:id=>intervals.delete(id),
    ResizeObserver:class {observe() {}}, CustomEvent:class {},
    location:{origin:'https://test.example', pathname:'/pages/index.html'},
    localStorage:{getItem:() => '', setItem() {}}, crypto:{randomUUID:() => String(++seq).padStart(36,'0')},
    navigator:{userAgent:'Chrome', permissions:{query:async () => ({state:'granted'})},
      mediaDevices:{getUserMedia:async () => {const t={stopped:false,stop(){this.stopped=true;}}; tracks.push(t); return {getTracks:()=>[t]};}}},
    fetch:async (url, options) => {
      requests.push({url, ...options});
      if (url === '/api/voice/calls') return create();
      if (url.endsWith('/end')) return ok({cleanup_pending:false});
      return read(url, options);
    },
    openHomeLoginModal:() => logins++,
  };
  context.window = context; context.isSecureContext = true;
  context.addEventListener = (name, callback) => events.set(name, callback); context.dispatchEvent = () => {};
  context.AudioWorkletNode = class {};
  context.AudioContext = class {constructor(){this.audioWorklet={};} async resume(){} async close(){}};
  context.VoiceAudioTransport = class {async start(){} resumeTransport(){} pause(){} frame(){}
    async close(){audioCloses++;} supportsOutputSelection(){return false;}};
  context.WebSocket = class {static OPEN=1; constructor(){this.readyState=1;sockets.push(this);queueMicrotask(()=>this.onopen?.());}
    send(){} close(){this.readyState=3;queueMicrotask(()=>this.onclose?.());}};
  vm.runInNewContext(source, context);
  return {context, nodes, tracks, sockets, requests, intervals, launcher, events,
    panel:()=>panel, audioCloses:()=>audioCloses, logins:()=>logins,
    begin:()=>context.VoiceEntry.begin(),
    primary:()=>nodes.get('.voice-entry-primary').onclick(),
    secondary:()=>nodes.get('.voice-entry-secondary').onclick(),
    close:()=>nodes.get('.voice-entry-close').onclick(),
    async frame(status, index=sockets.length-1){sockets[index].onmessage({data:JSON.stringify({v:1,type:'state',status,reconnect_timeout_ms:5000})});await flush();},
  };
}

const faults = {
  http503:()=>({status:503,ok:false,json:async()=>({code:503})}),
  nonterminal:()=>ok({...result(),status:'ending'}),
  network:()=>{throw new Error('synthetic network error');},
  invalid_json:()=>({status:200,ok:true,json:async()=>{throw new SyntaxError('synthetic JSON');}}),
  business_error:()=>({status:200,ok:true,json:async()=>({code:500,data:result()})}),
  missing_data:()=>ok(null),
};
for (const [name, fault] of Object.entries(faults)) {
  test('R06 terminal GET '+name+' remains retryable without another call or end', async () => {
    let unavailable=true;
    const h=harness(()=>unavailable?fault():ok(result()));
    await h.begin();await h.frame('ringing');await h.frame('ended');
    assert.equal(h.nodes.get('h1').textContent,'正在确认通话结果');
    assert.equal(h.nodes.get('.voice-entry-primary').textContent,'重新检查');
    assert.equal(h.tracks[0].stopped,true);assert.equal(h.audioCloses(),1);assert.equal(h.intervals.size,0);
    await h.begin();assert.equal(h.requests.filter(r=>r.url==='/api/voice/calls').length,1);
    unavailable=false;await h.primary();await flush();
    assert.equal(h.nodes.get('h1').textContent,'通话已结束');
    assert.equal(h.nodes.get('.voice-call-clock').textContent,'01:13');
    assert.equal(h.sockets.length,1);assert.equal(h.requests.filter(r=>r.method==='POST').length,1);
    assert.equal(h.requests.filter(r=>r.url==='/api/voice/calls/original').length,2);
  });
}

test('R06 pending terminal query releases media immediately and ignores duplicate frames/clicks', async () => {
  const gate=deferred();let reads=0;
  const h=harness(()=>{reads++;return gate.promise;});
  await h.begin();await h.frame('ringing');await h.frame('ended');
  assert.equal(h.tracks[0].stopped,true);assert.equal(h.sockets[0].readyState,3);
  assert.equal(h.intervals.size,0);assert.equal(h.nodes.get('.voice-call-clock').hidden,true);
  assert.equal(h.nodes.get('.voice-call-controls').hidden,true);
  await h.frame('ended',0);h.primary();h.primary();await flush();assert.equal(reads,1);
  gate.resolve(ok(result()));await flush();
  assert.equal(h.nodes.get('h1').textContent,'通话已结束');
  assert.equal(h.requests.filter(r=>r.method==='POST').length,1);
});

for(const exit of ['close','return','pagehide']) {
  test('R06 '+exit+' during terminal query releases UI without posting end',async()=>{
    const gate=deferred(),h=harness(()=>gate.promise);
    await h.begin();await h.frame('ended');
    if(exit==='close')h.close();else if(exit==='return')h.secondary();else h.events.get('pagehide')();
    gate.resolve(ok(result()));await flush();
    assert.equal(h.requests.filter(r=>r.url.endsWith('/end')).length,0);
    assert.notEqual(h.nodes.get('h1').textContent,'通话已结束');
    if(exit==='return')assert.equal(h.context.location.href,'/pages/chat.html');
    else if(exit==='close')assert.equal(h.panel().hidden,true);
  });
}

for(const oldResponse of ['success','unauthorized','invalid_json']) {
  for(const sameId of [false,true]) {
    test(`R06 stale ${oldResponse} cannot alter a new attempt (same ID: ${sameId})`,async()=>{
      const gate=deferred();let creates=0;
      const h=harness(()=>gate.promise,()=>ok({call_id:++creates===1||sameId?'original':'next',call_ticket:'ticket'}));
      await h.begin();await h.frame('ended');h.close();await h.begin();await h.frame('ringing');
      gate.resolve(oldResponse==='success'?ok(result()):oldResponse==='invalid_json'?faults.invalid_json():
        {status:401,ok:false,json:async()=>({detail:'expired'})});
      await flush();
      assert.equal(h.nodes.get('h1').textContent,'正在等待她接听');
      assert.equal(h.tracks[1].stopped,false);assert.equal(h.sockets[1].readyState,1);
      assert.equal(h.logins(),0);assert.equal(h.requests.filter(r=>r.url.endsWith('/end')).length,0);
    });
  }
}

test('R06 current unauthorized result keeps the existing login flow',async()=>{
  const h=harness(()=>({status:401,ok:false,json:async()=>({detail:'expired'})}));
  await h.begin();await h.frame('ended');
  assert.equal(h.logins(),1);assert.equal(h.panel().hidden,true);
  assert.equal(h.requests.filter(r=>r.url.endsWith('/end')).length,0);
});

for(const action of ['chat','source']) {
  test('R07 quota action '+action+' exits without redialling',async()=>{
    const h=harness(()=>{throw new Error('unexpected read');},()=>({status:409,ok:false,
      json:async()=>({code:409,data:{block_reason:'quota_empty'}})}));
    await h.begin();
    assert.equal(h.nodes.get('.voice-entry-primary').textContent,'回聊天找她');
    assert.equal(h.nodes.get('.voice-entry-secondary').textContent,'稍后再说');
    if(action==='chat'){h.primary();h.primary();assert.equal(h.context.location.href,'/pages/chat.html');}
    else{h.secondary();h.secondary();assert.equal(h.panel().hidden,true);assert.equal(h.context.document.activeElement,h.launcher);}
    assert.equal(h.requests.length,1);assert.equal(h.sockets.length,0);assert.equal(h.tracks[0].stopped,true);
  });
}

test('R08 missed offers return only and never shows duration',async()=>{
  const h=harness(()=>ok(result('original','missed')));
  await h.begin();await h.frame('missed');
  assert.equal(h.nodes.get('.voice-entry-description').textContent,'她现在可能不方便');
  assert.equal(h.nodes.get('.voice-entry-secondary').hidden,true);
  assert.equal(h.nodes.get('.voice-call-clock').hidden,true);
  h.primary();assert.equal(h.context.location.href,'/pages/chat.html');
  assert.equal(h.requests.filter(r=>r.method==='POST').length,1);
});

test('R08 preconnection failure can start a new checked attempt with a new key',async()=>{
  const h=harness(()=>ok(result('original','failed')));
  await h.begin();await h.frame('failed');
  assert.equal(h.nodes.get('.voice-entry-secondary').hidden,false);
  assert.equal(h.nodes.get('.voice-entry-secondary').textContent,'重新尝试');
  await h.secondary();
  const creates=h.requests.filter(r=>r.url==='/api/voice/calls');
  assert.equal(creates.length,2);assert.notEqual(creates[0].headers['Idempotency-Key'],creates[1].headers['Idempotency-Key']);
  assert.equal(h.tracks.length,2);
});

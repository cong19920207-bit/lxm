// State-machine regressions with controlled DOM/media/transport, not device evidence.
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('frontend/static/js/voice-entry.js', 'utf8');
function harness() {
  const nodes = new Map();
  const node = () => ({hidden:false, dataset:{},appendChild(){},classList:{add(){},remove(){},toggle(){},contains(){return false;}},setAttribute(){}, removeAttribute(){}, addEventListener(){}, focus(){},
    querySelector(key){if(!nodes.has(key))nodes.set(key,node());return nodes.get(key);},querySelectorAll(){return []}});
  const pending=[], requests=[], sockets=[], tracks=[];
  const storage=new Map();
  let counter=0;
  const context={console, URL, ResizeObserver:class{observe(){}},setInterval:()=>++counter,clearInterval(){},CustomEvent:class{},
    location:{origin:'https://test.example'},
    document:{createElement:node,body:{appendChild(){}},activeElement:node()},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    crypto:{randomUUID:()=>String(++counter).padStart(36,'0')},
    navigator:{userAgent:'Chrome',permissions:{async query(){return {state:'granted'};}},mediaDevices:{async getUserMedia(){
      const track={stopped:false,stop(){this.stopped=true}};tracks.push(track);return {getTracks:()=>[track]};
    }}},
    fetch:async(url, options)=>{
      if(url.endsWith('/end'))return {status:200,ok:true,json:async()=>({code:0})};
      requests.push(options);return new Promise(resolve=>pending.push(resolve));
    },
  };
  context.window=context;context.isSecureContext=true;context.AudioContext=class{constructor(){this.audioWorklet={};}async resume(){}async close(){}};context.AudioWorkletNode=class{};
  context.VoiceAudioTransport=class{async start(){}frame(){}async close(){}};
  const events = new Map();
  context.addEventListener=(name, handler)=>events.set(name,handler);context.dispatchEvent=()=>{};
  context.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;sockets.push(this)}send(){}close(){this.readyState=3}};
  vm.runInNewContext(source,context);
  return {context,nodes,pending,requests,sockets,tracks,events,
    resolve(){pending.shift()({status:200,ok:true,json:async()=>({code:0,data:{call_id:'call-'+requests.length,call_ticket:'test'}})})},
    close(){nodes.get('.voice-entry-close').onclick()}};
}
(async()=>{
  const h=harness();
  let first=h.context.VoiceEntry.begin();await new Promise(setImmediate);
  h.close();h.resolve();await first;
  let second=h.context.VoiceEntry.begin();await new Promise(setImmediate);
  assert.notEqual(h.requests[0].headers['Idempotency-Key'],h.requests[1].headers['Idempotency-Key']);
  h.resolve();await second;h.close();
  const old=h.sockets[0];
  let third=h.context.VoiceEntry.begin();await new Promise(setImmediate);
  const track=h.tracks.at(-1);old.onclose();old.onopen();
  assert.equal(track.stopped,false);
  await h.context.VoiceEntry.begin();assert.equal(h.requests.length,3);
  h.resolve();await third;
  assert.equal(track.stopped,false);
  h.close();
  const restored=harness();
  restored.context.AudioWorkletNode=null;
  let navigations=0;
  Object.defineProperty(restored.context.location,'href',{set(){navigations++;}});
  await restored.context.VoiceEntry.begin();
  const button=restored.nodes.get('.voice-entry-primary'), go=button.onclick;
  go(); go();
  assert.equal(navigations,1);assert.equal(button.disabled,true);
  await restored.context.VoiceEntry.begin();
  assert.equal(button.disabled,true);
  restored.events.get('pageshow')({persisted:true});
  await restored.context.VoiceEntry.begin();
  assert.equal(button.disabled,false);
  button.onclick();assert.equal(navigations,2);
  console.log(JSON.stringify({passed:3,scope:'controlled lifecycle only',cases:['pending cancel clears completed attempt','stale socket callbacks preserve new attempt','controlled persisted pageshow restores navigation guard']}));
})().catch(error=>{console.error(error);process.exitCode=1});

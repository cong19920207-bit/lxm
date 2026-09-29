const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

function setup(){
  const nodes=[],frames=[];
  const context={currentTime:0,state:'running',destination:{},
    createBuffer:(_channels,size,rate)=>({duration:size/rate,getChannelData:()=>new Float32Array(size)}),
    createBufferSource:()=>{const node={connect(){},disconnect(){},start(at){this.at=at;},stop(){this.onended?.();}};nodes.push(node);return node;},
    async resume(){this.state='running';},async close(){this.state='closed';}};
  const sandbox={window:{},Float32Array,DataView,Uint8Array,Map,Math,Error,
    atob:s=>Buffer.from(s,'base64').toString('binary'),setInterval:()=>1,clearInterval:()=>{}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/static/js/voice-playback.js'),'utf8'),sandbox);
  const output=new sandbox.window.VoicePlaybackOutput({callId:'c1',context,send:f=>frames.push(f)});
  const meta={reply_id:'r1'};
  const feed=(kind,data={})=>output.providerEvent(kind,meta,data);
  const audio=()=>output.enqueue(Buffer.alloc(4800).toString('base64'),meta);
  return {output,context,nodes,frames,meta,feed,audio};
}

test('sentence and full confirmation follow actual source completion, not audio receipt',()=>{
  const s=setup();s.feed('sentence_started',{sentence_id:'s1'});s.audio();
  s.feed('sentence_finished',{sentence_id:'s1'});s.feed('tts_finished');s.feed('text_finished');
  assert.equal(s.frames.length,0);
  s.context.currentTime=.1;s.nodes[0].onended();
  assert.deepEqual(s.frames.map(f=>f.type),['client_sentence_played','client_reply_playback_completed']);
  assert.equal(s.frames[0].sentence_id,'s1');assert.equal(s.frames[1].event_seq,2);
});

test('stopping clears all sources and never converts stop onended into completed ACK',()=>{
  const s=setup();s.audio();s.audio();s.context.currentTime=.05;
  s.output.stop('r1');
  assert.deepEqual(s.frames.map(f=>f.type),['client_barge_in']);
  assert.equal(s.frames[0].played_audio_ms,50);
  s.feed('tts_finished');s.feed('text_finished');s.audio();
  assert.equal(s.frames.length,1);assert.equal(s.nodes.length,2);
});

test('progress is cumulative rendered samples and does not include queued audio',()=>{
  const s=setup();s.audio();s.audio();s.context.currentTime=.025;
  s.output.reportProgress();
  assert.equal(s.frames[0].played_audio_ms,25);
  assert.equal(s.frames[0].call_id,'c1');assert.equal(s.frames[0].reply_id,'r1');
});

test('suspended or closed audio context cannot be reported as fully played',async()=>{
  const s=setup();s.audio();s.feed('tts_finished');s.feed('text_finished');
  s.context.state='suspended';s.context.currentTime=0;s.output.reportProgress();
  assert.equal(s.frames.length,0);
  await s.output.close();assert.equal(s.context.state,'closed');
  assert.equal(s.frames.some(f=>f.type==='client_reply_playback_completed'),false);
});

test('audio-only greeting finishes listening without fabricating full text evidence',()=>{
  const s=setup(),states=[];s.output.onState=state=>states.push(state);
  s.audio();s.feed('tts_finished');assert.equal(s.frames.length,0);
  s.context.currentTime=.1;s.nodes[0].onended();
  assert.equal(s.frames.filter(f=>f.type==='client_audio_playback_completed').length,1);
  assert.equal(s.frames.some(f=>f.type==='client_reply_playback_completed'),false);
  assert.equal(states.at(-1),'listening');
  const before=s.frames.length;s.output.reportProgress();assert.equal(s.frames.length,before);
  s.feed('text_finished');assert.equal(s.frames.filter(f=>f.type==='client_reply_playback_completed').length,1);
});

test('audio-only completion does not turn listening while another reply is queued',()=>{
 const s=setup(),states=[];s.output.onState=x=>states.push(x);s.audio();s.feed('tts_finished');
 s.output.enqueue(Buffer.alloc(4800).toString('base64'),{reply_id:'r2'});
 s.context.currentTime=.1;s.nodes[0].onended();assert.equal(states.includes('listening'),false);
});

test('renderer completion delayed by suspended context is acknowledged after recovery',()=>{
 const s=setup();s.audio();s.feed('tts_finished');s.context.state='suspended';s.nodes[0].onended();
 assert.equal(s.frames.length,0);s.context.state='running';s.context.currentTime=.1;s.output.reportProgress();
 assert.equal(s.frames.filter(f=>f.type==='client_audio_playback_completed').length,1);
});

test('queued replies and unchanged playback never flood progress frames',()=>{
  const s=setup();
  for(let i=0;i<10;i++)s.output.enqueue(Buffer.alloc(48000).toString('base64'),{reply_id:'r'+i});
  s.output.reportProgress();assert.equal(s.frames.length,0);
  for(let i=1;i<=9;i++){s.context.currentTime=i/10;s.output.reportProgress();s.output.reportProgress();}
  const progress=s.frames.filter(f=>f.type==='client_playback_progress');
  assert.equal(progress.length,9);assert.ok(progress.every(f=>f.reply_id==='r0' && f.played_audio_ms>0));
});

const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');
function setup(){let Processor;const packets=[];
  const sandbox={sampleRate:48000,Int16Array,Math,AudioWorkletProcessor:class{constructor(){this.port={postMessage:buffer=>packets.push(new Int16Array(buffer))};}},registerProcessor:(_name,p)=>{Processor=p;}};
  vm.runInNewContext(fs.readFileSync('frontend/static/js/voice-microphone-worklet.js','utf8'),sandbox);
  return {processor:new Processor(),packets};
}
test('real input samples determine 16k PCM packet length, silence is not invented',()=>{
  const {processor,packets}=setup();
  for(let n=0;n<15;n++)processor.process([[new Float32Array(128).fill(.5)]]);
  assert.equal(packets.length,1);assert.equal(packets[0].length,640);
  assert.equal(packets[0][0],16384);
});
test('muting drops capture and clears buffered pre-mute speech',()=>{
  const {processor,packets}=setup();
  processor.process([[new Float32Array(128).fill(.5)]]);
  processor.port.onmessage({data:'muted'});
  for(let n=0;n<15;n++)processor.process([[new Float32Array(128).fill(.5)]]);
  assert.equal(packets.length,0);
  processor.port.onmessage({data:'enabled'});
  for(let n=0;n<15;n++)processor.process([[new Float32Array(128)]]);
  assert.equal(packets.length,1);assert.equal(packets[0].some(v=>v!==0),false);
});

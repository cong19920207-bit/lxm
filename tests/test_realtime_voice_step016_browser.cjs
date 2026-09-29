// Real browser WebAudio renderer with synthetic PCM; not a device/provider test.
const assert=require('node:assert/strict');
const fs=require('node:fs');const http=require('node:http');const path=require('node:path');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
(async()=>{
  const server=http.createServer((req,res)=>{
    const names=['voice-playback.js','voice-audio-transport.js','voice-microphone-worklet.js'];
    const name=names.find(n=>req.url==='/static/js/'+n);
    if(name){res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync(path.join('frontend/static/js',name)));return;}
    res.setHeader('Content-Type','text/html');res.end('<button id="start">Start</button><script src="/static/js/voice-playback.js"></script><script src="/static/js/voice-audio-transport.js"></script>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try{
    browser=await chromium.launch({channel:'chrome',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
    const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port);
    const result=await page.evaluate(async()=>{
      const frames=[];const context=new AudioContext();await context.resume();
      const output=new VoicePlaybackOutput({callId:'c1',context,send:f=>frames.push(f)});
      const audio=btoa('\x01\x01'.repeat(2400));const meta={reply_id:'r1'};
      output.providerEvent('sentence_started',meta,{sentence_id:'s1'});
      output.enqueue(audio,meta);output.providerEvent('sentence_finished',meta,{sentence_id:'s1'});
      output.providerEvent('text_finished',meta);output.providerEvent('tts_finished',meta);
      const before=frames.filter(f=>f.type==='client_reply_playback_completed').length;
      await new Promise(r=>setTimeout(r,350));
      const completed=frames.filter(f=>f.type==='client_reply_playback_completed').length;
      const interrupted={reply_id:'r2'};output.enqueue(btoa('\x01\x01'.repeat(24000)),interrupted);
      await new Promise(r=>setTimeout(r,80));output.stop('r2');
      output.providerEvent('text_finished',interrupted);output.providerEvent('tts_finished',interrupted);
      await new Promise(r=>setTimeout(r,100));
      const stopped=frames.find(f=>f.type==='client_barge_in'&&f.reply_id==='r2');
      const falseComplete=frames.some(f=>f.type==='client_reply_playback_completed'&&f.reply_id==='r2');
      const states=[];output.onState=s=>states.push(s);
      const greeting={reply_id:'greeting'};output.enqueue(audio,greeting);output.providerEvent('tts_finished',greeting);
      const greetingBefore=frames.filter(f=>f.type==='client_audio_playback_completed').length;
      const deadline=performance.now()+3000;
      while (!frames.some(f=>f.type==='client_audio_playback_completed') && performance.now()<deadline) await new Promise(r=>setTimeout(r,25));
      const greetingDone=frames.filter(f=>f.type==='client_audio_playback_completed').length;
      const greetingFull=frames.some(f=>f.type==='client_reply_playback_completed'&&f.reply_id==='greeting');
      const greetingState=states.at(-1);
      await output.close();
      // Real AudioWorklet graph with a synthesized stream, no microphone permission.
      const captureContext=new AudioContext();await captureContext.resume();
      const oscillator=captureContext.createOscillator();const destination=captureContext.createMediaStreamDestination();
      oscillator.connect(destination);oscillator.start();const packets=[];
      const transport=new VoiceAudioTransport({context:captureContext,send:f=>{if(f.type==='audio')packets.push(f);}});
      await transport.start('c2',destination.stream);await new Promise(r=>setTimeout(r,250));
      transport.setMuted(true);await new Promise(r=>setTimeout(r,100));const mutedStart=packets.length;
      await new Promise(r=>setTimeout(r,150));const mutedEnd=packets.length;
      oscillator.stop();await transport.close();destination.stream.getTracks().forEach(t=>t.stop());
      return {before,completed,stopped,falseComplete,greetingBefore,greetingDone,greetingFull,greetingState,closed:context.state,packets:packets.length,
        packetBytes:packets[0]?atob(packets[0].pcm_base64).length:0,mutedStart,mutedEnd,captureClosed:captureContext.state};
    });
    assert.equal(result.greetingBefore,0);assert.equal(result.greetingDone,1);assert.equal(result.greetingFull,false);assert.equal(result.greetingState,'listening');
    assert.equal(result.before,0);assert.equal(result.completed,1);assert.equal(result.falseComplete,false);
    assert.ok(result.stopped.played_audio_ms>0&&result.stopped.played_audio_ms<1000);
    assert.equal(result.closed,'closed');assert.ok(result.packets>0);assert.equal(result.packetBytes,1280);
    assert.equal(result.mutedStart,result.mutedEnd);assert.equal(result.captureClosed,'closed');
    console.log(JSON.stringify({status:'passed',scope:'Chrome real WebAudio/AudioWorklet, synthetic stream and PCM, no real microphone or Provider',...result}));
  }finally{await browser?.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});

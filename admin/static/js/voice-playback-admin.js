/* Request-owned admin playback. Capability results use the original test API; no microphone. */
(() => {
  'use strict';
  const start = document.getElementById('btn-voice-playback');
  const stop = document.getElementById('btn-voice-playback-stop');
  const status = document.getElementById('voice-playback-status');
  if (!start || !stop || !status) return;
  let active = null;
  stop.onclick = () => active?.abort();
  async function run(capabilityKey = null) {
    if (active || !['super_admin','tech_ops'].includes(getAdminRole())) return;
    const isCapability = capabilityKey !== null;
    let resultData = null;
    const controller = new AbortController(); active = controller;
    const token = getAdminToken();
    const headers = {'Authorization':'Bearer '+token,'Content-Type':'application/json',...(isCapability?{'Accept':'application/x-ndjson'}:{})};
    const Audio = window.AudioContext || window.webkitAudioContext;
    let audio = null, reader = null, nextTime = 0, identity = null, bytes = 0, terminal = false, resultSeen = false;
    const sources = new Set(), ended = [];
    const abort = () => {
      controller.abort();
      sources.forEach(source => { try { source.stop(); } catch (_) {} });
    };
    const deadline = setTimeout(abort,50000);
    window.addEventListener('pagehide',abort);
    window.dispatchEvent(new CustomEvent('voice-admin-playback-busy',{detail:true}));
    stop.disabled = false;
    status.textContent = '正在准备短音频…';
    try {
      if (!token || !Audio) throw new Error('浏览器或登录状态不支持播放测试');
      audio = new Audio(); await audio.resume();
      if (audio.state !== 'running') throw new Error('浏览器尚未允许播放音频');
      const response = await fetch(isCapability?'/api/admin/voice/config/test-capability':'/api/admin/voice/config/test-playback',{
        method:'POST',headers,body:isCapability?JSON.stringify({capability_key:capabilityKey}):'{}',signal:controller.signal});
      if (!response.ok || !response.body) throw new Error('播放测试未能开始，请检查权限、草稿配置或服务状态');
      reader = response.body.getReader();
      const decoder = new TextDecoder(); let pending = '';
      async function handle(frame) {
        if (frame.type === 'audio') {
          if (terminal || !frame.test_id || !frame.call_id || !frame.session_id || !frame.reply_id) throw new Error('播放目标不匹配');
          const current = {test_id:frame.test_id,call_id:frame.call_id,session_id:frame.session_id,reply_id:frame.reply_id};
          if (identity && Object.keys(current).some(key=>identity[key]!==current[key])) throw new Error('播放目标发生变化');
          identity = current;
          const raw = atob(frame.pcm_base64);
          if (!raw.length || raw.length%2 || raw.length>1024*1024 || bytes+raw.length>4*1024*1024) throw new Error('音频格式或大小不正确');
          bytes += raw.length;
          const buffer = audio.createBuffer(1,raw.length/2,24000), samples=buffer.getChannelData(0);
          for (let i=0;i<samples.length;i++) {
            let value=raw.charCodeAt(i*2)|(raw.charCodeAt(i*2+1)<<8);
            if (value>=32768) value-=65536;
            samples[i]=value/32768;
          }
          const source = audio.createBufferSource(); source.buffer=buffer; source.connect(audio.destination);
          sources.add(source);
          ended.push(new Promise(resolve=>{source.onended=()=>{sources.delete(source);source.disconnect();resolve();};}));
          nextTime=Math.max(nextTime,audio.currentTime+.025);source.start(nextTime);nextTime+=buffer.duration;
          status.textContent='正在播放…';
        } else if (frame.type === 'playback_end') {
          if (terminal || !identity || frame.audio_bytes!==bytes || Object.keys(identity).some(key=>frame[key]!==identity[key])) throw new Error('播放完成信息不匹配');
          terminal=true;
          await Promise.race([Promise.all(ended),new Promise((_,reject)=>{
            if (controller.signal.aborted) reject(new Error('播放已停止'));
            else controller.signal.addEventListener('abort',()=>reject(new Error('播放已停止')),{once:true});
          })]);
          if (controller.signal.aborted || audio.state!=='running') throw new Error('播放未完成');
          let stopFields={};
          if (frame.stop_after_playback===true) {
            if (!Number.isInteger(frame.played_ms) || frame.played_ms!==Math.floor(bytes/48) || frame.stopped!==true) throw new Error('停止进度不匹配');
            await audio.suspend();
            if (audio.state!=='suspended') throw new Error('播放引擎未停止');
            stopFields={played_ms:frame.played_ms,stopped:true};
          }
          const ack=await fetch('/api/admin/voice/config/test-playback/'+identity.test_id+(frame.stop_after_playback===true?'/stop-ack':'/ack'),{
            method:'POST',headers,signal:controller.signal,
            body:JSON.stringify({call_id:identity.call_id,session_id:identity.session_id,reply_id:identity.reply_id,audio_bytes:bytes,...stopFields})});
          if (!ack.ok) throw new Error('播放确认未被服务端接受');
          status.textContent='播放完成，正在保存确认结果…';
        } else if (frame.type === 'result') {
          resultSeen=true;
          if (isCapability) {
            if (!['passed','failed','error'].includes(frame.status) || (identity && frame.test_id!==identity.test_id)) throw new Error('能力测试结果不匹配');
            const {type,test_id,...data}=frame; resultData=data;
            status.textContent='能力测试结束，结果已记录。';
          } else {
            if (frame.status!=='passed' || !terminal || frame.test_id!==identity?.test_id) throw new Error('播放测试未通过，结果已保留');
            status.textContent='播放确认通过，已记录测试结果。';
          }
        } else throw new Error('未知播放消息');
      }
      while (true) {
        const part=await reader.read();
        if (part.done) break;
        pending+=decoder.decode(part.value,{stream:true});
        if (pending.length>1500000) throw new Error('播放消息过大');
        let newline;
        while ((newline=pending.indexOf('\n'))!==-1) {
          const line=pending.slice(0,newline);pending=pending.slice(newline+1);
          if (line) await handle(JSON.parse(line));
        }
      }
      if (!resultSeen || pending.trim()) throw new Error('播放测试连接未完整结束');
      return isCapability?{code:0,data:resultData}:undefined;
    } catch (error) {
      status.textContent=controller.signal.aborted?'播放测试已停止。':error.message;
      return isCapability?{code:-1,message:status.textContent}:undefined;
    } finally {
      clearTimeout(deadline);window.removeEventListener('pagehide',abort);
      abort();try { await reader?.cancel(); } catch (_) {}
      try { await audio?.close(); } catch (_) {}
      active=null;stop.disabled=true;
      window.dispatchEvent(new CustomEvent('voice-admin-playback-busy',{detail:false}));
    }
  }
  start.onclick = () => run();
  window.runVoiceCapabilityPlayback = key => run(key);
})();

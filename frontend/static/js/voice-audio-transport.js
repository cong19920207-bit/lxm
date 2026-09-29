(() => {
  'use strict';
  class VoiceAudioTransport {
    constructor({context, send, onState = () => {}}) {
      this.context = context; this.send = send; this.onState = onState; this.closed = false; this.started = false; this.paused = false;
      this.playback = null; this.microphone = null; this.source = null;
      this.track = null; this.muted = false; this.reportMic = () => {};
    }
    async start(callId, stream) {
      if (this.closed || this.started) return;
      this.started = true;
      await this.context.audioWorklet.addModule('/static/js/voice-microphone-worklet.js');
      if (this.closed) return;
      this.playback = new window.VoicePlaybackOutput({callId, context: this.context, send: this.send, onState:this.onState});
      this.source = this.context.createMediaStreamSource(stream);
      this.microphone = new AudioWorkletNode(this.context, 'voice-microphone', {numberOfInputs:1,numberOfOutputs:0});
      this.microphone.port.onmessage = event => {
        if (this.closed || this.muted || this.paused) return;
        const bytes = new Uint8Array(event.data);
        let raw = ''; for (const byte of bytes) raw += String.fromCharCode(byte);
        this.send({type:'audio', pcm_base64:btoa(raw)});
      };
      this.source.connect(this.microphone);
      this.track = stream.getAudioTracks()[0];
      this.reportMic = () => {
        if (this.closed) return;
        try { this.send({type:'microphone_state', muted:this.muted,
          available:!!this.track && this.track.readyState === 'live' && !this.track.muted && this.context.state === 'running'}); }
        catch (_) {}
      };
      for (const name of ['mute','unmute','ended']) this.track?.addEventListener(name, this.reportMic);
      this.context.addEventListener('statechange', this.reportMic);
      this.reportMic();
    }
    frame(frame) {
      if (this.closed || !this.playback) return;
      if (frame.type === 'audio') this.playback.enqueue(frame.pcm_base64, frame.metadata);
      if (frame.type === 'provider_event') this.playback.providerEvent(frame.metadata.kind, frame.metadata, frame.data);
      if (frame.type === 'stop_playback') this.playback.stop(frame.reply_id);
    }
    isPlaying() { return this.playback?.isPlaying() || false; }
    supportsOutputSelection() {
      return typeof this.context.setSinkId === 'function' && typeof navigator.mediaDevices?.selectAudioOutput === 'function';
    }
    async selectOutput() {
      if (this.closed || !this.supportsOutputSelection()) throw new Error('请通过设备切换音频输出');
      const device = await navigator.mediaDevices.selectAudioOutput();
      if (this.closed) throw new Error('通话已结束');
      await this.context.setSinkId(device.deviceId);
      if (this.context.sinkId !== device.deviceId) throw new Error('音频输出未改变');
      return device.label || '已选输出';
    }
    pause() {
      this.paused = true;
      if (this.playback) for (const id of this.playback.replies.keys()) this.playback.stop(id, false);
    }
    resumeTransport() { this.paused = false; this.reportMic(); }
    setMuted(muted) {
      if (this.closed || !this.track || this.track.readyState !== 'live') throw new Error('麦克风不可用');
      this.track.enabled = !muted;
      if (this.track.enabled !== !muted) throw new Error('麦克风状态未改变');
      this.muted = muted;
      this.microphone.port.postMessage(muted ? 'muted' : 'enabled');
      this.reportMic();
      return this.muted;
    }
    async close() {
      if (this.closed) return;
      this.closed = true;
      for (const name of ['mute','unmute','ended']) this.track?.removeEventListener(name, this.reportMic);
      this.context.removeEventListener('statechange', this.reportMic);
      this.source?.disconnect(); this.microphone?.disconnect(); this.microphone?.port.close();
      if (this.playback) await this.playback.close();
      else await this.context.close();
    }
  }
  window.VoiceAudioTransport = VoiceAudioTransport;
})();

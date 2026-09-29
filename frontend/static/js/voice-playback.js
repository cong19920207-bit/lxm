/* STEP-016: WebAudio rendering evidence. No transcript or simulated timing. */
(() => {
  'use strict';
  class VoicePlaybackOutput {
    constructor({callId, context, send, onState = () => {}}) {
      this.callId = callId;
      this.context = context;
      this.send = send;
      this.onState = onState;
      this.replies = new Map();
      this.sequence = 0;
      this.nextTime = context.currentTime;
      this.closed = false;
      this.progressTimer = setInterval(() => this.reportProgress(), 100);
    }
    reply(id) {
      if (typeof id !== 'string' || !id) throw new Error('缺少播放归属');
      if (!this.replies.has(id)) {
        this.replies.set(id, {id, chunks: [], sentences: new Map(), totalFrames: 0,
          lastProgressMs: 0, textFinished: false, ttsFinished: false, stopped: false, completed: false, audioCompleted: false});
      }
      return this.replies.get(id);
    }
    emit(reply, type, fields = {}) {
      if (this.closed) return false;
      try {
        this.send({type, call_id: this.callId, reply_id: reply.id, event_seq: ++this.sequence, ...fields});
        return true;
      } catch (_) { return false; }
    }
    enqueue(encoded, metadata) {
      if (this.closed) return;
      const reply = this.reply(metadata.reply_id);
      if (reply.stopped || reply.completed || reply.audioCompleted) return;
      const raw = atob(encoded);
      if (!raw.length || raw.length % 2 || raw.length > 1024 * 1024) throw new Error('无效音频帧');
      const frames = raw.length / 2;
      const buffer = this.context.createBuffer(1, frames, 24000);
      const channel = buffer.getChannelData(0);
      for (let i = 0; i < frames; i++) {
        let value = raw.charCodeAt(i * 2) | (raw.charCodeAt(i * 2 + 1) << 8);
        if (value & 0x8000) value -= 0x10000;
        channel[i] = value / 32768;
      }
      const node = this.context.createBufferSource();
      node.buffer = buffer;
      node.connect(this.context.destination);
      const start = Math.max(this.context.currentTime, this.nextTime);
      const chunk = {node, start, frames, done: false, stopped: false};
      node.onended = () => {
        if (this.closed || reply.stopped || chunk.stopped || chunk.done) return;
        chunk.done = true;
        node.disconnect();
        node.buffer = null;
        this.update(reply);
      };
      node.start(start);
      this.nextTime = start + frames / 24000;
      reply.totalFrames += frames;
      reply.chunks.push(chunk);
    }
    playedFrames(reply) {
      return reply.chunks.reduce((sum, chunk) => sum + (chunk.done ? chunk.frames :
        Math.min(chunk.frames, Math.max(0, Math.floor((this.context.currentTime - chunk.start) * 24000)))), 0);
    }
    providerEvent(kind, metadata, data = {}) {
      if (this.closed || !metadata.reply_id) return;
      const reply = this.reply(metadata.reply_id);
      if (reply.stopped || reply.completed) return;
      if (kind === 'sentence_started' && data.sentence_id) {
        reply.sentences.set(data.sentence_id, {start: reply.totalFrames, end: null, acked: false});
      }
      if (kind === 'sentence_finished' && reply.sentences.has(data.sentence_id)) {
        reply.sentences.get(data.sentence_id).end = reply.totalFrames;
      }
      if (kind === 'text_finished') reply.textFinished = true;
      if (kind === 'tts_finished') reply.ttsFinished = true;
      this.update(reply);
    }
    update(reply) {
      if (this.closed || reply.stopped || reply.completed || this.context.state !== 'running') return;
      // Complete-sentence ACKs use completed renderer callbacks, not arrival
      // time or the number of chunks merely scheduled in the output queue.
      const rendered = reply.chunks.reduce((sum, chunk) => sum + (chunk.done ? chunk.frames : 0), 0);
      for (const [id, sentence] of reply.sentences) {
        if (!sentence.acked && sentence.end !== null && sentence.end > sentence.start && rendered >= sentence.end) {
          sentence.acked = this.emit(reply, 'client_sentence_played', {sentence_id: id});
        }
      }
      if (reply.ttsFinished && reply.totalFrames > 0 && reply.chunks.every(c => c.done)) {
        if (reply.textFinished) {
          reply.completed = this.emit(reply, 'client_reply_playback_completed');
          reply.audioCompleted = reply.completed || reply.audioCompleted;
        } else if (!reply.audioCompleted) {
          // Greeting/bridge audio can finish without a generated-text stream.
          // This report changes listening state, never grants full text evidence.
          reply.audioCompleted = this.emit(reply, 'client_audio_playback_completed',
            {played_audio_ms: Math.floor(reply.totalFrames / 24)});
        }
        const pending = [...this.replies.values()].some(r => !r.stopped && r.chunks.some(c => !c.done));
        if (reply.audioCompleted && !pending) this.onState('listening');
      }
    }
    isPlaying() {
      return this.context.state === 'running' && [...this.replies.values()].some(reply =>
        !reply.stopped && !reply.completed && reply.chunks.some(chunk => !chunk.done &&
          this.context.currentTime >= chunk.start && this.context.currentTime < chunk.start + chunk.frames / 24000));
    }
    reportProgress() {
      if (this.isPlaying()) this.onState('speaking');
      for (const reply of this.replies.values()) {
        this.update(reply); // Retry a completed renderer ACK after context/transport recovery.
        if (!this.closed && !reply.stopped && !reply.completed && !reply.audioCompleted && reply.totalFrames > 0) {
          const played = Math.floor(this.playedFrames(reply) / 24);
          if (played > reply.lastProgressMs && this.emit(reply, 'client_playback_progress', {played_audio_ms: played})) {
            reply.lastProgressMs = played;
          }
        }
      }
    }
    stop(replyId, report = true) {
      const reply = this.replies.get(replyId);
      if (!reply || reply.stopped || reply.completed) return;
      const played = Math.floor(this.playedFrames(reply) / 24);
      reply.stopped = true;
      let stopped = true;
      for (const chunk of reply.chunks) {
        if (chunk.done) continue;
        chunk.stopped = true;
        try { chunk.node.stop(); chunk.node.disconnect(); chunk.node.buffer = null; }
        catch (_) { stopped = false; }
      }
      this.nextTime = Math.max(this.context.currentTime, ...[...this.replies.values()]
        .filter(r => !r.stopped && !r.completed).flatMap(r => r.chunks.filter(c => !c.done).map(c => c.start + c.frames / 24000)));
      if (report && stopped) this.emit(reply, 'client_barge_in', {played_audio_ms: played});
      if (stopped && !this.isPlaying()) this.onState('listening');
      return stopped;
    }
    async resume() {
      await this.context.resume();
      if (this.context.state !== 'running') throw new Error('音频尚未恢复');
      for (const reply of this.replies.values()) this.update(reply);
    }
    async close() {
      if (this.closed) return;
      this.closed = true;
      clearInterval(this.progressTimer);
      for (const id of this.replies.keys()) this.stop(id, false);
      await this.context.close();
      this.replies.clear();
    }
  }
  window.VoicePlaybackOutput = VoicePlaybackOutput;
})();

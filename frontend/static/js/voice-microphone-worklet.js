/* 16 kHz mono PCM, 40 ms transport packets. Never stores recorded audio. */
class VoiceMicrophoneProcessor extends AudioWorkletProcessor {
  constructor() {
    super(); this.enabled = true; this.phase = 0; this.sum = 0; this.count = 0;
    this.packet = new Int16Array(640); this.offset = 0;
    this.port.onmessage = event => {
      this.enabled = event.data === 'enabled';
      this.offset = 0; this.phase = 0; this.sum = 0; this.count = 0;
    };
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!this.enabled || !channel) return true;
    for (const value of channel) {
      this.sum += value; this.count++; this.phase += 16000;
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate;
        this.packet[this.offset++] = Math.round(Math.max(-1, Math.min(1, this.sum / this.count)) * 32767);
        this.sum = 0; this.count = 0;
        if (this.offset === 640) {
          this.port.postMessage(this.packet.buffer, [this.packet.buffer]);
          this.packet = new Int16Array(640); this.offset = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('voice-microphone', VoiceMicrophoneProcessor);

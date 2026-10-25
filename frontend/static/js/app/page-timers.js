export function createPageTimers(context) {
  const releases = new Map();
  const clear = id => { releases.get('timer:' + id)?.(); releases.delete('timer:' + id); };
  const clearFrame = id => { releases.get('frame:' + id)?.(); releases.delete('frame:' + id); };
  const timeout = (callback, ms) => {
    const id = globalThis.setTimeout(() => { clear(id); if (context.valid()) callback(); }, ms);
    releases.set('timer:' + id, context.cleanup(() => globalThis.clearTimeout(id), { kind: 'timer' })); return id;
  };
  const interval = (callback, ms) => {
    const id = globalThis.setInterval(() => { if (context.valid()) callback(); }, ms);
    releases.set('timer:' + id, context.cleanup(() => globalThis.clearInterval(id), { kind: 'timer' })); return id;
  };
  const frame = callback => {
    const id = globalThis.requestAnimationFrame(time => { clearFrame(id); if (context.valid()) callback(time); });
    releases.set('frame:' + id, context.cleanup(() => globalThis.cancelAnimationFrame(id), { kind: 'raf' })); return id;
  };
  context.cleanup(() => releases.clear());
  return { setTimeout: timeout, setInterval: interval, clearTimeout: clear, clearInterval: clear, requestAnimationFrame: frame, cancelAnimationFrame: clearFrame };
}

// An activity remains owned until its actual source and every late resource stop.
export class ActivityLeases {
  constructor({ player, output, later = (...args) => setTimeout(...args), clear = id => clearTimeout(id) }) {
    Object.assign(this, { player, output, later, clear }); this.entries = new Map(); this.revision = 0; this.syncing = false; this.destroyed = false;
    this.unsubscribe = player.subscribe(() => this.synchronize());
  }
  eligible() { const s = this.player.state(); return !s.destroyed && s.intent === 'play' && !s.closed && !s.recoveryRequired && !s.blockers.length; }
  synchronize() {
    if (this.syncing) return; this.syncing = true;
    try {
      const precise = !!this.output.capabilities().preciseVolume;
      const ducked = [...this.entries.values()].some(e => e.kind === 'short');
      this.output.setMultiplier(ducked && precise ? 0.25 : 1, { fade: true });
      for (const entry of this.entries.values()) {
        const block = entry.kind !== 'short' || !precise;
        if (block && !entry.blocked) { entry.blocked = true; this.player.block(entry.key); }
        else if (!block && entry.blocked) { entry.blocked = false; this.player.unblock(entry.key); }
      }
    } finally { this.syncing = false; }
  }
  begin(owner, id, { kind = 'media', audible = true, timeoutMs = 30000, stop, isStopped, resumeAllowed = false } = {}) {
    if (this.destroyed) return null;
    if (!owner?.ownerId || typeof owner.valid !== 'function' || !owner.valid() || !id ||
      !['media', 'recording', 'short'].includes(kind) || !Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new TypeError('Invalid activity owner');
    const ownerKey = owner.ownerId + ':' + id;
    const existing = [...this.entries.values()].find(e => e.ownerKey === ownerKey && !e.closing);
    if (existing) return existing.lease;
    const entry = { ownerKey, kind, key: 'activity:' + crypto.randomUUID(), abort: new AbortController(), closing: false,
      blocked: false, unknown: false, resources: new Set(), timer: null, stopping: null, inert: kind === 'media' && !audible };
    const valid = () => !entry.closing && owner.valid() && !entry.abort.signal.aborted;
    const closeResource = async record => {
      if (record.closed) return true;
      if (record.closing) return record.closing;
      record.closing = Promise.resolve().then(() => record.dispose(record.value)).then(result => {
        record.closed = result === true || result?.status === 'closed';
        if (!record.closed) entry.unknown = true;
        return record.closed;
      }, () => { entry.unknown = true; return false; }).finally(() => { record.closing = null; });
      return record.closing;
    };
    const adopt = (promise, dispose) => {
      if (typeof dispose !== 'function') throw new TypeError('Late resource disposer required');
      const record = { dispose, value: undefined, settled: false, closed: false, closing: null };
      entry.resources.add(record);
      record.promise = Promise.resolve(promise).then(async value => {
        record.value = value; record.settled = true;
        if (!valid()) { await closeResource(record); return undefined; }
        return value;
      }, error => { record.settled = record.closed = true; throw error; });
      return record.promise;
    };
    const finish = ({ resumeAllowed: explicitResume = resumeAllowed } = {}) => {
      if (entry.stopping) return entry.stopping;
      if (!this.entries.has(entry.key) && !entry.inert) return Promise.resolve(true);
      entry.closing = true; entry.abort.abort(); this.clear(entry.timer); entry.unknown = false;
      // Invoke the source stop synchronously before waiting on any late acquisition.
      let stopped; try { stopped = stop?.(); } catch (_) { entry.unknown = true; }
      const task = (async () => {
        let result; try { result = await stopped; } catch (_) { entry.unknown = true; }
        await Promise.all([...entry.resources].map(async record => {
          try { await record.promise; } catch (_) { /* rejected acquisition produced no resource */ }
          if (!record.closed) await closeResource(record);
        }));
        let sourceStopped = entry.inert || result === true || result?.status === 'closed';
        try { if (isStopped) sourceStopped = isStopped() === true; } catch (_) { sourceStopped = false; }
        if (!stop && !isStopped && entry.resources.size) sourceStopped = [...entry.resources].every(r => r.closed);
        if (!sourceStopped || entry.unknown) return false;
        if (!this.entries.delete(entry.key) && !entry.inert) return true;
        this.revision++;
        if (entry.kind !== 'short' && explicitResume !== true && !entry.inert) {
          const s = this.player.state(); if (s.intent === 'play' && !s.closed) this.player.requireRecovery('permission');
        }
        if (entry.blocked) { entry.blocked = false; this.player.unblock(entry.key); }
        this.synchronize();
        const revision = this.revision;
        Promise.resolve().then(() => { if (!entry.inert && !this.destroyed && revision === this.revision && this.eligible()) void this.player.resume(); });
        return true;
      })();
      entry.stopping = task.finally(() => { entry.stopping = null; }); return entry.stopping;
    };
    entry.lease = Object.freeze({ id, ownerId: owner.ownerId, signal: entry.abort.signal, valid, adopt,
      end: finish, cancel: finish, destroy: finish, retryStop: finish });
    if (!entry.inert) { this.entries.set(entry.key, entry); this.revision++; this.synchronize(); }
    if (kind === 'short') entry.timer = this.later(() => { void finish(); }, timeoutMs);
    return entry.lease;
  }
  state() { return [...this.entries.values()].map(e => ({ owner: e.ownerKey, kind: e.kind, closing: e.closing, unknown: e.unknown, pending: [...e.resources].filter(r => !r.closed).length })); }
  dispose() { this.destroyed = true; this.unsubscribe(); return Promise.all([...this.entries.values()].map(e => e.lease.destroy())); }
}

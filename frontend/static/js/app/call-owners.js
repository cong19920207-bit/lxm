import { createCallOwnerRecord } from './call-owner-protocol.js';
import { createCallVerification } from './call-verification.js';

// Records survive routes. Tokens/capabilities stay inside this document, never diagnostics.
export class CallOwners {
  constructor({ acquireBlocker }) { this.acquireBlocker = acquireBlocker; this.records = new Map(); this.listeners = new Set(); this.proofs = new WeakSet(); }
  createVerification(options) { return createCallVerification(options); }
  accept(value) {
    const record = createCallOwnerRecord(value), previous = this.records.get(record.ownerId);
    if (previous) {
      if (previous.record !== value && (previous.record.attemptKey !== record.attemptKey || previous.record.authEpoch !== record.authEpoch || previous.record.principalId !== record.principalId)) throw new Error('Call owner collision');
      return previous.handle;
    }
    const entry = { record, localClose: record.localClose, remoteCleanup: record.remoteCleanup, pending: new Set(), failed: false,
      blocker: this.acquireBlocker('call', record.ownerId), handle: null };
    const ownerId = record.ownerId;
    entry.handle = Object.freeze({ ownerId, updateLocal: result => this.updateLocal(ownerId, result),
      adopt: (promise, dispose) => this.adopt(ownerId, promise, dispose) });
    this.records.set(record.ownerId, entry);
    for (const pending of record.pendingResources) this.adopt(record.ownerId, pending.promise, pending.dispose);
    entry.record = Object.freeze({ ...record, pendingResources: Object.freeze([]) });
    this.emit(); void this.verify(ownerId); return entry.handle;
  }
  adopt(ownerId, promise, dispose) {
    const entry = this.records.get(ownerId); if (!entry || typeof dispose !== 'function') throw new Error('Unknown call resource owner');
    const pending = { status: 'pending' }; entry.pending.add(pending); this.emit();
    pending.promise = Promise.resolve(promise).then(async resource => {
      try {
        const result = await dispose(resource);
        pending.status = result === true || result?.status === 'closed' ? 'closed' : 'unknown';
      } catch (_) { pending.status = 'unknown'; }
    }, () => { pending.status = 'closed'; }).finally(() => { if (pending.status === 'closed') entry.pending.delete(pending); else entry.failed = true; this.emit(); void this.verify(ownerId); });
    return pending.promise;
  }
  updateLocal(ownerId, result) {
    const entry = this.records.get(ownerId); if (!entry) return false;
    if (!['pending', 'closed', 'unknown'].includes(result?.status)) throw new TypeError('Explicit local close status required');
    entry.localClose = Object.freeze({ ...result }); this.emit(); void this.verify(ownerId); return true;
  }
  updateCall(ownerId, callId) {
    const entry = this.records.get(ownerId); if (!entry || !callId) return false;
    if (entry.record.callId && entry.record.callId !== callId) throw new Error('Original call ID cannot change');
    entry.record = Object.freeze({ ...entry.record, callId }); this.emit(); return true;
  }
  registerController(controller, context, ui) {
    const registration = { controller, context, ui }; this.active = registration;
    return () => { if (this.active === registration) this.active = null; };
  }
  async guardLeave({ current }) {
    const active = this.active;
    if (!active || !active.context.valid() || !active.controller.needsLeaveConfirmation()) return true;
    if (!active.confirming) active.confirming = active.ui.confirm('结束通话并离开？', '离开当前页面会结束这次通话。', '结束并离开', true, '继续通话').finally(() => { active.confirming = null; });
    const leave = await active.confirming;
    if (!current() || this.active !== active || !active.context.valid()) return false;
    if (leave) active.controller.leave('route');
    return leave;
  }
  async verify(ownerId) {
    const entry = this.records.get(ownerId); if (!entry) return false;
    if (entry.verifying) { entry.verifyAgain = true; return entry.verifying; }
    entry.verifying = Promise.resolve().then(() => entry.record.verifyOriginal()).then(result => {
      if (result?.callId) this.updateCall(ownerId, result.callId);
      const evidence = result?.evidence;
      const complete = result?.status === 'complete' && (evidence?.kind === 'not-created' && !entry.record.callId ||
        evidence?.kind === 'end' && evidence.callId === entry.record.callId && evidence.cleanup_pending === false);
      if (complete) { entry.remoteCleanup = Object.freeze({ status: 'complete', evidence }); this.proofs.add(evidence); }
      this.emit();
      return this.release(ownerId, entry.remoteCleanup.evidence);
    }).catch(() => false).finally(() => {
      entry.verifying = null;
      if (entry.verifyAgain) { entry.verifyAgain = false; void this.verify(ownerId); }
    });
    return entry.verifying;
  }
  verifyAll() { return Promise.all([...this.records.keys()].map(id => this.verify(id))); }
  release(ownerId, evidence) {
    const entry = this.records.get(ownerId);
    if (!entry || !evidence || !this.proofs.has(evidence) || entry.remoteCleanup.evidence !== evidence ||
        entry.remoteCleanup.status !== 'complete' || entry.localClose.status !== 'closed' || entry.pending.size || entry.failed) return false;
    this.records.delete(ownerId); entry.blocker.release(); this.emit(); return true;
  }
  occupied() { return this.records.size > 0; }
  state() { return [...this.records.values()].map(e => ({ ownerId: e.record.ownerId, principalId: e.record.principalId,
    authEpoch: e.record.authEpoch, attemptKey: e.record.attemptKey, callId: e.record.callId, localClose: e.localClose.status,
    remoteCleanup: e.remoteCleanup.status, pending: e.pending.size, failed: e.failed })); }
  emit() { for (const listener of this.listeners) { try { listener(this.state()); } catch (_) {} } }
  subscribe(listener) { this.listeners.add(listener); listener(this.state()); return () => this.listeners.delete(listener); }
}

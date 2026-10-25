// Every close path addresses one registration/session, never a later overlay with the same name.
export class OverlayManager {
  constructor({ history, doc = document }) { this.history = history; this.doc = doc; this.layers = new Map(); this.locks = new Set(); this.inert = new Map(); }
  register({ id = crypto.randomUUID(), kind, ownerId, open, close, element, background, lockScroll = true }) {
    if (this.layers.has(id)) throw new Error('重复弹层实例');
    const record = { id, kind, ownerId, open, close, element, background, lockScroll, visible: false, closing: null, disposed: false };
    this.layers.set(id, record);
    return Object.freeze({ id, open: () => this.open(record), close: options => this.close(record, options),
      dispose: () => { if (record.disposed) return; record.disposed = true; this.close(record, { fromHistory: true, reason: 'unmount' }); this.layers.delete(id); },
      isOpen: () => record.visible });
  }
  open(record, { fromHistory = false } = {}) {
    if (record.disposed || record.visible || record.closing) return false;
    record.visible = true; record.focus = this.doc.activeElement;
    if (record.lockScroll) {
      if (!this.locks.size) this.savedOverflow = this.doc.body.style.overflow;
      this.locks.add(record.id); this.doc.body.style.overflow = 'hidden';
    }
    if (record.background) {
      let lease = this.inert.get(record.background);
      if (!lease) { lease = { previous: record.background.inert, owners: new Set() }; this.inert.set(record.background, lease); }
      lease.owners.add(record.id); record.background.inert = true;
    }
    record.open?.();
    if (!fromHistory && record.kind === 'bgm') this.history.openOverlay(record.id);
    return true;
  }
  close(record, { fromHistory = false, reason = 'user' } = {}) {
    if (record.closing) return record.closing;
    if (!record.visible) return Promise.resolve(false);
    record.visible = false;
    try { record.close?.({ reason }); }
    finally {
      this.locks.delete(record.id); if (!this.locks.size && this.savedOverflow !== undefined) { this.doc.body.style.overflow = this.savedOverflow; this.savedOverflow = undefined; }
      if (record.background) {
        const lease = this.inert.get(record.background); lease?.owners.delete(record.id);
        if (lease && !lease.owners.size) { record.background.inert = lease.previous; this.inert.delete(record.background); }
      }
      if (record.focus?.isConnected && !record.disposed && ['user', 'back'].includes(reason)) record.focus.focus?.({ preventScroll: true });
    }
    const pending = !fromHistory && record.kind === 'bgm' ? this.history.closeOverlay(record.id) : Promise.resolve(true);
    record.closing = Promise.resolve(pending).finally(() => { record.closing = null; });
    return record.closing;
  }
  async closeHistorical(options = {}) {
    for (const record of this.layers.values()) if (record.kind === 'bgm' && record.visible) return this.close(record, options);
    return this.history.closeOverlay(this.history.current?.overlay?.id);
  }
  fromHistory(open, id) {
    const record = this.layers.get(id) || [...this.layers.values()].find(x => x.kind === 'bgm' && !x.disposed);
    if (!record) return false;
    if (open) this.open(record, { fromHistory: true });
    else this.close(record, { fromHistory: true, reason: 'back' });
    return true;
  }
  closeOwner(ownerId, options = {}) {
    return Promise.allSettled([...this.layers.values()].filter(x => x.ownerId === ownerId).map(x => this.close(x, options)));
  }
}

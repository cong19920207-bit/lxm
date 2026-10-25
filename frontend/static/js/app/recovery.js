// STEP-003 protocol. Native event wiring is intentionally owned by the document lifecycle service.
export class RecoveryCoordinator {
  constructor(services) { this.services = services; this.epoch = 0; this.transaction = null; }
  freeze(reason) {
    this.epoch++; this.transaction = null;
    this.services.invalidate?.(reason);
    this.services.maskPrivate?.();
    return this.epoch;
  }
  resume(epoch = this.epoch) {
    if (epoch !== this.epoch) return Promise.resolve(false);
    if (this.transaction) return this.transaction;
    const current = () => epoch === this.epoch;
    const run = async () => {
      // Each awaited stage rechecks generation. An older resume must never reach sound.
      for (const name of ['identity', 'history', 'storage', 'owners', 'blockers', 'view', 'sound']) {
        if (!current()) return false;
        await this.services[name]?.({ epoch, current });
      }
      return current();
    };
    this.transaction = run(); return this.transaction;
  }
}

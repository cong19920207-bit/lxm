import { RecoveryCoordinator } from './recovery.js';

// One owner for real document events. Route navigation never dispatches these events.
export class DocumentLifecycle {
  constructor({ shell, win = window, doc = document }) {
    Object.assign(this, { shell, win, doc });
    this.frozen = false; this.destroyed = false; this.cycles = 0; this.stages = []; this.events = []; this.masks = [];
    const stage = (name, action) => async transaction => { this.stages.push({ cycle: transaction.epoch, name }); if (this.stages.length > 56) this.stages.shift(); return action(transaction); };
    this.recovery = new RecoveryCoordinator({
      invalidate: reason => this.invalidate(reason), maskPrivate: () => this.mask(),
      identity: stage('identity', () => shell.services.auth.refresh()),
      history: stage('history', () => shell.services.history.reconcile()),
      storage: stage('storage', () => shell.services.audio.restoreStored()),
      // Remote uncertainty remains a blocker; it must not hold the visible page hostage.
      owners: stage('owners', () => { void shell.services.voice.verifyAll(); }),
      blockers: stage('blockers', () => shell.services.audio.preparation?.update?.()),
      view: stage('view', async ({ current }) => {
        const router = shell.router;
        if (router.current || shell.services.entry) {
          await router.navigate(router.current ? win.location.href : shell.initialURL, { force: true,
            reason: router.current ? 'pop' : 'initial', replace: !router.current, safety: true, recovery: true,
            historyTarget: shell.services.history.current });
          if (current() && router.current && (router.current.route.name !== 'index' || router.current.phase === 'error')) shell.services.entry?.prepared();
        }
        if (current() && !doc.hidden) this.unmask();
      }),
      sound: stage('sound', async ({ current }) => {
        if (!current() || doc.hidden) return;
        shell.router.suspended = false;
        shell.services.audio.restoreBlockers();
        await shell.services.audio.reconcile({ current: () => current() && !doc.hidden });
      }),
    });
    this.visibility = event => { this.note(event); if (doc.hidden) this.freeze('hidden'); else void this.resume(); };
    this.pagehide = event => { this.note(event); this.freeze('pagehide'); if (!event.persisted) shell.destroy(); };
    this.pageshow = event => { this.note(event); if (event.persisted) void this.resume(); };
    this.freezeEvent = event => { this.note(event); this.freeze('freeze'); };
    this.resumeEvent = event => { this.note(event); void this.resume(); };
    doc.addEventListener('visibilitychange', this.visibility);
    doc.addEventListener('freeze', this.freezeEvent); doc.addEventListener('resume', this.resumeEvent);
    win.addEventListener('pagehide', this.pagehide); win.addEventListener('pageshow', this.pageshow);
    if (doc.hidden) this.freeze('hidden');
  }
  note(event) {
    this.events.push({ type: event.type, trusted: event.isTrusted, persisted: event.persisted === true });
    if (this.events.length > 32) this.events.shift();
  }
  invalidate(reason) {
    const { router, services } = this.shell;
    services.entry?.suspend();
    services.audio.suspend('hidden');
    services.history.capture(router.current || {});
    router.suspended = true; router.navId++; router.pending?.abort();
    router.current?.context.scope.invalidate(reason);
    services.ui.closeLogin('document-hidden');
    router.current?.dispose(reason);
  }
  mask() {
    if (this.masks.length) return;
    for (const root of [this.shell.root, this.shell.overlayRoot]) {
      this.masks.push({ root, visibility: root.style.visibility, inert: root.inert });
      root.style.visibility = 'hidden'; root.inert = true;
    }
  }
  unmask() { for (const { root, visibility, inert } of this.masks.splice(0)) { root.style.visibility = visibility; root.inert = inert; } }
  freeze(reason) {
    if (this.destroyed || this.frozen && !this.restoring) return;
    this.frozen = true; this.cycles++; this.recovery.freeze(reason);
  }
  async resume() {
    if (this.destroyed || !this.frozen || this.doc.hidden) return false;
    const epoch = this.recovery.epoch;
    const attempt = this.restoring = { epoch };
    try {
      const restored = await this.recovery.resume(epoch);
      if (restored && epoch === this.recovery.epoch && !this.doc.hidden) this.frozen = false;
      return restored;
    } catch (error) {
      if (epoch === this.recovery.epoch) this.recovery.transaction = null;
      console.error('页面恢复失败', error); return false;
    } finally { if (this.restoring === attempt) this.restoring = null; }
  }
  dispose() {
    if (this.destroyed) return; this.destroyed = true;
    this.recovery.epoch++; this.shell.router.suspended = true;
    this.doc.removeEventListener('visibilitychange', this.visibility);
    this.doc.removeEventListener('freeze', this.freezeEvent); this.doc.removeEventListener('resume', this.resumeEvent);
    this.win.removeEventListener('pagehide', this.pagehide); this.win.removeEventListener('pageshow', this.pageshow);
  }
  inspect() { return { frozen: this.frozen, destroyed: this.destroyed, cycles: this.cycles, epoch: this.recovery.epoch,
    stages: this.stages.slice(-56), events: [...this.events] }; }
}

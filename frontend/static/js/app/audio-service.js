import { ActivityLeases } from './activity-leases.js';
import { CallOwners } from './call-owners.js';

export class AudioService {
  constructor({ player, output, session, preferences, preparationFactory, host = window, doc = document,
    initialRoute = 'index', entryPending = false, later = (...args) => setTimeout(...args), clear = id => clearTimeout(id) }) {
    Object.assign(this, { player, output, session, preferences, host, doc, later, clear });
    this.listeners = new Set(); this.motionListeners = new Set(); this.blockers = new Map(); this.documentBlockers = new Map(); this.callLeases = new Map();
    this.adapters = new Set(); this.parked = !!doc.hidden; this.syncing = true; this.destroyed = false; this.timer = null;
    this.signature = ''; this.resumeNeeded = false; this.homeLoading = initialRoute === 'index';
    const stored = session.inspect(); this.note = stored.note; this.bubble = stored.session?.bubble || { x: 1, y: 0.6 };
    this.activities = new ActivityLeases({ player, output, later, clear });
    this.callOwners = new CallOwners({ acquireBlocker: (_kind, ownerId) => this.acquireCall(ownerId) });
    this.preparation = preparationFactory?.({ player, document: doc, window: host, isHomeLoading: () => this.homeLoading });
    this.unsubscribe = player.subscribe(state => this.changed(state));
    if (doc.hidden) this.documentBlockers.set('hidden', this.acquireBlocker('hidden', 'document'));
    // Initial Login must not let initialization spend an autoplay opportunity.
    if (initialRoute === 'login') this.initialBlocker = this.acquireBlocker('login', 'initial');
    if (entryPending) this.holdEntry();
    const initial = initialRoute === 'login' && !stored.session ? { intent: 'pause', closed: false, recoveryRequired: false } : stored.session;
    this.ready = player.initialize({ session: initial }); this.syncing = false; this.changed(player.state());
    this.storageListener = event => {
      if (event.key !== preferences.motionKey) return;
      try { if (event.storageArea !== host.localStorage) return; } catch (_) { return; }
      const choice = preferences.readMotion(true);
      for (const listener of this.motionListeners) listener(choice);
    };
    host.addEventListener('storage', this.storageListener);
  }
  state() { return { ...this.player.state(), sessionNote: this.note, bubble: { ...this.bubble } }; }
  holdEntry() { if (!this.entryBlocker) this.entryBlocker = this.acquireBlocker('entry', 'document'); }
  prepareEntry() { return this.player.event('panel'); }
  enter({ music }) {
    if (!music) this.player.pause();
    this.entryBlocker?.release(); this.entryBlocker = null;
    return music ? this.player.play('home', { gesture: true }) : false;
  }
  publish() { for (const listener of this.listeners) { try { listener(this.state()); } catch (_) {} } }
  save() { this.note = this.session.save(this.player.checkpoint(), this.bubble).note; this.publish(); }
  changed(state) {
    if (this.destroyed) return;
    if (!this.syncing && !this.parked) {
      const signature = JSON.stringify([state.track?.id, state.track?.media_version, state.intent, state.closed, state.recoveryRequired, state.actual]);
      if (signature !== this.signature) { this.signature = signature; this.save(); }
      if (state.actual === 'playing' && this.timer === null) this.timer = this.later(() => {
        this.timer = null; if (!this.parked && !this.destroyed && this.player.state().actual === 'playing') { this.save(); this.changed(this.player.state()); }
      }, 2000);
      else if (state.actual !== 'playing') { this.clear(this.timer); this.timer = null; }
    }
    this.publish();
  }
  acquireBlocker(kind, ownerId) {
    const key = kind + ':' + ownerId + ':' + crypto.randomUUID(), entry = { key, kind, released: false };
    const already = [...this.blockers.values()].some(item => item.kind === kind);
    this.blockers.set(key, entry); if (!already) this.player.block(kind);
    if (kind === 'call') this.player.close();
    return Object.freeze({ key, release: () => {
      if (entry.released) return false; entry.released = true;
      this.blockers.delete(key); if (![...this.blockers.values()].some(item => item.kind === kind)) this.player.unblock(kind); this.resumeNeeded = true; return true;
    } });
  }
  acquireRouteBlocker(route, definition) {
    const lease = definition?.audioBlocker ? this.acquireBlocker('login', 'route:' + route.url) : null;
    this.initialBlocker?.release(); this.initialBlocker = null;
    return lease;
  }
  acquireCall(ownerId) {
    if (this.callLeases.has(ownerId)) return this.callLeases.get(ownerId);
    const blocker = this.acquireBlocker('call', ownerId);
    const lease = Object.freeze({ release: () => { if (this.callLeases.get(ownerId) !== lease) return false;
      this.callLeases.delete(ownerId); return blocker.release(); } });
    this.callLeases.set(ownerId, lease); return lease;
  }
  async stopForCall(ownerId, current) {
    this.acquireCall(ownerId);
    return this.output.silenceBarrier({ current });
  }
  async reconcile({ current = () => true } = {}) {
    if (this.destroyed || this.parked || !current()) return false;
    const s = this.player.state();
    if (!this.resumeNeeded || s.actual === 'playing' || s.intent !== 'play' || s.closed || s.recoveryRequired || s.blockers.length) return false;
    this.resumeNeeded = false; return this.player.resume();
  }
  observeMotion(context, listener) {
    const guarded = choice => { if (context.valid()) listener(choice); };
    this.motionListeners.add(guarded);
    return context.cleanup(() => this.motionListeners.delete(guarded));
  }
  attachPage(context, mode = context.route.name === 'index' ? 'home' : context.route.name === 'login' ? 'login' : 'content') {
    const service = this, subscriptions = new Set(), activities = new Set(); let disposed = false, warning = null;
    const valid = () => !disposed && context.valid();
    const owner = { ownerId: context.scope.ownerId, valid };
    const state = () => ({ ...service.state(), mode, destroyed: disposed || service.destroyed });
    const facade = {};
    for (const name of ['play','select','next','pause','close','event','resume']) facade[name] = (...args) => valid() ? service.player[name](...args) : false;
    facade.state = () => service.player.state();
    const subscribe = listener => {
      const guarded = () => { if (valid()) listener(state()); }; service.listeners.add(guarded); subscriptions.add(guarded); guarded();
      return () => { service.listeners.delete(guarded); subscriptions.delete(guarded); };
    };
    facade.subscribe = listener => subscribe(value => listener(value));
    const begin = (id, options) => { if (!valid()) return null; const lease = service.activities.begin(owner, id, options); activities.add(lease); return lease; };
    const adapter = { ownerId: owner.ownerId, context, player: Object.freeze(facade), ready: service.ready, state, subscribe,
      ducking: { begin: (id, options = {}) => begin(id, { ...options, kind: 'short' }) },
      mediaActivities: { begin: (id, options = {}) => begin(id, options) },
      setBubble(position) { if (!valid() || !Number.isFinite(position?.x) || !Number.isFinite(position?.y)) return;
        service.bubble = { x: Math.max(0, Math.min(1, position.x)), y: Math.max(0, Math.min(1, position.y)) }; service.save(); },
      onMotion(listener) { const guarded = choice => { if (valid()) listener(choice); }; service.motionListeners.add(guarded);
        context.cleanup(() => service.motionListeners.delete(guarded)); return () => service.motionListeners.delete(guarded); },
      setHomeLoading(value) { if (valid() && mode === 'home') { service.homeLoading = !!value; service.preparation?.update?.(); } },
      destroy() { if (disposed) return; disposed = true; warning?.remove(); subscriptions.forEach(fn => service.listeners.delete(fn)); subscriptions.clear();
        for (const lease of activities) void lease.destroy(); service.adapters.delete(adapter);
        if (mode === 'home') service.homeLoading = false; }
    };
    // Preserve the legacy page's visible storage warning; the current adapter owns it.
    subscribe(value => {
      if (value.sessionNote && !warning) {
        warning = context.root.ownerDocument.createElement('div'); warning.dataset.bgmSessionNote = ''; warning.setAttribute('role', 'status');
        warning.style.cssText = 'position:fixed;bottom:calc(env(safe-area-inset-bottom,0px) + 8px);left:12px;right:12px;max-width:536px;margin:auto;padding:8px 12px;background:#191329;color:#eee;font-size:12px;border-radius:10px;z-index:1200;pointer-events:none';
        context.root.append(warning);
      }
      if (warning) { warning.textContent = value.sessionNote; warning.hidden = !value.sessionNote; }
    });
    this.adapters.add(adapter); context.cleanup(() => adapter.destroy()); return Object.freeze(adapter);
  }
  suspend(reason) {
    if (this.destroyed) return;
    const wasParked = this.parked; this.parked = true; this.syncing = true; this.clear(this.timer); this.timer = null;
    if (!this.documentBlockers.has(reason)) this.documentBlockers.set(reason, this.acquireBlocker(reason, 'document'));
    if (!wasParked) this.save(); this.syncing = false;
  }
  restoreStored() {
    if (!this.parked || this.destroyed) return;
    const latest = this.session.inspect(); this.note = latest.note;
    const checkpoint = latest.session || { ...this.player.checkpoint(), intent: 'pause' };
    if (checkpoint.bubble) this.bubble = { ...checkpoint.bubble };
    this.player.restoreSession(checkpoint); this.output.refresh();
  }
  restoreBlockers() {
    if (this.destroyed || this.doc.hidden) return false;
    for (const lease of this.documentBlockers.values()) lease.release(); this.documentBlockers.clear();
    this.parked = false; this.signature = ''; this.changed(this.player.state()); return true;
  }
  async destroy() {
    if (this.destroyed) return; this.suspend('pagehide'); this.destroyed = true;
    this.host.removeEventListener('storage', this.storageListener); this.unsubscribe(); this.preparation?.destroy();
    this.adapters.forEach(adapter => adapter.destroy()); this.listeners.clear(); this.motionListeners.clear();
    this.player.destroy(); await this.activities.dispose();
  }
}

export async function createAudioService({ shared, initialRoute, entryPending = false, host = window, doc = document }) {
  for (const name of ['home-preferences','bgm-preferences','bgm-output','bgm-controller','bgm-catalog','bgm-player','bgm-session','bgm-preparation']) await shared.script('js/' + name + '.js');
  return new AudioService({ player: host.BgmPlayer.getDocumentInstance(), output: host.BgmOutput,
    session: host.BgmSession.create(), preferences: host.HomePreferences, preparationFactory: host.BgmPreparation.create,
    initialRoute, entryPending, host, doc });
}

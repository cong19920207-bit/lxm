import { PageStateStore } from './page-state.js';
import { layouts } from './document-state.js';

export const HISTORY_KEY = '__lxmAppShell';
const dataObject = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
const id = () => crypto.randomUUID();
export class AppHistory {
  constructor({ buildId, win = window, auth, snapshots = new PageStateStore() }) {
    this.buildId = buildId; this.win = win; this.auth = auth; this.snapshots = snapshots;
    this.current = null; this.currentURL = win.location.href; this.overlayClose = null; this.compensation = null;
    this.previousRestoration = win.history.scrollRestoration; win.history.scrollRestoration = 'manual';
  }
  read(state) {
    const entry = state?.[HISTORY_KEY];
    if (!entry || entry.schema !== 1 || entry.build !== this.buildId || typeof entry.entryId !== 'string' ||
        !Number.isSafeInteger(entry.position) || !layouts[entry.route] ||
        entry.overlay && (entry.overlay.kind !== 'bgm' || typeof entry.overlay.id !== 'string' || typeof entry.parentEntryId !== 'string')) return null;
    return entry;
  }
  write(entry, url, replace = false) {
    const state = { ...dataObject(this.win.history.state), [HISTORY_KEY]: entry };
    this.win.history[replace ? 'replaceState' : 'pushState'](state, '', url);
    this.current = entry; this.currentURL = this.win.location.href; return entry;
  }
  commit(route, options) {
    if (options.mode === 'pop' && options.historyTarget) {
      const target = options.historyTarget;
      if (!this.read(this.win.history.state)) this.write(target, route.url, true);
      this.current = target; this.currentURL = this.win.location.href; return target;
    }
    const old = this.current || this.read(this.win.history.state);
    const replace = options.mode === 'replace';
    const entry = { schema: 1, build: this.buildId, entryId: replace && old ? old.entryId : id(),
      position: old ? old.position + (replace ? 0 : 1) : 0, route: route.name,
      ...(replace && old?.source ? {source:old.source} : !replace && old ? {source:old.route} : {}) };
    return this.write(entry, route.url, replace);
  }
  async beforeCommit(_route, options) {
    if (options.mode !== 'pop' && this.current?.overlay) await this.overlays.closeHistorical({ reason: 'route' });
  }
  consumeParam(name, value) {
    const url = new URL(this.win.location.href);
    if (value !== undefined && url.searchParams.get(name) !== value) return false;
    url.searchParams.delete(name); this.win.history.replaceState(this.win.history.state, '', url.pathname + url.search + url.hash);
    this.currentURL = this.win.location.href; return true;
  }
  reconcile() {
    this.current = this.read(this.win.history.state); this.currentURL = this.win.location.href;
    if (this.overlayClose) { this.overlayClose.resolve(false); this.overlayClose = null; }
    if (this.compensation) { this.compensation.resolve(false); this.compensation = null; }
    return this.current;
  }
  openOverlay(token) {
    if (!this.current || this.current.overlay || this.overlayClose) return;
    const entry = { ...this.current, entryId: id(), position: this.current.position + 1,
      parentEntryId: this.current.entryId, overlay: { kind: 'bgm', id: token } };
    this.write(entry, this.win.location.href);
  }
  closeOverlay(token) {
    if (this.overlayClose) return this.overlayClose.promise;
    if (!this.current?.overlay || this.current.overlay.id !== token) return Promise.resolve(false);
    let resolve;
    const promise = new Promise(r => { resolve = r; });
    this.overlayClose = { promise, resolve, from: this.current };
    this.win.history.back(); return promise;
  }
  async handlePop(event, router) {
    const known = this.read(event.state), previous = this.current;
    if (this.compensation && known?.entryId === this.compensation.entryId) {
      this.current = known; this.currentURL = this.win.location.href;
      if (known.overlay) this.overlays?.fromHistory(true, known.overlay.id);
      const done = this.compensation; this.compensation = null; done.resolve(true); return;
    }
    if (previous?.overlay && known?.entryId === previous.parentEntryId) {
      this.overlays?.fromHistory(false, previous.overlay.id);
      this.current = known; this.currentURL = this.win.location.href;
      if (this.overlayClose) { const close = this.overlayClose; this.overlayClose = null; close.resolve(true); }
      return;
    }
    // A rapid multi-entry traversal can skip the panel's parent. It still consumes
    // the pending close, but the remaining traversal must reach the router once.
    if (previous?.overlay) this.overlays?.fromHistory(false, previous.overlay.id);
    if (this.overlayClose) { const close = this.overlayClose; this.overlayClose = null; close.resolve(true); }
    if (known?.overlay && known.parentEntryId === previous?.entryId && known.route === previous.route) {
      this.current = known; this.currentURL = this.win.location.href;
      if (!this.overlays?.fromHistory(true, known.overlay.id)) {
        const { overlay, parentEntryId, ...normal } = known; this.write(normal, this.win.location.href, true);
      }
      return;
    }
    // Unknown/old states have no trusted traversal delta. Keep a usable entry but do not guess a direction.
    const match = /\/pages\/([^/]+)\.html$/.exec(this.win.location.pathname);
    const target = known || { schema: 1, build: this.buildId, entryId: id(), position: 0, route: match?.[1] || 'index' };
    return router.navigate(this.win.location.href, { reason: 'pop', force: true,
      historyTarget: target, historyFrom: previous, historyFromURL: this.currentURL, unknownPosition: !known });
  }
  cancelPop(options) {
    const from = options.historyFrom, target = options.historyTarget;
    if (!from) return Promise.resolve(false);
    if (options.unknownPosition || !target || from.position === target.position) {
      this.write(from, options.historyFromURL, true); return Promise.resolve(true);
    }
    if (this.compensation) return this.compensation.promise;
    let resolve; const promise = new Promise(r => { resolve = r; });
    this.compensation = { entryId: from.entryId, promise, resolve };
    this.win.history.go(from.position - target.position); return promise;
  }
  capture(slot) {
    if (!slot.entry || !slot.context.valid()) return;
    const snapshot = { ...slot.instance?.captureState?.(), ...capturePosition(slot, this.win) };
    this.snapshots.set(slot.entry.entryId, slot.context.principalId, slot.route.name, snapshot);
  }
  stateFor(entry, route) {
    const identity = this.auth?.snapshot() || { principalId: null };
    return entry ? this.snapshots.get(entry.parentEntryId || entry.entryId, identity.principalId, route.name) : undefined;
  }
  async restore(slot) {
    const state = slot.context.state;
    if (state && !slot.context.params.has('focus')) restorePosition(slot, state, this.win);
    if (this.current?.overlay) this.overlays?.fromHistory(true, this.current.overlay.id);
  }
  dispose() { this.win.history.scrollRestoration = this.previousRestoration; this.snapshots.clear(); }
}

function scrollTarget(slot, win) {
  const selector = layouts[slot.route.name]?.scroll;
  return selector && selector !== 'document' ? slot.root.querySelector(selector) : win.document.scrollingElement;
}
function capturePosition(slot, win) {
  const target = scrollTarget(slot, win), focused = win.document.activeElement;
  const focus = slot.root.contains(focused) && focused.id && focused.type !== 'password' ? { id: focused.id,
    start: focused.selectionStart, end: focused.selectionEnd } : undefined;
  const viewportTop = target === win.document.scrollingElement ? 0 : target?.getBoundingClientRect().top || 0;
  const anchors = slot.root.querySelectorAll('[data-message-id],[data-post-id],[data-diary-id]');
  const anchor = [...anchors].find(node => node.getBoundingClientRect().bottom >= viewportTop);
  const kind = anchor && ['messageId','postId','diaryId'].find(key => anchor.dataset[key]);
  return { scroll: { top: target?.scrollTop || 0, left: target?.scrollLeft || 0,
    ...(anchor ? { anchor: { kind, id: anchor.dataset[kind], ...(anchor.dataset.messageSource ? {source:anchor.dataset.messageSource} : {}), offset: anchor.getBoundingClientRect().top - viewportTop } } : {}) }, ...(focus ? { focus } : {}) };
}
function restorePosition(slot, state, win) {
  const target = scrollTarget(slot, win); if (!target) return;
  let cancelled = false, initial = true;
  const stop = () => { cancelled = true; };
  for (const type of ['wheel','touchstart','pointerdown','keydown']) slot.context.scope.listen(slot.root, type, stop, { passive: true });
  const apply = () => {
    if (!slot.context.valid() || cancelled) return;
    const anchor = state.scroll?.anchor;
    const attr = { messageId: 'data-message-id', postId: 'data-post-id', diaryId: 'data-diary-id' }[anchor?.kind];
    const node = attr && [...slot.root.querySelectorAll('[' + attr + ']')].find(x => x.getAttribute(attr) === anchor.id && (!anchor.source || x.dataset.messageSource === anchor.source));
    if (node) {
      const top = target === win.document.scrollingElement ? 0 : target.getBoundingClientRect().top;
      target.scrollTop += node.getBoundingClientRect().top - top - anchor.offset;
    } else if (initial) { target.scrollTop = state.scroll?.top || 0; target.scrollLeft = state.scroll?.left || 0; }
    if (initial && state.focus?.id) {
      const focused = [...slot.root.querySelectorAll('[id]')].find(x => x.id === state.focus.id && x.type !== 'password');
      focused?.focus({ preventScroll: true });
      try { if (Number.isInteger(state.focus.start)) focused?.setSelectionRange(state.focus.start, state.focus.end); } catch (_) {}
    }
    initial = false;
  };
  apply(); slot.context.scope.frame(apply);
  // Layout settling is owned here, not by page modules. Stop after interaction or a bounded window.
  const removes = [slot.context.scope.listen(slot.root, 'load', apply, true)];
  if (typeof ResizeObserver === 'function') {
    const observer = new ResizeObserver(apply); observer.observe(slot.root);
    removes.push(slot.context.cleanup(() => observer.disconnect(), { kind: 'observer' }));
  }
  if (typeof MutationObserver === 'function') {
    const observer = new MutationObserver(apply); observer.observe(slot.root, { childList: true, subtree: true });
    removes.push(slot.context.cleanup(() => observer.disconnect(), { kind: 'observer' }));
  }
  slot.context.scope.timeout(() => removes.forEach(remove => remove()), 2000);
}

import { createPageContext, mountPage } from './page-context.js';
import { installDocumentState } from './document-state.js';

export const routeNames = Object.freeze(['index', 'chat', 'feed', 'diary', 'memory', 'relationship', 'settings', 'login']);
export const routeDefinitions = Object.freeze(Object.fromEntries(routeNames.map(name => [name, Object.freeze({
  name, module: `js/pages/${name === 'index' ? 'home' : name}.js`, template: `templates/${name}.html`,
  style: `css/pages/${name}.css`, parameterPolicy: 'remount',
  private: ['diary', 'memory', 'relationship'].includes(name), audioBlocker: name === 'login' ? 'login-page' : null
})])));

export function resolveRoute(value, base) {
  const url = new URL(value, base); const origin = new URL(base).origin;
  const match = /^\/pages\/(index|chat|feed|diary|memory|relationship|settings|login)\.html$/.exec(url.pathname);
  if (url.origin !== origin || !match) return null;
  const params = new URLSearchParams(url.search); params.sort();
  return Object.freeze({ name: match[1], pathname: url.pathname, search: url.search, hash: url.hash,
    url: url.pathname + url.search + url.hash, semantic: url.pathname + '?' + params.toString() + url.hash });
}

const expired = () => new DOMException('导航已失效', 'AbortError');
function bounded(promise, milliseconds, signal, onLate = () => {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn, value) => {
      if (settled) return false; settled = true; clearTimeout(timer); signal?.removeEventListener('abort', abort); fn(value); return true;
    };
    const abort = () => finish(reject, expired());
    const timer = setTimeout(() => finish(reject, new Error('页面资源等待超时')), milliseconds);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    Promise.resolve(promise).then(value => { if (!finish(resolve, value)) onLate(value); }, error => finish(reject, error));
  });
}

export async function prepareRoute(route, { resources, definitions = routeDefinitions, signal }) {
  const definition = definitions[route.name]; if (!definition) throw new Error('未注册页面');
  const releases = []; let disposed = false;
  const dispose = () => { if (disposed) return; disposed = true; for (const release of releases.splice(0)) release(); };
  const remember = release => { if (disposed || signal?.aborted) release(); else releases.push(release); };
  const abort = () => dispose(); signal?.addEventListener('abort', abort, { once: true });
  try {
    const [module, template] = await Promise.all([
      resources.module(definition.module), resources.text(definition.template),
      resources.style(definition.style).then(remember)
    ]);
    if (signal?.aborted) throw expired();
    return { module, template, definition, dispose };
  } catch (error) { dispose(); throw error; }
  finally { signal?.removeEventListener('abort', abort); }
}

export class Router {
  constructor({ root, services, win = window, prepare, installLayout = installDocumentState,
    definitions = routeDefinitions, waitMs = 15000, onError = error => console.error(error) }) {
    this.root = root; this.services = services; this.win = win; this.definitions = definitions;
    this.prepare = prepare || ((route, signal) => prepareRoute(route, { resources: services.resources, definitions, signal }));
    this.installLayout = installLayout; this.waitMs = waitMs; this.onError = onError;
    this.navId = 0; this.routeEpoch = 0; this.current = null; this.pending = null; this.closed = false;
  }
  identity() { return this.services.auth?.snapshot() || { principalId: null, authEpoch: 0 }; }
  sameIdentity(a) { const b = this.identity(); return a.authEpoch === b.authEpoch && a.principalId === b.principalId; }
  async navigate(value, options = {}) {
    if (this.closed) return { status: 'closed' };
    if (this.suspended && !options.recovery) return { status: 'suspended' };
    const route = resolveRoute(value, this.win.location.href); if (!route) return { status: 'external' };
    const mode = options.reason === 'pop' ? 'pop' : options.replace ? 'replace' : 'push';
    const backOwner = options.backTransaction || (mode === 'pop' && this.backTransaction?.handling ? this.backTransaction : null);
    const waitingBack = backOwner ? null : this.pendingBackTraversal();
    const id = ++this.navId, identity = this.identity();
    if (backOwner) backOwner.intentId = id;
    this.services.auth?.cancelAccessTransitions?.(options.accessOwner);
    this.pending?.abort();
    const intent = new AbortController(); this.pending = intent;
    const valid = () => !this.closed && id === this.navId && !intent.signal.aborted && this.sameIdentity(identity);
    let prepared;
    try {
      // A queued native traversal cannot be cancelled. Restore its source before
      // preparing the newer route, so failure/unchanged preserve both URL and view.
      if (waitingBack) await bounded(waitingBack.promise, this.waitMs, intent.signal);
      if (!valid()) return { status: 'superseded' };
      if (!options.force && this.current?.route.semantic === route.semantic && this.current.phase !== 'error') return { status: 'unchanged' };
      prepared = await bounded(this.prepare(route, intent.signal), this.waitMs, intent.signal, late => late?.dispose());
      if (!valid()) return { status: 'superseded' };
      const guard = await this.services.auth?.guardRoute?.(route, this.definitions[route.name]);
      if (!valid()) return { status: 'superseded' };
      if (guard?.redirect) {
        prepared.dispose(); prepared = null;
        const redirect = async accessOwner => {
          const result = await this.navigate(guard.redirect, { replace: true, reason: 'guard', force: true,
            recovery: options.recovery, accessOwner, backTransaction: backOwner });
          if (result.status === 'committed' && this.current?.context.routeEpoch === result.routeEpoch) await guard.afterCommit?.();
          return result;
        };
        return await (guard.transition ? guard.transition(redirect) : redirect());
      }
      if (guard === false) throw new Error('当前身份不可访问此页面');
      if (!options.safety && this.current && this.services.voice?.guardLeave) {
        const leave = await this.services.voice.guardLeave({ from: this.current.route, to: route, reason: options.reason || mode, current: valid });
        if (!valid()) return { status: 'superseded' };
        if (!leave) { if (mode === 'pop') await this.services.history?.cancelPop(options); return { status: 'cancelled' }; }
      }
      if (!valid()) return { status: 'superseded' };
      await this.services.history?.beforeCommit?.(route, { ...options, mode });
      if (!valid()) return { status: 'superseded' };
      const slot = this.commit(route, prepared, { ...options, mode, identity });
      prepared = null; // Ownership has transferred to the committed slot.
      try {
        const instance = await bounded(mountPage(slot.module, slot.context), this.waitMs, slot.context.signal,
          late => late?.unmount('late-mount'));
        if (this.current !== slot || !slot.context.valid()) return { status: 'superseded' };
        slot.instance = instance; slot.phase = 'mounted';
        await this.services.history?.restore?.(slot, options);
        if (!slot.context.valid()) return { status: 'superseded' };
        await this.services.audio?.reconcile?.({ reason: 'route', current: slot.context.valid });
        return { status: 'committed', route, routeEpoch: slot.context.routeEpoch };
      } catch (error) {
        if (this.current !== slot) return { status: 'superseded' };
        slot.context.scope.dispose('mount-failed'); this.showError(slot, error);
        return { status: 'failed', phase: 'mount', error };
      }
    } catch (error) {
      if (!valid() || error.name === 'AbortError') return { status: 'superseded' };
      if (mode === 'pop' || !this.current) {
        const slot = this.commit(route, { definition: this.definitions[route.name], dispose() {}, template: '', module: null }, { ...options, mode, identity });
        this.showError(slot, error);
      } else this.onError(error, { phase: 'prepare', route });
      return { status: 'failed', phase: 'prepare', error };
    } finally { prepared?.dispose(); intent.abort(); if (this.pending === intent) this.pending = null; }
  }
  commit(route, prepared, options) {
    const previous = this.current;
    // Install the target blocker before expiring/releasing the previous page's ownership.
    const blocker = this.services.audio?.acquireRouteBlocker?.(route, prepared.definition);
    if (previous) {
      try { this.services.history?.capture?.(previous); } catch (error) { this.onError(error); }
      previous.context.scope.invalidate('route-commit');
      previous.dispose('route-commit');
    }
    const entry = this.services.history?.commit?.(route, options) || null;
    if (!this.services.history && options.mode !== 'pop') {
      this.win.history[options.mode === 'replace' ? 'replaceState' : 'pushState'](this.win.history.state, '', route.url);
    }
    const element = this.root.ownerDocument.createElement('section'); element.dataset.appPage = route.name;
    element.innerHTML = prepared.template; this.root.replaceChildren(element);
    const restoreLayout = this.installLayout(route.name);
    const slot = { route, root: element, phase: 'mounting', module: prepared.module, entry, instance: null };
    slot.context = createPageContext({ root: element, route, reason: options.recovery ? 'resume' : options.reason || options.mode,
      router: this, services: this.services, routeEpoch: ++this.routeEpoch,
      state: options.state ?? this.services.history?.stateFor?.(entry, route), isCurrent: () => this.current === slot,
      onError: this.onError });
    let disposed = false;
    slot.dispose = reason => {
      if (disposed) return; disposed = true;
      for (const close of [() => slot.context.scope.dispose(reason), prepared.dispose, restoreLayout, () => blocker?.release?.()]) {
        try { close(); } catch (error) { this.onError(error); }
      }
    };
    this.current = slot; return slot;
  }
  showError(slot, error) {
    slot.phase = 'error'; slot.error = error;
    slot.root.replaceChildren(); slot.root.classList.add('app-route-error');
    const text = this.root.ownerDocument.createElement('p'); text.textContent = '页面加载失败，请重试。';
    const retry = this.root.ownerDocument.createElement('button'); retry.textContent = '重试';
    retry.addEventListener('click', () => { if (this.current === slot) this.navigate(slot.route.url, { replace: true, force: true, reason: 'retry' }); });
    slot.root.append(text, retry); this.onError(error, { phase: 'committed', route: slot.route });
  }
  async start({ initialPage } = {}) {
    this.click = event => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest?.('a[href]');
      if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
      if (!resolveRoute(link.href, this.win.location.href)) return;
      event.preventDefault(); this.navigate(link.href);
    };
    this.pop = async event => {
      const back = this.backTransaction && !this.backTransaction.handling ? this.backTransaction : null;
      if (back) back.handling = true;
      try {
        // Do not let a late pop allocate a newer navId than the route that already
        // superseded this return request. Compensation pops still reach AppHistory.
        if (!back || back.intentId === this.navId) {
          if (this.services.history?.handlePop) await this.services.history.handlePop(event, this);
          else await this.navigate(this.win.location.href, { reason: 'pop' });
        }
        if (back && this.pendingBackTraversal() === back && back.intentId !== this.navId) {
          const target = this.services.history.read(event.state);
          // The leave guard may already have restored this entry while a newer
          // intent was waiting. Do not traverse forward a second time.
          if (this.services.history.read(this.win.history.state)?.entryId !== back.entry.entryId) {
            await this.services.history.cancelPop({ historyFrom: back.entry, historyFromURL: back.url,
              historyTarget: target, unknownPosition: !target });
          }
        }
      } finally { if (back) this.finishBack(back); }
    };
    this.win.document.addEventListener('click', this.click); this.win.addEventListener('popstate', this.pop);
    const target = initialPage ? `/pages/${initialPage}.html` : this.win.location.pathname === '/' ? '/pages/index.html' : this.win.location.href;
    return this.navigate(target, { replace: true, reason: 'initial' });
  }
  consumeParam(name, value) {
    const changed = this.services.history?.consumeParam(name, value);
    if (changed && this.current) this.current.route = resolveRoute(this.win.location.href, this.win.location.href);
    return changed;
  }
  captureTransientInput() {
    if (this.current?.route.name !== 'chat' || !this.current.context.valid()) return undefined;
    const draft = this.current.instance?.captureState?.()?.draft;
    return typeof draft === 'string' && draft.length <= 65536 ? { draft } : undefined;
  }
  back() {
    if (this.backTransaction) return this.backTransaction.promise;
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    const entry = this.services.history?.read(this.win.history.state);
    const back = this.backTransaction = { promise, resolve, handling: false, native: entry?.position > 0,
      intentId: ++this.navId, entry, slot: this.current, url: this.win.location.href };
    this.pending?.abort(); this.pending = null;
    if (back.native) this.win.history.back();
    else {
      back.handling = true;
      this.navigate('/pages/index.html', { replace: true, reason: 'back', backTransaction: back })
        .finally(() => this.finishBack(back));
    }
    return promise;
  }
  pendingBackTraversal() {
    const back = this.backTransaction;
    return back?.native && this.current === back.slot && this.services.history.current?.entryId === back.entry.entryId ? back : null;
  }
  finishBack(back) {
    if (this.backTransaction !== back) return;
    this.backTransaction = null; back.resolve();
  }
  dispose() {
    if (this.closed) return; this.closed = true; this.navId++; this.pending?.abort();
    if (this.backTransaction) this.finishBack(this.backTransaction);
    this.win.document.removeEventListener('click', this.click); this.win.removeEventListener('popstate', this.pop);
    this.current?.dispose('document-destroy'); this.current = null;
  }
}

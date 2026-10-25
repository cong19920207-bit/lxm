export const policies = Object.freeze({
  LEGACY_LOGIN_PAGE: 'legacy-login-page', SILENT_VISITOR: 'silent-visitor',
  PROTECTED_HOME_MODAL: 'protected-home-modal', INTERACTIVE_MODAL: 'interactive-modal'
});
export function principalFromToken(token) {
  if (!token) return null;
  try {
    const value = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).user_id;
    return Number.isInteger(value) && value > 0 ? String(value) : undefined;
  } catch (_) { return undefined; }
}
export function staleError() { const error = new Error('Request is no longer current'); error.name = 'StaleRequestError'; return error; }

export class AuthService {
  constructor({ win = window, fetcher = globalThis.fetch.bind(globalThis), onChange = () => {}, beforeChange = () => {}, clearPrivate = () => {} } = {}) {
    this.win = win; this.fetcher = fetcher; this.onChange = onChange; this.beforeChange = beforeChange; this.clearPrivate = clearPrivate;
    this.listeners = new Set(); this.authEpoch = 0; this.authAttempt = 0; this.known = false;
    this.credential = null; this.available = false; this.lastStored = undefined; this.override = false;
    this.router = null; this.ui = null; this.restoration = Promise.resolve(); this.accessSequence = 0; this.accessTransitions = new Set();
    const initial = this.storage('getItem', 'token');
    if (initial.ok) { this.credential = initial.value; this.lastStored = initial.value; this.known = true; }
    this.available = initial.ok;
    this.storageEvent = event => { if (event.key == null || event.key === 'token') this.refresh({ external: true }); };
    win.addEventListener('storage', this.storageEvent);
  }
  storage(operation, key, value) {
    try { return { ok: true, value: this.win.localStorage[operation](key, value) }; }
    catch (_) { return { ok: false, value: null }; }
  }
  snapshot() {
    return Object.freeze({ known: this.known, available: this.available,
      principalId: this.known ? principalFromToken(this.credential) : undefined,
      authenticated: this.known && !!this.credential, authEpoch: this.authEpoch, authAttempt: this.authAttempt });
  }
  refresh({ external = false } = {}) {
    const stored = this.storage('getItem', 'token'); this.available = stored.ok;
    if (!stored.ok) return this.snapshot();
    if (this.override && !external && (this.lastStored === undefined || stored.value === this.lastStored)) {
      this.lastStored = stored.value; return this.snapshot();
    }
    if (!this.known || stored.value !== this.lastStored || external && this.override) {
      this.override = false; this.lastStored = stored.value;
      this.transition(stored.value, 'storage');
    }
    return this.snapshot();
  }
  readToken() { this.refresh(); return this.known ? this.credential : null; }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  transition(token, reason) {
    const previous = this.snapshot();
    try { this.beforeChange({ previous, principalId: principalFromToken(token), reason }); } catch (error) { console.error(error); }
    this.credential = token || null; this.known = true; this.authEpoch++; this.authAttempt++;
    const next = this.snapshot(), principalChanged = previous.principalId !== next.principalId;
    if (principalChanged || reason === 'logout' || reason === 'unauthorized') {
      // chat_draft has no account namespace; indexed submissions keep their original whitelist/deadline/retention.
      this.storage('removeItem', 'chat_draft'); this.storage('removeItem', 'relationship_level');
      try { this.win.sessionStorage.removeItem('chat_draft'); } catch (_) {}
      try { this.clearPrivate({ previous, next, reason }); } catch (error) { console.error(error); }
    }
    const change = Object.freeze({ previous, next, principalChanged, reason });
    for (const listener of this.listeners) { try { listener(change); } catch (error) { console.error(error); } }
    try { this.restoration = Promise.resolve(this.onChange(change)); }
    catch (error) { this.restoration = Promise.reject(error); }
    this.restoration.catch(error => console.error(error));
    return next;
  }
  persist(token, reason) {
    const result = this.storage(token ? 'setItem' : 'removeItem', 'token', token);
    this.available = result.ok; this.override = !result.ok;
    if (result.ok) this.lastStored = token || null;
    return this.transition(token, reason);
  }
  accept(token, { attempt } = {}) {
    if (!token || typeof token !== 'string' || attempt && !this.attemptCurrent(attempt)) return false;
    this.persist(token, 'login'); return true;
  }
  clear(reason = 'logout') {
    try { this.win.sessionStorage.removeItem('lxm_home_loader_done'); } catch (_) {}
    return this.persist(null, reason);
  }
  beginAttempt({ current = () => true, ownerId } = {}) {
    this.refresh(); const snapshot = this.snapshot();
    return Object.freeze({ id: ++this.authAttempt, authEpoch: snapshot.authEpoch, ownerId, current });
  }
  attemptCurrent(attempt) {
    this.refresh();
    try { return attempt?.id === this.authAttempt && attempt.authEpoch === this.authEpoch && attempt.current(); }
    catch (_) { return false; }
  }
  cancelAttempt(attempt) { if (attempt?.id === this.authAttempt) this.authAttempt++; }
  requestContext(options = {}) {
    this.refresh(); const snapshot = this.snapshot(), token = options.anonymous ? null : this.credential;
    const routeEpoch = options.routeEpoch ?? this.router?.current?.context.routeEpoch;
    const routeCurrent = options.routeCurrent || (() => routeEpoch === undefined || this.router?.current?.context.routeEpoch === routeEpoch);
    const current = () => {
      this.refresh();
      try { return snapshot.authEpoch === this.authEpoch && snapshot.principalId === this.snapshot().principalId &&
        !options.signal?.aborted && routeCurrent() && (!options.isCurrent || options.isCurrent()); }
      catch (_) { return false; }
    };
    const assert = () => {
      if (options.signal?.aborted) throw new DOMException('Request aborted', 'AbortError');
      if (!current()) throw staleError();
    };
    const headers = extras => { const result = new Headers(extras); if (token) result.set('Authorization', 'Bearer ' + token); else result.delete('Authorization'); return result; };
    return Object.freeze({ principalId: snapshot.principalId, authEpoch: snapshot.authEpoch, token, routeEpoch,
      routeCurrent, current, assert, headers, signal: options.signal,
      fetch: async (path, init = {}) => {
        assert(); const response = await this.fetcher(path, { ...init, headers: headers(init.headers), signal: init.signal || options.signal });
        assert(); return response;
      },
      read: async reader => { assert(); const chunk = await reader.read(); assert(); return chunk; }
    });
  }
  async request(method, path, data, options = {}) {
    const context = options.requestContext || this.requestContext(options);
    const init = { method, headers: { 'Content-Type': 'application/json' } };
    if (data && ['POST', 'PUT', 'PATCH'].includes(method)) init.body = JSON.stringify(data);
    try {
      const response = await context.fetch(path, init);
      if (response.status === 401) {
        if (!await this.unauthorized(context, options)) throw staleError();
        return { code: 401, data: null, message: '登录已过期' };
      }
      const result = await response.json(); context.assert(); return result;
    } catch (error) {
      if (error.name === 'AbortError' || error.name === 'StaleRequestError') throw error;
      context.assert();
      return { code: -1, data: null, message: '网络连接失败，请检查网络后重试' };
    }
  }
  async unauthorized(context, options = {}) {
    context.assert();
    const policy = options.authPolicy || policies.LEGACY_LOGIN_PAGE;
    const handoff = owner => this.unauthorizedHandoff(context, options, policy, owner);
    return [policies.PROTECTED_HOME_MODAL, policies.LEGACY_LOGIN_PAGE].includes(policy)
      ? this.withAccessBlocker(handoff, { clearsIdentity: true }) : handoff();
  }
  async withAccessBlocker(handoff, { clearsIdentity = false } = {}) {
    const audio = this.router?.services?.audio;
    const lease = audio?.acquireBlocker('access', `auth:${this.authEpoch}:${++this.accessSequence}`);
    let active = true, unsubscribe = () => {};
    const owner = { current: () => active, cancel: () => {
      if (!active) return;
      active = false; unsubscribe(); this.accessTransitions.delete(owner); lease?.release();
    } };
    this.accessTransitions.add(owner);
    // The handoff outlives the old page scope, which clear('unauthorized') disposes.
    // A subsequent identity transition releases this lease before its own remount.
    const expectedEpoch = this.authEpoch + (clearsIdentity ? 1 : 0);
    unsubscribe = this.subscribe(({ next }) => {
      if (next.authEpoch !== expectedEpoch) owner.cancel();
    });
    try { return await handoff(owner); }
    finally {
      owner.cancel();
      const slot = this.router?.current;
      // Reconcile the current owner and intent; an old handoff cannot release a newer lease.
      if (!this.router?.pending && slot?.phase === 'mounted' && slot.context.valid()) {
        await audio?.reconcile({ reason: 'access', current: slot.context.valid });
      }
    }
  }
  cancelAccessTransitions(except) {
    for (const owner of this.accessTransitions) if (owner !== except) owner.cancel();
  }
  async unauthorizedHandoff(context, options, policy, accessOwner) {
    const input = [policies.INTERACTIVE_MODAL, policies.SILENT_VISITOR].includes(policy) ? this.router?.captureTransientInput?.() : undefined;
    const cleared = this.clear('unauthorized');
    const abortedByClear = context.signal?.aborted;
    const current = () => {
      this.refresh(); return (!accessOwner || accessOwner.current()) && this.authEpoch === cleared.authEpoch && context.routeCurrent() &&
        (!context.signal?.aborted || abortedByClear);
    };
    if (!current()) return false;
    await options.onUnauthorized?.();
    if (!current()) return false;
    let result;
    if (policy === policies.PROTECTED_HOME_MODAL) {
      result = await this.router?.navigate('/pages/index.html', { replace: true, force: true, reason: 'unauthorized', safety: true, accessOwner });
    } else if (policy === policies.LEGACY_LOGIN_PAGE) {
      result = await this.router?.navigate('/pages/login.html', { replace: true, force: true, reason: 'unauthorized', safety: true, accessOwner });
      return accessOwner.current() && this.authEpoch === cleared.authEpoch && (!result || result.status === 'committed' && this.router.current?.context.routeEpoch === result.routeEpoch);
    } else {
      // Refresh the visible guest instance once after local rollback, keeping its permitted UI snapshot.
      result = await this.router?.navigate(this.win.location.href, { replace: true, force: true, reason: 'unauthorized', safety: true, state: input });
    }
    this.refresh();
    if (accessOwner && !accessOwner.current() || this.authEpoch !== cleared.authEpoch || result && (result.status !== 'committed' || this.router.current?.context.routeEpoch !== result.routeEpoch)) return false;
    if (policy === policies.PROTECTED_HOME_MODAL || policy === policies.INTERACTIVE_MODAL) this.ui?.openLogin?.({ reason: 'unauthorized' });
    return true;
  }
  guardRoute(route, definition) {
    const state = this.refresh();
    if (!definition?.private) return true;
    if (!state.known) return false;
    if (state.authenticated) return true;
    return { redirect: '/pages/index.html', transition: handoff => this.withAccessBlocker(handoff),
      afterCommit: () => { if (this.authEpoch === state.authEpoch) this.ui?.openLogin?.({ reason: 'guard' }); } };
  }
  redirectToLogin() {
    const snapshot = this.refresh();
    if (this.redirecting?.epoch === snapshot.authEpoch) return this.redirecting.promise;
    const transaction = { epoch: snapshot.authEpoch };
    transaction.promise = this.withAccessBlocker(async accessOwner => {
      try {
        const result = await this.router.navigate('/pages/index.html', { replace: true, force: true, reason: 'guard', safety: true, accessOwner });
        if (accessOwner.current() && snapshot.authEpoch === this.authEpoch && result.status === 'committed' && this.router.current?.context.routeEpoch === result.routeEpoch) this.ui?.openLogin?.({ reason: 'guard' });
      } finally { if (this.redirecting === transaction) this.redirecting = null; }
    });
    this.redirecting = transaction; return transaction.promise;
  }
  requireLogin(options = {}) {
    if (this.refresh().authenticated) return true;
    if (options.authPolicy === policies.PROTECTED_HOME_MODAL) this.redirectToLogin();
    else this.ui?.openLogin?.(options);
    return false;
  }
  dispose() { this.cancelAccessTransitions(); this.win.removeEventListener('storage', this.storageEvent); this.listeners.clear(); this.authAttempt++; }
}

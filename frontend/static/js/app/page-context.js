// Every mount owns a fresh scope, including resources acquired before a failed mount.
export class PageScope {
  constructor({ current = () => true, onError = error => console.error(error), ownerId = '' } = {}) {
    this.ownerId = ownerId; this.current = current; this.onError = onError;
    this.controller = new AbortController(); this.closed = false;
    this.resources = new Set(); this.pending = new Set(); this.errors = [];
  }
  get active() { return !this.closed && this.current(); }
  get signal() { return this.controller.signal; }
  report(error) { this.errors.push(error); try { this.onError(error); } catch (_) {} }
  guard(callback) { return (...args) => this.active ? callback(...args) : undefined; }
  own(dispose, { kind = 'resource', priority = 0 } = {}) {
    if (typeof dispose !== 'function') throw new TypeError('资源必须提供清理函数');
    let released = false;
    const record = { kind, priority, release: () => {
      if (released) return; released = true; this.resources.delete(record);
      try {
        const result = dispose();
        return result?.then ? Promise.resolve(result).catch(error => this.report(error)) : result;
      } catch (error) { this.report(error); }
    } };
    if (this.closed) record.release(); else this.resources.add(record);
    return record.release;
  }
  async adopt(promise, dispose, options) {
    const pending = Promise.resolve(promise); this.pending.add(pending);
    try {
      const value = await pending;
      // Register even after invalidation: own invokes the actual disposer immediately.
      if (!this.active && !this.closed) this.invalidate('identity-or-route-expired');
      this.own(() => dispose(value), options);
      return this.active ? value : undefined;
    } finally { this.pending.delete(pending); }
  }
  listen(target, type, handler, options) {
    const wrapped = this.guard(handler); target.addEventListener(type, wrapped, options);
    return this.own(() => target.removeEventListener(type, wrapped, options), { kind: 'listener' });
  }
  timeout(callback, ms) {
    let release;
    const id = setTimeout(() => { release(); if (this.active) callback(); }, ms);
    release = this.own(() => clearTimeout(id), { kind: 'timer' }); return release;
  }
  interval(callback, ms) {
    const id = setInterval(this.guard(callback), ms);
    return this.own(() => clearInterval(id), { kind: 'timer' });
  }
  frame(callback) {
    let release;
    const id = requestAnimationFrame(time => { release(); if (this.active) callback(time); });
    release = this.own(() => cancelAnimationFrame(id), { kind: 'raf' }); return release;
  }
  observe(observer, target, options) {
    observer.observe(target, options); this.own(() => observer.disconnect(), { kind: 'observer' }); return observer;
  }
  invalidate(reason = 'unmount') {
    if (this.closed) return;
    this.closed = true; this.controller.abort(reason);
  }
  dispose(reason = 'unmount') {
    if (this.disposing) return this.disposing;
    this.invalidate(reason);
    // All local stops are invoked synchronously, even when one awaits remote work or throws.
    const work = [...this.resources].sort((a, b) => b.priority - a.priority).map(item => item.release());
    this.disposing = Promise.allSettled(work).then(() => undefined);
    return this.disposing;
  }
  inspect() {
    const byKind = {};
    for (const item of this.resources) byKind[item.kind] = (byKind[item.kind] || 0) + 1;
    return { ownerId: this.ownerId, active: this.active, resources: this.resources.size, pending: this.pending.size, byKind };
  }
}

export function createPageContext({ root, route, reason, router, services, routeEpoch, state,
  isCurrent = () => true, onError }) {
  const identity = services.auth?.snapshot() || { principalId: null, authEpoch: 0 };
  const scope = new PageScope({ ownerId: `route:${routeEpoch}`, onError, current: () => {
    const now = services.auth?.snapshot() || identity;
    return isCurrent() && now.principalId === identity.principalId && now.authEpoch === identity.authEpoch;
  } });
  return Object.freeze({ root, route, params: new URLSearchParams(route.search || ''), reason, router,
    services, principalId: identity.principalId, authEpoch: identity.authEpoch, routeEpoch,
    identity: Object.freeze({ principalId: identity.principalId, authEpoch: identity.authEpoch }),
    signal: scope.signal, cleanup: (fn, options) => scope.own(fn, options), scope, state,
    valid: () => scope.active });
}

export async function mountPage(module, context) {
  let page;
  try {
    page = await module.mount(context);
    if (!page || typeof page.unmount !== 'function') throw new TypeError('页面必须返回unmount');
    context.cleanup(() => page.unmount(), { kind: 'page', priority: 100 });
    if (!context.valid()) { await context.scope.dispose('late-mount'); return null; }
    return Object.freeze({ context, captureState: () => page.captureState?.(),
      unmount: reason => context.scope.dispose(reason), invalidate: reason => context.scope.invalidate(reason) });
  } catch (error) { await context.scope.dispose('mount-failed'); throw error; }
}

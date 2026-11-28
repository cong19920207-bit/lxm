// One owner per H5 document. IndexedDB serializes first-use ids across tabs, including plain HTTP.
(() => {
  if (typeof window === 'undefined' || window.LxmVisitor) return;
  const day = 86400000;
  const endpoint = '/api/h5/visitors/';
  let opening, channel, connection, readyId, retryTimer, draining = false;
  let hidden = document.hidden, lastReturn = 0, lastAction = 0, trailingAction, trailingTimer, restoreReload = false;
  const outstanding = new Map();
  function uuid() {
    const bytes = new Uint8Array(16);
    if (window.crypto?.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
    return [hex.slice(0,8), hex.slice(8,12), hex.slice(12,16), hex.slice(16,20), hex.slice(20)].join('-');
  }
  function openStorage() {
    return new Promise(resolve => {
      let request, timedOut = false;
      const timer = setTimeout(() => { timedOut = true; resolve(null); }, 1500);
      try { request = indexedDB.open('lxm-h5-visits-v1', 1); }
      catch (_) { clearTimeout(timer); resolve(null); return; }
      request.onupgradeneeded = () => {
        request.result.createObjectStore('identity');
        request.result.createObjectStore('pending', { keyPath: 'event_id' });
      };
      request.onsuccess = () => {
        clearTimeout(timer);
        if (timedOut) request.result.close();
        else resolve(request.result);
      };
      request.onerror = () => { clearTimeout(timer); resolve(null); };
    });
  }
  async function transact(store, mode, operation) {
    const db = await connection;
    if (!db) return null;
    return new Promise(resolve => {
      try {
        const tx = db.transaction(store, mode);
        let result = null;
        operation(tx.objectStore(store), value => { result = value; });
        tx.oncomplete = () => resolve(result);
        tx.onabort = tx.onerror = () => resolve(null);
      } catch (_) { resolve(null); }
    });
  }
  function persistentId() {
    return transact('identity', 'readwrite', (store, done) => {
      const q = store.get('visitor');
      q.onsuccess = () => {
        const value = q.result || uuid();
        if (!q.result) store.put(value, 'visitor');
        done(value);
      };
    });
  }
  function accessToken() {
    if (channel === 'public') return null;
    try {
      if (window.AppShell?.services.auth) return window.AppShell.services.auth.readToken();
      return window.localStorage.getItem('token');
    } catch (_) { return null; }
  }
  function entry() {
    if (channel === 'public') return 'public/feed';
    const match = location.pathname.match(/^\/pages\/(index|chat|feed|diary|memory|relationship|settings|login|pet)\.html$/);
    return 'main/' + (match ? match[1] : (document.querySelector('meta[name="lxm-initial-page"]')?.content || 'index'));
  }
  function profile() {
    const ua = navigator.userAgent || '';
    const os = /Android/i.test(ua) ? 'Android' : /iPhone|iPad|iPod/.test(ua) ||
      (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1) ? 'iOS' :
      /Windows NT/.test(ua) ? 'Windows' : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : null;
    const version = ua.match(/Android[ /]([\d.]+)/i) || ua.match(/(?:CPU (?:iPhone )?OS|Mac OS X)[ /]([\d_\.]+)/);
    const browserTokens = [['Edge', /(?:EdgA|EdgiOS|Edg)\/(\d+)/], ['Opera', /OPR\/(\d+)/],
      ['Firefox', /(?:Firefox|FxiOS)\/(\d+)/], ['Chrome', /(?:Chrome|CriOS)\/(\d+)/],
      ['Safari', /Version\/(\d+).*Safari\//]];
    const detected = browserTokens.find(([, pattern]) => pattern.test(ua));
    const androidModel = ua.match(/Android[^;)]*;\s*([^;()]+?)\s+Build\//i)?.[1]?.trim();
    const reducedVersion = /Android 10; K(?:[ )]|;)|Mac OS X 10_15_7.*(?:Chrome|Edg)\//.test(ua);
    const finite = n => Number.isFinite(n) && n > 0 ? n : null;
    const width = finite(window.innerWidth), height = finite(window.innerHeight);
    return {
      device: /iPad|Tablet/i.test(ua) || (/Android/i.test(ua) && !/Mobile/i.test(ua)) ||
        (os === 'iOS' && /Macintosh/.test(ua)) ? '平板' : /Mobile|iPhone|iPod/i.test(ua) ? '手机' : os ? '电脑' : null,
      os, os_version: version && !reducedVersion ? version[1].replaceAll('_', '.') : null,
      model: androidModel && !/^(?:K|Android|Mobile|Unknown|Linux|Generic)$/i.test(androidModel) ? androidModel.slice(0, 80) : null,
      browser: detected?.[0] || null, browser_version: detected ? ua.match(detected[1])[1] : null,
      environment: /MicroMessenger/i.test(ua) ? '微信' : /; wv\)|\bWebView\b/i.test(ua) ? '应用内浏览器' : '浏览器',
      screen_width: finite(screen.width), screen_height: finite(screen.height),
      viewport_width: width, viewport_height: height, orientation: width && height ? (width > height ? '横屏' : '竖屏') : null,
      pixel_ratio: finite(window.devicePixelRatio), processors: finite(navigator.hardwareConcurrency),
    };
  }
  async function post(path, body, token) {
    let timer;
    try {
      const controller = new AbortController();
      timer = setTimeout(() => controller.abort(), 4500);
      const headers = { 'Content-Type': 'application/json' };
      if (channel !== 'public' && token) headers.Authorization = 'Bearer ' + token;
      const response = await fetch(endpoint + path, { method: 'POST', headers, body: JSON.stringify(body),
        credentials: 'omit', mode: 'same-origin', cache: 'no-store', keepalive: true, signal: controller.signal });
      if (!response.ok) return null;
      const reply = await response.json();
      return reply.code === 0 ? reply.data : null;
    } catch (_) { return null; }
    finally { clearTimeout(timer); }
  }
  function save(row) {
    return transact('pending', 'readwrite', store => store.put(row));
  }
  async function forget(key) {
    outstanding.delete(key);
    await transact('pending', 'readwrite', store => store.delete(key));
  }
  async function deliver(row, replay, token) {
    if (Date.now() - Date.parse(row.occurred_at) > day) { await forget(row.event_id); return false; }
    const { nextAttempt, ...body } = row;
    const receipt = await post('events', { ...body, replay }, token);
    if (receipt?.received) { await forget(row.event_id); return true; }
    row.nextAttempt = Date.now() + 15000;
    outstanding.set(row.event_id, row);
    await save(row);
    return false;
  }
  function schedule(delay = 15000) {
    clearTimeout(retryTimer);
    retryTimer = setTimeout(() => { void drain(); }, Math.max(100, delay));
  }
  async function drain() {
    if (draining) return;
    draining = true;
    try {
      const stored = await transact('pending', 'readonly', (store, done) => {
        const q = store.getAll(); q.onsuccess = () => done(q.result);
      });
      const rows = new Map((stored || []).map(row => [row.event_id, row]));
      for (const [key, row] of outstanding) rows.set(key, row);
      let next = Infinity;
      for (const row of rows.values()) {
        if (row.nextAttempt <= Date.now()) {
          if (!(await deliver(row, true, null)) && outstanding.has(row.event_id)) next = Math.min(next, row.nextAttempt);
        } else next = Math.min(next, row.nextAttempt);
      }
      if (Number.isFinite(next)) schedule(next - Date.now());
    } finally { draining = false; }
  }
  async function openPage() {
    const token = accessToken(), at = new Date().toISOString(), page = entry(), sampled = profile();
    const reference = { event_id: uuid(), occurred_at: at, entry: page, visitor_id: await readyId };
    const row = { ...reference, kind: 'open', profile: sampled, nextAttempt: Date.now() + 12000 };
    await save(row);
    // Captured credentials live only in this call. Retries carry the original
    // signed observation if it was available and never persist an account token.
    const context = await post('open-context', reference, token);
    if (context?.witness) { row.witness = context.witness; await save(row); }
    if (!(await deliver(row, false, token))) schedule();
  }
  async function signal(kind, token = accessToken(), at = Date.now(), page = entry()) {
    if (!opening || (channel === 'public' && kind === 'identity')) return false;
    const visitor = await readyId;
    if (!visitor) return false;
    const result = await post('events', { event_id: uuid(), visitor_id: visitor, kind, entry: page,
      occurred_at: new Date(at).toISOString() }, token);
    return !!result?.received;
  }
  function flushAction() {
    clearTimeout(trailingTimer);
    if (!trailingAction) return;
    const { at, page, token } = trailingAction;
    trailingAction = null;
    lastAction = at;
    void signal('interaction', token, at, page);
  }
  function action(e) {
    if (!e.isTrusted || document.hidden) return;
    const at = Date.now();
    trailingAction = { at, page: entry(), token: accessToken() };
    if (at - lastAction >= 10000) flushAction();
    else {
      clearTimeout(trailingTimer);
      trailingTimer = setTimeout(flushAction, Math.max(1, lastAction + 10000 - at));
    }
  }
  function returned() {
    if (restoreReload) return;
    const now = Date.now();
    if (now - lastReturn > 500) void signal('return');
    lastReturn = now;
    void drain();
  }
  function priorNavigation() {
    const activation = window.navigation?.activation;
    const modern = { push: 'navigate', replace: 'navigate', traverse: 'back_forward', reload: 'reload' };
    const type = performance.getEntriesByType('navigation')[0]?.type ||
      modern[activation?.navigationType] || ['navigate', 'reload', 'back_forward'][performance.navigation?.type];
    if (history.state?.lxmVisitorRestore === location.pathname) {
      const { lxmVisitorRestore, ...state } = history.state;
      history.replaceState(state, '');
      if (type === 'reload') return 'return';
    }
    if (type === 'back_forward') return 'return';
    let prior;
    try {
      prior = sessionStorage.getItem('lxm-visitor-departed');
      sessionStorage.removeItem('lxm-visitor-departed');
    } catch (_) { /* The browser's current navigation can still identify a same-tab departure. */ }
    if (type !== 'navigate' || !document.referrer) return 'open';
    const ref = new URL(document.referrer), previous = activation?.from?.url;
    if (ref.origin === location.origin && /^\/pages\/[a-z]+\.html$/.test(ref.pathname) &&
        (prior === ref.pathname || previous && new URL(previous).origin === ref.origin &&
         new URL(previous).pathname === ref.pathname)) return 'navigate';
    return 'open';
  }
  function start(mode) {
    if (opening) return;
    opening = true;
    channel = mode;
    connection = openStorage();
    readyId = persistentId();
    const first = priorNavigation();
    if (first === 'open') void openPage().catch(() => {});
    else void signal(first);
    void drain();
    addEventListener('online', () => void drain());
    addEventListener('pagehide', () => {
      flushAction();
      try { sessionStorage.setItem('lxm-visitor-departed', location.pathname); } catch (_) {}
    });
    addEventListener('pageshow', event => {
      if (!event.persisted) return;
      try { sessionStorage.removeItem('lxm-visitor-departed'); } catch (_) {}
      if (!document.hidden) returned();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { hidden = true; flushAction(); }
      else if (hidden) { hidden = false; returned(); }
    });
    for (const name of ['pointerup', 'keydown', 'wheel']) document.addEventListener(name, action, { passive: true });
  }
  // The independent feed refreshes its document when restored from the back/forward cache.
  // Carry that native return through the automatic reload without counting another opening.
  function prepareRestoreReload() {
    try {
      history.replaceState({ ...history.state, lxmVisitorRestore: location.pathname }, '');
      restoreReload = true;
    } catch (_) { /* A restored document can still report its foreground transition. */ }
  }
  window.LxmVisitor = { start, signal, profile, prepareRestoreReload };
  const mode = document.currentScript?.dataset.visitorEntry;
  if (mode === 'main' || mode === 'public') start(mode);
})();

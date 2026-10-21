/* Anonymous, event-driven catalog snapshots. This module never schedules polling. */
(function () {
  'use strict'
  if (window.BgmCatalog) return
  const KEY = 'lxm_bgm_catalog_v1'
  const limits = Object.freeze({ freshMs: 300000, maxAgeMs: 1800000, totalMs: 30000, directoryMs: 8000,
    directoryRetries: 1, backoffMs: 1000, mediaMs: 15000, candidates: 3, forcedRefreshes: 1, cooldownMs: 30000 })
  const copy = value => value === null ? null : JSON.parse(JSON.stringify(value))
  function validate(value) {
    const fail = () => { throw new TypeError('Invalid public BGM catalog') }
    if (!value || !Number.isSafeInteger(value.catalog_version) || value.catalog_version < 0 || !Array.isArray(value.tracks)) fail()
    const ids = new Set()
    const https = value => {
      if (typeof value !== 'string') return false
      try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password } catch (_) { return false }
    }
    const tracks = value.tracks.map(track => {
      if (!track || typeof track.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(track.id) || ids.has(track.id) ||
          typeof track.name !== 'string' || !track.name.trim() || typeof track.media_version !== 'string' || !track.media_version ||
          !https(track.audio_url) || !Number.isFinite(track.duration_seconds) || track.duration_seconds <= 0 || track.duration_seconds > 300 ||
          track.cover_url !== null && !https(track.cover_url) || track.cover_version !== null && typeof track.cover_version !== 'string') fail()
      ids.add(track.id)
      return { id: track.id, name: track.name, media_version: track.media_version, audio_url: track.audio_url,
        duration_seconds: track.duration_seconds, cover_url: track.cover_url, cover_version: track.cover_version }
    })
    if (tracks.length ? !ids.has(value.default_track_id) : value.default_track_id !== null) fail()
    return { catalog_version: value.catalog_version, default_track_id: value.default_track_id, tracks }
  }
  function create(options = {}) {
    const fetcher = options.fetch || window.fetch.bind(window), wallNow = options.wallNow || Date.now
    const now = options.now || (() => performance.now()), later = options.setTimeout || setTimeout, clear = options.clearTimeout || clearTimeout
    let storage, snapshot = null, successAt = null, failureAt = null, flight = null, scope = 'session'
    let anchorAge = 0, anchorMono = now()
    try { storage = options.storage || window.sessionStorage } catch (_) { scope = 'memory' }
    try {
      const saved = JSON.parse(storage && storage.getItem(KEY) || 'null')
      if (saved && saved.version === 1) {
        if (Number.isFinite(saved.successAt) && saved.successAt > 0) { snapshot = validate(saved.catalog); successAt = saved.successAt }
        if (Number.isFinite(saved.failureAt) && saved.failureAt > 0) failureAt = saved.failureAt
        anchorAge = successAt === null ? Infinity : wallNow() - successAt
      }
    } catch (_) { /* Invalid or unavailable storage is not an empty server catalog. */ }
    function reload() {
      try {
        const saved = JSON.parse(storage && storage.getItem(KEY) || 'null')
        if (!saved || saved.version !== 1 || !Number.isFinite(saved.successAt) || saved.successAt <= 0) return
        const next = validate(saved.catalog)
        if (snapshot && (next.catalog_version < snapshot.catalog_version || saved.successAt < successAt)) return
        snapshot = next; successAt = saved.successAt; anchorAge = wallNow() - successAt; anchorMono = now()
        failureAt = Number.isFinite(saved.failureAt) && saved.failureAt > 0 ? saved.failureAt : null
      } catch (_) { /* Retain the old finite-age snapshot; storage is never an empty catalog. */ }
    }
    function save() {
      try {
        if (!storage) throw new Error('Session storage unavailable')
        storage.setItem(KEY, JSON.stringify({ version: 1, catalog: snapshot, successAt, failureAt }))
      } catch (_) { scope = 'memory' }
    }
    function age() {
      const wall = wallNow() - successAt, elapsed = now() - anchorMono
      if (successAt === null || !Number.isFinite(wall) || wall < 0 || !Number.isFinite(elapsed) || elapsed < 0 || anchorAge < 0) return Infinity
      return Math.max(wall, anchorAge + elapsed)
    }
    function peek() {
      const elapsed = age(), failedAge = wallNow() - failureAt
      return { catalog: copy(snapshot), successAt, failureAt, ageMs: elapsed, fresh: !!snapshot && elapsed < limits.freshMs,
        usable: !!snapshot && elapsed < limits.maxAgeMs, cooling: failureAt !== null && failedAge >= 0 && failedAge < limits.cooldownMs, scope }
    }
    function request(timeoutMs) {
      const abort = new AbortController()
      let valid = true, timer
      const task = new Promise((resolve, reject) => {
        timer = later(() => { valid = false; abort.abort(); reject(new Error('BGM directory timeout')) }, Math.min(limits.directoryMs, timeoutMs))
        Promise.resolve().then(() => fetcher('/api/bgm/catalog', { method: 'GET', credentials: 'omit', cache: 'no-store',
          referrerPolicy: 'no-referrer', redirect: 'error', headers: { Accept: 'application/json' }, signal: abort.signal }))
          .then(async response => {
            if (!response.ok) throw new Error('BGM directory unavailable')
            const body = await response.json()
            if (body.code !== 0) throw new Error('BGM directory unavailable')
            const next = validate(body.data)
            if (!valid) return
            // Older snapshots cannot extend the lifetime of a newer catalog.
            if (snapshot && next.catalog_version < snapshot.catalog_version) throw new Error('BGM directory version regressed')
            snapshot = next; successAt = wallNow(); anchorAge = 0; anchorMono = now(); failureAt = null; save()
            resolve(copy(snapshot))
          }).catch(error => { if (valid) reject(error) })
      }).catch(error => { failureAt = wallNow(); save(); throw error }).finally(() => { valid = false; clear(timer); if (flight === task) flight = null })
      flight = task
      return task
    }
    function read({ force = false, bypassCooldown = false, signal, timeoutMs = limits.directoryMs } = {}) {
      if (signal && signal.aborted) return Promise.reject(new DOMException('Cancelled', 'AbortError'))
      const cached = peek()
      if (!force && cached.fresh) return Promise.resolve(cached.catalog)
      if (!force && !bypassCooldown && cached.cooling) return Promise.reject(new Error('BGM directory cooling down'))
      if (!(timeoutMs > 0)) return Promise.reject(new Error('BGM directory budget exhausted'))
      const shared = flight || request(timeoutMs)
      // Cancelling one consumer must not cancel another panel/player consumer.
      return new Promise((resolve, reject) => {
        let timer
        const cancel = () => finish(reject, new DOMException('Cancelled', 'AbortError'))
        const finish = (fn, value) => { clear(timer); if (signal) signal.removeEventListener('abort', cancel); fn(value) }
        timer = later(() => finish(reject, new Error('BGM directory budget exhausted')), timeoutMs)
        if (signal) signal.addEventListener('abort', cancel, { once: true })
        shared.then(value => finish(resolve, copy(value)), error => finish(reject, error))
      })
    }
    return Object.freeze({ peek, read, reload })
  }
  let singleton
  window.BgmCatalog = Object.freeze({ create, validate, limits, key: KEY,
    getDocumentInstance() { return singleton || (singleton = create()) } })
})()

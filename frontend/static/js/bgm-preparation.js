/* Optional single metadata hint. Actual selection always stays in BgmPlayer. */
(function () {
  'use strict'
  if (window.BgmPreparation) return
  function create(options = {}) {
    const player = options.player, doc = options.document || document, host = options.window || window
    const network = options.navigator || navigator, audioFactory = options.audioFactory || (() => new Audio())
    const later = options.setTimeout || setTimeout, clear = options.clearTimeout || clearTimeout
    const maxAge = window.BgmCatalog.limits.maxAgeMs
    let destroyed = false, current = null, scheduled = null, attempted = '', status = 'idle', reason = null
    const bindings = []
    function bind(target, event, fn) {
      if (!target || !target.addEventListener) return
      target.addEventListener(event, fn); bindings.push(() => target.removeEventListener(event, fn))
    }
    function eligible() {
      const s = player.state(), connection = network.connection || network.mozConnection || network.webkitConnection
      if (destroyed || s.destroyed || doc.hidden || doc.readyState !== 'complete' || doc.getElementById('home-loading-screen') ||
          s.actual !== 'playing' || s.intent !== 'play' || s.closed || s.recoveryRequired || s.blockers.length ||
          !['ready', 'stale', 'loading'].includes(s.catalogStatus) || !Number.isFinite(s.catalogAgeMs) || s.catalogAgeMs < 0 || s.catalogAgeMs >= maxAge ||
          !s.track || s.tracks.length < 2 || network.onLine === false || connection && (connection.saveData === true ||
          ['slow-2g', '2g', '3g'].includes(connection.effectiveType) || Number.isFinite(connection.downlink) && connection.downlink > 0 && connection.downlink < 1)) return null
      const duration = s.track.duration_seconds, remaining = duration - s.position
      // 20 seconds is an upper bound; short tracks wait until their last quarter.
      if (!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(s.position) || s.position < 0 || remaining <= 0 || remaining > Math.min(20, duration / 4)) return null
      const index = s.tracks.findIndex(t => t.id === s.track.id && t.media_version === s.track.media_version)
      if (index < 0) return null
      const next = s.tracks[(index + 1) % s.tracks.length]
      try { const url = new URL(next.audio_url); if (url.protocol !== 'https:' || url.username || url.password) return null } catch (_) { return null }
      return { track: next, key: JSON.stringify([s.generation, s.track.id, s.track.media_version, s.track.audio_url, next.id, next.media_version, next.audio_url]) }
    }
    function dispose(entry) {
      if (!entry) return
      clear(entry.timer)
      for (const [event, fn] of entry.handlers) entry.media.removeEventListener(event, fn)
      try { entry.media.pause(); entry.media.removeAttribute('src'); entry.media.load() } catch (_) {}
    }
    function cancel() {
      if (scheduled) { clear(scheduled.timer); scheduled = null }
      const old = current; current = null; dispose(old)
    }
    function start(expected) {
      const next = eligible()
      if (!next || next.key !== expected.key || player.state().catalogStatus === 'loading') return
      attempted = next.key
      let media
      try {
        media = audioFactory()
        if (!('preload' in media) || media.canPlayType && !media.canPlayType('audio/mp4; codecs="mp4a.40.2"')) { status = 'skipped'; reason = 'capability'; return }
        media.preload = 'metadata'; media.muted = true; media.volume = 0; media.loop = false; media.crossOrigin = 'anonymous'
        media.setAttribute('playsinline', '')
        if ('fetchPriority' in media) media.fetchPriority = 'low'
        const entry = { media, key: next.key, track: next.track, handlers: [], timer: null }
        current = entry; status = 'loading'; reason = null
        const failed = why => {
          if (current !== entry) return
          current = null; dispose(entry); status = 'failed'; reason = why
        }
        const ready = () => { if (current === entry) { clear(entry.timer); entry.timer = null; status = 'ready' } }
        entry.handlers = [['loadedmetadata', ready], ['error', () => failed('media')]]
        for (const [event, fn] of entry.handlers) media.addEventListener(event, fn)
        entry.timer = later(() => failed('metadata-timeout'), 5000)
        media.src = next.track.audio_url; media.load()
      } catch (_) { cancel(); status = 'skipped'; reason = 'capability' }
    }
    function update() {
      const next = eligible()
      if (!next) { cancel(); status = 'idle'; reason = null; return }
      if (current && current.key === next.key || scheduled && scheduled.key === next.key) return
      cancel()
      // A still-valid cached catalog can retain its candidate while refreshing.
      // Do not start new optional work until that refresh has settled.
      if (player.state().catalogStatus === 'loading') return
      if (attempted === next.key) return
      // Yield to the current playback and main-page work before requesting optional bytes.
      const pending = { key: next.key, timer: null }; scheduled = pending
      pending.timer = later(() => { if (scheduled !== pending) return; scheduled = null; start(next) }, 0)
    }
    const unsubscribe = player.subscribe(update)
    bind(doc, 'visibilitychange', update); bind(host, 'load', update)
    bind(network.connection || network.mozConnection || network.webkitConnection, 'change', update)
    function destroy() {
      if (destroyed) return
      destroyed = true; unsubscribe(); bindings.forEach(fn => fn()); cancel(); status = 'idle'
    }
    return Object.freeze({ destroy, state: () => ({ status, reason, candidate: current ? { id: current.track.id, mediaVersion: current.track.media_version } : null }) })
  }
  window.BgmPreparation = Object.freeze({ create })
})()

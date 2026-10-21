/* Explicit short-audio activities; no provider, account or independent TTS playback. */
(function () {
  'use strict'
  if (window.BgmDucking) return
  function create(options = {}) {
    const player = options.player, output = options.output || window.BgmOutput
    const ratio = options.ratio === undefined ? 0.25 : options.ratio
    const later = options.setTimeout || setTimeout, clear = options.clearTimeout || clearTimeout
    if (!player || !output || !Number.isFinite(ratio) || ratio < 0 || ratio > 1) throw new TypeError('Invalid short-audio adapter')
    const entries = new Map()
    let destroyed = false, paused = false, syncing = false, revision = 0
    function eligible() {
      const s = player.state()
      return !s.destroyed && s.intent === 'play' && !s.closed && !s.recoveryRequired && !s.blockers.length
    }
    function synchronize() {
      if (syncing) return
      syncing = true
      try {
        const active = entries.size > 0
        let precise = !!output.capabilities().preciseVolume
        try { output.setMultiplier(active && precise ? ratio : 1, { fade: true }) }
        catch (_) { precise = false }
        const mustPause = active && !precise
        if (mustPause && !paused) { paused = true; player.block('short-audio') }
        else if (!mustPause && paused) {
          paused = false; player.unblock('short-audio')
          const current = revision
          // A newer activity, pause, close or call wins over this deferred release.
          Promise.resolve().then(() => { if (current === revision && !paused && eligible()) void player.resume() })
        }
      } finally { syncing = false }
    }
    function release(entry) {
      if (entries.get(entry.id) !== entry) return false
      clear(entry.timer); entries.delete(entry.id); revision++; synchronize(); return true
    }
    function begin(id, { timeoutMs = 30000 } = {}) {
      if (destroyed) return null
      if (typeof id !== 'string' || !id || id.length > 128 || !Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new TypeError('Invalid short-audio activity')
      if (entries.has(id)) return entries.get(id).lease
      const entry = { id, timer: null, lease: null }
      entry.lease = Object.freeze({ id, end: () => release(entry), cancel: () => release(entry), destroy: () => release(entry) })
      entries.set(id, entry); revision++; entry.timer = later(() => release(entry), timeoutMs); synchronize()
      return entry.lease
    }
    const unsubscribe = player.subscribe(() => { if (!destroyed) synchronize() })
    function destroy() {
      if (destroyed) return
      destroyed = true; unsubscribe()
      for (const entry of entries.values()) clear(entry.timer)
      entries.clear(); revision++; synchronize()
    }
    return Object.freeze({ begin, destroy, state: () => ({ count: entries.size, paused, ratio, destroyed }) })
  }
  window.BgmDucking = Object.freeze({ create })
})()

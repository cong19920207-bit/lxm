/* Explicit ordinary-media leases. VoiceEntry remains the separate call owner. */
(function () {
  'use strict'
  if (window.BgmMedia) return
  function create({ player } = {}) {
    if (!player) throw new TypeError('BGM player required')
    const entries = new Map()
    let destroyed = false, revision = 0
    const silent = Object.freeze({ end: () => false, cancel: () => false, destroy: () => false })
    function eligible() {
      const s = player.state()
      return !s.destroyed && s.intent === 'play' && !s.closed && !s.recoveryRequired && !s.blockers.length
    }
    function release(entry, { resumeAllowed = false } = {}) {
      if (entries.get(entry.id) !== entry) return false
      entries.delete(entry.id); revision++
      const s = player.state()
      if (resumeAllowed !== true && !s.destroyed && s.intent === 'play' && !s.closed) player.requireRecovery('permission')
      if (!entries.size) {
        player.unblock('ordinary-media')
        const current = revision
        Promise.resolve().then(() => { if (!destroyed && current === revision && !entries.size && eligible()) void player.resume() })
      }
      return true
    }
    function begin(id, { audible = true, kind = 'media' } = {}) {
      if (destroyed) return null
      if (typeof id !== 'string' || !id || id.length > 128 || !['media', 'recording'].includes(kind)) throw new TypeError('Invalid media activity')
      if (entries.has(id)) return entries.get(id).lease
      if (kind === 'media' && audible === false) return silent
      const entry = { id, lease: null }
      entry.lease = Object.freeze({ id, end: options => release(entry, options), cancel: options => release(entry, options), destroy: options => release(entry, options) })
      entries.set(id, entry); revision++; player.block('ordinary-media'); return entry.lease
    }
    function destroy() {
      if (destroyed) return
      destroyed = true
      for (const entry of [...entries.values()]) release(entry)
    }
    return Object.freeze({ begin, destroy, state: () => ({ count: entries.size, destroyed }) })
  }
  window.BgmMedia = Object.freeze({ create })
})()

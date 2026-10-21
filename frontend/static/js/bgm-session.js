/* Small, per-tab state. No account namespace, cross-tab broadcasts or wall-time progress. */
(function () {
  'use strict'
  if (window.BgmSession) return
  const KEY = 'lxm_bgm_session_v1', UNSAFE = 'lxm_bgm_session_unsafe_v1', PROBE = 'lxm_bgm_session_probe_v1'
  const note = '本页音乐控制仍可使用；当前无法可靠保存会话，跨页恢复受限。'
  const fallback = () => ({ trackId: null, mediaVersion: null, position: 0, intent: 'pause', closed: false, recoveryRequired: false, bubble: { x: 1, y: 0.6 } })
  function normalize(value) {
    if (!value || value.version !== 1 || !['play', 'pause'].includes(value.intent) || typeof value.closed !== 'boolean' || typeof value.recoveryRequired !== 'boolean' || !Number.isSafeInteger(value.revision) || value.revision < 0) return null
    const id = typeof value.trackId === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value.trackId) ? value.trackId : null
    const version = typeof value.mediaVersion === 'string' && value.mediaVersion ? value.mediaVersion : null
    const coordinate = (v, otherwise) => Number.isFinite(v) && v >= 0 && v <= 1 ? v : otherwise
    return { trackId: id, mediaVersion: version, position: Number.isFinite(value.position) && value.position >= 0 && value.position <= 300 ? value.position : 0,
      intent: value.intent, closed: value.closed, recoveryRequired: value.recoveryRequired, revision: value.revision,
      bubble: { x: coordinate(value.bubble && value.bubble.x, 1), y: coordinate(value.bubble && value.bubble.y, 0.6) } }
  }
  function create(options = {}) {
    let storage, reliable = false, memory = null, revision = 0, unknown = false, warning = ''
    try { storage = options.storage || window.sessionStorage } catch (_) {}
    function failed() {
      reliable = false; warning = note
      // A small marker can sometimes still be written when the full checkpoint cannot.
      try { storage.setItem(UNSAFE, '1') } catch (_) {}
    }
    function inspect() {
      let raw = null, parsed = null, unsafe = false
      try {
        raw = storage.getItem(KEY)
        if (raw !== null) parsed = JSON.parse(raw)
        unsafe = storage.getItem(UNSAFE) === '1'
        unknown = !!(parsed && parsed.version !== 1)
        const token = String(Date.now()) + ':' + Math.random()
        storage.setItem(PROBE, token)
        if (storage.getItem(PROBE) !== token) throw new Error('Session write did not persist')
        storage.removeItem(PROBE)
        if (storage.getItem(PROBE) !== null) throw new Error('Session probe not removed')
        reliable = !unknown; warning = reliable && !unsafe ? '' : note
      } catch (_) { failed() }
      const saved = normalize(parsed)
      if (saved) revision = Math.max(revision, saved.revision)
      if (raw !== null && !saved) { reliable = false; warning = note }
      if (!reliable || unsafe) {
        const safe = memory || saved || fallback()
        memory = { ...safe, intent: 'pause' }
        return { reliable: false, session: { ...memory, bubble: { ...memory.bubble } }, note: warning || note }
      }
      memory = saved
      return { reliable: true, session: saved && { ...saved, bubble: { ...saved.bubble } }, note: '' }
    }
    function save(checkpoint, bubble) {
      const record = { version: 1, ...checkpoint, revision: ++revision, bubble: bubble || memory && memory.bubble || fallback().bubble }
      const valid = normalize(record)
      if (!valid) { failed(); return { reliable: false, note } }
      memory = valid
      if (unknown) { failed(); return { reliable: false, note } }
      try {
        const serialized = JSON.stringify({ version: 1, ...valid })
        storage.setItem(KEY, serialized)
        if (storage.getItem(KEY) !== serialized) throw new Error('Session checkpoint not persisted')
        storage.removeItem(UNSAFE)
        if (storage.getItem(UNSAFE) !== null) throw new Error('Session unsafe marker not cleared')
        reliable = true; warning = ''
      } catch (_) { failed() }
      return { reliable, note: warning }
    }
    return Object.freeze({ inspect, save, status: () => ({ reliable, note: warning }) })
  }
  window.BgmSession = Object.freeze({ create, key: KEY, unsafeKey: UNSAFE })
})()

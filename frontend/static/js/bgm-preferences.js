/* Local choices only. Playback intent and account state belong to their owners. */
(function () {
  'use strict'
  const defaults = Object.freeze({ fadeEnabled: true, autoplayEnabled: true, volume: 0.30, lastSelectedTrackId: null })
  const keys = Object.freeze({ fadeEnabled: 'lxm_bgm_fade_enabled', autoplayEnabled: 'lxm_bgm_autoplay_enabled',
    volume: 'lxm_bgm_volume', lastSelectedTrackId: 'lxm_bgm_last_selected_track_id' })
  const sessionKeys = Object.freeze(Object.fromEntries(Object.entries(keys).map(([field, key]) => [field, key + '_session'])))
  const memory = new Map()
  let revision = 0
  const notes = { local: '', session: '选择仅本次生效，暂时无法长期保存。',
    memory: '选择仅在本页生效，暂时无法保存；离开页面后可能恢复原设置。' }

  function storage(kind, method, key, value) {
    try { return { ok: true, value: window[kind][method](key, value) } }
    catch (_) { return { ok: false, value: null } }
  }
  function valid(field, value) {
    if (field === 'fadeEnabled' || field === 'autoplayEnabled' || field === 'motionEnabled') return typeof value === 'boolean'
    if (field === 'volume') return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    if (field === 'lastSelectedTrackId') return value === null || (typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value))
    return false
  }
  function decode(field, stored) {
    try {
      const record = JSON.parse(stored.value)
      if (!record || typeof record !== 'object') return { ...stored, record: null }
      // Preserve future records instead of treating them as this version's schema.
      if (record.version !== 1) return { ...stored, unknown: true, record: null }
      if (!valid(field, record.value) || !Number.isSafeInteger(record.revision) || record.revision < 0) return { ...stored, record: null }
      revision = Math.max(revision, record.revision)
      return { ...stored, record }
    } catch (_) { return { ...stored, record: null } }
  }
  function sources(field) {
    return [decode(field, storage('localStorage', 'getItem', keys[field])),
      decode(field, storage('sessionStorage', 'getItem', sessionKeys[field]))]
  }
  function choice(value, scope, note = notes[scope]) { return { value, scope, note } }
  function motion(result) {
    return choice(result.enabled, result.note.includes('无法读取') ? 'default'
      : result.note.includes('本页') ? 'memory' : result.note ? 'session' : 'local', result.note)
  }
  function read(field) {
    if (field === 'motionEnabled') return motion(window.HomePreferences.readMotion())
    if (!Object.hasOwn(keys, field)) throw new TypeError('Invalid BGM preference field')
    if (memory.has(field)) return { ...memory.get(field) }
    const [local, session] = sources(field)
    if (session.record && (!local.record || session.record.revision > local.record.revision)) return choice(session.record.value, 'session')
    if (local.record) return choice(local.record.value, 'local')
    const note = local.unknown || session.unknown ? '已保存的设置版本暂不支持，本次采用默认值。'
      : !local.ok ? '无法读取已保存的选择，本次采用默认值。' : ''
    return choice(defaults[field], 'default', note)
  }
  function write(field, value) {
    if (!valid(field, value)) throw new TypeError('Invalid BGM preference value')
    if (field === 'motionEnabled') return motion(window.HomePreferences.writeMotion(value))
    const [local, session] = sources(field)
    revision = Math.max(Date.now(), revision + 1)
    const serialized = JSON.stringify({ version: 1, value, revision })
    // Do not replace a record whose version cannot be understood, or an unreadable one.
    if (local.ok && !local.unknown && storage('localStorage', 'setItem', keys[field], serialized).ok) {
      if (!session.unknown) storage('sessionStorage', 'removeItem', sessionKeys[field])
      memory.delete(field)
      return choice(value, 'local')
    }
    if (session.ok && !session.unknown && storage('sessionStorage', 'setItem', sessionKeys[field], serialized).ok) {
      memory.delete(field)
      return choice(value, 'session')
    }
    const result = choice(value, 'memory')
    memory.set(field, result)
    return { ...result }
  }
  function get() {
    return Object.fromEntries(['motionEnabled', ...Object.keys(defaults)].map(field => [field, read(field).value]))
  }
  window.BgmPreferences = Object.freeze({ keys, sessionKeys, read, write, get })
})()

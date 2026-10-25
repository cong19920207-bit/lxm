/* Single-document intent owner. Output, catalog I/O and page storage are injected. */
(function () {
  'use strict'
  if (window.BgmController) return
  let documentInstance = null
  const manualSources = new Set(['home', 'home-list', 'bubble', 'retry'])
  const safePosition = (value, track) => typeof value === 'number' && Number.isFinite(value) && value >= 0 && track && value <= track.duration_seconds ? value : 0
  function normalizeCatalog(value) {
    if (!value || !Number.isSafeInteger(value.catalog_version) || value.catalog_version < 0 || !Array.isArray(value.tracks)) throw new TypeError('Invalid BGM catalog')
    const ids = new Set()
    const tracks = value.tracks.map(track => {
      if (!track || typeof track.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(track.id) || ids.has(track.id) ||
          typeof track.name !== 'string' || typeof track.media_version !== 'string' || !track.media_version ||
          typeof track.duration_seconds !== 'number' || !Number.isFinite(track.duration_seconds) || track.duration_seconds <= 0 || track.duration_seconds > 300) throw new TypeError('Invalid BGM track')
      const url = new URL(track.audio_url)
      if (url.protocol !== 'https:' || url.username || url.password) throw new TypeError('Invalid BGM media URL')
      ids.add(track.id)
      return Object.freeze({ id: track.id, name: track.name, media_version: track.media_version, audio_url: track.audio_url,
        duration_seconds: track.duration_seconds, cover_url: track.cover_url || null, cover_version: track.cover_version || null })
    })
    return { catalog_version: value.catalog_version, default_track_id: value.default_track_id, tracks }
  }
  function create(options = {}) {
    const preferences = options.preferences || window.BgmPreferences
    const outputFactory = options.outputFactory || (window.BgmOutput && window.BgmOutput.create)
    if (!preferences || typeof outputFactory !== 'function') throw new TypeError('BGM output and preferences required')
    let catalog = { catalog_version: 0, default_track_id: null, tracks: [] }
    let selected = null, position = 0, intent = 'pause', closed = false, actual = 'idle', failure = null
    let recoveryRequired = false, initialized = false, destroyed = false, generation = 0, output = null
    let pending = null, abort = new AbortController(), ending = false, outputEpoch = -1, pausing = null
    const blockers = new Set(), listeners = new Set(), retiring = new Set()
    const eligible = () => !destroyed && intent === 'play' && !closed && !blockers.size && !recoveryRequired && !!selected
    const chooseDefault = () => catalog.tracks.find(t => t.id === catalog.default_track_id) || catalog.tracks[0] || null
    const status = node => node ? node.getState() : null
    function state() {
      return { intent, closed, actual, failure: failure && { ...failure }, recoveryRequired, position, generation,
        track: selected && { ...selected }, catalogVersion: catalog.catalog_version,
        tracks: catalog.tracks.map(t => ({ ...t })), blockers: [...blockers], nextEnabled: !closed && catalog.tracks.length > 1, destroyed,
        capabilities: outputFactory.capabilities ? outputFactory.capabilities() : null }
    }
    function emit() {
      for (const listener of listeners) { try { listener(state()) } catch (_) {} }
    }
    function capture() {
      if (output && selected) position = safePosition(status(output).position, selected)
      return { trackId: selected && selected.id, mediaVersion: selected && selected.media_version, position, intent, closed, recoveryRequired }
    }
    function cancel() {
      generation++; abort.abort(); abort = new AbortController(); pending = null; ending = false
      pausing = null
      for (const node of retiring) { node.silence(); node.destroy() }
      retiring.clear()
    }
    function silence() { if (output) output.silence() }
    function discard() {
      const old = output; output = null
      if (old) { old.silence(); old.destroy() }
    }
    function resting() { actual = !selected ? 'empty' : blockers.size ? 'blocked' : 'paused' }
    function markFailure(error, node = output) {
      cancel()
      if (node) node.silence()
      const permission = error && (error.name === 'NotAllowedError' || error.name === 'OutputBlockedError')
      failure = { category: permission ? 'permission' : 'resource', message: permission ? '点按播放开始音乐' : '音乐播放失败，请重试' }
      if (permission) recoveryRequired = true
      actual = permission ? 'blocked' : 'error'; emit()
    }
    function onMedia(node, type) {
      if (retiring.has(node) || pausing === node) return
      if (node !== output || destroyed) { node.silence(); return }
      if (!eligible() || outputEpoch !== generation) { node.silence(); return }
      const media = status(node)
      if (type === 'playing') {
        if (media.playing && media.contextRunning) { actual = 'playing'; failure = null; emit() }
        else if (!media.contextRunning) markFailure({ name: 'OutputBlockedError' }, node)
      } else if (type === 'timeupdate') {
        if (media.playing && media.contextRunning) { position = safePosition(media.position, selected); emit() }
      } else if (type === 'waiting') { actual = 'loading'; emit() }
      else if (type === 'pause' && !media.playing && media.paused !== false) {
        if (!media.ended) markFailure({ name: 'OutputBlockedError' }, node)
        else { actual = 'paused'; emit() }
      }
      else if (type === 'error') markFailure({ name: 'MediaError' }, node)
      else if (type === 'ended' && media.ended && !ending) {
        if (options.onEnded) {
          const checkpoint = capture(); cancel(); actual = 'paused'; emit()
          const epoch = generation
          Promise.resolve(options.onEnded(checkpoint)).catch(error => { if (epoch === generation && eligible()) markFailure(error) })
        } else void advanceAfterEnd(node)
      }
      // Metadata readiness alone never changes actual output to playing.
    }
    async function start() {
      if (!eligible()) return false
      if (output && actual === 'playing' && status(output).playing && status(output).contextRunning) return true
      if (pending) return pending
      const epoch = generation, signal = abort.signal
      let node = output
      try {
        if (!node) {
          node = outputFactory({ ...selected }, type => onMedia(node, type))
          output = node; node.seek(position)
        }
      } catch (error) { markFailure(error); return false }
      outputEpoch = epoch; actual = 'loading'; failure = null; emit()
      const task = (async () => {
        try {
          await node.play({ signal })
          if (epoch !== generation || signal.aborted || node !== output || !eligible()) {
            if (node !== output || !eligible()) node.silence()
            return false
          }
          const media = status(node)
          if (!media.contextRunning) { markFailure({ name: 'OutputBlockedError' }, node); return false }
          if (media.playing) { actual = 'playing'; position = safePosition(media.position, selected); emit() }
          return media.playing
        } catch (error) {
          if (epoch === generation && !signal.aborted && node === output && eligible()) markFailure(error, node)
          else if (node !== output || !eligible()) node.silence()
          return false
        }
      })()
      pending = task
      void task.then(() => { if (pending === task) pending = null })
      return task
    }
    function initialize(value, { session = null } = {}) {
      if (initialized || destroyed) return state()
      catalog = normalizeCatalog(value); initialized = true
      const validSession = session && ['play', 'pause'].includes(session.intent) && typeof session.closed === 'boolean'
      selected = validSession && catalog.tracks.find(t => t.id === session.trackId) ||
        catalog.tracks.find(t => t.id === preferences.read('lastSelectedTrackId').value) || chooseDefault()
      intent = validSession ? session.intent : preferences.read('autoplayEnabled').value ? 'play' : 'pause'
      closed = validSession ? session.closed : false
      recoveryRequired = !!(validSession && session.recoveryRequired)
      position = validSession && selected && session.trackId === selected.id && session.mediaVersion === selected.media_version ? safePosition(session.position, selected) : 0
      resting(); emit(); return state()
    }
    function setCatalog(value, { initialCheckpoint = null } = {}) {
      const next = normalizeCatalog(value)
      if (next.catalog_version < catalog.catalog_version) return false
      catalog = next
      const preferred = initialCheckpoint && (catalog.tracks.find(t => t.id === initialCheckpoint.trackId) ||
        catalog.tracks.find(t => t.id === preferences.read('lastSelectedTrackId').value))
      const replacement = preferred || selected && catalog.tracks.find(t => t.id === selected.id) || chooseDefault()
      const same = selected && replacement && selected.id === replacement.id && selected.media_version === replacement.media_version && selected.audio_url === replacement.audio_url
      if (!same) {
        cancel(); discard(); selected = replacement
        position = initialCheckpoint && selected && selected.id === initialCheckpoint.trackId && selected.media_version === initialCheckpoint.mediaVersion ? safePosition(initialCheckpoint.position, selected) : 0
        resting()
      }
      else selected = replacement
      emit(); return !same
    }
    async function play({ source = 'automatic', defer = false } = {}) {
      if (destroyed) return false
      if (!manualSources.has(source) && intent !== 'play') return false
      if (closed && (source !== 'home' || blockers.size)) return false
      if (closed) closed = false
      intent = 'play'
      if (manualSources.has(source)) { recoveryRequired = false; failure = null }
      if (blockers.size || recoveryRequired) { resting(); emit(); return false }
      if (actual === 'playing' && output && status(output).playing && status(output).contextRunning) return true
      cancel(); emit(); return defer || !selected ? false : start()
    }
    function pause() {
      if (destroyed) return
      intent = 'pause'; capture(); cancel()
      const node = output, epoch = generation
      if (!node || !node.fadeOut || !status(node).playing) { silence(); resting(); emit(); return }
      pausing = node; actual = 'pausing'; emit()
      return node.fadeOut({ signal: abort.signal }).catch(() => node.silence()).then(() => {
        if (epoch !== generation || node !== output) return
        capture(); pausing = null; resting(); emit()
      })
    }
    function close() {
      if (destroyed) return
      intent = 'pause'; closed = true; capture(); cancel(); silence(); resting(); emit()
    }
    async function select(id, { manual = true, source = 'home-list', resume = true, startPosition = null } = {}) {
      const track = catalog.tracks.find(t => t.id === id)
      if (destroyed || !track || (closed && (!manual || source !== 'home-list' || blockers.size))) return false
      if (manual) preferences.write('lastSelectedTrackId', track.id)
      const same = selected && selected.id === track.id && selected.media_version === track.media_version && selected.audio_url === track.audio_url
      if (closed) closed = false
      if (manual && source === 'home-list') { recoveryRequired = false; failure = null }
      if (resume && (manual || intent === 'play')) intent = 'play'
      if (startPosition === null && same && output && actual === 'playing' && eligible() && status(output).playing && status(output).contextRunning) return true
      capture(); cancel()
      const old = !same && output
      if (!same) { output = null; position = 0 }
      selected = track
      if (startPosition !== null) { position = safePosition(startPosition, track); if (same && output) output.seek(position) }
      resting(); emit()
      if (old) {
        const epoch = generation
        retiring.add(old)
        try {
          if (eligible() && old.fadeOut && status(old).playing) { actual = 'loading'; emit(); await old.fadeOut({ signal: abort.signal }) }
        } catch (_) { /* A failed transition still stops old output before the next. */ }
        finally { retiring.delete(old); old.silence(); old.destroy() }
        if (epoch !== generation) return false
      }
      return eligible() ? start() : true
    }
    async function next() {
      if (destroyed || closed || catalog.tracks.length <= 1) return false
      const index = catalog.tracks.findIndex(t => selected && t.id === selected.id)
      return select(catalog.tracks[(index + 1) % catalog.tracks.length].id, { manual: true, source: 'next', resume: intent === 'play' })
    }
    function block(reason) {
      if (destroyed || blockers.has(reason)) return
      blockers.add(reason); capture(); cancel(); silence(); resting(); emit()
    }
    function unblock(reason) { if (blockers.delete(reason)) { resting(); emit() } }
    function requireRecovery(category = 'resource') {
      recoveryRequired = true; capture(); cancel(); silence()
      failure = { category, message: category === 'permission' ? '点按播放开始音乐' : category === 'catalog' ? '音乐目录暂不可用，请重试' : '音乐播放失败，请重试' }
      actual = category === 'permission' ? 'blocked' : 'error'; emit()
    }
    async function advanceAfterEnd(node) {
      if (node !== output || !eligible()) return
      capture(); cancel(); ending = true
      const epoch = generation, signal = abort.signal, endedId = selected.id
      actual = 'paused'; emit()
      try {
        const updated = options.beforeAdvance && await options.beforeAdvance({ signal, checkpoint: capture() })
        if (epoch !== generation || signal.aborted || !eligible() || node !== output) return
        // An ended read may replace the catalog, but never resume a newer pause/close.
        if (updated) setCatalog(updated)
        if (!eligible()) return
        const index = catalog.tracks.findIndex(t => t.id === endedId)
        const target = index >= 0 ? catalog.tracks[(index + 1) % catalog.tracks.length] : chooseDefault()
        if (!target) return
        if (selected && target.id === selected.id) { position = 0; if (output) output.seek(0) }
        await select(target.id, { manual: false, source: 'automatic', resume: true })
      } catch (error) { if (epoch === generation && !signal.aborted) markFailure(error) }
      finally { if (epoch === generation) ending = false }
    }
    function restoreSession(value) {
      if (destroyed || !value || !['play', 'pause'].includes(value.intent) || typeof value.closed !== 'boolean') return false
      cancel(); discard(); intent = value.intent; closed = value.closed; recoveryRequired = !!value.recoveryRequired
      selected = catalog.tracks.find(t => t.id === value.trackId) || catalog.tracks.find(t => t.id === preferences.read('lastSelectedTrackId').value) || chooseDefault()
      position = selected && selected.id === value.trackId && selected.media_version === value.mediaVersion ? safePosition(value.position, selected) : 0
      failure = null; resting(); emit(); return true
    }
    function halt() { if (!destroyed) { capture(); cancel(); silence(); resting(); emit() } }
    function destroy() {
      if (destroyed) return
      capture(); cancel(); discard(); destroyed = true; resting(); emit(); listeners.clear()
      if (outputFactory.dispose) void outputFactory.dispose()
    }
    return Object.freeze({ initialize, setCatalog, play, pause, close, select, next, block, unblock, requireRecovery,
      halt, restoreSession, reconcile: start, checkpoint: capture, state, destroy,
      subscribe(listener) { listeners.add(listener); listener(state()); return () => listeners.delete(listener) } })
  }
  window.BgmController = Object.freeze({ create,
    getDocumentInstance(options) {
      if (!documentInstance || documentInstance.state().destroyed) documentInstance = create(options)
      return documentInstance
    } })
})()

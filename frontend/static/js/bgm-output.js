/* BGM-owned media/output only. No call context, microphone or account storage. */
(function () {
  'use strict'
  if (window.BgmOutput) return
  const abortError = () => new DOMException('BGM operation cancelled', 'AbortError')
  function createEngine(options = {}) {
    const preferences = options.preferences || window.BgmPreferences
    const audioFactory = options.audioFactory || (() => new Audio())
    const contextFactory = options.contextFactory || (() => {
      const Context = window.AudioContext || window.webkitAudioContext
      if (!Context) throw new Error('Web Audio unavailable')
      return new Context()
    })
    const fadeSeconds = options.fadeSeconds === undefined ? 0.5 : options.fadeSeconds
    if (!(fadeSeconds >= 0 && fadeSeconds <= 2)) throw new TypeError('Invalid BGM fade duration')
    const live = new Set()
    let context = null, multiplier = 1, lastMode = 'pending', lastFade = false, preview = null
    const volume = () => preview === null ? preferences.read('volume').value : preview
    const fadeEnabled = () => preferences.read('fadeEnabled').value
    const target = () => volume() * multiplier
    function capabilities() {
      return { mode: lastMode, preciseVolume: lastMode === 'gain' || lastMode === 'media', fadeAvailable: lastFade,
        volume: volume(), muted: volume() === 0,
        note: lastMode === 'device' ? '此环境请使用设备音量' : lastMode !== 'pending' && !lastFade ? '当前环境暂不支持渐变，使用直接播放／暂停' : '' }
    }
    function create(track, emit) {
      let media, source = null, gain = null, mode = 'device', canFade = false
      let disposed = false, wanted = false, started = false, starting = false, epoch = 0, seekTo = 0, ramp = null, level = 0
      const handlers = []
      function newMedia() {
        const element = audioFactory()
        element.preload = 'none'; element.loop = false; element.crossOrigin = 'anonymous'
        element.setAttribute('playsinline', ''); element.src = track.audio_url
        return element
      }
      media = newMedia()
      try {
        if (!context || context.state === 'closed') context = contextFactory()
        gain = context.createGain(); gain.gain.setValueAtTime(0, context.currentTime)
        source = context.createMediaElementSource(media); source.connect(gain); gain.connect(context.destination)
        mode = 'gain'
        canFade = typeof gain.gain.linearRampToValueAtTime === 'function' && typeof gain.gain.cancelScheduledValues === 'function'
        if (options.onGraph) options.onGraph({ context, media, source, gain, track })
      } catch (_) {
        // Once a media element has entered a graph it cannot be reused as a
        // normal output. Replace it before any play, retaining no connected path.
        media.pause(); media.removeAttribute('src'); media.load()
        try { if (source) source.disconnect() } catch (_) {}
        try { if (gain) gain.disconnect() } catch (_) {}
        source = gain = null; media = newMedia()
        mode = options.verifiedMediaVolume === true ? 'media' : 'device'
        canFade = mode === 'media'
      }
      const graphContext = mode === 'gain' ? context : null
      lastMode = mode; lastFade = canFade
      function now() { return mode === 'gain' ? graphContext.currentTime : performance.now() / 1000 }
      function rampValue() {
        if (!ramp) return level
        const fraction = Math.min(1, Math.max(0, (now() - ramp.started) / ramp.seconds))
        return ramp.from + (ramp.to - ramp.from) * fraction
      }
      function writeGain(value) {
        level = value
        if (mode === 'gain') {
          gain.gain.cancelScheduledValues && gain.gain.cancelScheduledValues(graphContext.currentTime)
          gain.gain.setValueAtTime(value, graphContext.currentTime)
        } else if (mode === 'media') media.volume = value
      }
      function stopRamp() {
        if (!ramp) return
        const old = ramp, value = rampValue(); ramp = null
        clearTimeout(old.timer); if (old.frame) cancelAnimationFrame(old.frame)
        if (old.signal) old.signal.removeEventListener('abort', old.abort)
        try { writeGain(value) } finally { old.resolve(false) }
      }
      function animate(to, seconds, kind, signal) {
        const from = rampValue(); stopRamp()
        if (!canFade || !seconds || signal && signal.aborted) { writeGain(to); return Promise.resolve(false) }
        return new Promise(resolve => {
          const current = { from, to, seconds, kind, started: now(), resolve, signal, timer: null, frame: null, abort: null }
          ramp = current
          const finish = () => {
            if (ramp !== current) return
            ramp = null; clearTimeout(current.timer); if (current.frame) cancelAnimationFrame(current.frame)
            if (signal) signal.removeEventListener('abort', current.abort)
            writeGain(current.to); resolve(true)
          }
          current.abort = () => { if (ramp === current) stopRamp() }
          if (signal) signal.addEventListener('abort', current.abort, { once: true })
          if (mode === 'gain') {
            gain.gain.setValueAtTime(from, graphContext.currentTime)
            try { gain.gain.linearRampToValueAtTime(to, graphContext.currentTime + seconds) }
            catch (_) { canFade = false; lastFade = false; finish(); return }
          } else {
            const frame = () => {
              if (ramp !== current) return
              media.volume = rampValue()
              if (now() - current.started >= seconds) finish()
              else current.frame = requestAnimationFrame(frame)
            }
            current.frame = requestAnimationFrame(frame)
          }
          current.timer = setTimeout(finish, seconds * 1000 + 20)
        })
      }
      function silence() {
        epoch++; wanted = false; started = false; starting = false
        try { stopRamp() } catch (_) {}
        media.muted = true
        try { writeGain(0) } catch (_) { canFade = false; lastFade = false }
        media.pause()
      }
      function seek(value) {
        seekTo = Number.isFinite(value) && value >= 0 && value <= track.duration_seconds ? value : 0
        if (media.readyState >= 1) { try { media.currentTime = seekTo; seekTo = null } catch (_) {} }
      }
      function getState() {
        return { playing: wanted && started && !media.paused && !media.ended && media.readyState >= 2,
          ended: media.ended, paused: media.paused, contextRunning: mode !== 'gain' || graphContext.state === 'running',
          position: seekTo !== null ? seekTo : Number.isFinite(media.currentTime) ? media.currentTime : 0 }
      }
      for (const name of ['playing', 'pause', 'waiting', 'stalled', 'timeupdate', 'ended', 'error', 'loadedmetadata']) {
        const handler = () => {
          if (disposed) return
          if (name === 'loadedmetadata') { if (seekTo !== null) seek(seekTo); return }
          if (name === 'playing') {
            if (!wanted) { media.muted = true; media.pause(); return }
            started = true
            // Media can start before the same explicit operation resumes its context.
            if (starting && mode === 'gain' && graphContext.state !== 'running') return
          }
          // A queued pause from an older stop cannot invalidate a media element already restarted.
          if (name === 'pause' && !media.paused) return
          if (name === 'pause' || name === 'ended') started = false
          if (name === 'waiting' || name === 'stalled') {
            if (media.readyState < 3) { started = false; emit('waiting') }
            return
          }
          emit(name)
        }
        handlers.push([name, handler]); media.addEventListener(name, handler)
      }
      const contextChanged = () => {
        if (mode === 'gain' && wanted && !starting && graphContext.state !== 'running') emit('playing')
      }
      if (mode === 'gain') graphContext.addEventListener('statechange', contextChanged)
      async function play({ signal } = {}) {
        if (disposed || signal && signal.aborted) throw abortError()
        const attempt = ++epoch; wanted = true; starting = true; stopRamp()
        media.muted = volume() === 0
        const fade = fadeEnabled() && canFade && fadeSeconds > 0
        writeGain(fade ? 0 : target())
        let removeAbort = () => {}
        try {
          // Both calls happen in the originating gesture, before awaiting either.
          const resumed = mode === 'gain' ? graphContext.resume() : Promise.resolve()
          const played = media.play()
          const cancelled = new Promise((_, reject) => {
            const cancel = () => { if (attempt === epoch) silence(); reject(abortError()) }
            if (signal) { signal.addEventListener('abort', cancel, { once: true }); removeAbort = () => signal.removeEventListener('abort', cancel) }
          })
          await Promise.race([Promise.all([resumed, played]), cancelled])
          removeAbort()
          if (disposed || attempt !== epoch || signal && signal.aborted || !wanted) {
            if (!wanted) { media.muted = true; media.pause() }
            throw abortError()
          }
          if (mode === 'gain' && graphContext.state !== 'running') throw new DOMException('BGM output unavailable', 'OutputBlockedError')
          started = !media.paused && !media.ended
          if (fade) void animate(target(), fadeSeconds, 'in', signal)
          else writeGain(target())
        } catch (error) {
          removeAbort()
          if (attempt === epoch) silence()
          throw error
        } finally { if (attempt === epoch) starting = false }
      }
      async function fadeOut({ signal } = {}) {
        const attempt = ++epoch
        if (disposed || media.paused || !canFade || !fadeEnabled()) { silence(); return }
        try { await animate(0, fadeSeconds, 'out', signal) }
        catch (_) { canFade = false; lastFade = false }
        if (attempt === epoch) silence()
      }
      function refresh() {
        media.muted = !wanted || volume() === 0
        if (!wanted) return
        if (ramp) {
          if (!fadeEnabled()) {
            const kind = ramp.kind; stopRamp()
            if (kind === 'out') silence()
            else writeGain(target())
          } else if (ramp.kind === 'in' || ramp.kind === 'level') {
            const remaining = Math.max(0, ramp.seconds - (now() - ramp.started)), signal = ramp.signal
            void animate(target(), remaining, ramp.kind, signal)
          }
        } else writeGain(target())
      }
      function refreshMultiplier(fade) {
        if (!wanted || ramp && ramp.kind === 'out') return refresh()
        media.muted = volume() === 0
        if (fade && fadeEnabled() && canFade) void animate(target(), fadeSeconds, 'level')
        else refresh()
      }
      function destroy() {
        if (disposed) return
        silence(); disposed = true
        for (const [name, handler] of handlers) media.removeEventListener(name, handler)
        if (mode === 'gain') graphContext.removeEventListener('statechange', contextChanged)
        media.removeAttribute('src'); media.load()
        try { if (source) source.disconnect(); if (gain) gain.disconnect() } catch (_) {}
        live.delete(node)
      }
      const node = { play, fadeOut, silence, seek, getState, destroy, refresh, refreshMultiplier }
      live.add(node); return node
    }
    const refresh = () => { for (const node of live) node.refresh() }
    function setVolume(value) { const result = preferences.write('volume', value); preview = null; refresh(); return result }
    function previewVolume(value) {
      if (!Number.isFinite(value) || value < 0 || value > 1) throw new TypeError('Invalid BGM volume')
      preview = value; refresh()
    }
    function commitVolume() { return preview === null ? preferences.read('volume') : setVolume(preview) }
    function cancelVolumePreview() { preview = null; refresh() }
    function setFadeEnabled(value) { const result = preferences.write('fadeEnabled', value); refresh(); return result }
    function unmute() { return volume() === 0 ? setVolume(0.30) : preferences.read('volume') }
    function setMultiplier(value, { fade = false } = {}) {
      if (!Number.isFinite(value) || value < 0 || value > 1) throw new TypeError('Invalid BGM multiplier')
      if (multiplier === value) return
      multiplier = value
      for (const node of live) node.refreshMultiplier(fade)
    }
    async function dispose() {
      for (const node of [...live]) node.destroy()
      if (context && context.state !== 'closed') await context.close().catch(() => {})
      context = null
    }
    Object.assign(create, { capabilities, dispose })
    return Object.freeze({ create, capabilities, setVolume, previewVolume, commitVolume, cancelVolumePreview, setFadeEnabled, unmute, setMultiplier, refresh, dispose })
  }
  let engine = null
  const defaultEngine = () => engine || (engine = createEngine())
  const create = (...args) => defaultEngine().create(...args)
  create.capabilities = () => defaultEngine().capabilities()
  create.dispose = () => engine ? engine.dispose() : Promise.resolve()
  window.BgmOutput = Object.freeze({ createEngine, create, capabilities: () => defaultEngine().capabilities(),
    setVolume: value => defaultEngine().setVolume(value), previewVolume: value => defaultEngine().previewVolume(value),
    commitVolume: () => defaultEngine().commitVolume(), cancelVolumePreview: () => defaultEngine().cancelVolumePreview(), setFadeEnabled: value => defaultEngine().setFadeEnabled(value),
    unmute: () => defaultEngine().unmute(), setMultiplier: (value, options) => defaultEngine().setMultiplier(value, options), refresh: () => defaultEngine().refresh() })
})()

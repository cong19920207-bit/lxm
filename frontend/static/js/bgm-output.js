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
    let context = null, physical = null, active = null, sourceGeneration = 0, rebuilding = null, multiplier = 1, lastMode = 'pending', lastFade = false, preview = null
    const volume = () => preview === null ? preferences.read('volume').value : preview
    const fadeEnabled = () => preferences.read('fadeEnabled').value
    const target = () => volume() * multiplier
    function capabilities() {
      return { mode: lastMode, preciseVolume: lastMode === 'gain' || lastMode === 'media', fadeAvailable: lastFade,
        volume: volume(), muted: volume() === 0,
        note: lastMode === 'device' ? '此环境请使用设备音量' : lastMode !== 'pending' && !lastFade ? '当前环境暂不支持渐变，使用直接播放／暂停' : '' }
    }
    function preparePhysical(track) {
      if (physical) return physical
      let media = audioFactory(), source = null, gain = null, mode = 'device', canFade = false
      const configure = () => {
        media.preload = 'none'; media.loop = false; media.crossOrigin = 'anonymous'
        media.setAttribute('playsinline', ''); media.muted = true
      }
      configure()
      try {
        if (!context || context.state === 'closed') context = contextFactory()
        gain = context.createGain(); gain.gain.setValueAtTime(0, context.currentTime)
        source = context.createMediaElementSource(media); source.connect(gain); gain.connect(context.destination)
        mode = 'gain'
        canFade = typeof gain.gain.linearRampToValueAtTime === 'function' && typeof gain.gain.cancelScheduledValues === 'function'
        if (options.onGraph) options.onGraph({ context, media, source, gain, track })
      } catch (_) {
        // A captured element cannot return to direct output. This is one owner-led
        // initialization downgrade, never a per-track reconstruction.
        if (source) {
          media.pause(); media.removeAttribute('src'); media.load()
          try { source.disconnect() } catch (_) {}
          media = audioFactory(); configure()
        }
        try { if (gain) gain.disconnect() } catch (_) {}
        source = gain = null
        mode = options.verifiedMediaVolume === true ? 'media' : 'device'; canFade = mode === 'media'
      }
      lastMode = mode; lastFade = canFade
      physical = { media, source, gain, mode, canFade, context: mode === 'gain' ? context : null }
      return physical
    }
    function create(track, emit = () => {}) {
      if (rebuilding) throw new DOMException('BGM output rebuilding', 'OutputBlockedError')
      active?.destroy()
      const graph = preparePhysical(track), generation = ++sourceGeneration, boundAt = performance.now()
      const { media, source, gain, mode, context: graphContext } = graph
      let canFade = graph.canFade, disposed = false, wanted = false, started = false, starting = false
      let epoch = 0, seekTo = 0, ramp = null, level = 0, lastPosition = 0, endedSent = false
      let phase = 'currentSrc' in media ? 'selected' : 'loading'
      const handlers = [], operations = new Set()
      const owns = () => !disposed && active === node && physical === graph && generation === sourceGeneration
      const expectedResource = () => ('currentSrc' in media ? media.currentSrc : media.src) === track.audio_url
      // Pending native play may settle after cancellation. Only quench its own
      // physical generation; never pause a newer track sharing the element.
      const quenchLate = () => {
        if (physical !== graph || generation === sourceGeneration && (!owns() || !wanted)) {
          media.muted = true; media.pause()
        }
      }
      function now() { return mode === 'gain' ? graphContext.currentTime : performance.now() / 1000 }
      function rampValue() {
        if (!ramp) return level
        const fraction = Math.min(1, Math.max(0, (now() - ramp.started) / ramp.seconds))
        return ramp.from + (ramp.to - ramp.from) * fraction
      }
      function writeGain(value) {
        if (!owns()) return
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
        if (!owns()) return Promise.resolve(false)
        const attempt = epoch
        const from = rampValue(); stopRamp()
        if (!canFade || !seconds || signal && signal.aborted) { writeGain(to); return Promise.resolve(false) }
        return new Promise(resolve => {
          const current = { from, to, seconds, kind, started: now(), resolve, signal, timer: null, frame: null, abort: null }
          ramp = current
          const finish = () => {
            if (ramp !== current) return
            ramp = null; clearTimeout(current.timer); if (current.frame) cancelAnimationFrame(current.frame)
            if (signal) signal.removeEventListener('abort', current.abort)
            if (owns() && attempt === epoch) writeGain(current.to)
            resolve(owns() && attempt === epoch)
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
              if (!owns() || attempt !== epoch) { stopRamp(); return }
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
        if (!owns()) return
        epoch++; wanted = false; started = false; starting = false
        for (const cancel of [...operations]) cancel()
        try { stopRamp() } catch (_) {}
        media.muted = true
        try { writeGain(0) } catch (_) { canFade = false; lastFade = false }
        media.pause()
      }
      function seek(value) {
        if (!owns()) return
        endedSent = false
        seekTo = Number.isFinite(value) && value >= 0 && value <= track.duration_seconds ? value : 0
        if (expectedResource() && phase !== 'selected' && media.readyState >= 1) { try { media.currentTime = seekTo; seekTo = null } catch (_) {} }
      }
      function getState() {
        if (!owns()) return { playing: false, ended: false, paused: true, contextRunning: false, position: lastPosition }
        return { playing: wanted && started && !media.paused && !media.ended && media.readyState >= 2,
          ended: media.ended, paused: media.paused, contextRunning: mode !== 'gain' || graphContext.state === 'running',
          position: seekTo !== null ? seekTo : Number.isFinite(media.currentTime) ? media.currentTime : 0 }
      }
      for (const name of ['loadstart', 'playing', 'pause', 'waiting', 'stalled', 'timeupdate', 'ended', 'error', 'loadedmetadata']) {
        const handler = event => {
          // Native events have no source generation. In addition to this bound
          // handle, require the expected loaded resource, phase and actual state.
          if (!owns() || event.timeStamp < boundAt || !expectedResource()) return
          if (name === 'loadstart') { phase = 'loading'; return }
          if (phase === 'selected') return
          if (name === 'loadedmetadata') {
            if (media.readyState < 1 || media.error) return
            phase = 'ready'; if (seekTo !== null) seek(seekTo); return
          }
          if (name === 'error') { if (media.error) emit('error'); return }
          if (name === 'playing') {
            if (!wanted) { quenchLate(); return }
            if (media.paused || media.ended || media.readyState < 2) return
            started = true; phase = 'ready'
            if (starting && mode === 'gain' && graphContext.state !== 'running') return
          }
          if (!wanted) return
          if (name === 'pause' && !media.paused) return
          if (name === 'ended') {
            if (phase !== 'ready' || !media.ended || endedSent || media.readyState < 2) return
            endedSent = true
          }
          if (name === 'timeupdate' && (phase !== 'ready' || media.readyState < 2)) return
          if (name === 'pause' || name === 'ended') started = false
          if (name === 'waiting' || name === 'stalled') {
            if (!media.paused && media.readyState < 3) { started = false; emit('waiting') }
            return
          }
          emit(name)
        }
        handlers.push([name, handler]); media.addEventListener(name, handler)
      }
      const contextChanged = () => {
        if (owns() && mode === 'gain' && wanted && !starting && graphContext.state !== 'running') emit('playing')
      }
      if (mode === 'gain') graphContext.addEventListener('statechange', contextChanged)
      async function play({ signal } = {}) {
        if (!owns() || signal && signal.aborted) throw abortError()
        const attempt = ++epoch; wanted = true; starting = true; stopRamp()
        media.muted = volume() === 0
        const fade = fadeEnabled() && canFade && fadeSeconds > 0
        writeGain(fade ? 0 : target())
        let removeAbort = () => {}
        try {
          // Both calls happen in the originating gesture, before awaiting either.
          const resumed = mode === 'gain' ? graphContext.resume() : Promise.resolve()
          const played = media.play()
          Promise.resolve(played).then(quenchLate, () => {})
          const cancelled = new Promise((_, reject) => {
            const cancel = () => { operations.delete(cancel); if (owns() && attempt === epoch) silence(); reject(abortError()) }
            operations.add(cancel)
            if (signal) signal.addEventListener('abort', cancel, { once: true })
            removeAbort = () => { operations.delete(cancel); signal?.removeEventListener('abort', cancel) }
          })
          await Promise.race([Promise.all([resumed, played]), cancelled])
          removeAbort()
          if (!owns() || attempt !== epoch || signal && signal.aborted || !wanted) {
            quenchLate()
            throw abortError()
          }
          if (mode === 'gain' && graphContext.state !== 'running') throw new DOMException('BGM output unavailable', 'OutputBlockedError')
          started = !media.paused && !media.ended
          if (fade) void animate(target(), fadeSeconds, 'in', signal)
          else writeGain(target())
        } catch (error) {
          removeAbort()
          if (owns() && attempt === epoch) silence()
          throw error
        } finally { if (owns() && attempt === epoch) starting = false }
      }
      async function fadeOut({ signal } = {}) {
        if (!owns()) return
        const attempt = ++epoch
        if (disposed || media.paused || !canFade || !fadeEnabled()) { silence(); return }
        try { await animate(0, fadeSeconds, 'out', signal) }
        catch (_) { canFade = false; lastFade = false }
        if (owns() && attempt === epoch) silence()
      }
      function refresh() {
        if (!owns()) return
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
        if (!owns()) return
        if (!wanted || ramp && ramp.kind === 'out') return refresh()
        media.muted = volume() === 0
        if (fade && fadeEnabled() && canFade) void animate(target(), fadeSeconds, 'level')
        else refresh()
      }
      function destroy() {
        if (disposed) return
        lastPosition = getState().position
        silence(); disposed = true
        for (const [name, handler] of handlers) media.removeEventListener(name, handler)
        if (mode === 'gain') graphContext.removeEventListener('statechange', contextChanged)
        // A logical handle never disconnects the shared graph or clears its src.
        live.delete(node); if (active === node) active = null
      }
      const node = { play, fadeOut, silence, seek, getState, destroy, refresh, refreshMultiplier, sourceGeneration: generation }
      active = node; live.add(node)
      media.src = track.audio_url
      return node
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
    async function silenceBarrier({ current = () => true } = {}) {
      const graph = physical, generation = sourceGeneration
      active?.silence()
      if (graph) {
        graph.media.muted = true; graph.media.pause()
        if (graph.gain) {
          graph.gain.gain.cancelScheduledValues?.(graph.context.currentTime)
          graph.gain.gain.setValueAtTime(0, graph.context.currentTime)
        }
      }
      await Promise.resolve()
      const observe = () => ({ current: current(), sameOutput: graph === physical && generation === sourceGeneration,
        paused: !graph || graph.media.paused, muted: !graph || graph.media.muted, gain: graph?.gain?.gain.value ?? 0 })
      // AudioParam.value is updated by native render quanta, not by the JS
      // microtask that scheduled zero. Observe that convergence before capture.
      const deadline = performance.now() + 500
      let observation = observe()
      while (observation.current && observation.sameOutput && observation.paused && observation.muted && observation.gain !== 0 && performance.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 10)); observation = observe()
      }
      if (!observation.current || !observation.sameOutput || !observation.paused || !observation.muted || observation.gain !== 0) {
        throw Object.assign(new Error('BGM stop remains unconfirmed'), { code: 'BGM_STOP_UNCONFIRMED', observation })
      }
      return { stopped: true, sourceGeneration: generation }
    }
    async function releasePhysical() {
      for (const node of [...live]) node.destroy()
      sourceGeneration++
      const old = physical, oldContext = context; physical = context = null
      if (old) {
        old.media.muted = true; old.media.pause(); old.media.removeAttribute('src'); old.media.load()
        try { old.source?.disconnect(); old.gain?.disconnect() } catch (_) {}
      }
      if (oldContext && oldContext.state !== 'closed') await oldContext.close().catch(() => {})
    }
    function rebuild({ permitted = () => false } = {}) {
      if (rebuilding) return rebuilding
      const task = (async () => {
        await releasePhysical()
        if (!permitted()) return false
        preparePhysical(null)
        if (!permitted()) { await releasePhysical(); return false }
        return true
      })()
      rebuilding = task.finally(() => { rebuilding = null })
      return rebuilding
    }
    async function dispose() {
      if (rebuilding) await rebuilding
      await releasePhysical()
    }
    Object.assign(create, { capabilities, dispose })
    return Object.freeze({ create, capabilities, setVolume, previewVolume, commitVolume, cancelVolumePreview, setFadeEnabled, unmute, setMultiplier, refresh, silenceBarrier, rebuild, dispose })
  }
  let engine = null
  const defaultEngine = () => engine || (engine = createEngine())
  const create = (...args) => defaultEngine().create(...args)
  create.capabilities = () => defaultEngine().capabilities()
  create.dispose = () => engine ? engine.dispose() : Promise.resolve()
  window.BgmOutput = Object.freeze({ createEngine, create, capabilities: () => defaultEngine().capabilities(),
    setVolume: value => defaultEngine().setVolume(value), previewVolume: value => defaultEngine().previewVolume(value),
    commitVolume: () => defaultEngine().commitVolume(), cancelVolumePreview: () => defaultEngine().cancelVolumePreview(), setFadeEnabled: value => defaultEngine().setFadeEnabled(value),
    unmute: () => defaultEngine().unmute(), setMultiplier: (value, options) => defaultEngine().setMultiplier(value, options), refresh: () => defaultEngine().refresh(),
    silenceBarrier: options => defaultEngine().silenceBarrier(options) })
})()

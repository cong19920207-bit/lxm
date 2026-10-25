/* Event catalog + bounded recovery coordinator. All output still belongs to BgmController. */
(function () {
  'use strict'
  if (window.BgmPlayer) return
  const RECOVERY_KEY = 'lxm_bgm_recovery_v1'
  function create(options = {}) {
    const catalog = options.catalog || window.BgmCatalog.getDocumentInstance(), limits = window.BgmCatalog.limits
    const preferences = options.preferences || window.BgmPreferences
    const now = options.now || (() => performance.now()), later = options.setTimeout || setTimeout, clear = options.clearTimeout || clearTimeout
    let storage, savedRecovery = null, recoveryScope = 'session'
    try { storage = options.storage || window.sessionStorage; savedRecovery = JSON.parse(storage.getItem(RECOVERY_KEY) || 'null') } catch (_) { recoveryScope = 'memory' }
    let initialized = false, active = null, destroyed = false, catalogStatus = 'idle', initialChoice = null, savedRequired = null, notice = null
    const listeners = new Set(), readers = new Set()
    const core = window.BgmController.create({ preferences, outputFactory: options.outputFactory,
      onEnded: checkpoint => begin('ended', { endedId: checkpoint.trackId }) })
    const allowed = () => { const s = core.state(); return !destroyed && s.intent === 'play' && !s.closed && !s.blockers.length && !s.recoveryRequired }
    const state = () => ({ ...core.state(), catalogStatus, notice: notice && { ...notice }, catalogAgeMs: catalog.peek().ageMs, recoveryScope })
    function emit() { for (const listener of listeners) { try { listener(state()) } catch (_) {} } }
    function persist(s) {
      if (!initialized || savedRequired === s.recoveryRequired) return
      savedRequired = s.recoveryRequired
      try {
        if (!storage) throw new Error('Session unavailable')
        storage.setItem(RECOVERY_KEY, JSON.stringify({ version: 1, required: s.recoveryRequired, category: s.failure && s.failure.category }))
      } catch (_) { recoveryScope = 'memory' }
    }
    core.subscribe(s => {
      persist(s); emit()
      if (initialized && !active && allowed() && (s.actual === 'loading' || s.actual === 'error')) {
        // Only a native buffering/resource event starts this watchdog, never a timer or arbitrary click.
        Promise.resolve().then(() => {
          const current = core.state()
          if (!active && allowed() && (current.actual === 'loading' || current.actual === 'error')) void begin('resource', { waiting: current.actual === 'loading' })
        })
      }
    })
    function cancelled(job) { return destroyed || job.abort.signal.aborted }
    function remaining(job) { return Math.max(0, job.deadline - now()) }
    function check(job) {
      if (cancelled(job)) throw new DOMException('Cancelled', 'AbortError')
      if (!remaining(job)) throw new Error('BGM total budget exhausted')
    }
    function delay(job, ms) {
      check(job)
      return new Promise((resolve, reject) => {
        const cancel = () => { clear(timer); reject(new DOMException('Cancelled', 'AbortError')) }
        const timer = later(() => { job.abort.signal.removeEventListener('abort', cancel); resolve() }, Math.min(ms, remaining(job)))
        job.abort.signal.addEventListener('abort', cancel, { once: true })
      })
    }
    function makeJob() { return { abort: new AbortController(), deadline: now() + limits.totalMs, retries: 0, forced: 0, attempted: new Set() } }
    async function read(job, { force = false, manual = false } = {}) {
      check(job)
      catalogStatus = 'loading'; emit()
      const cooling = !manual && !force && catalog.peek().cooling
      while (true) {
        try {
          const data = await catalog.read({ force, bypassCooldown: manual || job.retries > 0, signal: job.abort.signal,
            timeoutMs: Math.min(limits.directoryMs, remaining(job)) })
          check(job); catalogStatus = data.tracks.length ? 'ready' : 'empty'; return data
        } catch (error) {
          if (cancelled(job)) throw error
          if (!cooling && job.retries < limits.directoryRetries && remaining(job) > limits.backoffMs) {
            job.retries++; await delay(job, limits.backoffMs); continue
          }
          const cached = catalog.peek()
          catalogStatus = cached.usable ? (cached.catalog.tracks.length ? 'stale' : 'empty') : 'error'; emit()
          if (cached.usable) return cached.catalog
          throw error
        }
      }
    }
    function apply(data) {
      const changed = core.setCatalog(data, { initialCheckpoint: initialChoice })
      initialChoice = null
      return changed
    }
    function waitForOutput(job, launch) {
      check(job)
      return new Promise((resolve, reject) => {
        let done = false, unsubscribe = () => {}, timer
        const finish = (fn, value) => {
          if (done) return
          done = true; clear(timer); unsubscribe(); job.abort.signal.removeEventListener('abort', cancel); fn(value)
        }
        const cancel = () => finish(reject, new DOMException('Cancelled', 'AbortError'))
        const inspect = s => {
          if (s.actual === 'playing') finish(resolve, 'playing')
          else if (s.recoveryRequired || s.failure && s.failure.category === 'permission') finish(resolve, 'permission')
          else if (s.actual === 'error') finish(resolve, 'resource')
        }
        timer = later(() => finish(resolve, 'timeout'), Math.min(limits.mediaMs, remaining(job)))
        job.abort.signal.addEventListener('abort', cancel, { once: true })
        // Launch before subscribing so an old playing/error state cannot settle a new candidate.
        try { if (launch) Promise.resolve(launch()).catch(() => finish(resolve, 'resource')) } catch (_) { finish(resolve, 'resource') }
        unsubscribe = core.subscribe(inspect)
        if (done) unsubscribe()
      })
    }
    function exhaust(job, category) {
      if (!cancelled(job) && allowed()) core.requireRecovery(category)
      return false
    }
    async function execute(job, kind, args) {
      let data, category = 'catalog', target, startPosition = null
      try {
        if (kind === 'resource' && args.waiting) {
          // A transient wait may recover on its own; it still consumes this chain's deadline.
          category = 'resource'
          const result = await waitForOutput(job)
          if (result === 'playing') return true
          if (result === 'permission') return false
        }
        if (kind === 'resource') {
          if (core.state().track) job.attempted.add(core.state().track.id)
          core.halt(); job.forced++
        }
        // The opening preloads the catalog without output. A usable prepared
        // track must reach media.play()/AudioContext.resume() in the click stack.
        const prepared = args.gesture && catalog.peek()
        if (prepared && prepared.usable) data = prepared.catalog
        else data = await read(job, { force: kind === 'resource', manual: !!args.manual })
        check(job); apply(data)
        if (!data.tracks.length) return false
        const s = core.state()
        if (kind === 'select') target = data.tracks.find(t => t.id === args.id) || s.track
        else if (kind === 'next' || kind === 'ended') {
          const index = data.tracks.findIndex(t => t.id === (args.endedId || args.previousId))
          target = index < 0 ? s.track : data.tracks[(index + 1) % data.tracks.length]; startPosition = 0
        } else target = s.track
        if (!allowed()) {
          if (kind === 'next' && !s.closed && !s.recoveryRequired && target) await core.select(target.id, { manual: true, source: 'next', resume: false, startPosition: 0 })
          return false
        }
        if (kind === 'next' && target) preferences.write('lastSelectedTrackId', target.id)
        category = 'resource'
        while (target && job.attempted.size < limits.candidates) {
          check(job)
          if (!allowed()) return false
          if (!catalog.peek().usable) return exhaust(job, 'catalog')
          if (job.attempted.has(target.id)) { target = data.tracks.find(t => !job.attempted.has(t.id)); startPosition = null; continue }
          job.attempted.add(target.id)
          const result = await waitForOutput(job, () => core.select(target.id, { manual: false, source: 'automatic', resume: true, startPosition }))
          if (result === 'playing') return true
          if (result === 'permission' || !allowed()) return false
          core.halt()
          if (job.forced < limits.forcedRefreshes && remaining(job)) {
            job.forced++; category = 'catalog'
            data = await read(job, { force: true, manual: !!args.manual }); check(job); apply(data)
            if (!data.tracks.length) return false
            category = 'resource'
          }
          if (kind === 'select') notice = { category: 'selection', message: '所选音乐播放失败，正在尝试其他可用音乐' }
          const old = args.previous && data.tracks.find(t => t.id === args.previous.trackId && t.media_version === args.previous.mediaVersion && !job.attempted.has(t.id))
          target = old || data.tracks.find(t => !job.attempted.has(t.id))
          startPosition = old ? args.previous.position : null
        }
        return exhaust(job, category)
      } catch (error) {
        if (error.name === 'AbortError' || cancelled(job)) return false
        return exhaust(job, category)
      }
    }
    function stopJob() { if (active) { active.abort.abort(); active = null } }
    function begin(kind, args = {}) {
      if (!initialized || destroyed) return Promise.resolve(false)
      if (!args.manual && kind !== 'next' && !allowed()) return Promise.resolve(false)
      if (active) return active.task
      const job = makeJob(); active = job
      job.task = execute(job, kind, args).finally(() => { if (active === job) active = null; emit() })
      return job.task
    }
    function initialize({ session = null } = {}) {
      if (initialized) return active ? active.task : Promise.resolve(false)
      initialized = true
      const cached = catalog.peek()
      const recovery = savedRecovery && savedRecovery.version === 1 && savedRecovery.required === true
      const validSession = session && ['play', 'pause'].includes(session.intent) && typeof session.closed === 'boolean'
      const restored = validSession ? { ...session, recoveryRequired: !!session.recoveryRequired || recovery } : recovery ? {
        intent: preferences.read('autoplayEnabled').value ? 'play' : 'pause', closed: false, recoveryRequired: true } : null
      initialChoice = cached.catalog ? null : restored || {}
      core.initialize(cached.catalog || { catalog_version: 0, default_track_id: null, tracks: [] }, { session: restored })
      catalogStatus = cached.catalog ? cached.fresh ? cached.catalog.tracks.length ? 'ready' : 'empty' : 'stale' : 'idle'
      if (recovery) core.requireRecovery(['permission', 'catalog'].includes(savedRecovery.category) ? savedRecovery.category : 'resource')
      return begin('initialize')
    }
    function play(source = 'home', { gesture = false } = {}) {
      if (!initialized || destroyed || !['home', 'home-list', 'bubble', 'retry'].includes(source)) return Promise.resolve(false)
      if (core.state().blockers.length || core.state().closed && source !== 'home') return Promise.resolve(false)
      stopJob(); notice = null; void core.play({ source, defer: true })
      return begin('play', { manual: true, gesture })
    }
    function select(id) {
      if (!initialized || destroyed || !core.state().tracks.some(t => t.id === id) || core.state().blockers.length) return Promise.resolve(false)
      const previous = core.checkpoint()
      stopJob(); notice = null; initialChoice = null; preferences.write('lastSelectedTrackId', id)
      void core.play({ source: 'home', defer: true })
      return begin('select', { id, previous, manual: true })
    }
    function next() {
      const s = core.state()
      if (!initialized || destroyed || !s.nextEnabled || s.blockers.length) return Promise.resolve(false)
      if (s.recoveryRequired) return core.next()
      stopJob()
      return begin('next', { previousId: s.track && s.track.id, manual: true })
    }
    async function panel() {
      if (!initialized || destroyed) return false
      const job = makeJob(); readers.add(job)
      try {
        const data = await read(job, { manual: true }); check(job)
        const changed = apply(data)
        // A newer catalog may retire the playing track. Preserve the current
        // intent and this read's remaining budget; the panel grants no new intent.
        if (changed && data.tracks.length && allowed() && !active) {
          active = job; job.task = execute(job, 'catalog', {})
          return await job.task
        }
        return true
      }
      catch (_) { return false }
      finally { if (active === job) active = null; readers.delete(job); emit() }
    }
    function event(name) {
      if (name === 'panel') return panel()
      if (['initialize', 'visible', 'ended'].includes(name)) return begin(name, { endedId: name === 'ended' && core.state().track && core.state().track.id })
      return Promise.resolve(false)
    }
    function checkpoint() {
      const point = core.checkpoint()
      if (!point.trackId && initialChoice) return { ...point, trackId: initialChoice.trackId || null,
        mediaVersion: initialChoice.mediaVersion || null, position: Number.isFinite(initialChoice.position) ? initialChoice.position : 0 }
      return point
    }
    function restoreSession(session) {
      stopJob()
      if (catalog.reload) catalog.reload()
      const cached = catalog.peek()
      if (cached.catalog) core.setCatalog(cached.catalog)
      initialChoice = cached.catalog ? null : session
      return core.restoreSession(session)
    }
    function pause() { stopJob(); return core.pause() }
    function close() { stopJob(); core.close() }
    function block(reason) { stopJob(); core.block(reason) }
    function requireRecovery(reason) { stopJob(); core.requireRecovery(reason) }
    function destroy() { stopJob(); for (const job of readers) job.abort.abort(); readers.clear(); destroyed = true; core.destroy(); listeners.clear() }
    return Object.freeze({ initialize, play, select, next, event, resume: () => begin('resume'), pause, close, block, requireRecovery, unblock: core.unblock,
      state, checkpoint, restoreSession, destroy, core,
      subscribe(listener) { listeners.add(listener); listener(state()); return () => listeners.delete(listener) } })
  }
  let documentInstance
  window.BgmPlayer = Object.freeze({ create, recoveryKey: RECOVERY_KEY,
    getDocumentInstance(options) {
      if (!documentInstance || documentInstance.state().destroyed) documentInstance = create(options)
      return documentInstance
    } })
})()

/* Page lifecycle is independent of the home loader and account-data initialization. */
(function () {
  'use strict'
  if (window.BgmPage) return
  function create(options = {}) {
    const mode = options.mode || 'content', doc = options.document || document, host = options.window || window
    if (!['home', 'content', 'login'].includes(mode) || options.authorized === false) return null
    const session = options.session || window.BgmSession.create()
    const stored = session.inspect()
    const callOccupied = () => !!(host.VoiceEntry && host.VoiceEntry.isAudioOccupied && host.VoiceEntry.isAudioOccupied())
    const player = options.player || window.BgmPlayer.getDocumentInstance()
    const later = options.setTimeout || setTimeout, clear = options.clearTimeout || clearTimeout
    let parked = !!doc.hidden, syncing = true, destroyed = false, timer = null, signature = '', note = stored.note
    let bubble = stored.session && stored.session.bubble || { x: 1, y: 0.6 }
    const listeners = new Set(), handlers = []
    const publish = () => { for (const listener of listeners) { try { listener({ ...player.state(), sessionNote: note, bubble: { ...bubble }, mode }) } catch (_) {} } }
    function save() {
      const result = session.save(player.checkpoint(), bubble)
      note = result.note; publish()
    }
    function clearCheckpoint() { clear(timer); timer = null }
    function scheduleCheckpoint() {
      if (timer !== null || parked || destroyed || player.state().actual !== 'playing') return
      timer = later(() => { timer = null; if (!parked && !destroyed && player.state().actual === 'playing') { save(); scheduleCheckpoint() } }, 2000)
    }
    function changed(s) {
      if (destroyed) return
      if (!syncing && !parked) {
        const current = JSON.stringify([s.track && s.track.id, s.track && s.track.media_version, s.intent, s.closed, s.recoveryRequired, s.actual])
        if (current !== signature) { signature = current; save() }
        if (s.actual === 'playing') scheduleCheckpoint(); else clearCheckpoint()
      }
      publish()
    }
    const ducking = window.BgmDucking ? window.BgmDucking.create({ player }) : null
    const mediaActivities = window.BgmMedia ? window.BgmMedia.create({ player }) : null
    const preparation = window.BgmPreparation ? window.BgmPreparation.create({ player, document: doc, window: host }) : null
    const unsubscribe = player.subscribe(changed)
    if (doc.hidden) player.block('hidden')
    if (mode === 'login') player.block('login')
    if (callOccupied()) player.block('call')
    let initial = mode === 'login' && !stored.session ? { intent: 'pause', closed: false, recoveryRequired: false } : stored.session
    if (callOccupied()) initial = { ...(initial || {}), intent: 'pause', closed: true }
    const ready = player.initialize({ session: initial })
    syncing = false
    if (!parked) changed(player.state()); else save()
    function suspend(reason) {
      if (destroyed) return
      const wasParked = parked; parked = true; syncing = true; clearCheckpoint()
      player.block(reason)
      // Once frozen, the old document must not overwrite a later document's checkpoint.
      if (!wasParked) save()
      syncing = false; publish()
    }
    function resume() {
      if (destroyed || doc.hidden || !parked) return
      syncing = true
      const latest = session.inspect(); note = latest.note
      const fallback = { ...player.checkpoint(), intent: 'pause' }
      const checkpoint = latest.session || fallback
      if (checkpoint.bubble) bubble = { ...checkpoint.bubble }
      player.restoreSession(checkpoint)
      player.unblock('hidden'); player.unblock('pagehide')
      if (options.refreshOutput) options.refreshOutput()
      else if (window.BgmOutput) window.BgmOutput.refresh()
      parked = false; syncing = false; signature = ''; changed(player.state())
      if (mode !== 'login') void player.event('visible')
    }
    function bind(target, name, fn) { target.addEventListener(name, fn); handlers.push(() => target.removeEventListener(name, fn)) }
    bind(host, 'voice:audio-occupancy', () => {
      if (callOccupied()) { player.block('call'); player.close() }
      else player.unblock('call')
    })
    bind(doc, 'visibilitychange', () => doc.hidden ? suspend('hidden') : resume())
    bind(host, 'pagehide', event => { suspend('pagehide'); if (!event.persisted) destroy() })
    bind(host, 'pageshow', resume)
    function destroy() {
      if (destroyed) return
      if (!parked) suspend('pagehide')
      destroyed = true; clearCheckpoint(); unsubscribe(); handlers.forEach(fn => fn()); if (preparation) preparation.destroy(); if (ducking) ducking.destroy(); if (mediaActivities) mediaActivities.destroy(); player.destroy(); listeners.clear()
    }
    return Object.freeze({ player, ducking, mediaActivities, preparation, ready, suspend, resume, destroy,
      state: () => ({ ...player.state(), sessionNote: note, bubble: { ...bubble }, mode }),
      setBubble(position) {
        if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return
        bubble = { x: Math.max(0, Math.min(1, position.x)), y: Math.max(0, Math.min(1, position.y)) }; save()
      },
      subscribe(listener) { listeners.add(listener); listener({ ...player.state(), sessionNote: note, bubble: { ...bubble }, mode }); return () => listeners.delete(listener) } })
  }
  let current = null
  function mount(options = {}) {
    if (current && !current.state().destroyed) return current
    try { if (typeof options.authorized === 'function' && !options.authorized()) return null } catch (_) { return null }
    current = create(options)
    if (!current) return null
    const render = state => {
      let warning = document.querySelector('[data-bgm-session-note]')
      if (state.sessionNote && !warning) {
        warning = document.createElement('div'); warning.dataset.bgmSessionNote = ''; warning.setAttribute('role', 'status')
        warning.style.cssText = 'position:fixed;bottom:calc(env(safe-area-inset-bottom,0px) + 8px);left:12px;right:12px;max-width:536px;margin:auto;padding:8px 12px;background:#191329;color:#eee;font-size:12px;border-radius:10px;z-index:1200;pointer-events:none'
        document.body.appendChild(warning)
      }
      if (warning) { warning.textContent = state.sessionNote; warning.hidden = !state.sessionNote }
      const loader = document.getElementById('home-loading-screen')
      if (options.mode === 'home' && loader) {
        let button = loader.querySelector('[data-bgm-loader-pause]')
        if (!button) {
          button = document.createElement('button'); button.type = 'button'; button.dataset.bgmLoaderPause = ''; button.textContent = '暂停音乐'
          button.style.cssText = 'position:absolute;z-index:3;right:16px;top:calc(env(safe-area-inset-top,0px) + 16px);background:transparent;border:1px solid #ffffff40;color:#eee;border-radius:18px;padding:7px 12px;font-size:12px'
          button.addEventListener('click', () => current.player.pause()); loader.appendChild(button)
        }
        button.hidden = state.intent !== 'play' || state.closed || !['playing', 'loading', 'pausing'].includes(state.actual)
      }
    }
    current.subscribe(render)
    window.dispatchEvent(new CustomEvent('bgm:ready', { detail: current }))
    return current
  }
  window.BgmPage = Object.freeze({ create, mount, getCurrent: () => current,
    suspendAccess() { if (current) current.suspend('access') } })
})()

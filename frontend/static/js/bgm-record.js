/* One shared record and cover policy for home, panel and later page bubbles. */
(function () {
  'use strict'
  if (window.BgmRecord) return
  const DEFAULT_COVER = '/static/images/bgm/record.svg'
  const icons = Object.freeze({
    play: '<path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
    pause: '<path d="M8 5v14M16 5v14" stroke-width="4"/>',
    next: '<path d="m5 5 11 7-11 7Z" fill="currentColor" stroke="none"/><path d="M19 5v14" stroke-width="2.5"/>',
    down: '<path d="m5 9 7 7 7-7"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    volume: '<path d="M3 9h4l5-4v14l-5-4H3ZM16 8a6 6 0 0 1 0 8M19 5a10 10 0 0 1 0 14"/>',
    music: '<path d="M9 18V5l12-2v13M9 8l12-2"/><ellipse cx="5.5" cy="18" rx="3.5" ry="3"/><ellipse cx="17.5" cy="16" rx="3.5" ry="3"/>'
  })
  const icon = name => '<svg class="bgm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + (icons[name] || '') + '</svg>'
  function equalizer(className = '') {
    const element = document.createElement('span'); element.className = 'bgm-equalizer' + (className ? ' ' + className : ''); element.setAttribute('aria-hidden', 'true')
    for (let i = 0; i < 3; i++) element.append(document.createElement('i'))
    return element
  }
  function create({ onActivate, label = '打开背景音乐面板' } = {}) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'bgm-record'; button.setAttribute('aria-label', label)
    const scale = document.createElement('span'); scale.className = 'bgm-record-scale'
    const disc = document.createElement('span'); disc.className = 'bgm-record-disc'; disc.setAttribute('aria-hidden', 'true')
    const fallback = document.createElement('span'); fallback.className = 'bgm-record-fallback'; fallback.innerHTML = icon('music')
    const base = new Image(); base.className = 'bgm-record-image'; base.alt = ''; base.draggable = false
    base.onerror = () => { base.hidden = true }; base.src = DEFAULT_COVER
    disc.append(fallback, base); scale.append(disc, equalizer('bgm-record-playing-mark')); button.append(scale)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)'), failed = new Set()
    let rotation = null
    try { if (typeof disc.animate === 'function') rotation = disc.animate([{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }], { duration: 12000, iterations: Infinity }) } catch (_) { /* Optional motion cannot block the control. */ }
    if (rotation) { disc.style.animation = 'none'; rotation.pause() }
    let signature = '', generation = 0, cover = null, pending = null, timer = null, playing = false, visible = true, destroyed = false
    function syncMotion() {
      const active = playing && visible && !document.hidden && !reduced.matches
      if (rotation) active ? rotation.play() : rotation.pause()
      else disc.style.animationPlayState = active ? 'running' : 'paused'
      button.classList.toggle('is-playing', playing)
      button.classList.toggle('is-motion-active', active)
    }
    function forgetPending() { clearTimeout(timer); if (pending) { pending.onload = pending.onerror = null; pending.removeAttribute('src'); pending = null } }
    function setCover(track) {
      const key = track ? [track.id, track.cover_version, track.cover_url].join('|') : ''
      if (key === signature) return
      signature = key; const epoch = ++generation; forgetPending()
      if (cover) { cover.remove(); cover = null }
      button.dataset.cover = 'default'
      if (!track || !track.cover_url || failed.has(key)) return
      const image = new Image(); image.className = 'bgm-record-image bgm-record-cover'; image.alt = ''; image.draggable = false; pending = image
      const fail = () => {
        if (epoch !== generation || destroyed) return
        failed.add(key); if (failed.size > 64) failed.delete(failed.values().next().value)
        forgetPending(); button.dataset.cover = 'fallback'
      }
      image.onload = () => {
        if (epoch !== generation || destroyed) return
        clearTimeout(timer); image.onload = image.onerror = null; pending = null; cover = image; disc.append(image); button.dataset.cover = 'custom'
      }
      image.onerror = fail; timer = setTimeout(fail, 5000); image.src = track.cover_url
    }
    function update(state) { if (!destroyed) { playing = state.actual === 'playing' && !state.closed && !state.blockers.length; syncMotion(); setCover(state.track) } }
    const activate = event => { if (onActivate) onActivate(event) }
    button.addEventListener('click', activate); reduced.addEventListener('change', syncMotion); document.addEventListener('visibilitychange', syncMotion)
    return Object.freeze({ element: button, disc, update,
      setLabel(value) { button.setAttribute('aria-label', value) },
      setVisible(value) { visible = value; syncMotion() },
      destroy() { destroyed = true; generation++; forgetPending(); if (rotation) rotation.cancel(); reduced.removeEventListener('change', syncMotion); document.removeEventListener('visibilitychange', syncMotion); button.removeEventListener('click', activate); button.remove() } })
  }
  window.BgmRecord = Object.freeze({ create, icon, equalizer, defaultCover: DEFAULT_COVER })
})()

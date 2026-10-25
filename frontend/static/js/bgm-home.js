/* Public home controls. One record element moves between the fifth slot and dialog. */
(function () {
  'use strict'
  if (window.BgmHome) return
  let instance
  function mount(page = window.BgmPage && window.BgmPage.getCurrent()) {
    if (instance || !page || page.state().mode !== 'home') return instance
    const entry = document.getElementById('bgm-home-entry'), homeSlot = document.getElementById('bgm-home-slot')
    if (!entry || !homeSlot || !window.BgmRecord) return null
    const player = page.player, reduced = matchMedia('(prefers-reduced-motion: reduce)'), icon = window.BgmRecord.icon
    const backdrop = document.createElement('div'); backdrop.className = 'bgm-backdrop'; backdrop.hidden = true
    const panel = document.createElement('section'); panel.className = 'bgm-panel'; panel.id = 'bgm-panel'; panel.hidden = true
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-labelledby', 'bgm-panel-title'); panel.tabIndex = -1
    panel.innerHTML = `<div class="bgm-panel-handle" data-bgm-handle></div>
      <header class="bgm-panel-heading"><h2 id="bgm-panel-title">背景音乐<small>BGM</small></h2><button type="button" class="bgm-panel-collapse" aria-label="收起音乐面板">${icon('down')}</button></header>
      <div class="bgm-now"><div class="bgm-panel-slot"></div><div><strong class="bgm-current-name"></strong><span class="bgm-play-status" role="status"></span></div><div class="bgm-now-controls"><button type="button" class="bgm-play" aria-label="播放音乐"></button><button type="button" class="bgm-next" aria-label="下一首">${icon('next')}</button></div></div>
      <div class="bgm-list-heading"><span>音乐列表</span><span class="bgm-track-count"></span></div><div class="bgm-track-list" role="group" aria-label="音乐列表"></div>
      <div class="bgm-catalog-message" hidden><span></span><button type="button" class="bgm-retry">刷新音乐列表</button></div><p class="bgm-inline-note" role="status" hidden></p>
      <label class="bgm-volume-row">${icon('volume')}<input type="range" min="0" max="100" step="1" aria-label="音乐音量"><output></output></label>
      <div class="bgm-volume-fallback" hidden><span>此环境请使用设备音量</span><button type="button" class="bgm-mute">静音</button></div>
      <footer class="bgm-panel-footer"><span>让音乐陪你一会儿</span><button type="button" class="bgm-close-session">关闭本次 BGM</button></footer>`
    ;(window.AppShell?.overlayRoot || document.body).append(backdrop, panel)
    const $ = selector => panel.querySelector(selector), caption = document.getElementById('bgm-home-caption'), captionText = caption.querySelector('span')
    const background = document.querySelector('.page.h5-home-page'), sheetSlot = $('.bgm-panel-slot'), playButton = $('.bgm-play'), nextButton = $('.bgm-next')
    const list = $('.bgm-track-list'), message = $('.bgm-catalog-message'), slider = $('input[type=range]')
    let open = false, transition = 0, panelAnimation = null, recordAnimation = null, captionAnimation = null, captionSignature = '', rowsSignature = '', volumeNote = ''
    let pageOverflow = null, overlayLease = null, focusFrame = null
    const bindings = []
    function bind(target, name, callback) { target.addEventListener(name, callback); bindings.push(() => target.removeEventListener(name, callback)) }
    function scrollLock(lock) {
      if (overlayLease) return
      if (lock && !pageOverflow) { pageOverflow = [document.documentElement.style.overflow, document.body.style.overflow]; document.documentElement.style.overflow = document.body.style.overflow = 'hidden' }
      else if (!lock && pageOverflow) { [document.documentElement.style.overflow, document.body.style.overflow] = pageOverflow; pageOverflow = null }
    }
    let previousInert = false, ownedHistory = false, historyBackPending = false, drag = null, destroyed = false
    const historyId = 'bgm-' + Math.random().toString(36).slice(2)
    const record = window.BgmRecord.create({ onActivate(event) { event.stopPropagation(); setOpen(!open) } })
    record.element.setAttribute('aria-controls', panel.id); record.element.setAttribute('aria-expanded', 'false'); homeSlot.append(record.element)
    const animate = (node, frames, options) => { try { return node.animate ? node.animate(frames, options) : null } catch (_) { return null } }
    const text = (node, value) => { if (node.textContent !== value) node.textContent = value }
    function viewport() {
      const view = window.visualViewport
      panel.style.setProperty('--bgm-viewport-height', (view ? view.height : innerHeight) + 'px')
      panel.style.setProperty('--bgm-keyboard-inset', Math.max(0, view ? innerHeight - view.height - view.offsetTop : 0) + 'px')
      syncCaption()
    }
    function stopCaption() { if (captionAnimation) captionAnimation.cancel(); captionAnimation = null; captionSignature = '' }
    function syncCaption() {
      const s = player.state(), distance = Math.max(0, captionText.scrollWidth - caption.clientWidth)
      panel.classList.toggle('is-motion-active', open && !document.hidden && !reduced.matches)
      const overflow = s.actual === 'playing' && distance > 1
      caption.classList.toggle('is-overflow', overflow)
      const enabled = overflow && !open && !document.hidden && !reduced.matches && typeof captionText.animate === 'function'
      const key = enabled ? [captionText.textContent, distance, caption.clientWidth].join('|') : ''
      if (captionSignature === key) return
      stopCaption(); if (!enabled) return
      const travel = distance / 20 * 1000, duration = 2000 + 2 * travel
      captionAnimation = animate(captionText, [{ transform: 'translateX(0)', offset: 0 }, { transform: 'translateX(0)', offset: 1000 / duration },
        { transform: `translateX(-${distance}px)`, offset: (1000 + travel) / duration }, { transform: `translateX(-${distance}px)`, offset: (2000 + travel) / duration },
        { transform: 'translateX(0)', offset: 1 }], { duration, iterations: Infinity, easing: 'linear' }); captionSignature = key
    }
    function moveRecord(target, from, duration) {
      if (recordAnimation) recordAnimation.cancel()
      target.append(record.element)
      const to = record.element.getBoundingClientRect()
      if (duration && from.width && to.width && typeof record.element.animate === 'function') {
        recordAnimation = animate(record.element, [{ transformOrigin: '0 0', transform: `translate(${from.left - to.left}px,${from.top - to.top}px) scale(${from.width / to.width},${from.height / to.height})` },
          { transformOrigin: '0 0', transform: 'translate(0,0) scale(1)' }], { duration, easing: 'cubic-bezier(.2,.75,.25,1)' })
      }
    }
    function pushHistory() {
      if (!ownedHistory && !historyBackPending) { history.pushState({ ...(history.state || {}), lxmBgmPanel: historyId }, '', location.href); ownedHistory = true }
    }
    function setOpen(next, { historyChange = true } = {}) {
      if (destroyed || next && player.state().blockers.includes('call')) return
      if (overlayLease && historyChange) return next ? overlayLease.open() : overlayLease.close()
      if (open === next) return
      const from = record.element.getBoundingClientRect(), epoch = ++transition, duration = reduced.matches ? 0 : 400
      if (panelAnimation) panelAnimation.cancel()
      open = next; scrollLock(next); window.BgmOutput.commitVolume(); viewport()
      if (next) {
        if (background && !overlayLease) { previousInert = background.inert; background.inert = true }
        backdrop.hidden = panel.hidden = false; panel.style.pointerEvents = ''; panel.style.transform = 'translateX(-50%)'; panel.setAttribute('aria-modal', 'true'); panel.removeAttribute('aria-hidden')
        if (duration && panel.animate) panelAnimation = animate(panel, [{ transform: 'translate(-50%,100%)' }, { transform: 'translate(-50%,0)' }], { duration, easing: 'cubic-bezier(.2,.75,.25,1)' })
        moveRecord(sheetSlot, from, duration)
        if (historyChange) pushHistory()
        void player.event('panel')
        focusFrame = requestAnimationFrame(() => { focusFrame = null; if (!destroyed && open) (playButton.disabled ? $('.bgm-panel-collapse') : playButton).focus({ preventScroll: true }) })
      } else {
        if (background && !overlayLease) background.inert = previousInert
        backdrop.hidden = true; panel.style.pointerEvents = 'none'; panel.removeAttribute('aria-modal'); panel.setAttribute('aria-hidden', 'true')
        moveRecord(homeSlot, from, duration)
        if (historyChange && ownedHistory) { ownedHistory = false; historyBackPending = true; history.back() }
        const finish = () => { if (epoch === transition && !open) panel.hidden = true }
        if (duration && panel.animate) {
          panelAnimation = animate(panel, [{ transform: panel.style.transform || 'translateX(-50%)' }, { transform: 'translate(-50%,100%)' }], { duration, easing: 'cubic-bezier(.2,.75,.25,1)' })
          if (panelAnimation) panelAnimation.finished.then(finish).catch(() => {}); else finish()
        } else finish()
        if (!overlayLease) record.element.focus({ preventScroll: true })
      }
      record.setLabel(open ? '收起背景音乐面板' : '打开背景音乐面板'); record.element.setAttribute('aria-expanded', String(open)); syncCaption()
    }
    function status(s) {
      if (s.closed) return '本次已关闭'
      if (s.failure && s.recoveryRequired) return s.failure.message
      if (s.catalogStatus === 'error') return '音乐列表暂不可用，请重试'
      if (s.catalogStatus === 'empty') return '暂无可播放音乐'
      if (s.actual === 'playing') return s.capabilities && s.capabilities.muted ? '静音播放中' : '正在播放'
      if (s.actual === 'loading' || s.catalogStatus === 'loading') return '正在加载音乐'
      if (s.actual === 'error') return '音乐播放失败，请重试'
      if (s.blockers.length) return '音乐已临时暂停'
      return '已暂停，等你继续'
    }
    const pausable = s => s.intent === 'play' && !s.closed && !s.recoveryRequired && (['playing', 'loading', 'pausing'].includes(s.actual) || s.catalogStatus === 'loading')
    function render(s) {
      if (destroyed) return
      record.update(s)
      const playing = s.actual === 'playing' && !s.closed && !s.blockers.length, name = s.track ? s.track.name : '暂无可播放音乐'
      const captionValue = playing ? name : 'BGM'
      if (captionText.textContent !== captionValue) { stopCaption(); captionText.textContent = captionValue }
      entry.title = captionValue; caption.title = captionValue; text($('.bgm-current-name'), name); $('.bgm-current-name').title = name; text($('.bgm-play-status'), status(s))
      const playIcon = pausable(s) ? 'pause' : 'play'
      if (playButton.dataset.icon !== playIcon) { playButton.innerHTML = icon(playIcon); playButton.dataset.icon = playIcon }
      playButton.setAttribute('aria-label', pausable(s) ? '暂停音乐' : s.recoveryRequired ? '重试播放音乐' : '播放音乐')
      playButton.disabled = s.catalogStatus === 'empty' || s.blockers.includes('call') || s.blockers.includes('access')
      nextButton.disabled = !s.nextEnabled || s.blockers.length > 0
      $('.bgm-close-session').disabled = s.closed
      text($('.bgm-track-count'), `${s.tracks.length} 首 · 顺序循环`)
      const key = JSON.stringify([s.tracks.map(t => [t.id, t.name]), s.track && s.track.id, playing, s.actual, s.closed, s.capabilities && s.capabilities.muted])
      if (key !== rowsSignature) {
        const focused = document.activeElement && document.activeElement.dataset.track
        list.replaceChildren()
        for (const [index, track] of s.tracks.entries()) {
          const row = document.createElement('button'); row.type = 'button'; row.className = 'bgm-track-row'; row.dataset.track = track.id; row.setAttribute('aria-pressed', String(!!s.track && s.track.id === track.id))
          const number = document.createElement('span'); number.className = 'bgm-track-number'; number.setAttribute('aria-hidden', 'true')
          if (s.track && s.track.id === track.id && playing) number.append(window.BgmRecord.equalizer())
          else number.textContent = String(index + 1).padStart(2, '0')
          const title = document.createElement('span'); title.className = 'bgm-track-title'; title.textContent = track.name
          const mark = document.createElement('span'); mark.className = 'bgm-track-state'
          if (s.track && s.track.id === track.id) mark.textContent = playing ? s.capabilities && s.capabilities.muted ? '静音' : '播放中' : s.actual === 'loading' ? '加载中' : '已选择'
          row.append(number, title, mark); row.addEventListener('click', () => void player.select(track.id)); list.append(row)
          if (focused === track.id) row.focus({ preventScroll: true })
        }
        rowsSignature = key
      }
      const showMessage = !s.tracks.length || s.catalogStatus === 'error'
      list.hidden = showMessage; message.hidden = !showMessage
      if (showMessage) { text(message.querySelector('span'), s.catalogStatus === 'empty' ? '暂时没有可播放的背景音乐' : s.catalogStatus === 'error' ? '音乐列表暂时加载失败，稍后可以再试。' : '正在读取音乐列表'); text($('.bgm-retry'), s.catalogStatus === 'error' ? '重试加载' : '刷新音乐列表') }
      const note = [s.notice && s.notice.message, volumeNote].filter(Boolean).join('；'); $('.bgm-inline-note').hidden = !note; text($('.bgm-inline-note'), note)
      const cap = s.capabilities || window.BgmOutput.capabilities(), value = Math.round(cap.volume * 100)
      $('.bgm-volume-row').hidden = cap.mode === 'device' || s.catalogStatus === 'empty'; $('.bgm-volume-fallback').hidden = cap.mode !== 'device' || s.catalogStatus === 'empty'
      if (Number(slider.value) !== value) slider.value = value
      slider.style.setProperty('--bgm-volume', value + '%')
      text($('.bgm-volume-row output'), value + '%'); slider.setAttribute('aria-valuetext', value === 0 ? '静音' : value + '%'); text($('.bgm-mute'), cap.muted ? '取消静音' : '静音')
      if (s.blockers.includes('call') && open) setOpen(false)
      syncCaption()
    }
    function refresh() { render(page.state()) }
    function commitVolume() { if (destroyed) return; const saved = window.BgmOutput.commitVolume(); volumeNote = saved.note || ''; refresh() }
    bind(slider, 'input', () => { if (destroyed) return; window.BgmOutput.previewVolume(Number(slider.value) / 100); refresh() })
    for (const event of ['change', 'pointerup', 'blur']) bind(slider, event, commitVolume)
    bind(slider, 'pointercancel', () => { if (destroyed) return; window.BgmOutput.cancelVolumePreview(); refresh() })
    $('.bgm-mute').onclick = () => { if (destroyed) return; const result = window.BgmOutput.capabilities().muted ? window.BgmOutput.unmute() : window.BgmOutput.setVolume(0); volumeNote = result.note || ''; refresh() }
    playButton.onclick = () => pausable(player.state()) ? player.pause() : void player.play('home')
    nextButton.onclick = () => void player.next(); $('.bgm-close-session').onclick = () => player.close()
    $('.bgm-retry').onclick = () => void player.event('panel'); $('.bgm-panel-collapse').onclick = () => setOpen(false)
    backdrop.onclick = () => setOpen(false); bind(entry, 'click', () => setOpen(!open))
    function keys(event) {
      if (!open) return
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false) }
      if (event.key === 'Tab') {
        const buttons = [...panel.querySelectorAll('button:not(:disabled),input:not(:disabled)')].filter(node => node.getClientRects().length && !node.closest('[hidden]'))
        if (!buttons.length) { event.preventDefault(); panel.focus(); return }
        const first = buttons[0], last = buttons[buttons.length - 1]
        if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { event.preventDefault(); first.focus() }
      }
    }
    function popped() {
      const wasPending = historyBackPending; historyBackPending = false
      ownedHistory = !!(history.state && history.state.lxmBgmPanel === historyId)
      if (wasPending && open) pushHistory()
      else if (!wasPending && open && !ownedHistory) setOpen(false, { historyChange: false })
    }
    function pointerDown(event) {
      if (!open || event.button !== 0 || event.target.closest('button')) return
      drag = { id: event.pointerId, start: event.clientY, dy: 0 }; event.currentTarget.setPointerCapture(event.pointerId)
    }
    function pointerMove(event) { if (drag && event.pointerId === drag.id) { drag.dy = Math.max(0, event.clientY - drag.start); panel.style.transform = `translate(-50%,${drag.dy}px)` } }
    function pointerUp(event) {
      if (!drag || drag.id !== event.pointerId) return
      const dy = drag.dy; drag = null
      if (dy > 54) setOpen(false)
      else { if (!reduced.matches && panel.animate) animate(panel, [{ transform: panel.style.transform }, { transform: 'translateX(-50%)' }], { duration: 180 }); panel.style.transform = 'translateX(-50%)' }
    }
    for (const handle of [$('[data-bgm-handle]'), $('.bgm-panel-heading')]) { bind(handle, 'pointerdown', pointerDown); bind(handle, 'pointermove', pointerMove); bind(handle, 'pointerup', pointerUp); bind(handle, 'pointercancel', () => { drag = null; panel.style.transform = 'translateX(-50%)' }) }
    if (page.context) overlayLease = page.context.services.overlays.register({ kind: 'bgm', ownerId: page.ownerId, element: panel, background: page.context.root,
      open: () => setOpen(true, { historyChange: false }), close: () => setOpen(false, { historyChange: false }) })
    document.addEventListener('keydown', keys); if (!overlayLease) window.addEventListener('popstate', popped); window.addEventListener('resize', viewport); document.addEventListener('visibilitychange', syncCaption); reduced.addEventListener('change', syncCaption)
    if (window.visualViewport) { visualViewport.addEventListener('resize', viewport); visualViewport.addEventListener('scroll', viewport) }
    let resize = null
    try { if (typeof ResizeObserver === 'function') { resize = new ResizeObserver(syncCaption); resize.observe(caption); resize.observe(captionText) } } catch (_) { if (resize) resize.disconnect(); resize = null }
    const unsubscribe = page.subscribe(render); viewport()
    instance = Object.freeze({ setOpen, isOpen: () => open, record, panel,
      destroy() { if (destroyed) return; overlayLease?.dispose(); destroyed = true; instance = null; bindings.forEach(remove => remove()); if (focusFrame !== null) cancelAnimationFrame(focusFrame); scrollLock(false); unsubscribe(); stopCaption(); if (resize) resize.disconnect(); if (panelAnimation) panelAnimation.cancel(); if (recordAnimation) recordAnimation.cancel(); record.destroy(); backdrop.remove(); panel.remove(); if (background && open && !overlayLease) background.inert = previousInert; document.removeEventListener('keydown', keys); window.removeEventListener('popstate', popped); window.removeEventListener('resize', viewport); document.removeEventListener('visibilitychange', syncCaption); reduced.removeEventListener('change', syncCaption); if (window.visualViewport) { visualViewport.removeEventListener('resize', viewport); visualViewport.removeEventListener('scroll', viewport) } } })
    return instance
  }
  window.BgmHome = Object.freeze({ mount, current: () => instance })
  if (!window.AppShell) {
  window.addEventListener('bgm:ready', event => mount(event.detail))
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount(), { once: true }); else mount()
  }
})()

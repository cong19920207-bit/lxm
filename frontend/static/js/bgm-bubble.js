/* Six explicit page adapters; no automatic detection of arbitrary page content. */
(function () {
  'use strict'
  if (window.BgmBubble) return
  const sharedOverlays = '#auth-login-modal.is-open,.modal-overlay'
  const pages = Object.freeze({
    feed: { top: '.feed-hero-bar', bottom: '', overlays: '.preview-overlay,#comment-mask.show,#comment-panel.show,#feed-boot-loading.is-visible' },
    diary: { top: '.diary-hero-bar', bottom: '', overlays: '' },
    memory: { top: '.nebula-top-bar', bottom: '#nebula-bottom-bar', overlays: '#nebula-sheet.is-open,#nebula-sheet-mask.is-open' },
    relationship: { top: '.rel-hero-bar', bottom: '', overlays: '.levelup-overlay' },
    chat: { top: '.chat-top-bar', bottom: '.input-area', overlays: '' },
    settings: { top: '.top-bar', bottom: '.logout-card', overlays: '', avoid: '.settings-item-action,.settings-item.clickable,.settings-expand-wrap.visible', observe: '#settings-private-sections,.settings-expand-wrap,.settings-page-body' }
  })
  let current
  function mount(page = window.BgmPage && window.BgmPage.getCurrent()) {
    if (current || !page || page.state().mode !== 'content') return current
    const name = location.pathname.split('/').pop().replace(/\.html$/, ''), config = pages[name]
    if (!config || !window.BgmRecord) return null
    const player = page.player, icon = window.BgmRecord.icon, overlaySelector = sharedOverlays + (config.overlays ? ',' + config.overlays : '')
    const observedSelector = [config.top, config.bottom, config.avoid, config.observe, '#auth-login-modal', '.modal-overlay', ...config.overlays.split(',').map(s => s.replace(/\.(is-open|is-visible|show)$/, ''))].filter(Boolean).join(',')
    const root = document.createElement('div'); root.className = 'bgm-bubble'; root.dataset.page = name
    const actions = document.createElement('div'); actions.className = 'bgm-bubble-actions'; actions.id = 'bgm-bubble-actions'; actions.hidden = true; actions.setAttribute('role', 'group'); actions.setAttribute('aria-label', '背景音乐控制')
    const play = document.createElement('button'); play.type = 'button'; play.className = 'bgm-bubble-play'
    const close = document.createElement('button'); close.type = 'button'; close.className = 'bgm-bubble-close'; close.innerHTML = icon('close') + '<span>关闭本次</span>'; close.setAttribute('aria-label', '关闭本次 BGM')
    actions.append(play, close)
    const record = window.BgmRecord.create({ onActivate(event) { if (event.detail && performance.now() < suppressClickUntil) return; setExpanded(!expanded) } })
    record.element.setAttribute('aria-controls', actions.id); record.element.setAttribute('aria-expanded', 'false'); root.append(actions, record.element)
    const safe = document.createElement('div'); safe.className = 'bgm-safe-insets'; safe.setAttribute('aria-hidden', 'true'); document.body.append(safe)
    let expanded = false, destroyed = false, frame = null, drag = null, suppressClickUntil = 0, ratio = page.state().bubble.y, bounds = null
    const cleanup = [], observed = new Set()
    function bind(target, event, callback, options) { target.addEventListener(event, callback, options); cleanup.push(() => target.removeEventListener(event, callback, options)) }
    function visible(node) {
      if (!node || !node.isConnected || node.hidden || node.getAttribute('aria-hidden') === 'true') return false
      const css = getComputedStyle(node), rect = node.getBoundingClientRect()
      return css.display !== 'none' && css.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    function obscured() { return document.fullscreenElement || [...document.querySelectorAll(overlaySelector)].some(visible) }
    function setExpanded(value, focus = false) {
      expanded = value && root.isConnected && !root.hidden
      actions.hidden = !expanded; record.element.setAttribute('aria-expanded', String(expanded))
      layout()
      if (focus && root.isConnected && !root.hidden) record.element.focus({ preventScroll: true })
    }
    function layout() {
      if (destroyed || !root.isConnected || root.hidden) return
      const viewport = window.visualViewport, offsetTop = viewport ? viewport.offsetTop : 0, offsetLeft = viewport ? viewport.offsetLeft : 0
      const width = viewport ? viewport.width : innerWidth, height = viewport ? viewport.height : innerHeight
      const css = getComputedStyle(safe), safeTop = parseFloat(css.paddingTop) || 0, safeBottom = parseFloat(css.paddingBottom) || 0, safeRight = parseFloat(css.paddingRight) || 0, safeLeft = parseFloat(css.paddingLeft) || 0
      // Measure the rendered horizontal controls, including wrapped labels on small screens.
      const size = root.getBoundingClientRect(), recordWidth = size.width, recordHeight = size.height
      actions.style.maxWidth = Math.max(0, width - safeLeft - safeRight - 32 - recordWidth - 24) + 'px'
      const scale = record.element.querySelector('.bgm-record-scale').getBoundingClientRect()
      const mark = record.element.querySelector('.bgm-record-playing-mark').getBoundingClientRect()
      const extra = record.element.classList.contains('is-playing') ? [mark] : []
      const rects = [scale, ...extra, ...(expanded ? [actions.getBoundingClientRect()] : [])]
      const footprint = { left: Math.min(-7, ...rects.map(r => r.left - size.left)), right: Math.max(recordWidth + 7, ...rects.map(r => r.right - size.left)), top: Math.min(-7, ...rects.map(r => r.top - size.top)), bottom: Math.max(recordHeight + 7, ...rects.map(r => r.bottom - size.top)) }
      let top = offsetTop + safeTop + 16, bottom = offsetTop + height - safeBottom - 16
      const header = config.top && document.querySelector(config.top)
      if (visible(header)) { const r = header.getBoundingClientRect(); if (r.bottom > offsetTop && r.top < offsetTop + 80) top = Math.max(top, r.bottom + 12) }
      const footer = config.bottom && document.querySelector(config.bottom)
      if (visible(footer)) { const r = footer.getBoundingClientRect(); if (r.top < bottom && r.bottom > top) bottom = Math.min(bottom, r.top - 14) }
      const min = top - footprint.top, max = bottom - footprint.bottom
      bounds = { min, max, x: offsetLeft + width - safeRight - 16 - footprint.right, footprint, viewport: { top: offsetTop, height, width } }
      if (max < min || width < 220 || bounds.x + footprint.left < offsetLeft + safeLeft + 12) { root.hidden = true; setExpanded(false); record.setVisible(false); return }
      let intervals = [[min, max]]
      for (const node of config.avoid ? document.querySelectorAll(config.avoid) : []) {
        if (!visible(node)) continue
        const r = node.getBoundingClientRect()
        if (r.left >= bounds.x + footprint.right + 6 || r.right <= bounds.x + footprint.left - 6) continue
        const low = r.top - footprint.bottom - 6, high = r.bottom - footprint.top + 6
        intervals = intervals.flatMap(([a, b]) => high <= a || low >= b ? [[a, b]] : [[a, Math.min(b, low)], [Math.max(a, high), b]].filter(([l, h]) => h > l))
      }
      if (!intervals.length) { root.hidden = true; setExpanded(false); record.setVisible(false); return }
      const desired = min + Math.max(0, Math.min(1, ratio)) * (max - min)
      const y = intervals.map(([a, b]) => Math.max(a, Math.min(b, desired))).sort((a, b) => Math.abs(a - desired) - Math.abs(b - desired))[0]
      bounds.intervals = intervals
      root.style.left = bounds.x + 'px'; root.style.top = y + 'px'
      record.setVisible(true)
    }
    function schedule() { if (frame === null && !destroyed) frame = requestAnimationFrame(() => { frame = null; render(page.state()) }) }
    const pausable = s => s.intent === 'play' && !s.recoveryRequired && ['playing', 'loading', 'pausing'].includes(s.actual)
    function render(s) {
      if (destroyed) return
      if (!drag) ratio = s.bubble.y
      record.update(s)
      const removed = s.closed || s.destroyed || s.catalogStatus === 'empty' || s.blockers.includes('call') || s.blockers.includes('access')
      const hidden = removed || document.hidden || !!obscured()
      if (hidden) { setExpanded(false); if (drag) { drag = null; suppressClickUntil = performance.now() + 400 } }
      if (removed) root.remove()
      else if (!root.isConnected) document.body.append(root)
      root.hidden = hidden
      const status = s.actual === 'playing' ? s.capabilities && s.capabilities.muted ? '静音播放中' : '正在播放' : s.recoveryRequired ? '等待手动恢复' : s.actual === 'loading' || s.catalogStatus === 'loading' ? '正在加载' : '已暂停'
      record.setLabel('背景音乐，' + status + '，展开控制'); root.title = s.track ? s.track.name : '背景音乐'
      const label = pausable(s) ? '暂停音乐' : s.recoveryRequired ? '重试播放音乐' : '播放音乐'
      if (play.getAttribute('aria-label') !== label) { play.innerHTML = icon(pausable(s) ? 'pause' : 'play') + '<span>' + (pausable(s) ? '暂停' : s.recoveryRequired ? '重试播放' : '播放') + '</span>'; play.setAttribute('aria-label', label) }
      play.disabled = s.blockers.length > 0
      layout()
      record.setVisible(root.isConnected && !root.hidden)
    }
    play.onclick = () => pausable(player.state()) ? player.pause() : void player.play('bubble')
    close.onclick = () => player.close()
    bind(document, 'pointerdown', event => { if (expanded && !root.contains(event.target)) setExpanded(false) }, true)
    bind(document, 'keydown', event => { if (expanded && event.key === 'Escape') { event.preventDefault(); setExpanded(false, true) } })
    bind(record.element, 'pointerdown', event => {
      if (event.button !== 0 || !bounds) return
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, top: parseFloat(root.style.top), moved: false }
      record.element.setPointerCapture(event.pointerId)
    })
    bind(record.element, 'pointermove', event => {
      if (!drag || event.pointerId !== drag.id) return
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 6) drag.moved = true
      if (!drag.moved) return
      event.preventDefault(); setExpanded(false)
      ratio = Math.max(0, Math.min(1, (drag.top + event.clientY - drag.y - bounds.min) / Math.max(1, bounds.max - bounds.min))); layout()
    })
    bind(record.element, 'pointerup', event => {
      if (!drag || event.pointerId !== drag.id) return
      const moved = drag.moved; drag = null
      if (moved) { suppressClickUntil = performance.now() + 400; ratio = Math.max(0, Math.min(1, (parseFloat(root.style.top) - bounds.min) / Math.max(1, bounds.max - bounds.min))); page.setBubble({ x: 1, y: ratio }); layout() }
    })
    bind(record.element, 'pointercancel', () => { drag = null; suppressClickUntil = performance.now() + 400; render(page.state()) })
    bind(record.element, 'keydown', event => {
      if (!['ArrowUp', 'ArrowDown'].includes(event.key) || !bounds) return
      event.preventDefault(); ratio = Math.max(0, Math.min(1, ratio + (event.key === 'ArrowUp' ? -.1 : .1))); page.setBubble({ x: 1, y: ratio }); layout()
    })
    bind(record.element, 'transitionend', schedule)
    // Observe only explicitly named page regions and modal roots, never canvas animation descendants.
    const mutations = new MutationObserver(() => { discover(); render(page.state()) })
    let resize = null
    try { if (window.ResizeObserver) resize = new ResizeObserver(schedule) } catch (_) {}
    function discover() {
      const nodes = new Set(document.querySelectorAll(observedSelector))
      if (nodes.size === observed.size && [...nodes].every(node => observed.has(node))) return
      mutations.disconnect(); mutations.observe(document.body, { childList: true })
      if (resize) for (const node of observed) resize.unobserve(node)
      observed.clear()
      for (const node of nodes) {
        observed.add(node); mutations.observe(node, { attributes: true, attributeFilter: ['class', 'style', 'hidden', 'aria-hidden'] }); if (resize) resize.observe(node)
      }
    }
    mutations.observe(document.body, { childList: true }); discover()
    bind(window, 'resize', schedule); bind(window, 'scroll', schedule, { passive: true }); bind(document, 'visibilitychange', schedule); bind(document, 'fullscreenchange', schedule); bind(window, 'pageshow', schedule)
    if (window.visualViewport) { bind(visualViewport, 'resize', schedule); bind(visualViewport, 'scroll', schedule) }
    const unsubscribe = page.subscribe(render)
    current = Object.freeze({ record, element: root,
      inspect: () => ({ page: name, expanded, visible: root.isConnected && !root.hidden, ratio, bounds }),
      destroy() { if (destroyed) return; destroyed = true; unsubscribe(); cleanup.forEach(fn => fn()); mutations.disconnect(); if (resize) resize.disconnect(); if (frame !== null) cancelAnimationFrame(frame); record.destroy(); root.remove(); safe.remove(); current = null } })
    return current
  }
  window.BgmBubble = Object.freeze({ mount, current: () => current })
  window.addEventListener('bgm:ready', event => mount(event.detail))
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount(), { once: true }); else mount()
})()

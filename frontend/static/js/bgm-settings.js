(function () {
  'use strict'
  let current = null
  function mount(page = window.BgmPage?.getCurrent(), root = page?.context?.root || document) {
    current?.destroy()
    let destroyed = false
    const cleaners = [], valid = () => !destroyed && (!page?.context || page.context.valid())
    function renderCapability(state) {
      if (!valid()) return
      const description = root.querySelector('#bgm-fade-desc')
      if (!description) return
      const capability = state?.capabilities || window.BgmOutput?.capabilities()
      const unavailable = capability && ['gain', 'media', 'device'].includes(capability.mode) && capability.fadeAvailable === false
      description.textContent = unavailable ? '当前环境暂不支持，使用直接播放／暂停' : description.dataset?.supportedDescription || '在开始、暂停和切换时，让声音自然过渡'
    }
    function render(field) {
      if (!valid()) return
      const result = window.BgmPreferences.read(field), button = root.querySelector('[data-bgm-preference="' + field + '"]')
      if (!button) return
      button.classList.toggle('active', result.value); button.setAttribute('aria-checked', String(result.value))
      const note = root.querySelector('#' + button.dataset.note); if (note) note.textContent = result.note
    }
    function refresh() { root.querySelectorAll('[data-bgm-preference]').forEach(button => render(button.dataset.bgmPreference)); renderCapability(page?.state()) }
    root.querySelectorAll('[data-bgm-preference]').forEach(button => {
      const field = button.dataset.bgmPreference
      const click = () => {
        if (!valid()) return
        const value = !window.BgmPreferences.read(field).value
        if (field === 'fadeEnabled' && window.BgmOutput) window.BgmOutput.setFadeEnabled(value)
        else window.BgmPreferences.write(field, value)
        render(field)
      }
      button.addEventListener('click', click); cleaners.push(() => button.removeEventListener('click', click))
    })
    if (page) cleaners.push(page.subscribe(renderCapability))
    refresh()
    const instance = Object.freeze({ refresh, destroy() { if (destroyed) return; destroyed = true; cleaners.forEach(fn => fn()); if (current === instance) current = null } })
    current = instance; return instance
  }
  window.BgmSettings = Object.freeze({ mount, current: () => current })
  if (!window.AppShell) {
    document.addEventListener('DOMContentLoaded', () => mount(), { once: true })
    window.addEventListener('pageshow', () => current?.refresh())
    window.addEventListener('bgm:ready', event => mount(event.detail))
  }
})()

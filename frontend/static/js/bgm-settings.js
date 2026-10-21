(function () {
  'use strict'
  let observedPage = null, unsubscribe = null
  function renderCapability(state) {
    const description = document.getElementById('bgm-fade-desc')
    if (!description) return
    const capability = state && state.capabilities || window.BgmOutput && window.BgmOutput.capabilities()
    const unavailable = capability && ['gain', 'media', 'device'].includes(capability.mode) && capability.fadeAvailable === false
    description.textContent = unavailable ? '当前环境暂不支持，使用直接播放／暂停' : '在开始、暂停和切换时，让声音自然过渡'
  }
  function observePage(page = window.BgmPage && window.BgmPage.getCurrent()) {
    if (!page || page === observedPage) { renderCapability(page && page.state()); return }
    if (unsubscribe) unsubscribe()
    observedPage = page; unsubscribe = page.subscribe(renderCapability)
  }
  function render(field) {
    const result = window.BgmPreferences.read(field)
    const button = document.querySelector('[data-bgm-preference="' + field + '"]')
    if (!button) return
    button.classList.toggle('active', result.value)
    button.setAttribute('aria-checked', String(result.value))
    document.getElementById(button.dataset.note).textContent = result.note
  }
  function initialize() {
    document.querySelectorAll('[data-bgm-preference]').forEach(button => {
      const field = button.dataset.bgmPreference
      button.addEventListener('click', () => {
        const value = !window.BgmPreferences.read(field).value
        if (field === 'fadeEnabled' && window.BgmOutput) window.BgmOutput.setFadeEnabled(value)
        else window.BgmPreferences.write(field, value)
        render(field)
      })
      render(field)
    })
    observePage()
  }
  document.addEventListener('DOMContentLoaded', initialize, { once: true })
  // Re-render saved choices on document restoration; never send player commands.
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-bgm-preference]').forEach(button => render(button.dataset.bgmPreference))
    observePage()
  })
  window.addEventListener('bgm:ready', event => observePage(event.detail))
})()

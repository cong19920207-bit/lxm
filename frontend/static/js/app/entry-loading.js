// One persistent loading composition; only its footer changes after preparation.
export const loadingMarkup = `  <div id="home-loading-screen" class="home-loading-screen" aria-live="polite" aria-busy="true">
    <div class="home-loading-bg">
      <img id="home-loading-hero" src="/static/images/home-scene/v4/background.c094490a4d8e.webp" alt="" width="1024" height="1024">
      <div class="home-loading-bg-grad"></div>
      <div class="home-loading-vignette" aria-hidden="true"></div>
      <div class="home-loading-glow" aria-hidden="true"></div>
    </div>
    <div class="home-loading-particles" id="home-loading-particles" aria-hidden="true"></div>
    <div class="home-loading-brand">
      <div class="loading-avatar-stack">
        <span class="loading-avatar-glow" aria-hidden="true"></span>
        <span class="loading-avatar-ripple" aria-hidden="true"></span>
        <span class="loading-avatar-ripple loading-avatar-ripple--delay" aria-hidden="true"></span>
        <span class="loading-avatar-ring" aria-hidden="true"></span>
        <img id="loading-avatar"
             src="/static/images/home-thumbnails/v2/loader_avatar.68494af2b4bf.jpg"
             alt="林小梦"
             width="96"
             height="96">
      </div>
      <h1 class="home-loading-title" id="app-entry-title">林小梦</h1>
      <span class="home-loading-subtitle">正在靠近你的世界</span>
    </div>
    <div class="home-loading-footer">
      <div class="app-entry-progress-stage">
      <p id="home-loading-message">我在。别急。</p>
      <div class="home-loading-bar" id="app-entry-progress" role="progressbar" aria-label="页面加载进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div id="home-loading-bar-fill"></div>
      </div>
      <span id="home-loading-percent">0%</span>
      </div>
      <div class="app-entry-actions" inert aria-hidden="true">
        <p class="app-entry-features">
          <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true" focusable="false"><path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/></svg>背景音乐</span>
          <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true" focusable="false"><rect x="7" y="3" width="10" height="18" rx="2" transform="rotate(15 12 12)"/><path d="M3 9l-2 3 3 2m17-5 2 3-3 2"/></svg>倾斜互动</span>
        </p>
        <p class="app-entry-copy">进入时开启，可随时关闭。</p>
        <button id="app-entry-primary" class="app-entry-primary lxm-invitation-button" type="button" disabled>
          <span class="lxm-invitation-button__aura" aria-hidden="true"></span>
          <span class="lxm-invitation-button__surface" aria-hidden="true">
            <span class="lxm-invitation-button__wash"></span>
            <span class="lxm-invitation-button__shine"></span>
          </span>
          <span id="app-entry-primary-label" class="lxm-invitation-button__label">正在准备…</span>
          <svg class="lxm-invitation-button__arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M4 12h15m-5-5 5 5-5 5"/></svg>
        </button>
        <button id="app-entry-direct" class="app-entry-direct" type="button">直接进入</button>
        <p class="app-entry-note" id="app-entry-note" role="status">需要时，系统会请求倾斜授权。</p>
      </div>
    </div>
  </div>`;

    export function populateLoadingParticles(root, reduced) {
      if (reduced) return
      const wrap = root.querySelector('#home-loading-particles')
      if (!wrap) return

      const palette = [
        'rgba(255, 255, 255, 0.9)',
        'rgba(255, 119, 168, 0.85)',
        'rgba(160, 102, 255, 0.8)',
      ]

      // 全屏缓慢漂移星点（参考图密度，不过密）
      for (let i = 0; i < 18; i++) {
        const pt = document.createElement('span')
        pt.className = 'home-loading-particle home-loading-particle--drift'
        const size = 1.5 + Math.random() * 2.5
        const color = palette[i % palette.length]
        pt.style.left = (8 + Math.random() * 84) + '%'
        pt.style.top = (10 + Math.random() * 78) + '%'
        pt.style.width = size + 'px'
        pt.style.height = size + 'px'
        pt.style.background = color
        pt.style.boxShadow = '0 0 ' + (4 + Math.random() * 4) + 'px ' + color
        pt.style.setProperty('--pt-dur', (12 + Math.random() * 10) + 's')
        pt.style.setProperty('--pt-delay', (Math.random() * 8) + 's')
        pt.style.setProperty('--pt-o-min', String(0.2 + Math.random() * 0.15))
        pt.style.setProperty('--pt-o-mid', String(0.45 + Math.random() * 0.2))
        pt.style.setProperty('--pt-o-max', String(0.7 + Math.random() * 0.2))
        wrap.appendChild(pt)
      }

      // 少量自下而上飘升，范围加大
      for (let i = 0; i < 6; i++) {
        const pt = document.createElement('span')
        pt.className = 'home-loading-particle home-loading-particle--rise'
        const size = 2 + Math.random() * 2
        const color = palette[(i + 1) % palette.length]
        pt.style.left = (12 + Math.random() * 76) + '%'
        pt.style.bottom = (Math.random() * 18) + '%'
        pt.style.width = size + 'px'
        pt.style.height = size + 'px'
        pt.style.background = color
        pt.style.boxShadow = '0 0 6px ' + color
        pt.style.setProperty('--pt-dur', (9 + Math.random() * 7) + 's')
        pt.style.setProperty('--pt-delay', (Math.random() * 5) + 's')
        pt.style.setProperty('--pt-rise', (-55 - Math.random() * 35) + 'vh')
        wrap.appendChild(pt)
      }
    }

import { createHomeStartup } from './home-startup.js';
import { createPageTimers } from '../app/page-timers.js';

export async function mount(context) {
  const { root, services } = context, byId = id => root.querySelector('#' + id);
  const { setTimeout, clearTimeout, setInterval, clearInterval, requestAnimationFrame } = createPageTimers(context);
  const HomeStartup = createHomeStartup(context);
  let feedBadge = { unread: 0, hasNew: false, newCount: 0 };
  const styles = ['css/home-scene.css', 'css/bgm.css', 'css/voice-entry.css'];
  await Promise.all(styles.map(key => context.scope.adopt(services.resources.style(key), release => release())));
  for (const name of ['home-scene-core','home-scene','home-data','voice-playback','voice-audio-transport','voice-entry','bgm-page','bgm-record','bgm-home']) {
    await services.shared.script('js/' + name + '.js'); if (!context.valid()) return { unmount() {} };
  }

    const LEVEL_NAMES = ['陌生', '朋友', '亲密', '知己']
    const DIARY_PLACEHOLDER = '今天记录点什么好呢...'
    const HOME_LOADER_KEY = 'lxm_home_loader_done'
    const LOADER_MIN_MS = 3000
    const LOADER_HOLD_MS = 500
    const LOADER_MESSAGES = [
      '我在。别急。',
      '马上就见面了。',
      '来了？我等你一会儿了。',
    ]
    const STATIC_ASSETS = [
      '/static/images/home-scene/v4/background.c094490a4d8e.webp',
      '/static/images/Index/home-feed-icon.png',
      '/static/images/Index/home-diary-icon.png',
    ]

    const HOME_AVATAR_MAP = {
  "default": "/static/images/home-thumbnails/v2/default.0d3cb97c2162.webp",
  "平静": "/static/images/home-thumbnails/v2/emotion_calm.c92996b91505.webp",
  "开心": "/static/images/home-thumbnails/v2/emotion_happy.eed62969ffbc.webp",
  "好奇": "/static/images/home-thumbnails/v2/emotion_curious.cc184da7f1d6.webp",
  "想念": "/static/images/home-thumbnails/v2/emotion_miss.b552a52cadab.webp",
  "担心": "/static/images/home-thumbnails/v2/emotion_worry.7542495825fb.webp",
  "害羞": "/static/images/home-thumbnails/v2/emotion_shy.3c7f0553088b.webp",
  "困倦": "/static/images/home-thumbnails/v2/emotion_sleepy.779d18fc6bcb.webp"
}
    const HOME_LOADER_AVATAR = "/static/images/home-thumbnails/v2/loader_avatar.68494af2b4bf.jpg"
    const homeAvatarFailures = new Set()

    let clockTimer = null
    let loaderMsgTimer = null
    let loaderProgressTimer = null
    let loaderDismissTimer = null
    const loaderCleanups = []
    const initialHomeAuth = HomeStartup.auth()
    let homeAuthMode = initialHomeAuth.known ? (initialHomeAuth.token ? 'authenticated' : 'visitor') : 'unknown'
    let homeVisitorRendered = false

    function homeAvatarFallback(img, failedSrc) {
      homeAvatarFailures.add(new URL(failedSrc || img.src, location.href).pathname)
      const candidates = img.id === 'loading-avatar'
        ? [HOME_LOADER_AVATAR, HOME_AVATAR_MAP.default]
        : [HOME_AVATAR_MAP.default, HOME_LOADER_AVATAR]
      const next = candidates.find(src => !homeAvatarFailures.has(src))
      if (next) {
        if (new URL(img.src, location.href).pathname !== next) img.src = next
      } else {
        img.onerror = null
        img.removeAttribute('src')
        img.style.visibility = 'hidden'
      }
    }

    function handleAvatarError(img) { homeAvatarFallback(img) }
    function handleLoaderAvatarError(img) { homeAvatarFallback(img) }

    function updateHomeAvatar(emotion, isCurrent) {
      const img = byId('linxiaomeng-avatar')
      const src = emotionAvatarSrc(emotion)
      if (!img) return
      if (homeAvatarFailures.has(src)) { homeAvatarFallback(img, src); return }
      if (new URL(img.src, location.href).pathname === src) {
        if (img.complete && !img.naturalWidth) homeAvatarFallback(img, src)
        return
      }
      const preload = new Image()
      const release = context.cleanup(() => {
        preload.onload = preload.onerror = null
        if (!preload.complete) preload.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='
      })
      preload.onload = () => { release(); if (context.valid() && (!isCurrent || isCurrent())) img.src = src }
      preload.onerror = () => { release(); if (context.valid() && (!isCurrent || isCurrent())) homeAvatarFallback(img, src) }
      preload.src = src
    }

    function isReloadNavigation() {
      const nav = performance.getEntriesByType('navigation')[0]
      return context.reason === 'initial' && !!(nav && nav.type === 'reload')
    }

    function shouldSkipHomeLoader() {
      if (context.reason === 'resume' && context.state?.loaderDone === false) return false
      if (context.reason !== 'initial') return true
      if (isReloadNavigation()) return false
      try {
        return sessionStorage.getItem(HOME_LOADER_KEY) === '1'
      } catch (e) {
        return false
      }
    }

    function prefersReducedMotion() {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    }

    function preloadImage(src) {
      if (homeAvatarFailures.has(src)) return Promise.resolve()
      const existing = [...root.querySelectorAll('img')].find(img => new URL(img.src, location.href).pathname === src)
      if (existing) {
        if (existing.complete) return Promise.resolve()
        return new Promise(resolve => {
          existing.addEventListener('load', resolve, { once: true })
          existing.addEventListener('error', resolve, { once: true })
        })
      }
      return new Promise((resolve) => {
        const img = new Image()
        img.onload = () => resolve()
        img.onerror = () => {
          if (src.startsWith('/static/images/home-thumbnails/')) homeAvatarFailures.add(src)
          resolve()
        }
        img.src = src
      })
    }

    function emotionAvatarSrc(emotion) {
      if (!emotion) return HOME_AVATAR_MAP.default
      return HOME_AVATAR_MAP[emotion] || HOME_AVATAR_MAP.default
    }

    function updateLoadingProgressUI(progress) {
      const fill = byId('home-loading-bar-fill')
      const percent = byId('home-loading-percent')
      if (fill) fill.style.width = progress + '%'
      if (percent) percent.textContent = Math.round(progress) + '%'
    }

    function initLoadingParticles() {
      if (prefersReducedMotion()) return
      const wrap = byId('home-loading-particles')
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

    function triggerHomeEntrance() {
      const page = root.querySelector('.h5-home-page')
      if (!page) return
      if (prefersReducedMotion()) {
        page.classList.add('is-enter-active')
        return
      }
      page.classList.add('is-enter-reveal')
      requestAnimationFrame(() => {
        page.classList.add('is-enter-active')
      })
    }

    function clearLoaderTimers() {
      for (const clean of loaderCleanups.splice(0)) clean()
      if (loaderMsgTimer) {
        clearInterval(loaderMsgTimer)
        loaderMsgTimer = null
      }
      if (loaderProgressTimer) {
        clearInterval(loaderProgressTimer)
        loaderProgressTimer = null
      }
      if (loaderDismissTimer) {
        clearTimeout(loaderDismissTimer)
        loaderDismissTimer = null
      }
    }

    function dismissHomeLoader() {
      const state = HomeStartup
      if (state.phase === 'ready' || state.disposed) return
      const screen = byId('home-loading-screen')
      state.phase = 'exiting'
      if (screen) { screen.setAttribute('aria-busy', 'false'); screen.classList.add('is-exiting') }
      triggerHomeEntrance()
      loaderDismissTimer = setTimeout(() => {
        clearLoaderTimers()
        state.complete(false)
      }, prefersReducedMotion() ? 0 : 550)
    }

    function hideHomeLoaderImmediately() {
      clearLoaderTimers()
      HomeStartup.complete(false)
    }

    function waitCoreImage(img) {
      return new Promise(resolve => {
        let settled = false
        const finish = () => {
          if (settled) return
          settled = true
          clearTimeout(deadline)
          img.removeEventListener('load', loaded)
          img.removeEventListener('error', finish)
          resolve()
        }
        const loaded = () => {
          if (img.naturalWidth && typeof img.decode === 'function') {
            try { Promise.resolve(img.decode()).then(finish, finish) } catch (_) { finish() }
          } else finish()
        }
        const deadline = setTimeout(finish, Math.max(0, HomeStartup.coreDeadline - Date.now()))
        context.cleanup(finish)
        img.addEventListener('load', loaded, { once: true })
        img.addEventListener('error', finish, { once: true })
        if (img.complete) loaded()
      })
    }

    function runHomeLoader() {
      const state = HomeStartup
      let coreReady = false, finishing = false, msgIndex = 0
      byId('main-content').classList.add('content-loaded')
      // Data and avatar updates run independently of the core-image gate.
      loadPage().catch(() => {})
      if (state.phase === 'ready' || !byId('home-loading-screen')) {
        state.complete(false)
        return
      }
      try { initLoadingParticles() } catch (_) { /* Optional decoration */ }
      const coreImages = [...root.querySelectorAll('.home-scene-core')]
      Promise.all(coreImages.map(waitCoreImage)).then(async () => {
        if (!context.valid()) return
        if (state.sceneMode === 'dynamic' && coreImages.every(image => !image.naturalWidth)) state.useLegacyScene()
        if (state.sceneMode === 'legacy') await waitCoreImage(root.querySelector('.home-scene-background'))
        if (!context.valid()) return
        coreReady = true; tick()
      })
      const msgEl = byId('home-loading-message')
      loaderMsgTimer = setInterval(() => {
        msgIndex = (msgIndex + 1) % LOADER_MESSAGES.length
        if (msgEl) msgEl.textContent = LOADER_MESSAGES[msgIndex]
      }, 1500)
      function tick() {
        if (state.disposed || state.phase === 'ready') { clearLoaderTimers(); return }
        state.checkDeadline()
        if (state.phase === 'ready') { clearLoaderTimers(); return }
        const elapsed = Date.now() - state.startedAt
        if (Date.now() >= state.coreDeadline) coreReady = true
        updateLoadingProgressUI(finishing ? 100 : Math.min(97, elapsed / LOADER_MIN_MS * (coreReady ? 100 : 85)))
        if (coreReady && elapsed >= LOADER_MIN_MS && !finishing) {
          finishing = true; state.phase = 'core-ready'
          updateLoadingProgressUI(100)
          loaderDismissTimer = setTimeout(dismissHomeLoader, LOADER_HOLD_MS)
        }
      }
      loaderProgressTimer = setInterval(tick, 60)
      context.scope.listen(window, 'home-startup-change', () => { if (state.phase === 'ready') clearLoaderTimers() })
      tick()
    }

    async function initHomePage() {
      if (services.entry) {
        startHeroClock(); byId('main-content').classList.add('content-loaded');
        void loadPage().catch(() => {});
        if (services.entry.pending) {
          const images = [...root.querySelectorAll('.home-scene-core')];
          await Promise.all(images.map(waitCoreImage));
          if (!context.valid()) return;
          if (images.length && images.every(image => !image.naturalWidth)) HomeStartup.useLegacyScene();
        }
        HomeStartup.complete(false);
        return;
      }
      if (isReloadNavigation()) HomeStartup.storage('sessionStorage', 'removeItem', HOME_LOADER_KEY)
      startHeroClock()
      byId('main-content').classList.add('content-loaded')
      if (shouldSkipHomeLoader()) {
        hideHomeLoaderImmediately()
        await loadPage()
        return
      }
      runHomeLoader()
    }

    /** 取北京时间（TD-HOME-05） */
    function getBeijingDate() {
      return new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }))
    }

    function getBeijingPeriodLabel(hour) {
      if (hour < 5) return '深夜'
      if (hour < 8) return '清晨'
      if (hour < 12) return '上午'
      if (hour < 14) return '中午'
      if (hour < 18) return '下午'
      if (hour < 20) return '傍晚'
      return '晚上'
    }

    function shouldShowGoodNight(hour) {
      return hour >= 20 || hour < 5
    }

    function pad2(n) {
      return String(n).padStart(2, '0')
    }

    function updateHeroClock() {
      const now = getBeijingDate()
      const hour = now.getHours()
      const minute = now.getMinutes()
      const timeEl = byId('beijing-time')
      const periodEl = byId('beijing-period')
      const goodNightEl = byId('good-night')

      if (timeEl) {
        timeEl.innerHTML = pad2(hour) + '<span class="home-clock-colon">:</span>' + pad2(minute)
      }
      if (periodEl) {
        periodEl.textContent = getBeijingPeriodLabel(hour)
      }
      if (goodNightEl) {
        goodNightEl.classList.toggle('is-visible', shouldShowGoodNight(hour))
      }
    }

    function startHeroClock() {
      updateHeroClock()
      if (clockTimer) clearInterval(clockTimer)
      clockTimer = setInterval(updateHeroClock, 60000)
    }

    function renderKnownDays(milestones) {
      const el = byId('known-days')
      if (!el) return
      const days = milestones && milestones.known_days
      if (days == null || Number.isNaN(Number(days))) {
        el.textContent = '—'
        return
      }
      el.textContent = '陪伴你的第 ' + days + ' 天'
      el.classList.remove('is-hidden')
    }

    function hideKnownDays() {
      const el = byId('known-days')
      if (!el) return
      el.classList.add('is-hidden')
    }

    function renderVisitorKnownDays() {
      const el = byId('known-days')
      if (!el) return
      el.textContent = '故事从今天开始'
      el.classList.remove('is-hidden')
    }

    function renderTopBarIntimacy(d) {
      const growth = d.current_growth ?? d.growth_value ?? 0
      const progressInfo = byId('progress-info')
      const progressFill = byId('progress-fill')
      if (!progressInfo || !progressFill) return

      if (d.next_threshold == null) {
        progressInfo.textContent = growth + ' / 已满级'
        progressFill.style.width = '100%'
        return
      }

      progressInfo.textContent = growth + ' / ' + d.next_threshold
      const percent = d.progress_percent != null
        ? d.progress_percent
        : Math.min(100, Math.round(growth / d.next_threshold * 100))
      progressFill.style.width = percent + '%'
    }

    function renderDiaryPreview(items, level) {
      const previewEl = byId('diary-preview')
      const timeEl = byId('diary-time')
      const newEl = byId('diary-new')
      const lockEl = byId('diary-lock')
      if (!previewEl) return

      previewEl.textContent = DIARY_PLACEHOLDER

      if (lockEl) {
        lockEl.dataset.lockState = level == null ? 'unknown' : (level === 0 ? 'locked' : 'unlocked')
        lockEl.textContent = level == null ? '…' : '🔒'
        lockEl.setAttribute('aria-label', level == null ? '解锁状态待确认' : '尚未解锁')
        lockEl.style.display = level == null || level === 0 ? 'inline' : 'none'
      }

      if (!items || items.length === 0) {
        if (timeEl) timeEl.textContent = ''
        if (newEl) newEl.style.display = 'none'
        return
      }

      const item = items[0]
      if (timeEl) {
        const rel = formatTime(item.created_at)
        timeEl.textContent = rel ? '刚刚写下 · ' + rel : '—'
      }
      if (newEl) {
        newEl.style.display = item.is_read === false ? 'inline-block' : 'none'
      }
    }

    function renderRelationshipPreview(d) {
      const el = byId('relationship-level-name')
      if (!el || !d) return
      const level = d.level || 0
      el.textContent = d.level_name || LEVEL_NAMES[level] || LEVEL_NAMES[0]
    }

    function renderUnreadBadge(unreadRes) {
      if (unreadRes.code !== 0) return
      const count = unreadRes.data?.count || 0
      const badge = byId('unread-badge')
      if (!badge) return
      if (count > 0) {
        badge.textContent = formatBadgeCount(count)
        badge.style.display = 'block'
        badge.classList.add('unread-badge--active')
      } else {
        badge.style.display = 'none'
        badge.classList.remove('unread-badge--active')
      }
    }

    function hideUnreadBadge() {
      const badge = byId('unread-badge')
      if (!badge) return
      badge.textContent = '0'
      badge.style.display = 'none'
      badge.classList.remove('unread-badge--active')
    }

    function renderVisitorHome() {
      homeAuthMode = 'visitor'
      homeVisitorRendered = true
      HomeStartup.storage('localStorage', 'removeItem', 'relationship_level')
      const avatarAuth = HomeStartup.auth()
      updateHomeAvatar(null, () => { const current = HomeStartup.auth(); return context.valid() && current.authEpoch === avatarAuth.authEpoch && current.known === avatarAuth.known && current.token === avatarAuth.token })
      byId('status-text').textContent = DEFAULT_STATUS_TEXT
      renderRelationshipPreview({ level: 0, level_name: LEVEL_NAMES[0] })
      renderTopBarIntimacy({ current_growth: 0, next_threshold: 200, progress_percent: 0 })
      renderVisitorKnownDays()
      renderDiaryPreview([], 0)
      hideUnreadBadge()
      renderFeedReplyPill(0)
      renderFeedFooter(0)
      feedBadge = { unread: 0, hasNew: false, newCount: 0 }
      byId('main-content').classList.add('content-loaded')
    }

    function switchHomeToVisitor() {
      if (homeAuthMode === 'visitor' && homeVisitorRendered) return
      renderVisitorHome()
    }

    function openHomeLoginModal() {
      context.services.ui.openLogin()
    }

    async function refreshHomeAfterLogin() {
      if (!HomeStartup.auth().token) return
      homeAuthMode = 'authenticated'
      homeVisitorRendered = false
      await loadPage()
    }

    function goHomeRelationship() {
      if (homeAuthMode === 'visitor' || !HomeStartup.auth().token) {
        openHomeLoginModal()
        return
      }
      context.router.navigate('/pages/relationship.html')
    }

    function goHomeDiary() {
      if (homeAuthMode === 'visitor' || !HomeStartup.auth().token) {
        openHomeLoginModal()
        return
      }
      context.router.navigate('/pages/diary.html')
    }

    function handleHomeQuickAction(action) {
      if (homeAuthMode === 'visitor' || !HomeStartup.auth().token) {
        openHomeLoginModal()
        return
      }
      if (action === 'memory') {
        context.router.navigate('/pages/memory.html')
        return
      }
      if (action === 'voice') {
        window.VoiceEntry.begin()
        return
      }
      showToast('敬请期待')
    }

    /** 朋友圈更新时间：今天/昨天/更早（按北京墙钟字符串解析，避免浏览器时区偏移） */
    function formatFeedUpdateLabel(iso) {
      if (!iso) return ''
      const m = String(iso).match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
      if (!m) return ''
      const y = Number(m[1])
      const mo = Number(m[2])
      const day = Number(m[3])
      const hm = m[4] + ':' + m[5]
      const now = getBeijingDate()
      const sameYMD = (yy, mm, dd) =>
        now.getFullYear() === yy && (now.getMonth() + 1) === mm && now.getDate() === dd
      if (sameYMD(y, mo, day)) return '更新 · 今天 ' + hm
      const yest = new Date(now)
      yest.setDate(yest.getDate() - 1)
      if (
        yest.getFullYear() === y
        && (yest.getMonth() + 1) === mo
        && yest.getDate() === day
      ) {
        return '更新 · 昨天 ' + hm
      }
      return '更新 · ' + mo + '月' + day + '日 ' + hm
    }

    /** 从最近帖倒序抽出最多 2 张图 */
    function collectFeedThumbUrls(posts) {
      const urls = []
      if (!posts) return urls
      for (let i = 0; i < posts.length && urls.length < 2; i++) {
        const imgs = posts[i].image_urls || []
        for (let j = 0; j < imgs.length && urls.length < 2; j++) {
          if (imgs[j]) urls.push(imgs[j])
        }
      }
      return urls
    }

    function renderFeedPreview(posts) {
      const textEl = byId('feed-preview-text')
      const updatedEl = byId('feed-updated')
      const thumbsEl = byId('feed-thumbs')
      if (!textEl || !updatedEl || !thumbsEl) return

      if (!posts || posts.length === 0) {
        textEl.textContent = ''
        updatedEl.textContent = ''
        thumbsEl.innerHTML = ''
        return
      }

      const latest = posts[0]
      textEl.textContent = latest.content_text || ''
      updatedEl.textContent = formatFeedUpdateLabel(latest.scheduled_publish_time)

      const urls = collectFeedThumbUrls(posts)
      thumbsEl.innerHTML = ''
      urls.forEach((src) => {
        const img = document.createElement('img')
        img.src = src
        img.alt = ''
        img.loading = 'lazy'
        context.scope.listen(img, 'error', () => { img.style.display = 'none' })
        thumbsEl.appendChild(img)
      })
    }

    function renderFeedFooter(newPostCount) {
      const el = byId('feed-footer-text')
      if (!el) return
      const n = Number(newPostCount) || 0
      if (n > 0) {
        const shown = n > 99 ? '99+' : String(n)
        el.textContent = shown + ' 条新动态 · 快来看看她分享了什么吧'
      } else {
        el.textContent = '快来看看她分享了什么吧'
      }
    }

    function renderFeedReplyPill(unread) {
      const pill = byId('feed-reply-pill')
      if (!pill) return
      const n = Number(unread) || 0
      if (n > 0) {
        const shown = n > 99 ? '99+' : String(n)
        pill.textContent = 'NEW · ' + shown + '条新回复'
        pill.style.display = ''
      } else {
        pill.style.display = 'none'
      }
    }

    let homeDataController = null
    let homeRelationshipLevel = null
    let homeDiaryItems = null
    const homeModuleLabels = { relationship:'关系', days:'陪伴天数', diary:'日记', unread:'消息', feedList:'动态', feedBadge:'动态提醒' }
    const homeModuleTargets = { relationship:'.bar-right', days:'.home-top-meta', diary:'.home-diary-card .home-card-body', unread:'.home-chat-btn-wrap', feedList:'.home-feed-head-text', feedBadge:'.home-feed-footer' }
    function renderHomeModuleState(key, state) {
      let note = root.querySelector('[data-home-module="' + key + '"]')
      if (!note) {
        const target = root.querySelector(homeModuleTargets[key])
        if (!target) return
        note = document.createElement('span'); note.className = 'home-module-note'
        note.dataset.homeModule = key; note.setAttribute('aria-live','polite'); target.appendChild(note)
      }
      note.dataset.state = state.status; note.replaceChildren()
      if (state.status === 'pending' && !state.data) note.textContent = homeModuleLabels[key] + '加载中…'
      else if (state.status === 'unknown') note.textContent = '登录状态暂不可用'
      else if (state.status === 'error') {
        note.append(homeModuleLabels[key] + (state.data ? '更新失败 ' : '暂时未加载 '))
        const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = '重试'
        context.scope.listen(retry, 'click', event => { event.stopPropagation(); homeDataController.retry(key) })
        note.appendChild(retry)
      }
      note.hidden = !note.childNodes.length
    }
    function resetHomeData(auth) {
      homeRelationshipLevel = null; homeDiaryItems = null
      if (auth.known && !auth.token) { renderVisitorHome(); return }
      homeAuthMode = auth.token ? 'authenticated' : 'unknown'; homeVisitorRendered = false
      const avatarAuth = HomeStartup.auth()
      updateHomeAvatar(null, () => { const current = HomeStartup.auth(); return context.valid() && current.authEpoch === avatarAuth.authEpoch && current.known === avatarAuth.known && current.token === avatarAuth.token })
      byId('relationship-level-name').textContent = '—'
      byId('progress-info').textContent = '—'
      byId('progress-fill').style.width = '0%'
      byId('status-text').textContent = DEFAULT_STATUS_TEXT
      byId('known-days').textContent = '—'
      renderDiaryPreview([],null); hideUnreadBadge()
      renderFeedPreview([]); renderFeedReplyPill(0); renderFeedFooter(0)
      feedBadge = {unread:0,hasNew:false,newCount:0}
    }
    function renderHomeModule(key, data, isCurrent) {
      if (key === 'relationship') {
        homeRelationshipLevel = data.level ?? null
        updateHomeAvatar(data.ai_current_emotion,isCurrent)
        byId('status-text').textContent = resolveStatusText(data)
        renderTopBarIntimacy(data); renderRelationshipPreview(data)
        HomeStartup.storage('localStorage','setItem','relationship_level',homeRelationshipLevel)
        renderDiaryPreview(homeDiaryItems || [],homeRelationshipLevel)
      } else if (key === 'days') renderKnownDays(data.milestones)
      else if (key === 'diary') { homeDiaryItems = data.items || []; renderDiaryPreview(homeDiaryItems,homeRelationshipLevel) }
      else if (key === 'unread') renderUnreadBadge({code:0,data})
      else if (key === 'feedList') renderFeedPreview(data.posts || [])
      else if (key === 'feedBadge') {
        feedBadge = {unread:data.unread_reply_count || 0,hasNew:!!data.has_new,newCount:data.new_post_count || 0}
        renderFeedReplyPill(feedBadge.unread); renderFeedFooter(feedBadge.newCount)
      }
    }
    function getHomeDataController() {
      if (!homeDataController) homeDataController = HomeData.mount({auth:resetHomeData,state:renderHomeModuleState,success:renderHomeModule}, context)
      return homeDataController
    }
    async function loadPage() {
      await getHomeDataController().load()
      return {emotion:null}
    }
    async function loadFeedHomeCard() { await getHomeDataController().feed() }

    /** 点击朋友圈入口：有未读回复带 focus 定位，否则进列表顶部（PRD 5.6.3） */
    function goFeed() {
      const b = feedBadge || {}
      if (b.unread > 0) {
        context.router.navigate('/pages/feed.html?focus=unread_reply')
      } else {
        context.router.navigate('/pages/feed.html')
      }
    }


  context.cleanup(() => { clearLoaderTimers(); clearInterval(clockTimer); homeDataController?.destroy(); });
  const scene = HomeScene.mount(context); if (scene) context.cleanup(() => scene.destroy());
  const audioPage = services.audio.attachPage(context, 'home');
  const music = BgmHome.mount(audioPage); if (music) context.cleanup(() => music.destroy());
  VoiceEntry.mount(context);
  for (const id of ['linxiaomeng-avatar', 'loading-avatar']) {
    const image = byId(id); if (!image) continue;
    context.scope.listen(image, 'error', () => homeAvatarFallback(image));
    if (image.complete && !image.naturalWidth) homeAvatarFallback(image);
  }
  const activate = element => {
    const action = element.dataset.homeAction;
    if (action === 'relationship') goHomeRelationship();
    else if (action === 'diary') goHomeDiary();
    else if (action === 'feed') goFeed();
    else if (action.startsWith('quick-')) handleHomeQuickAction(action.slice(6));
    else context.router.navigate('/pages/' + action + '.html');
  };
  context.scope.listen(root, 'click', event => { const element = event.target.closest('[data-home-action]'); if (element && root.contains(element)) activate(element); });
  context.scope.listen(root, 'keydown', event => {
    const element = event.target.closest('[data-home-action]');
    if (element && element.tagName !== 'BUTTON' && ['Enter', ' '].includes(event.key)) { event.preventDefault(); activate(element); }
  });
  void initHomePage();
  consumeLoginModalSignal();
  return { unmount() {}, captureState: () => ({ loaderDone: HomeStartup.phase === 'ready', loaderStartedAt: HomeStartup.startedAt }), inspect: () => ({ scene: scene?.inspect(), data: homeDataController?.inspect() }) };
}

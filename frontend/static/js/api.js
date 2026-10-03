/* -*- coding: utf-8 -*- */
/* 林小梦 H5 公共工具函数 */

// 同域部署（Nginx）用空串；本地开发（不同端口）用 localhost:8000
const API_BASE = (typeof window !== 'undefined' && window.location.hostname === 'localhost' && !['80','443',''].includes(window.location.port))
  ? 'http://localhost:8000'
  : ''

const AVATAR_MAP = {
  'default': '/static/images/avatar/default.png',
  '平静':    '/static/images/avatar/emotion_calm.png',
  '开心':    '/static/images/avatar/emotion_happy.png',
  '好奇':    '/static/images/avatar/emotion_curious.png',
  '想念':    '/static/images/avatar/emotion_miss.png',
  '担心':    '/static/images/avatar/emotion_worry.png',
  '害羞':    '/static/images/avatar/emotion_shy.png',
  '困倦':    '/static/images/avatar/emotion_sleepy.png',
}

/** 情绪 → 状态语兜底映射（首页与设置页共用，清偿 TD-HOME-07） */
const EMOTION_STATUS_MAP = {
  '开心': '今天状态不错，继续陪伴你吧~',
  '平静': '今天也在呢，等你来聊天~',
  '好奇': '对新的一天充满好奇呢~',
  '想念': '有点想你了，来聊聊吧~',
  '担心': '一直在想着你，还好吗~',
  '害羞': '见到你有点开心又不好意思~',
  '困倦': '有点困啦，但还是想陪着你~',
}

/** 状态语最终兜底文案 */
const DEFAULT_STATUS_TEXT = '今天状态不错，继续陪伴你吧~'

/** 登录页与共享弹窗共用的输入规则。 */
const AUTH_FORM_RULES = Object.freeze({
  username: {
    pattern: /^[a-zA-Z0-9]{6,20}$/,
    msg: '账号需要6-20位字母或数字',
  },
  password: {
    pattern: /^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z0-9!@#$%^&*]{8,20}$/,
    msg: '密码需要8-20位，同时包含字母和数字',
  },
})

/** 调用点可显式选择的 401 行为；默认仍保留历史独立登录页跳转。 */
const AUTH_401_POLICIES = Object.freeze({
  LEGACY_LOGIN_PAGE: 'legacy-login-page',
  SILENT_VISITOR: 'silent-visitor',
  PROTECTED_HOME_MODAL: 'protected-home-modal',
  INTERACTIVE_MODAL: 'interactive-modal',
})

const AUTH_LOGIN_SIGNAL_KEY = 'lxm_open_login_once'

const authModalState = {
  onSuccess: null,
  submitting: false,
  callbackDelivered: false,
}

let protectedLoginRedirecting = false

/**
 * 解析关系状态语：status_text → 情绪映射 → 默认文案
 * @param {object|null|undefined} data 关系 status 接口 data
 * @returns {string}
 */
function resolveStatusText(data) {
  if (!data) return DEFAULT_STATUS_TEXT
  if (data.status_text) return data.status_text
  const emotion = data.ai_current_emotion
  if (emotion && EMOTION_STATUS_MAP[emotion]) {
    return EMOTION_STATUS_MAP[emotion]
  }
  return DEFAULT_STATUS_TEXT
}

/**
 * 统一请求函数
 * 自动携带 Token，并按调用点选择 401 策略；未迁移调用点仍跳独立登录页。
 */
// Home-only recovery; default storage behavior on other pages stays unchanged.
function readAuthToken() {
  if (typeof window !== 'undefined' && window.HomeStartup) return window.HomeStartup.auth().token
  return localStorage.getItem('token')
}
function authStorage(operation, key, value) {
  if (typeof window !== 'undefined' && window.HomeStartup) {
    return window.HomeStartup.storage('localStorage', operation, key, value).value
  }
  return localStorage[operation](key, value)
}

async function request(method, path, data, requestOptions = {}) {
  const token = readAuthToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = 'Bearer ' + token
  }

  const options = { method, headers }
  if (requestOptions.signal) options.signal = requestOptions.signal
  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(data)
  }

  try {
    assertRequestCurrent(requestOptions)
    const response = await fetch(API_BASE + path, options)
    assertRequestCurrent(requestOptions)

    if (response.status === 401) {
      await handleUnauthorized(requestOptions)
      return { code: 401, data: null, message: '登录已过期' }
    }

    const result = await response.json()
    assertRequestCurrent(requestOptions)
    return result
  } catch (err) {
    assertRequestCurrent(requestOptions)
    if (requestOptions.signal && err.name === 'AbortError') throw err
    console.error('请求失败:', method, path, err)
    return { code: -1, data: null, message: '网络连接失败，请检查网络后重试' }
  }
}

/** Optional callers own cancellation/stale-result handling; legacy results stay unchanged. */
function assertRequestCurrent(options) {
  let name = null
  if (options.signal?.aborted) name = 'AbortError'
  else if (typeof options.isCurrent === 'function') {
    try { if (!options.isCurrent()) name = 'StaleRequestError' }
    catch (_) { name = 'StaleRequestError' }
  }
  if (name) { const error = new Error('Request is no longer current'); error.name = name; throw error }
}

async function handleUnauthorized(requestOptions = {}) {
  const options = requestOptions || {}
  const policy = options.authPolicy || AUTH_401_POLICIES.LEGACY_LOGIN_PAGE
  clearToken()

  if (policy === AUTH_401_POLICIES.SILENT_VISITOR) {
    if (typeof options.onUnauthorized === 'function') {
      await options.onUnauthorized()
    }
    return
  }

  if (policy === AUTH_401_POLICIES.PROTECTED_HOME_MODAL) {
    if (typeof options.onUnauthorized === 'function') {
      await options.onUnauthorized()
    }
    redirectToHomeLogin()
    return
  }

  if (policy === AUTH_401_POLICIES.INTERACTIVE_MODAL) {
    if (typeof options.onUnauthorized === 'function') {
      await options.onUnauthorized()
    }
    openLoginModal({ onSuccess: options.onLoginSuccess })
    return
  }

  window.location.href = '/pages/login.html'
}

function saveToken(token) {
  if (typeof window !== 'undefined' && window.HomeStartup) window.HomeStartup.rememberAuth(token)
  authStorage('setItem', 'token', token)
  if (typeof window !== 'undefined' && window.HomeStartup) window.dispatchEvent(new Event('home-auth-change'))
}

function clearToken() {
  if (typeof window !== 'undefined' && window.HomeStartup) window.HomeStartup.rememberAuth(null)
  authStorage('removeItem', 'token')
  try {
    sessionStorage.removeItem('lxm_home_loader_done')
  } catch (e) {
    /* sessionStorage 不可用时忽略 */
  }
  if (typeof window !== 'undefined' && window.HomeStartup) window.dispatchEvent(new Event('home-auth-change'))
}

function checkLogin() {
  if (!readAuthToken()) {
    window.location.href = '/pages/login.html'
  }
}

/**
 * 主动交互登录门禁。返回 true 表示已有登录态，false 表示已触发登录处理。
 */
function requireLogin(options = {}) {
  if (readAuthToken()) return true
  const normalized = typeof options === 'function' ? { onSuccess: options } : options
  const policy = normalized.authPolicy || AUTH_401_POLICIES.INTERACTIVE_MODAL
  if (policy === AUTH_401_POLICIES.PROTECTED_HOME_MODAL) {
    redirectToHomeLogin()
  } else {
    openLoginModal({ onSuccess: normalized.onSuccess })
  }
  return false
}

/** 受保护页入口门禁：无 token 时立即写单次信号并替换到首页。 */
function requireProtectedPage() {
  if (readAuthToken()) return true
  redirectToHomeLogin()
  return false
}

/** 受保护页请求统一 401 策略；页面可在导航前停止自己的资源。 */
function protectedPageAuthOptions(onUnauthorized) {
  return {
    authPolicy: AUTH_401_POLICIES.PROTECTED_HOME_MODAL,
    onUnauthorized: onUnauthorized,
  }
}

/** 受保护页统一回首页，并写入仅消费一次的弹窗信号。 */
function redirectToHomeLogin() {
  if (protectedLoginRedirecting) return false
  protectedLoginRedirecting = true
  clearToken()
  try {
    sessionStorage.setItem(AUTH_LOGIN_SIGNAL_KEY, '1')
  } catch (e) {
    console.warn('无法写入登录弹窗信号:', e)
  }

  if (window.location.pathname === '/pages/index.html') {
    protectedLoginRedirecting = false
    consumeLoginModalSignal()
    return true
  }

  if (typeof window.location.replace === 'function') {
    window.location.replace('/pages/index.html')
  } else {
    window.location.href = '/pages/index.html'
  }
  return true
}

/** 首页读取受保护页留下的弹窗信号；先删除再打开，避免刷新/后退循环。 */
function consumeLoginModalSignal(options = {}) {
  let shouldOpen = false
  try {
    shouldOpen = sessionStorage.getItem(AUTH_LOGIN_SIGNAL_KEY) === '1'
    if (shouldOpen) sessionStorage.removeItem(AUTH_LOGIN_SIGNAL_KEY)
  } catch (e) {
    console.warn('无法读取登录弹窗信号:', e)
  }
  if (!shouldOpen) return false
  openLoginModal(options)
  return true
}

function authModalIcon(name) {
  if (name === 'user') {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"></circle><path d="M4.5 21c.4-4 3-6 7.5-6s7.1 2 7.5 6"></path></svg>'
  }
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"></rect><path d="M8 10V7a4 4 0 0 1 8 0v3"></path><circle cx="12" cy="15.5" r="1"></circle></svg>'
}

function authModalPasswordToggle(inputId) {
  return `
    <button class="auth-modal-password-toggle" type="button"
      data-auth-password-toggle="${inputId}" aria-label="显示密码" aria-pressed="false">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg>
    </button>`
}

function authModalField(id, label, type, placeholder, iconName) {
  return `
    <label class="auth-modal-field" for="${id}">
      <span class="auth-modal-label">${label}</span>
      <span class="auth-modal-control">
        <span class="auth-modal-field-icon">${authModalIcon(iconName)}</span>
        <input id="${id}" type="${type}" autocomplete="${type === 'password' ? 'current-password' : 'username'}"
          placeholder="${placeholder}" maxlength="20" aria-describedby="${id}-error">
        ${type === 'password' ? authModalPasswordToggle(id) : ''}
      </span>
      <span class="auth-modal-error" id="${id}-error" aria-live="polite"></span>
    </label>`
}

function ensureLoginModal() {
  if (typeof document === 'undefined') return null
  let overlay = document.getElementById('auth-login-modal')
  if (overlay) return overlay

  overlay = document.createElement('div')
  overlay.id = 'auth-login-modal'
  overlay.className = 'auth-modal-overlay'
  overlay.setAttribute('aria-hidden', 'true')
  overlay.innerHTML = `
    <section class="auth-modal-sheet" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <button class="auth-modal-close" type="button" aria-label="关闭登录弹窗">×</button>
      <div class="auth-modal-handle" aria-hidden="true"></div>
      <div class="auth-modal-identity" aria-hidden="true">
        <span class="auth-modal-spark auth-modal-spark-left">✦</span>
        <span class="auth-modal-avatar-wrap">
          <img class="auth-modal-avatar" src="${AVATAR_MAP.default}" alt="">
          <span class="auth-modal-heart">♥</span>
        </span>
        <span class="auth-modal-spark auth-modal-spark-right">✦</span>
      </div>
      <h2 class="auth-modal-title" id="auth-modal-title">登录后，她就能记住你了</h2>
      <p class="auth-modal-subtitle" id="auth-modal-subtitle">保存聊天、记忆和关系进度，下次回来还能继续陪伴。</p>

      <form class="auth-modal-panel is-active" data-auth-modal-panel="login" novalidate>
        ${authModalField('auth-modal-login-username', '账号', 'text', '请输入账号', 'user')}
        ${authModalField('auth-modal-login-password', '密码', 'password', '请输入密码', 'lock')}
        <label class="auth-modal-remember">
          <input type="checkbox" id="auth-modal-remember-me">
          <span>记住我</span>
        </label>
        <button class="auth-modal-submit" type="submit" data-auth-modal-submit="login" disabled>登录并继续</button>
        <button class="auth-modal-later" type="button">暂不登录，继续看看 <span aria-hidden="true">›</span></button>
        <div class="auth-modal-links">
          <button type="button" data-auth-modal-switch="register">注册账号</button>
          <span aria-hidden="true">|</span>
          <button type="button" data-auth-modal-switch="reset">找回密码</button>
        </div>
      </form>

      <form class="auth-modal-panel" data-auth-modal-panel="register" novalidate>
        ${authModalField('auth-modal-register-username', '账号', 'text', '6-20位字母数字', 'user')}
        ${authModalField('auth-modal-register-password', '密码', 'password', '8-20位，含字母和数字', 'lock')}
        ${authModalField('auth-modal-register-password2', '确认密码', 'password', '请再次输入密码', 'lock')}
        <button class="auth-modal-submit" type="submit" data-auth-modal-submit="register" disabled>注册并继续</button>
        <div class="auth-modal-links auth-modal-links-single">
          <button type="button" data-auth-modal-switch="login">返回登录</button>
        </div>
      </form>

      <form class="auth-modal-panel" data-auth-modal-panel="reset" novalidate>
        ${authModalField('auth-modal-reset-username', '账号', 'text', '请输入账号', 'user')}
        ${authModalField('auth-modal-reset-password', '新密码', 'password', '8-20位，含字母和数字', 'lock')}
        ${authModalField('auth-modal-reset-password2', '确认密码', 'password', '请再次输入密码', 'lock')}
        <button class="auth-modal-submit" type="submit" data-auth-modal-submit="reset" disabled>重置密码</button>
        <div class="auth-modal-links auth-modal-links-single">
          <button type="button" data-auth-modal-switch="login">返回登录</button>
        </div>
      </form>
    </section>`

  document.body.appendChild(overlay)

  overlay.querySelector('.auth-modal-close').addEventListener('click', closeLoginModal)
  overlay.querySelector('.auth-modal-later').addEventListener('click', closeLoginModal)
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeLoginModal()
  })
  overlay.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeLoginModal()
  })
  overlay.querySelectorAll('[data-auth-modal-switch]').forEach((button) => {
    button.addEventListener('click', () => switchAuthModalPanel(button.dataset.authModalSwitch))
  })
  overlay.querySelectorAll('[data-auth-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => toggleAuthModalPassword(button.dataset.authPasswordToggle, button))
  })
  overlay.querySelectorAll('input').forEach((input) => {
    input.addEventListener('input', () => {
      clearAuthModalError(input.id)
      updateAuthModalSubmitState(input.closest('[data-auth-modal-panel]').dataset.authModalPanel)
    })
  })
  overlay.querySelector('[data-auth-modal-panel="login"]').addEventListener('submit', submitAuthModalLogin)
  overlay.querySelector('[data-auth-modal-panel="register"]').addEventListener('submit', submitAuthModalRegister)
  overlay.querySelector('[data-auth-modal-panel="reset"]').addEventListener('submit', submitAuthModalReset)
  return overlay
}

function normalizeAuthModalOptions(options) {
  if (typeof options === 'function') return { onSuccess: options }
  return options || {}
}

function openLoginModal(options = {}) {
  const normalized = normalizeAuthModalOptions(options)
  const overlay = ensureLoginModal()
  if (!overlay) return false
  const wasOpen = overlay.classList.contains('is-open')
  if (!wasOpen) {
    authModalState.onSuccess = typeof normalized.onSuccess === 'function'
      ? normalized.onSuccess
      : null
    authModalState.callbackDelivered = false
  } else if (!authModalState.onSuccess && typeof normalized.onSuccess === 'function') {
    authModalState.onSuccess = normalized.onSuccess
  }

  switchAuthModalPanel(normalized.panel || 'login')
  overlay.classList.add('is-open')
  overlay.setAttribute('aria-hidden', 'false')
  document.body.classList.add('auth-modal-open')

  const remembered = authStorage('getItem', 'remember_username')
  if (remembered) {
    overlay.querySelector('#auth-modal-login-username').value = remembered
    overlay.querySelector('#auth-modal-remember-me').checked = true
    updateAuthModalSubmitState('login')
  }
  window.setTimeout(() => {
    const input = overlay.querySelector('[data-auth-modal-panel].is-active input')
    if (input) input.focus()
  }, 0)
  return true
}

function closeLoginModal(options = {}) {
  const overlay = typeof document === 'undefined'
    ? null
    : document.getElementById('auth-login-modal')
  if (overlay) {
    overlay.classList.remove('is-open')
    overlay.setAttribute('aria-hidden', 'true')
  }
  if (typeof document !== 'undefined') document.body.classList.remove('auth-modal-open')
  authModalState.submitting = false
  if (!options.preserveState) {
    authModalState.onSuccess = null
    authModalState.callbackDelivered = false
  }
}

function switchAuthModalPanel(name) {
  const overlay = ensureLoginModal()
  if (!overlay) return
  const copy = {
    login: ['登录后，她就能记住你了', '保存聊天、记忆和关系进度，下次回来还能继续陪伴。'],
    register: ['创建账号，继续陪伴', '注册后会直接登录，当前页面与进度都会保留。'],
    reset: ['重新找回这段陪伴', '设置新密码后返回登录，不改变现有找回密码流程。'],
  }
  const target = copy[name] ? name : 'login'
  overlay.querySelectorAll('[data-auth-modal-panel]').forEach((panel) => {
    panel.classList.toggle('is-active', panel.dataset.authModalPanel === target)
  })
  overlay.querySelector('#auth-modal-title').textContent = copy[target][0]
  overlay.querySelector('#auth-modal-subtitle').textContent = copy[target][1]
  clearAllAuthModalErrors()
  updateAuthModalSubmitState(target)
}

function toggleAuthModalPassword(inputId, button) {
  const input = document.getElementById(inputId)
  if (!input) return
  const shouldShow = input.type === 'password'
  input.type = shouldShow ? 'text' : 'password'
  button.setAttribute('aria-pressed', shouldShow ? 'true' : 'false')
  button.setAttribute('aria-label', shouldShow ? '隐藏密码' : '显示密码')
}

function clearAuthModalError(inputId) {
  const input = document.getElementById(inputId)
  const error = document.getElementById(inputId + '-error')
  if (input) input.closest('.auth-modal-control').classList.remove('is-error')
  if (error) error.textContent = ''
}

function clearAllAuthModalErrors() {
  const overlay = document.getElementById('auth-login-modal')
  if (!overlay) return
  overlay.querySelectorAll('.auth-modal-control').forEach((control) => control.classList.remove('is-error'))
  overlay.querySelectorAll('.auth-modal-error').forEach((error) => { error.textContent = '' })
}

function setAuthModalError(inputId, message) {
  const input = document.getElementById(inputId)
  const error = document.getElementById(inputId + '-error')
  if (input) input.closest('.auth-modal-control').classList.add('is-error')
  if (error) error.textContent = message
}

function authModalPanelValues(panel) {
  const prefix = 'auth-modal-' + panel + '-'
  return {
    username: document.getElementById(prefix + 'username').value.trim(),
    password: document.getElementById(prefix + 'password').value,
    password2: document.getElementById(prefix + 'password2')
      ? document.getElementById(prefix + 'password2').value
      : '',
  }
}

function isAuthModalPanelValid(panel) {
  const values = authModalPanelValues(panel)
  const baseValid = AUTH_FORM_RULES.username.pattern.test(values.username)
    && AUTH_FORM_RULES.password.pattern.test(values.password)
  return panel === 'login' ? baseValid : baseValid && values.password === values.password2
}

function updateAuthModalSubmitState(panel) {
  const overlay = document.getElementById('auth-login-modal')
  if (!overlay) return
  const button = overlay.querySelector(`[data-auth-modal-submit="${panel}"]`)
  if (button) button.disabled = authModalState.submitting || !isAuthModalPanelValid(panel)
}

function validateAuthModalPanel(panel) {
  clearAllAuthModalErrors()
  const values = authModalPanelValues(panel)
  const prefix = 'auth-modal-' + panel + '-'
  if (!AUTH_FORM_RULES.username.pattern.test(values.username)) {
    setAuthModalError(prefix + 'username', AUTH_FORM_RULES.username.msg)
    return false
  }
  if (!AUTH_FORM_RULES.password.pattern.test(values.password)) {
    setAuthModalError(prefix + 'password', AUTH_FORM_RULES.password.msg)
    return false
  }
  if (panel !== 'login' && values.password !== values.password2) {
    setAuthModalError(prefix + 'password2', '两次密码不一致')
    return false
  }
  return true
}

function setAuthModalSubmitting(panel, submitting) {
  authModalState.submitting = submitting
  const overlay = document.getElementById('auth-login-modal')
  if (!overlay) return
  const button = overlay.querySelector(`[data-auth-modal-submit="${panel}"]`)
  const labels = {
    login: ['登录中…', '登录并继续'],
    register: ['注册中…', '注册并继续'],
    reset: ['重置中…', '重置密码'],
  }
  if (button) {
    button.textContent = labels[panel][submitting ? 0 : 1]
    button.disabled = submitting || !isAuthModalPanelValid(panel)
  }
}

async function finishAuthModal(token, username) {
  if (!token || authModalState.callbackDelivered) return
  authModalState.callbackDelivered = true
  saveToken(token)
  const remember = document.getElementById('auth-modal-remember-me')
  if (remember && remember.checked && username) {
    authStorage('setItem', 'remember_username', username)
  } else if (remember) {
    authStorage('removeItem', 'remember_username')
  }
  const callback = authModalState.onSuccess
  authModalState.onSuccess = null
  closeLoginModal({ preserveState: true })
  try {
    if (typeof callback === 'function') await callback()
  } catch (error) {
    console.error('登录成功回调失败:', error)
  } finally {
    authModalState.callbackDelivered = false
  }
}

async function submitAuthModalLogin(event) {
  event.preventDefault()
  if (authModalState.submitting || !validateAuthModalPanel('login')) return
  const values = authModalPanelValues('login')
  setAuthModalSubmitting('login', true)
  const result = await request('POST', '/api/auth/login', {
    username: values.username,
    password: values.password,
  }, { authPolicy: AUTH_401_POLICIES.SILENT_VISITOR })
  if (result.code === 0 && result.data && result.data.token) {
    await finishAuthModal(result.data.token, values.username)
  } else {
    let message = result.message || '登录失败'
    if (result.data && result.data.remaining_seconds) {
      message = '密码错误次数过多，请' + Math.ceil(result.data.remaining_seconds / 60) + '分钟后重试'
    }
    showToast(message, 'error')
  }
  setAuthModalSubmitting('login', false)
}

async function submitAuthModalRegister(event) {
  event.preventDefault()
  if (authModalState.submitting || !validateAuthModalPanel('register')) return
  const values = authModalPanelValues('register')
  setAuthModalSubmitting('register', true)
  const result = await request('POST', '/api/auth/register', {
    username: values.username,
    password: values.password,
    confirm_password: values.password2,
  }, { authPolicy: AUTH_401_POLICIES.SILENT_VISITOR })
  if (result.code === 0 && result.data && result.data.token) {
    await finishAuthModal(result.data.token, values.username)
  } else {
    showToast(result.message || '注册失败', 'error')
  }
  setAuthModalSubmitting('register', false)
}

async function submitAuthModalReset(event) {
  event.preventDefault()
  if (authModalState.submitting || !validateAuthModalPanel('reset')) return
  const values = authModalPanelValues('reset')
  setAuthModalSubmitting('reset', true)
  const result = await request('POST', '/api/auth/reset-password', {
    username: values.username,
    new_password: values.password,
    confirm_password: values.password2,
  }, { authPolicy: AUTH_401_POLICIES.SILENT_VISITOR })
  if (result.code === 0) {
    showToast('密码重置成功，请登录', 'success')
    switchAuthModalPanel('login')
    document.getElementById('auth-modal-login-username').value = values.username
    updateAuthModalSubmitState('login')
  } else {
    showToast(result.message || '重置失败', 'error')
  }
  setAuthModalSubmitting('reset', false)
}

/**
 * 时间格式化：刚刚 / X分钟前 / X小时前 / 月-日
 */
function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  const diffHour = Math.floor(diffMs / 3600000)

  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return diffMin + '分钟前'
  if (diffHour < 24) return diffHour + '小时前'

  const month = date.getMonth() + 1
  const day = date.getDate()
  return month + '月' + day + '日'
}

/**
 * 头像情绪切换（所有页面通用）
 * 预加载图片避免闪烁
 */
function updateAvatarEmotion(emotionLabel, avatarOptions = {}) {
  const imgs = [
    document.getElementById('linxiaomeng-avatar'),
  ].filter(Boolean)
  if (!imgs.length) return

  const avatarMap = avatarOptions.avatarMap || AVATAR_MAP
  const src = avatarMap[emotionLabel] || avatarMap['default']
  const fallback = avatarMap['default']
  const preload = new Image()
  preload.onload = () => {
    if (avatarOptions.isCurrent && !avatarOptions.isCurrent()) return
    imgs.forEach((img) => { img.src = src })
  }
  preload.onerror = () => {
    if (avatarOptions.isCurrent && !avatarOptions.isCurrent()) return
    imgs.forEach((img) => {
      if (typeof avatarOptions.onError === 'function') avatarOptions.onError(img, src)
      else img.src = fallback
    })
  }
  preload.src = src
}

/**
 * 全局 Toast 提示
 * 从屏幕顶部滑入，自动消失
 * @param {string} message 提示文案
 * @param {'info'|'success'|'error'} type 类型
 * @param {number} duration 持续时间(ms)
 */
function showToast(message, type = 'info', duration = 2000) {
  let container = document.querySelector('.toast-container')
  if (!container) {
    container = document.createElement('div')
    container.className = 'toast-container'
    document.body.appendChild(container)
  }

  const toast = document.createElement('div')
  toast.className = 'toast-item toast-' + type
  toast.textContent = message
  container.appendChild(toast)

  setTimeout(() => {
    toast.classList.add('toast-out')
    toast.addEventListener('animationend', () => {
      toast.remove()
      if (container.children.length === 0) {
        container.remove()
      }
    })
  }, duration)
}

/**
 * 自定义确认弹窗（替代原生 confirm）
 * @returns {Promise<boolean>}
 */
function showConfirm(title, content, confirmText = '确认', isDanger = false) {
  return new Promise(resolve => {
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay'

    overlay.innerHTML = `
      <div class="modal-box">
        <div class="modal-title">${title}</div>
        <div class="modal-content">${content}</div>
        <div class="modal-actions">
          <button class="modal-cancel">取消</button>
          <button class="modal-confirm ${isDanger ? 'danger' : ''}">${confirmText}</button>
        </div>
      </div>
    `

    const close = (result) => {
      overlay.classList.add('fade-out')
      overlay.addEventListener('animationend', () => overlay.remove())
      resolve(result)
    }

    overlay.querySelector('.modal-cancel').onclick = () => close(false)
    overlay.querySelector('.modal-confirm').onclick = () => close(true)
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(false)
    })

    document.body.appendChild(overlay)
  })
}

/**
 * 格式化未读数显示（>99 显示 99+）
 */
function formatBadgeCount(count) {
  if (count <= 0) return ''
  return count > 99 ? '99+' : String(count)
}

/**
 * 跳转到关系状态页
 * @param {boolean} justLeveledUp 是否刚刚升级
 */
function goToRelationship(justLeveledUp) {
  if (!requireLogin()) return
  const url = justLeveledUp
    ? '/pages/relationship.html?just_leveled_up=true'
    : '/pages/relationship.html'
  window.location.href = url
}

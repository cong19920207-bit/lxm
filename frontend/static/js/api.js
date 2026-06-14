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
 * 自动携带 Token，401 自动跳登录页，统一错误处理
 */
async function request(method, path, data) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = 'Bearer ' + token
  }

  const options = { method, headers }
  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(data)
  }

  try {
    const response = await fetch(API_BASE + path, options)

    if (response.status === 401) {
      clearToken()
      window.location.href = '/pages/login.html'
      return { code: 401, data: null, message: '登录已过期' }
    }

    const result = await response.json()
    return result
  } catch (err) {
    console.error('请求失败:', method, path, err)
    return { code: -1, data: null, message: '网络连接失败，请检查网络后重试' }
  }
}

function saveToken(token) {
  localStorage.setItem('token', token)
}

function clearToken() {
  localStorage.removeItem('token')
  try {
    sessionStorage.removeItem('lxm_home_loader_done')
  } catch (e) {
    /* sessionStorage 不可用时忽略 */
  }
}

function checkLogin() {
  if (!localStorage.getItem('token')) {
    window.location.href = '/pages/login.html'
  }
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
function updateAvatarEmotion(emotionLabel) {
  const imgs = [
    document.getElementById('linxiaomeng-avatar'),
  ].filter(Boolean)
  if (!imgs.length) return

  const src = AVATAR_MAP[emotionLabel] || AVATAR_MAP['default']
  const fallback = AVATAR_MAP['default']
  const preload = new Image()
  preload.onload = () => {
    imgs.forEach((img) => { img.src = src })
  }
  preload.onerror = () => {
    imgs.forEach((img) => { img.src = fallback })
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
  const url = justLeveledUp
    ? '/pages/relationship.html?just_leveled_up=true'
    : '/pages/relationship.html'
  window.location.href = url
}

/* -*- coding: utf-8 -*- */
/**
 * 聊天居中时间戳工具（自然日、中英文、12/24 小时）
 * 仅用于 H5 chat.html；记忆页等继续使用 api.js 的 formatTime。
 */

/** 超过该间隔（或跨自然日）则插入居中时间戳 */
var CHAT_TIME_GAP_MS = 5 * 60 * 1000

var CHAT_TIME_STRINGS = {
  zh: {
    yesterday: '昨天',
    dayBeforeYesterday: '前天',
    weekdays: ['周日', '周一', '周二', '周三', '周四', '周五', '周六'],
  },
  en: {
    yesterday: 'Yesterday',
    dayBeforeYesterday: '2 days ago',
    weekdays: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  },
}

var chatTimeOptions = {
  locale: 'zh',
  hour12: false,
  weekStartsOn: 1,
}

/**
 * 读取当前聊天时间配置（副本，避免外部直接改引用）
 */
function getChatTimeOptions() {
  return {
    locale: chatTimeOptions.locale,
    hour12: chatTimeOptions.hour12,
    weekStartsOn: chatTimeOptions.weekStartsOn,
  }
}

/**
 * 更新聊天时间配置；未传字段保持原值
 * @param {{ locale?: string, hour12?: boolean, weekStartsOn?: 0|1 }} partial
 */
function setChatTimeOptions(partial) {
  if (!partial) return getChatTimeOptions()
  if (partial.locale === 'en' || partial.locale === 'zh') {
    chatTimeOptions.locale = partial.locale
  }
  if (typeof partial.hour12 === 'boolean') {
    chatTimeOptions.hour12 = partial.hour12
  }
  if (partial.weekStartsOn === 0 || partial.weekStartsOn === 1) {
    chatTimeOptions.weekStartsOn = partial.weekStartsOn
  }
  return getChatTimeOptions()
}

/** 本地自然日 0:00 时间戳 */
function startOfLocalDay(ts) {
  var d = new Date(ts)
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

/** 是否同一本地自然日 */
function isSameLocalDay(a, b) {
  return startOfLocalDay(a) === startOfLocalDay(b)
}

/**
 * laterTs 相对 earlierTs 相差的自然日数（非负，按本地日历）
 */
function diffLocalDays(laterTs, earlierTs) {
  var dayMs = 86400000
  return Math.round((startOfLocalDay(laterTs) - startOfLocalDay(earlierTs)) / dayMs)
}

/** 本地自然周起点（weekStartsOn：1=周一，0=周日） */
function startOfLocalWeek(ts) {
  var d = new Date(ts)
  var day = d.getDay()
  var offset
  if (chatTimeOptions.weekStartsOn === 1) {
    offset = day === 0 ? 6 : day - 1
  } else {
    offset = day
  }
  return startOfLocalDay(ts) - offset * 86400000
}

function isSameLocalWeek(a, b) {
  return startOfLocalWeek(a) === startOfLocalWeek(b)
}

/** 格式化为时:分（随 locale / hour12） */
function formatHourMinute(ts) {
  var loc = chatTimeOptions.locale === 'en' ? 'en-US' : 'zh-CN'
  return new Intl.DateTimeFormat(loc, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: chatTimeOptions.hour12,
  }).format(new Date(ts))
}

/**
 * 居中分组时间戳文案
 * 当天 → 14:30；昨天/前天/本周周几/更早 2026/5/23 14:30
 */
function formatChatTime(timestamp) {
  var ts = typeof timestamp === 'number' ? timestamp : new Date(timestamp).getTime()
  if (!Number.isFinite(ts)) return ''

  var now = Date.now()
  var hm = formatHourMinute(ts)
  var strings = CHAT_TIME_STRINGS[chatTimeOptions.locale] || CHAT_TIME_STRINGS.zh
  var days = diffLocalDays(now, ts)

  if (days === 0) return hm
  if (days === 1) return strings.yesterday + ' ' + hm
  if (days === 2) return strings.dayBeforeYesterday + ' ' + hm

  if (days > 2 && isSameLocalWeek(now, ts)) {
    var wd = strings.weekdays[new Date(ts).getDay()]
    return wd + ' ' + hm
  }

  var d = new Date(ts)
  return d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate() + ' ' + hm
}

/**
 * 是否在当前消息前插入居中时间戳
 * @param {number|string|Date} current
 * @param {number|string|Date|null|undefined} prev 上一条消息时间；无则必显
 */
function shouldShowTimeStamp(current, prev) {
  var cur = typeof current === 'number' ? current : new Date(current).getTime()
  if (!Number.isFinite(cur)) return false
  if (prev == null || prev === undefined) return true

  var prv = typeof prev === 'number' ? prev : new Date(prev).getTime()
  if (!Number.isFinite(prv)) return true
  if (!isSameLocalDay(cur, prv)) return true
  return cur - prv > CHAT_TIME_GAP_MS
}

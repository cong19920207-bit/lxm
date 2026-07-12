/* -*- coding: utf-8 -*- */
/**
 * 聊天居中时间戳工具（自然日、中英文、12/24 小时）
 * 仅用于 H5 chat.html；记忆页等继续使用 api.js 的 formatTime。
 * 展示与自然日一律按 Asia/Shanghai（北京时间），不依赖设备本地时区。
 */

/** 超过该间隔（或跨自然日）则插入居中时间戳 */
var CHAT_TIME_GAP_MS = 5 * 60 * 1000

var CHAT_TZ = 'Asia/Shanghai'

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

/**
 * 取某时刻在北京时区的年月日时分与星期
 * @returns {{ y: number, mo: number, d: number, h: number, mi: number, wd: number }}
 */
function getBeijingParts(ts) {
  var parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CHAT_TZ,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    weekday: 'short',
    hour12: false,
  }).formatToParts(new Date(ts))
  var map = {}
  for (var i = 0; i < parts.length; i++) {
    map[parts[i].type] = parts[i].value
  }
  var wdMap = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 }
  var h = Number(map.hour)
  // 部分环境 24:xx 表示午夜
  if (h === 24) h = 0
  return {
    y: Number(map.year),
    mo: Number(map.month),
    d: Number(map.day),
    h: h,
    mi: Number(map.minute),
    wd: wdMap[map.weekday] != null ? wdMap[map.weekday] : 0,
  }
}

/** 北京自然日序号（用于日差，非 Unix 日） */
function beijingDayIndex(ts) {
  var p = getBeijingParts(ts)
  return Math.floor(Date.UTC(p.y, p.mo - 1, p.d) / 86400000)
}

/** 是否同一北京自然日 */
function isSameBeijingDay(a, b) {
  return beijingDayIndex(a) === beijingDayIndex(b)
}

/**
 * laterTs 相对 earlierTs 相差的北京自然日数（非负）
 */
function diffBeijingDays(laterTs, earlierTs) {
  return beijingDayIndex(laterTs) - beijingDayIndex(earlierTs)
}

/** 北京自然周起点的 dayIndex（weekStartsOn：1=周一，0=周日） */
function beijingWeekStartIndex(ts) {
  var p = getBeijingParts(ts)
  var day = p.wd
  var offset
  if (chatTimeOptions.weekStartsOn === 1) {
    offset = day === 0 ? 6 : day - 1
  } else {
    offset = day
  }
  return beijingDayIndex(ts) - offset
}

function isSameBeijingWeek(a, b) {
  return beijingWeekStartIndex(a) === beijingWeekStartIndex(b)
}

/** 格式化为时:分（北京时间，随 locale / hour12） */
function formatHourMinute(ts) {
  var loc = chatTimeOptions.locale === 'en' ? 'en-US' : 'zh-CN'
  return new Intl.DateTimeFormat(loc, {
    timeZone: CHAT_TZ,
    hour: 'numeric',
    minute: '2-digit',
    hour12: chatTimeOptions.hour12,
  }).format(new Date(ts))
}

/**
 * 居中分组时间戳文案（北京时间）
 * 当天 → 14:30；昨天/前天/本周周几/更早 2026/5/23 14:30
 */
function formatChatTime(timestamp) {
  var ts = typeof timestamp === 'number' ? timestamp : new Date(timestamp).getTime()
  if (!Number.isFinite(ts)) return ''

  var now = Date.now()
  var hm = formatHourMinute(ts)
  var strings = CHAT_TIME_STRINGS[chatTimeOptions.locale] || CHAT_TIME_STRINGS.zh
  var days = diffBeijingDays(now, ts)

  if (days === 0) return hm
  if (days === 1) return strings.yesterday + ' ' + hm
  if (days === 2) return strings.dayBeforeYesterday + ' ' + hm

  if (days > 2 && isSameBeijingWeek(now, ts)) {
    var p = getBeijingParts(ts)
    var wd = strings.weekdays[p.wd]
    return wd + ' ' + hm
  }

  var d = getBeijingParts(ts)
  return d.y + '/' + d.mo + '/' + d.d + ' ' + hm
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
  if (!isSameBeijingDay(cur, prv)) return true
  return cur - prv > CHAT_TIME_GAP_MS
}

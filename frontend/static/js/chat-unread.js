/* One H5 inbox, with account-scoped receipts that survive navigation and offline reads. */
(function () {
  'use strict'
  const pendingPrefix = 'lxm.chat.read.pending:'
  const acknowledgement = 'lxm.chat.read.confirmed'
  const focusKey = 'lxm.chat.unread.focus'
  const pending = new Set()
  const sending = new Map()
  const replaying = new WeakMap()
  let firstUnread, navigationAnchor

  function currentUser() {
    try {
      const token = readAuthToken()
      if (window.ChatSubmissions) return ChatSubmissions.userFromToken(token || '')
      const claim = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).user_id
      return Number.isInteger(claim) && claim > 0 ? String(claim) : null
    } catch (_) { return null }
  }

  function validMessage(source, id) {
    return (source === 'agent' || source === 'assistant') && /^[1-9]\d*$/.test(String(id))
  }

  function pendingKey(user, source, id) {
    return pendingPrefix + user + ':' + source + ':' + id
  }

  async function boundedRequest(request, method, path, options) {
    // Receipts survive re-login for the same account, but an HTTP response belongs
    // to the credential that issued the request (including its 401 handling).
    const credential = readAuthToken()
    const isCurrent = () => readAuthToken() === credential && (!options.isCurrent || options.isCurrent())
    const controller = new AbortController()
    const abort = () => controller.abort()
    const parent = options.signal
    if (parent?.aborted) abort()
    else parent?.addEventListener('abort',abort,{once:true})
    const timer = setTimeout(abort,8000)
    try { return await request(method,path,null,{...options,signal:controller.signal,isCurrent}) }
    catch (error) {
      if (controller.signal.aborted && !parent?.aborted) return {code:-1,data:null}
      throw error
    }
    finally { clearTimeout(timer); parent?.removeEventListener('abort',abort) }
  }

  function sendReceipt(request, user, source, id, options) {
    const key = pendingKey(user, source, id)
    if (sending.has(key)) return sending.get(key)
    const current = () => currentUser() === user && (!options.isCurrent || options.isCurrent())
    const job = (async () => {
      if (!current() || !navigator.onLine) return
      const result = await boundedRequest(request,'POST','/api/chat/messages/' + source + '/' + id + '/read',
        { authPolicy: 'silent-visitor', ...options, isCurrent: current })
      if (!current() || (result?.code !== 0 && result?.code !== 10111)) return
      pending.delete(key)
      try { localStorage.removeItem(key) } catch (_) {}
      const detail = {user, source, id: String(id)}
      try { localStorage.setItem(acknowledgement, JSON.stringify(detail)) } catch (_) {}
      window.dispatchEvent(new CustomEvent(acknowledgement, {detail}))
    })().finally(() => sending.delete(key))
    sending.set(key, job)
    return job
  }

  function markMessageRead(request, source, id, options = {}) {
    const user = currentUser()
    if (!user || !validMessage(source, id)) return Promise.resolve()
    const key = pendingKey(user, source, id)
    pending.add(key)
    try { localStorage.setItem(key, '1') } catch (_) {}
    return sendReceipt(request, user, source, id, options)
  }

  function replayPending(request,user,options) {
    if (!user || !navigator.onLine) return
    const running = replaying.get(request)
    if (running?.user === user) {
      // An online/foreground wake can arrive before a lost response settles.
      // Keep the newest route options and make one more pass over remaining IDs.
      running.nextOptions = options
      return
    }
    const prefix = pendingPrefix + user + ':'
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith(prefix)) pending.add(key)
      }
    } catch (_) {}
    const keys = [...pending].filter(key => key.startsWith(prefix))
    if (!keys.length) return
    const replay = {user, nextOptions:null}
    replaying.set(request,replay)
    // A home badge fetch has its own short-lived batch. Receipts belong to the account
    // and the active route and get an independent deadline.
    const {routeCurrent, routeEpoch, onUnauthorized} = options
    const current = () => currentUser() === user && navigator.onLine && (!routeCurrent || routeCurrent())
    let index = 0
    const worker = async () => {
      while (index < keys.length && current()) {
        const key = keys[index++]
        const [source,id] = key.slice(prefix.length).split(':')
        if (!validMessage(source,id)) continue
        // A previous route may still own the first attempt at this receipt.
        if (sending.has(key)) await sending.get(key).catch(() => {})
        if (current() && pending.has(key)) await sendReceipt(request,user,source,id,{
          ...(routeCurrent ? {routeCurrent,routeEpoch} : {}), isCurrent:current, onUnauthorized
        }).catch(() => {})
      }
    }
    void Promise.all(Array.from({length:Math.min(4,keys.length)},worker)).finally(() => {
      if (replaying.get(request) !== replay) return
      replaying.delete(request)
      if (replay.nextOptions && currentUser() === user) replayPending(request,user,replay.nextOptions)
    })
  }

  async function getUnreadCount(request, options = {}) {
    const user = currentUser()
    replayPending(request,user,options)
    const current = () => currentUser() === user && (!options.isCurrent || options.isCurrent())
    const result = await boundedRequest(request,'GET','/api/chat/unread',{...options,isCurrent:current})
    if (current() && result?.code === 0) {
      const first = result.data?.first_unread
      firstUnread = user && first && validMessage(first.source,first.id)
        ? {user, source:first.source, id:first.id, sort_seq:first.sort_seq} : null
    }
    return result
  }

  // Carry the badge's anchor across this navigation, including standalone HTML.
  // The chat verifies it against the newly loaded timeline before using it.
  function chatURL(hasBadge) {
    navigationAnchor = hasBadge && firstUnread?.user === currentUser() ? firstUnread : null
    try {
      if (navigationAnchor) sessionStorage.setItem(focusKey,JSON.stringify(navigationAnchor))
      else sessionStorage.removeItem(focusKey)
    } catch (_) {}
    return hasBadge ? '/pages/chat.html?focus=unread' : '/pages/chat.html'
  }

  function takeFocusAnchor(user) {
    let anchor = navigationAnchor
    navigationAnchor = null
    try {
      const stored = sessionStorage.getItem(focusKey)
      sessionStorage.removeItem(focusKey)
      if (!anchor && stored) anchor = JSON.parse(stored)
    } catch (_) {}
    return anchor && anchor.user === user && validMessage(anchor.source,anchor.id) &&
      /^[1-9]\d*$/.test(anchor.sort_seq) ? anchor : null
  }

  function getMessageStatus(request, messages, options) {
    const params = new URLSearchParams()
    for (const {messageSource,messageId} of messages) params.append(messageSource+'_id',messageId)
    return boundedRequest(request,'GET','/api/chat/unread/status?'+params,options)
  }

  // Each mounted surface owns its timer and listeners. Initial fetch belongs to page initialization.
  function watch(refresh, onRead) {
    let timer, running = false, again = false, disposed = false
    let needsFreshSnapshot = false, wasHidden = document.hidden
    const active = () => !disposed && !document.hidden && navigator.onLine
    function schedule(delay) {
      clearTimeout(timer)
      if (active()) timer = setTimeout(tick, delay)
    }
    async function tick() {
      if (!active()) return
      if (running) { again = true; return }
      running = true
      const refreshAfterPending = needsFreshSnapshot
      needsFreshSnapshot = false
      try { await refresh(refreshAfterPending) } catch (error) {
        if (!['AbortError','StaleRequestError'].includes(error.name)) console.warn('聊天未读同步失败', error.name)
      } finally {
        running = false
        schedule(again ? 0 : 30000)
        again = false
      }
    }
    const wake = () => { if (running) again = true; else schedule(0) }
    const refreshAfterChange = () => { needsFreshSnapshot = true; wake() }
    const onVisible = () => {
      if (wasHidden && !document.hidden) refreshAfterChange()
      else wake()
      wasHidden = document.hidden
    }
    const onShow = event => { if (event.persisted) refreshAfterChange() }
    function received(detail) {
      if (!detail || detail.user !== currentUser() || !validMessage(detail.source, detail.id)) return
      pending.delete(pendingKey(detail.user, detail.source, detail.id))
      onRead?.(detail)
      refreshAfterChange()
    }
    const local = event => received(event.detail)
    const storage = event => {
      if (event.key !== acknowledgement || !event.newValue) return
      try { received(JSON.parse(event.newValue)) } catch (_) {}
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('online', refreshAfterChange)
    window.addEventListener('offline', wake)
    window.addEventListener('pageshow', onShow)
    window.addEventListener('storage', storage)
    window.addEventListener(acknowledgement, local)
    schedule(30000)
    return () => {
      disposed = true
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('online', refreshAfterChange)
      window.removeEventListener('offline', wake)
      window.removeEventListener('pageshow', onShow)
      window.removeEventListener('storage', storage)
      window.removeEventListener(acknowledgement, local)
    }
  }

  function getTimelinePage(request, url, options) {
    return boundedRequest(request, 'GET', url, options)
  }

  window.ChatUnread = {getUnreadCount, getMessageStatus, getTimelinePage, markMessageRead, watch, chatURL, takeFocusAnchor}
})()

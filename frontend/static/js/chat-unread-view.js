/* Mounted by both H5 chat entries. A receipt belongs to a bubble, never to a scroll cursor. */
(function () {
  'use strict'

  const dismissedByUser = new Map()

  function historyCursor(container) {
    const rows = [...container.querySelectorAll('.msg-row[data-sort-seq]')]
    const top = container.getBoundingClientRect().top
    const index = rows.findIndex(row => row.getBoundingClientRect().bottom >= top)
    if (index < 0) return null
    // Resume one page containing the visible anchor even if newer arrivals displaced it.
    const last = rows[Math.min(index + 19, rows.length - 1)].dataset.sortSeq
    return /^[1-9]\d*$/.test(last) ? String(BigInt(last) + 1n) : null
  }

  function mount({root, user, request, active, options, findRow, older, insertItems, observePage, streaming}) {
    const container = root.querySelector('#chat-messages')
    const tip = root.querySelector('#agent-tip')
    const label = root.querySelector('#tip-content')
    const close = root.querySelector('#tip-close')
    const acknowledged = new Set(), attempted = new Set(), dwell = new Map()
    const listeners = []
    const controller = new AbortController()
    const readOptions = () => ({...options(), signal:controller.signal})
    const entryAnchor = ChatUnread.takeFocusAnchor(user)
    const dismissKey = 'lxm.chat.tip.dismissed:' + user
    let dismissedThrough = dismissedByUser.get(user) || 0n
    try {
      const saved = sessionStorage.getItem(dismissKey)
      if (/^[0-9]+$/.test(saved)) dismissedThrough = BigInt(saved)
    } catch (_) {}
    let summary, ready = false, jumping = false, disposed = false
    let pendingFocus, forwardRequest, statusRequest
    let syncing, again = false, frame
    let head = 0n
    const key = (source,id) => source + ':' + id
    const valid = () => !disposed && active()
    const listen = (target,type,fn,opts) => {
      if (!target) return
      target.addEventListener(type,fn,opts)
      listeners.push(() => target.removeEventListener(type,fn,opts))
    }

    function flag(row, unread) {
      if (!row) return
      const k = key(row.dataset.messageSource,row.dataset.messageId)
      const bubble = row.querySelector('.msg-bubble')
      if (!bubble) return
      if (unread === false) acknowledged.add(k)
      const show = unread === true && !acknowledged.has(k)
      row.dataset.chatUnread = show ? '1' : '0'
      let tag = bubble.querySelector('.msg-unread-tag')
      if (show && !tag) {
        tag = document.createElement('span')
        tag.className = 'msg-unread-tag'
        tag.textContent = '未读'
        bubble.prepend(tag)
      } else if (!show) tag?.remove()
    }

    function drawTip() {
      const latest = summary?.latest_unread
      const show = Boolean(summary?.count && latest && BigInt(latest.sort_seq) > dismissedThrough)
      if (show) label.textContent = '有 ' + summary.count + ' 条新消息'
      tip.classList.toggle('hidden',!show)
      tip.setAttribute('aria-hidden',String(!show))
      label.tabIndex = close.tabIndex = show ? 0 : -1
      container.classList.toggle('has-tip',show)
    }

    // Give the printed text its own hit target. A pseudo-element on .msg-content
    // hits its host, while the uncovered letters hit this inline span.
    function messageText(row) {
      const content = row.querySelector('.msg-content')
      if (!content) return null
      let text = content.querySelector(':scope > .chat-readable-text')
      if (!text) {
        const nodes = [...content.childNodes].filter(node => node.nodeType === Node.TEXT_NODE)
        if (!nodes.length) return null
        text = document.createElement('span')
        text.className = 'chat-readable-text'
        content.insertBefore(text,nodes[0])
        text.append(...nodes)
      }
      return text
    }

    function hasColor(color) {
      return color && color !== 'transparent' && !/^rgba\(.*,\s*0\)$|\/\s*0%?\)$/.test(color)
    }

    function painted(style, hasText, replaced = false) {
      return style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) > 0 &&
        (replaced || hasColor(style.backgroundColor) || style.backgroundImage !== 'none' ||
        (style.backdropFilter && style.backdropFilter !== 'none') || (hasText && hasColor(style.color)))
    }

    function transparentParts(el) {
      const host = getComputedStyle(el)
      if (host.display !== 'contents' && el.checkVisibility?.({checkOpacity:true}) === false) return 'self before after'
      const text = [...el.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
      const parts = painted(host,text,el.matches('img,svg,svg *,canvas,video')) ? [] : ['self']
      for (const part of ['before','after']) {
        const style = getComputedStyle(el,'::'+part)
        if (style.content === 'none' || style.content === 'normal' || !painted(style,style.content !== '""')) parts.push(part)
      }
      return parts.join(' ')
    }

    function textIsExposed(content, bounds, checkedLayers) {
      const box = content.getBoundingClientRect()
      if (box.bottom <= bounds.top || box.top >= bounds.bottom || !box.height ||
          content.checkVisibility?.({checkOpacity:true,checkVisibilityCSS:true}) === false) return false
      const range = document.createRange()
      range.selectNodeContents(content)
      // Streaming can split a single printed line across multiple text nodes.
      const lines = []
      for (const rect of range.getClientRects()) {
        if (!rect.width || !rect.height) continue
        const last = lines[lines.length-1]
        if (last && Math.abs(last.top-rect.top) < 0.5) {
          last.left = Math.min(last.left,rect.left)
          last.right = Math.max(last.right,rect.right)
          last.bottom = Math.max(last.bottom,rect.bottom)
        } else lines.push({left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom})
      }
      const required = Math.min(2,lines.length)
      let consecutive = 0
      for (const line of lines) {
        const inside = line.left >= bounds.left-0.5 && line.right <= bounds.right+0.5 &&
          line.top >= bounds.top-0.5 && line.bottom <= bounds.bottom+0.5
        if (!inside) { consecutive = 0; continue }
        // Hit-test the printed width, including both ends of the line.
        const steps = Math.max(1,Math.ceil((line.right-line.left)/8))
        const clearAt = x => [line.top+1,(line.top+line.bottom)/2,line.bottom-1].every(y => {
          let hit = document.elementFromPoint(x,y)
          while (hit && hit !== content && hit !== document.documentElement && !checkedLayers.has(hit)) {
            const parts = transparentParts(hit)
            checkedLayers.add(hit)
            if (!parts) break
            hit.setAttribute('data-chat-transparent',parts)
            hit = document.elementFromPoint(x,y)
          }
          return hit === content
        })
        let clear = true
        const inset = Math.min(0.5,(line.right-line.left)/2)
        for (let i = 0; i <= steps && clear; i++) {
          clear = clearAt(line.left+inset+(line.right-line.left-2*inset)*i/steps)
        }
        consecutive = clear ? consecutive+1 : 0
        if (consecutive === required) return true
      }
      return false
    }

    function visibleRows() {
      const result = new Map()
      if (!ready || pendingFocus || jumping || !valid() || document.hidden || !document.hasFocus() ||
          container.closest('[inert]') || document.querySelector('#app-entry, #auth-login-modal.is-open')) return result
      const viewport = window.visualViewport
      const box = container.getBoundingClientRect()
      const top = Math.max(box.top,viewport?.offsetTop || 0,
        root.querySelector('.chat-top-bar').getBoundingClientRect().bottom,
        tip.classList.contains('hidden') ? 0 : tip.getBoundingClientRect().bottom)
      const bottom = Math.min(box.bottom,
        root.querySelector('.input-area').getBoundingClientRect().top,
        (viewport?.offsetTop || 0) + (viewport?.height || innerHeight))
      const left = Math.max(box.left,viewport?.offsetLeft || 0)
      const right = Math.min(box.right,(viewport?.offsetLeft || 0)+(viewport?.width || innerWidth))
      const rows = container.querySelectorAll('[data-chat-unread="1"]')
      if (!rows.length) return result
      // Probe only the layers above sampled text, using their paint at this frame.
      // Normal touch handling is restored synchronously before the browser can dispatch input.
      const checkedLayers = new Set()
      document.documentElement.setAttribute('data-chat-read-probe','')
      try {
        for (const row of rows) {
          const k = key(row.dataset.messageSource,row.dataset.messageId)
          if (attempted.has(k) || acknowledged.has(k)) continue
          const content = messageText(row)
          if (content && textIsExposed(content,{top,bottom,left,right},checkedLayers)) result.set(k,row)
        }
      } finally {
        document.documentElement.removeAttribute('data-chat-read-probe')
        for (const el of checkedLayers) el.removeAttribute('data-chat-transparent')
      }
      // A running mask can uncover the text well before its animation ends.
      if (checkedLayers.size && document.getAnimations?.().some(animation => {
        const target = animation.effect?.target
        const host = target?.element || target
        return animation.playState === 'running' && [...checkedLayers].some(el => host?.contains?.(el))
      })) schedule()
      return result
    }

    function measure() {
      const now = performance.now()
      const visible = visibleRows()
      for (const k of dwell.keys()) if (!visible.has(k)) dwell.delete(k)
      for (const [k,row] of visible) {
        if (!dwell.has(k)) dwell.set(k,now)
        if (now-dwell.get(k) < 650) continue
        dwell.delete(k)
        attempted.add(k)
        ChatUnread.markMessageRead(request,row.dataset.messageSource,row.dataset.messageId,options()).catch(() => {})
      }
      if (dwell.size) schedule()
    }
    function schedule() {
      if (disposed || frame != null) return
      frame = requestAnimationFrame(() => { frame = null; measure() })
    }

    function notePage(items) {
      for (const item of items) {
        const seq = BigInt(item.sort_seq_text || item.sort_seq || 0)
        if (seq > head) head = seq
      }
    }

    function insertItem(item) {
      const id = item.source === 'call' ? item.call_id : item.id
      const present = findRow(item.source,id)
      if (present) return present
      const sequence = BigInt(item.sort_seq_text || item.sort_seq)
      const next = [...container.querySelectorAll('.msg-row[data-sort-seq]')].find(row =>
        row.dataset.sortSeq && BigInt(row.dataset.sortSeq) > sequence)
      const divider = next?.previousElementSibling
      insertItems([item],divider?.classList.contains('msg-time-divider') ? divider : next || null)
      return findRow(item.source,id)
    }

    function fetchNewer(allowFollow = true) {
      if (forwardRequest) return forwardRequest
      forwardRequest = appendNewer(allowFollow).finally(() => { forwardRequest = null })
      return forwardRequest
    }

    async function appendNewer(allowFollow) {
      let cursor = head
      while (valid() && !document.hidden && navigator.onLine) {
        const url = '/api/chat/timeline?limit=50&after='+cursor
        const reply = await ChatUnread.getTimelinePage(request,url,readOptions())
        if (!valid() || reply?.code !== 0 || !Array.isArray(reply.data?.items)) return
        const items = reply.data.items
        const follow = allowFollow && !jumping && !pendingFocus &&
          container.scrollHeight-container.scrollTop-container.clientHeight < 48
        const hasStream = streaming()
        for (const item of items) {
          // The local stream owns unfinished reply bubbles. A later poll catches skipped rows.
          if (!hasStream || item.source === 'agent' || item.source === 'call') insertItem(item)
        }
        if (items.length) observePage(items,url)
        if (!hasStream) notePage(items)
        if (follow && items.length) container.scrollTop = container.scrollHeight
        if (!reply.data.has_more || !items.length || !(follow || hasStream)) return
        const last = items[items.length-1]
        const next = BigInt(last.sort_seq_text || last.sort_seq)
        if (next <= cursor) return
        cursor = next
      }
    }

    async function reconcileRows(rows, snapshot) {
      const middle = []
      for (const row of rows) {
        const seq = BigInt(row.dataset.sortSeq)
        if (!snapshot.count || seq < BigInt(snapshot.first_unread.sort_seq) || seq > BigInt(snapshot.latest_unread.sort_seq))
          flag(row,false)
        else if (seq > BigInt(snapshot.first_unread.sort_seq) && seq < BigInt(snapshot.latest_unread.sort_seq))
          middle.push(row)
      }
      // First and last alone cannot identify a read in the middle on another device.
      for (let i = 0; valid() && i < middle.length; i += 100) {
        const batch = middle.slice(i,i+100)
        const res = await ChatUnread.getMessageStatus(request,batch.map(row=>row.dataset),readOptions())
        if (!valid() || res?.code !== 0 || !Array.isArray(res.data?.unread)) return
        const unread = new Set(res.data.unread.map(m=>key(m.source,m.id)))
        for (const row of batch) {
          const {messageSource,messageId} = row.dataset
          if (!unread.has(key(messageSource,messageId))) flag(row.isConnected ? row : findRow(messageSource,messageId),false)
        }
      }
    }

    async function refresh() {
      if (!valid() || document.hidden || !navigator.onLine) return
      // Neither the summary nor the forward timeline waits on the other request.
      if (ready) void fetchNewer().catch(() => {})
      if (syncing) { again = true; return syncing }
      syncing = (async () => {
        do {
          again = false
          const previouslyUnread = [...container.querySelectorAll('[data-chat-unread="1"]')]
          const res = await ChatUnread.getUnreadCount(request,readOptions())
          if (!valid() || res?.code !== 0 || !Number.isInteger(res.data?.count)) return
          summary = res.data
          drawTip()
          if (!statusRequest) {
            statusRequest = reconcileRows(previouslyUnread,summary).catch(() => {}).finally(() => { statusRequest = null })
          }
          if (ready && pendingFocus) void applyPendingFocus().catch(() => {})
          schedule()
        } while (again && valid())
      })()
      try { await syncing } finally { syncing = null }
    }

    function alignToUnread(row) {
      const header = tip.classList.contains('hidden') ? root.querySelector('.chat-top-bar') : tip
      container.scrollTop += row.getBoundingClientRect().top-header.getBoundingClientRect().bottom-8
    }

    async function jump() {
      const first = summary?.first_unread
      if (!valid() || !first || jumping) return false
      jumping = true
      measure()
      try {
        let row = findRow(first.source,first.id)
        while (!row && valid() && head < BigInt(first.sort_seq)) {
          const previous = head
          await fetchNewer(false)
          row = findRow(first.source,first.id)
          if (!row && head === previous) return false
        }
        while (valid() && !(row=findRow(first.source,first.id)) && await older()) { /* Need an earlier page. */ }
        if (valid() && row) {
          alignToUnread(row)
          return true
        }
        return false
      } finally { jumping = false; schedule() }
    }

    async function applyPendingFocus({renderedOnly = false} = {}) {
      if (!pendingFocus || jumping || !valid()) return
      if (renderedOnly || !summary) {
        const anchor = summary ? summary.first_unread : entryAnchor
        const row = anchor && findRow(anchor.source,anchor.id)
        if (row?.dataset.chatUnread !== '1' || row.dataset.sortSeq !== anchor.sort_seq) return
        alignToUnread(row)
      } else if (summary.count > 0 && !await jump()) return
      if (!valid() || !pendingFocus) return
      pendingFocus()
      pendingFocus = null
      schedule()
    }

    const onClick = event => {
      if (event.target.closest('#tip-close')) {
        const latest = summary?.latest_unread
        if (latest) {
          dismissedThrough = BigInt(latest.sort_seq)
          dismissedByUser.set(user,dismissedThrough)
          try { sessionStorage.setItem(dismissKey,String(dismissedThrough)) } catch (_) {}
        }
        drawTip();schedule()
      } else void (pendingFocus ? applyPendingFocus() : jump()).catch(() => {})
    }
    listen(tip,'click',onClick)
    listen(tip,'keydown',event=>{
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.target.click() }
    })
    listen(container,'scroll',measure,{passive:true})
    const interruptDwell = () => { dwell.clear(); schedule() }
    listen(document,'visibilitychange',interruptDwell)
    listen(window,'blur',interruptDwell)
    listen(window,'pagehide',interruptDwell)
    listen(window,'focus',schedule)
    listen(window,'resize',schedule)
    listen(window.visualViewport,'scroll',measure)
    listen(window.visualViewport,'resize',measure)
    for (const event of ['transitionstart','transitionend','transitioncancel','animationstart','animationend','animationcancel']) {
      listen(document,event,schedule,true)
    }
    const changes = new MutationObserver(records => {
      // A later timeline response can render the badge target after the initial page failed.
      if (pendingFocus && records.some(record => container.contains(record.target))) {
        void applyPendingFocus({renderedOnly:true}).catch(() => {})
      }
      schedule()
    })
    changes.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style','inert','hidden','data-chat-unread']})
    const stop = ChatUnread.watch(refresh, ({source,id}) => {
      acknowledged.add(key(source,id))
      flag(findRow(source,id),false)
    })
    drawTip()
    return {
      flag, refresh, jump, notePage, insertItem,
      async start({onFocus, restoring = false} = {}) {
        pendingFocus = onFocus
        ready = true
        if (pendingFocus) await applyPendingFocus()
        if (valid()) void fetchNewer(!restoring).catch(() => {})
        schedule()
      },
      dispose() {
        disposed = true; ready = false; controller.abort(); changes.disconnect();stop()
        if (frame != null) cancelAnimationFrame(frame)
        dwell.clear();listeners.forEach(remove=>remove())
      }
    }
  }

  window.ChatUnreadView = {mount, historyCursor}
})()

import { createPageTimers } from '../app/page-timers.js';

export async function mount(pageContext) {
  const { root, services } = pageContext, byId=id=>root.querySelector('#'+id);
  const listen=(target,type,callback,options)=>pageContext.scope.listen(target,type,(...args)=>{
    const result=callback(...args);if(result?.then)run(result);
  },options);
  const {setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame}=createPageTimers(pageContext);
  await Promise.all(['css/voice-call-cards.css','css/bgm.css'].map(key=>pageContext.scope.adopt(services.resources.style(key),release=>release())));
  for(const name of ['chat-time','voice-call-cards','chat-submissions','bgm-page','bgm-record','bgm-bubble']){
    await services.shared.script('js/'+name+'.js');if(!pageContext.valid())return{unmount(){}};
  }
  const routeCurrent=()=>pageContext.router.current?.context.routeEpoch===pageContext.routeEpoch;
  const request=(method,path,data,options={})=>services.auth.request(method,path,data,{routeEpoch:pageContext.routeEpoch,routeCurrent,isCurrent:pageContext.valid,signal:pageContext.signal,...options});
  const identities=new WeakMap();
  const fetch=async(url,options={})=>{
    const identity=services.auth.requestContext({routeEpoch:pageContext.routeEpoch,routeCurrent,isCurrent:pageContext.valid,signal:options.signal||pageContext.signal});
    const response=await identity.fetch(url,options);identities.set(response,identity);return response;
  };
  const handleUnauthorized=(options,response)=>services.auth.unauthorized(identities.get(response),options);
  const VoiceCallCards=window.VoiceCallCards.create(pageContext);
  const readers=new Set();
  const run=promise=>Promise.resolve(promise).catch(error=>{
    if(pageContext.valid()&&!['AbortError','StaleRequestError'].includes(error.name)) services.ui.toast('暂时无法加载，请稍后重试');
  });
  let backgroundGeneration=0,restoreSuppressed=false;
  for(const event of ['wheel','touchstart','pointerdown','keydown'])listen(root,event,()=>{restoreSuppressed=true});

    /** 全屏背景随 AI 情绪切换（与 AVATAR_MAP 同源；顶栏头像固定 default） */
    function updateChatBackgroundEmotion(emotionLabel) {
      const layer = byId('chat-bg-image')
      if (!layer) return
      const src = AVATAR_MAP[emotionLabel] || AVATAR_MAP['default']
      const generation=++backgroundGeneration
      const preload = new Image()
      const release=pageContext.cleanup(()=>{
        preload.onload=preload.onerror=null
        // Cancel a pending load without creating an empty-src image retained by
        // Chromium's native viewport listener. Completed images can be collected.
        if(!preload.complete)preload.src='data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='
      })
      preload.onload = function () {
        release();if(!pageContext.valid()||generation!==backgroundGeneration)return
        layer.style.backgroundImage = 'url(' + src + ')'
      }
      preload.onerror = function () {
        release();if(!pageContext.valid()||generation!==backgroundGeneration)return
        layer.style.backgroundImage = 'url(' + AVATAR_MAP['default'] + ')'
      }
      preload.src = src
    }

    let timelineCursor = null
    let loadingTimeline = false
    let noMoreTimeline = false
    let timelinePages = 0
    let agentTipMessageId = null
    let chatFeedBadge = {unread:0,newCount:0}
    let chatAuthMode = services.auth.readToken() ? 'authenticated' : 'visitor'
    let chatResumePromise = null
    let chatResumeUser = null
    let chatUiEpoch = 0
    let chatShellInitialized = false
    let chatScrollObserver = null
    const visitorChatRequests = Object.freeze([])

    function isChatAuthenticated() {
      return pageContext.valid() && chatAuthMode === 'authenticated' && Boolean(services.auth.readToken())
    }

    function chatSilentAuthOptions() {
      return {
        authPolicy: AUTH_401_POLICIES.SILENT_VISITOR,
        onUnauthorized: () => {},
      }
    }

    function chatInteractiveAuthOptions(onUnauthorized) {
      return {
        authPolicy: AUTH_401_POLICIES.INTERACTIVE_MODAL,
        onUnauthorized: () => {},
      }
    }

    function openChatLoginModal() {
      services.ui.openLogin()
    }

    function goChatProtected(path) {
      if (!isChatAuthenticated()) {
        openChatLoginModal()
        return
      }
      pageContext.router.navigate(path)
    }

    /* 用户默认头像（与 static 目录一致：user 小写，Linux 区分大小写） */
    const USER_AVATAR_SRC = '/static/images/user/avatar/user_default.png'
    const USER_AVATAR_FALLBACK = '/static/images/avatar/emotion_calm.png'

    /* ====== 聊天区底部留白：随固定输入栏高度变化，避免消息被遮挡 ====== */
    function syncChatBottomPadding() {
      const bar = root.querySelector('.input-area')
      const msgs = byId('chat-messages')
      if (!bar || !msgs) return
      const atBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 48
      msgs.style.paddingBottom = (bar.offsetHeight + 8) + 'px'
      if (atBottom) {
        requestAnimationFrame(() => {
          msgs.scrollTop = msgs.scrollHeight
        })
      }
    }

    function setupInputAreaBottomSync() {
      const bar = root.querySelector('.input-area')
      if (!bar || typeof ResizeObserver === 'undefined') return
      const ro = new ResizeObserver(() => syncChatBottomPadding())
      ro.observe(bar)
      pageContext.cleanup(()=>ro.disconnect())
    }

    /* ====== 输入框自适应高度 ====== */
    function autoResize(el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, window.innerHeight / 3) + 'px'
      syncChatBottomPadding()
    }

    function updateSendBtn() {
      const btn = byId('send-btn')
      const input = byId('msg-input')
      if (!btn || !input) return
      const empty = !input.value.trim()
      btn.classList.toggle('disabled', empty)
      btn.disabled = empty
    }

    let inputComposing = false
    function handleEnterKey(e) {
      if (inputComposing || e.isComposing || e.keyCode === 229) return
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        run(handleSend())
      }
    }

    /** 发送键拦截默认按下行为，避免焦点从输入框移到按钮导致移动端键盘收起；发送仍走 click → handleSend */
    function setupSendBtnKeepKeyboard() {
      const btn = byId('send-btn')
      if (!btn) return
      listen(btn,'mousedown', function (e) { e.preventDefault() })
      listen(btn,'touchstart', function (e) { e.preventDefault() }, { passive: false })
    }

    /* ====== 草稿保存 ====== */
    function saveDraft() {
      if (!isChatAuthenticated()) return
      sessionStorage.setItem('chat_draft', byId('msg-input').value)
    }

    function loadDraft() {
      if (!isChatAuthenticated()) return
      const draft = sessionStorage.getItem('chat_draft')
      if (draft) {
        const input = byId('msg-input')
        if (input.value) return
        input.value = draft
        autoResize(input)
        updateSendBtn()
      }
    }

    function clearDraft() {
      sessionStorage.removeItem('chat_draft')
    }

    /* ====== 居中时间戳 DOM 辅助 ====== */
    /**
     * 解析消息时间：无时区后缀的 ISO 按 UTC（后端 utcnow naive），再供北京时间格式化
     */
    function parseMessageTimestamp(isoOrMs, fallback = Date.now()) {
      if (typeof isoOrMs === 'number' && Number.isFinite(isoOrMs)) return isoOrMs
      if (!isoOrMs) return fallback
      if (typeof isoOrMs === 'string') {
        var s = isoOrMs.trim()
        // 已有 Z / ±offset 则直接解析；否则按 UTC naive 补 Z
        if (/^\d{4}-\d{2}-\d{2}T/.test(s) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
          s = s + 'Z'
        }
        var d = new Date(s)
        var t = d.getTime()
        return Number.isFinite(t) ? t : fallback
      }
      var d2 = new Date(isoOrMs)
      var t2 = d2.getTime()
      return Number.isFinite(t2) ? t2 : fallback
    }

    function getRowTimestamp(row) {
      if (!row) return null
      const v = row.getAttribute('data-created-at')
      if (!v) return null
      const n = Number(v)
      return Number.isFinite(n) ? n : parseMessageTimestamp(v)
    }

    /** 从容器末尾向前找最近一条消息行（跳过 divider / sentinel） */
    function getLastMessageRow(container) {
      if (!container) return null
      let node = container.lastElementChild
      while (node) {
        if (node.id === 'top-sentinel') return null
        if (node.classList && node.classList.contains('msg-row')) return node
        node = node.previousElementSibling
      }
      return null
    }

    function createTimeDivider(ts) {
      const el = document.createElement('div')
      el.className = 'msg-time-divider'
      el.setAttribute('role', 'separator')
      el.textContent = formatChatTime(ts)
      return el
    }

    /** 按规则在 row 前插入居中戳，并追加 row */
    function appendChatRow(container, row, ts) {
      const prevRow = getLastMessageRow(container)
      const prevTs = prevRow ? getRowTimestamp(prevRow) : null
      if (shouldShowTimeStamp(ts, prevTs)) {
        container.appendChild(createTimeDivider(ts))
      }
      container.appendChild(row)
    }

    /** 批量插入时间线（items 按时间升序）；prepend 时处理与已有首条边界 */
    function insertTimelineBatch(container, items, insertBeforeNode) {
      const nodes = []
      const seen=new Set()
      let prevTs = null
      items.forEach(function (item) {
        const id=item.source==='call'?item.call_id:item.id,key=item.source+':'+id
        if(seen.has(key))return
        seen.add(key)
        const existing = findChatMessageRow(item.source, id)
        if (existing) return
        const ts = parseMessageTimestamp(item.created_at)
        const row = renderTimelineItem(item, ts)
        if (shouldShowTimeStamp(ts, prevTs)) {
          nodes.push(createTimeDivider(ts))
        }
        nodes.push(row)
        prevTs = ts
      })
      if (!insertBeforeNode) {
        nodes.forEach(function (n) { container.appendChild(n) })
        return
      }
      const lastBatchTs = prevTs
      const firstExistingTs = getRowTimestamp(insertBeforeNode)
      if (firstExistingTs != null && lastBatchTs != null &&
          shouldShowTimeStamp(firstExistingTs, lastBatchTs)) {
        container.insertBefore(createTimeDivider(firstExistingTs), insertBeforeNode)
      }
      nodes.forEach(function (n) {
        container.insertBefore(n, insertBeforeNode)
      })
    }

    /* ====== 消息渲染 ====== */
    function appendUserBubble(content, deliveryStatus) {
      const container = byId('chat-messages')
      const ts = Date.now()
      const row = document.createElement('div')
      row.className = 'msg-row user'
      const ds = deliveryStatus || 'pending_llm'
      row.setAttribute('data-delivery', ds)
      row.setAttribute('data-created-at', String(ts))
      const needBang = ds === 'failed_timeout' || ds === 'failed_error'
      const bangBtn = needBang
        ? `<button type="button" class="msg-bang" title="重试">!</button>`
        : ''
      row.innerHTML = `
        <img class="msg-avatar" src="${USER_AVATAR_SRC}" alt="">
        <div class="msg-user-with-side">
          ${bangBtn}
          <div class="msg-body">
            <div class="msg-bubble">${escapeHtml(content)}</div>
          </div>
        </div>
      `
      appendChatRow(container, row, ts)
      return row
    }

    /** 用户行标记为失败态时补叹号按钮（与 timeline 结构一致） */
    function ensureUserRowBangButton(row) {
      if (!row || !row.parentNode) return
      const ds = row.getAttribute('data-delivery') || ''
      if (ds !== 'failed_timeout' && ds !== 'failed_error') return
      const side = row.querySelector('.msg-user-with-side')
      if (!side || side.querySelector('.msg-bang')) return
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'msg-bang'
      btn.title = '重试'
      btn.textContent = '!'
      side.insertBefore(btn, side.firstChild)
    }

    /** 移除所有「流式进行中」的 AI 行（S2：打断 / 新 send / failed / obsolete） */
    function removeAiInFlightRows() {
      root.querySelectorAll('#chat-messages .msg-row.ai[data-ai-in-flight="1"]').forEach((el) => el.remove())
    }

    function mapSseFailedToDelivery(data) {
      const msg = (data && data.message) ? String(data.message) : ''
      if (msg.indexOf('超时') >= 0) return 'failed_timeout'
      return 'failed_error'
    }

    function appendAIBubble(content, isAgent, isUnread) {
      const container = byId('chat-messages')
      const ts = Date.now()
      const row = document.createElement('div')
      row.className = 'msg-row ai' + (isAgent ? ' agent' : '')
      row.setAttribute('data-created-at', String(ts))
      row.innerHTML = `
        <img class="msg-avatar" src="/static/images/avatar/default.png" alt="">
        <div class="msg-body">
          <div class="msg-bubble">
            ${isUnread ? '<span class="msg-unread-tag">未读</span>' : ''}
            ${escapeHtml(content)}
          </div>
        </div>
      `
      appendChatRow(container, row, ts)
      return row
    }

    /**
     * 多气泡流式渲染器：支持 message_count + message_index 按条填槽。
     * 初始仅展示一个 thinking 气泡；收到 meta.message_count 后不预铺空气泡（§2.7.5）。
     * delta 到达时按 message_index 动态创建/填充对应气泡行。
     * done 到达后以 done.messages 为真相源纠偏定稿。
     */
    function appendAIThinkingBubble() {
      const container = byId('chat-messages')

      // 初始 thinking 行（收到首个 delta 后移除）
      const thinkingRow = document.createElement('div')
      thinkingRow.className = 'msg-row ai'
      thinkingRow.setAttribute('data-ai-in-flight', '1')
      thinkingRow.innerHTML = `
        <img class="msg-avatar" src="/static/images/avatar/default.png" alt="">
        <div class="msg-body">
          <div class="msg-bubble thinking-bubble">
            <div class="msg-content">
              <div class="loading-dots"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>
      `
      container.appendChild(thinkingRow)

      // 多气泡槽位管理
      let messageCount = 1
      let bubbleSlots = []  // [{row, bubble, contentEl}]
      let thinkingRemoved = false

      function removeThinking() {
        if (!thinkingRemoved && thinkingRow.parentNode) {
          thinkingRow.remove()
          thinkingRemoved = true
        }
      }

      function ensureSlot(index) {
        while (bubbleSlots.length <= index) {
          const row = document.createElement('div')
          row.className = 'msg-row ai'
          row.setAttribute('data-ai-in-flight', '1')
          const ts = Date.now()
          row.setAttribute('data-created-at', String(ts))
          row.innerHTML = `
            <img class="msg-avatar" src="/static/images/avatar/default.png" alt="">
            <div class="msg-body">
              <div class="msg-bubble">
                <div class="msg-content"></div>
              </div>
            </div>
          `
          appendChatRow(container, row, ts)
          bubbleSlots.push({
            row,
            bubble: row.querySelector('.msg-bubble'),
            contentEl: row.querySelector('.msg-content'),
          })
        }
        return bubbleSlots[index]
      }

      return {
        row: thinkingRow,
        setMessageCount(count) {
          messageCount = count || 1
        },
        removeRow() {
          removeThinking()
          bubbleSlots.forEach(s => { if (s.row.parentNode) s.row.remove() })
          bubbleSlots = []
        },
        appendTextAt(index, text) {
          removeThinking()
          const slot = ensureSlot(index)
          slot.contentEl.innerHTML += escapeHtml(text)
        },
        /** done 到达：以 messages 数组为真相源，纠偏所有气泡内容 */
        finalize(messages, emotion) {
          removeThinking()
          // 按 done.messages 纠偏/定稿
          for (let i = 0; i < messages.length; i++) {
            const slot = ensureSlot(i)
            slot.contentEl.innerHTML = escapeHtml(messages[i].content || '')
            slot.row.removeAttribute('data-ai-in-flight')
          }
          // 移除多余槽位（理论上不会出现，防御性处理）
          while (bubbleSlots.length > messages.length) {
            const extra = bubbleSlots.pop()
            if (extra.row.parentNode) extra.row.remove()
          }
        },
        markComplete() {
          removeThinking()
          bubbleSlots.forEach(s => {
            s.row.removeAttribute('data-ai-in-flight')
          })
        },
        showError(msg) {
          if (!thinkingRemoved) {
            const bubble = thinkingRow.querySelector('.msg-bubble')
            const content = thinkingRow.querySelector('.msg-content')
            bubble.classList.remove('thinking-bubble')
            if (content) {
              content.innerHTML = '<span class="msg-error">' + escapeHtml(msg) + '</span>'
            }
          } else if (bubbleSlots.length > 0) {
            bubbleSlots[0].contentEl.innerHTML = '<span class="msg-error">' + escapeHtml(msg) + '</span>'
          }
        }
      }
    }

    function escapeHtml(text) {
      const div = document.createElement('div')
      div.textContent = text
      return div.innerHTML
    }

    function scrollToBottom() {
      const container = byId('chat-messages')
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight
      })
    }

    /* ====== 发送消息（TD-015：Abort 打断、meta.generation_id、幂等键、队列满） ====== */
    let chatSendAbort = null
    /** 每次发起 send/resend 前递增；与 meta.generation_id 配合丢弃过期 SSE（对齐契约） */
    let chatSendSession = 0
    // Client total wait covers response headers AND the full SSE body; nginx read timeout is idle.
    let chatTiming = ChatSubmissions.TIMING
    let chatTimingReady = false
    const CHAT_SEND_DEBOUNCE_MS = 300
    let lastSendOrResendAt = 0
    let chatTransportTimer = null
    const chatRowVersions = new Map()
    let chatStatusEpoch=0
    function currentChatUser() { return pageContext.valid() ? ChatSubmissions.userFromToken(services.auth.readToken() || '') : null }
    function findChatMessageRow(source, id) {
      if (id == null) return null
      return [...root.querySelectorAll('#chat-messages .msg-row')].find(row =>
        row.dataset.messageSource === source && row.dataset.messageId === String(id)) || null
    }
    function markChatUnverified(record) {
      record.observationUnknown=true
      const rows = [...root.querySelectorAll('#chat-messages .msg-row.user')].filter(row =>
        row.dataset.requestId === record.request_id || (record.source_messages || []).some(m => String(m.id) === row.dataset.messageId))
      if (!rows.length) byId('chat-sync-note').hidden=false
      rows.forEach(row => {
        if (row.dataset.processing === 'success' || row.dataset.processing === 'failed' || row.dataset.processing === 'superseded') return
        row.dataset.delivery = 'unverified'; row.dataset.processing = 'unverified'
        row.querySelectorAll('.msg-bang').forEach(b => b.remove())
        let label = row.querySelector('.msg-sync-status')
        if (!label) { label=document.createElement('span'); label.className='msg-sync-status'; row.querySelector('.msg-body').appendChild(label) }
        label.textContent = '待核实'
      })
    }
    function applyChatStatus(record, status) {
      chatStatusEpoch++
      const revision = status.state_revision
      const state = status.processing_state || 'unverified'
      record.lastStatus=status
      record.observationUnknown=state==='unverified'
      if (record.bubble && ['success','failed','superseded'].includes(state)) record.bubble.removeRow()
      byId('chat-sync-note').hidden=![...chatSubmissions.records.values()].some(r=>!r.terminal && r.observationUnknown && !r.source_messages.length)
      let provisional = [...root.querySelectorAll('#chat-messages .msg-row.user')].find(row =>
        row.dataset.requestId === record.request_id && !row.dataset.messageId)
      ;(record.source_messages || []).forEach(message => {
        const key='user:'+message.id, old=chatRowVersions.get(key)
        if (old && (ChatSubmissions.compareRevision(revision,old.revision) === null ||
          ChatSubmissions.compareRevision(revision,old.revision) < 0 ||
          (old.terminal && ChatSubmissions.compareRevision(revision,old.revision) === 0))) return
        let row=findChatMessageRow('user',message.id)
        if (row && provisional && record.operation==='send') { provisional.remove();provisional=null }
        if (!row && provisional) { row=provisional; provisional=null }
        if (!row) return // Restore uses the ordinary timeline for user content; no local text copy.
        row.dataset.messageSource='user'; row.dataset.messageId=String(message.id); row.dataset.sortSeq=message.sort_seq
        row.dataset.generationId=status.effective_generation_id || ''; row.dataset.processing=state
        if (revision) { row.dataset.stateRevision=revision; chatRowVersions.set(key,{revision,terminal:['success','failed','superseded'].includes(state)}) }
        row.dataset.delivery=state==='success'?'delivered':state==='failed'?(status.status_reason==='deadline_exceeded'?'failed_timeout':'failed_error'):state==='pending'?'pending_llm':state
        row.querySelectorAll('.msg-bang,.msg-sync-status').forEach(b=>b.remove())
        row.dataset.canResend=String(state==='failed' && status.can_resend===true)
        if (state==='failed' && status.can_resend===true) ensureUserRowBangButton(row)
        else if (state==='failed' || state==='unverified' || state==='superseded') {
          const label=document.createElement('span');label.className='msg-sync-status'
          label.textContent=state==='failed'?(status.status_reason==='content_blocked'?'内容未通过安全检查':'回复失败'):state==='superseded'?'已作废':'待核实'
          row.querySelector('.msg-body').appendChild(label)
        }
      })
      if (provisional) markChatUnverified(record)
      if (state==='success' && status.result && Array.isArray(status.result.messages)) {
        // A newer effective generation on a source row makes an older round's SSE/result stale.
        if ((record.source_messages || []).some(m=>{
          const old=chatRowVersions.get('user:'+m.id)
          return old && ChatSubmissions.compareRevision(revision,old.revision)<0
        })) return
        status.result.messages.forEach(message => {
          if (message.id == null) return
          const existing=findChatMessageRow('assistant',message.id)
          const row=existing || appendAIBubble(message.content,false,false)
          row.dataset.messageSource='assistant';row.dataset.messageId=String(message.id);row.dataset.sortSeq=message.sort_seq
          row.dataset.roundId=status.result.round_id || '';row.dataset.stateRevision=revision || ''
          row.querySelector('.msg-bubble').textContent=message.content || ''
        })
        if (status.result.emotion && status.result.emotion.label) updateChatBackgroundEmotion(status.result.emotion.label)
      }
    }
    const chatSubmissions = new ChatSubmissions.Reconciler({
      user:currentChatUser,
      active:()=>isChatAuthenticated() && document.visibilityState==='visible' && navigator.onLine,
      unknown:record=>{if(pageContext.valid())markChatUnverified(record)}, update:applyChatStatus,
      fetch:async(record,signal)=>{
        const user=currentChatUser()
        const response=await fetch(API_BASE+'/api/chat/submissions/'+record.operation+'/'+ChatSubmissions.encodeRequestId(record.request_id),{
          headers:{Authorization:'Bearer '+services.auth.readToken()},signal
        })
        if (user!==currentChatUser()) return null
        if (response.status===401) { await handleUnauthorized(chatSilentAuthOptions(),response); return null }
        if (!response.ok) throw new Error('status_http_'+response.status)
        return response.json()
      }
    })
    function stopChatObservation() {
      chatSubmissions.pause();if(chatEligibilityAbort)chatEligibilityAbort.abort();chatEligibilityAbort=null;clearTimeout(chatTransportTimer);chatTransportTimer=null
      if (chatSendAbort) { chatSendSession++;chatSendAbort.abort();chatSendAbort=null }
      for(const reader of readers) { try { void reader.cancel().catch(()=>{}) } catch(_) {} }
      removeAiInFlightRows()
    }
    function armChatTransport(record, controller) {
      clearTimeout(chatTransportTimer)
      const serverDeadline=Date.parse(record.effective_deadline_at)
      const end=Number.isFinite(serverDeadline)?serverDeadline+chatTiming.text_client_transport_margin_ms:
        record.submitted_at+chatTiming.text_business_deadline_ms+chatTiming.text_client_transport_margin_ms
      chatTransportTimer=setTimeout(()=>controller.abort(),Math.max(0,end-Date.now()))
    }

    function rollbackChatSendForUnauthorized(userRow, aiBubble, content) {
      if (aiBubble) aiBubble.removeRow()
      if (userRow && userRow.parentNode) userRow.remove()
      const input = byId('msg-input')
      if (input && !input.value) {
        input.value = content || ''
        autoResize(input)
        updateSendBtn()
      }
    }

    /** 未闭环窗口内 user 行：最后一条已落库 assistant（非 agent、非流式中）之后，与后端 fetch_open_window_user_rows 对齐 */
    function getOpenWindowUserRows() {
      const rows = [...root.querySelectorAll('#chat-messages .msg-row')]
      let lastAiIdx = -1
      for (let i = rows.length - 1; i >= 0; i--) {
        const row = rows[i]
        if (!row.classList.contains('ai') || row.classList.contains('agent')) continue
        if (row.getAttribute('data-ai-in-flight') === '1') continue
        lastAiIdx = i
        break
      }
      const users = []
      for (let i = lastAiIdx + 1; i < rows.length; i++) {
        if (rows[i].classList.contains('user')) users.push(rows[i])
      }
      return users
    }

    function countOpenPendingUsers() {
      let pending = 0
      let hasBang = false
      for (const el of getOpenWindowUserRows()) {
        const d = el.getAttribute('data-delivery') || ''
        if (d === 'failed_timeout' || d === 'failed_error') hasBang = true
        if (d === 'pending_llm' || d === 'failed_timeout' || d === 'failed_error') pending++
      }
      return { pending, hasBang }
    }

    /** 与后端 pack 闭环一致：将未闭环窗口内 user 行标为 delivered（须在 finalize 前调用） */
    function markOpenWindowUsersDelivered() {
      for (const row of getOpenWindowUserRows()) {
        const ds = row.getAttribute('data-delivery') || ''
        if (ds === 'pending_llm' || ds === 'failed_timeout' || ds === 'failed_error') {
          row.setAttribute('data-delivery', 'delivered')
          row.querySelectorAll('.msg-bang').forEach(function (b) { b.remove() })
        }
      }
    }

    /**
     * 解析对话 SSE（§2.9.4 多气泡协议）。
     * 协议：meta(message_count+generation_id) → delta(message_index+content) → done(messages+emotion)
     * sseCtx.userRowForFailure：send 传入；failed 时标叹号态。
     * done 成功时 markOpenWindowUsersDelivered 标未闭环窗口内 user（含 resend 成功后的 failed_*）。
     */
    function isCurrentChatSubmission(context) {
      const record=context.record
      return pageContext.valid() && currentChatUser()===context.owner && chatSubmissions.user===context.owner &&
        chatSubmissions.records.get(record.operation+':'+record.request_id)===record &&
        chatUiEpoch===context.uiEpoch && chatSendSession===context.session
    }

    async function consumeChatSse(response, aiBubble, context) {
      const reader=response.body.getReader(),decoder=new TextDecoder()
      readers.add(reader)
      let buffer='',identity=null,terminal=false
      try {
        while (true) {
          const part=await reader.read()
          if (!isCurrentChatSubmission(context) || !chatSubmissions.active()) return
          if (part.done) break
          buffer+=decoder.decode(part.value,{stream:true})
          const lines=buffer.split('\n');buffer=lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            let data;try { data=JSON.parse(line.slice(6)) } catch (_) { continue }
            const record=context.record
            if (data.type==='meta') {
              if (data.operation!==record.operation || data.request_id!==record.request_id) continue
              identity=data
              chatSubmissions.apply(record,{...data,admission_state:'accepted',processing_state:'pending'})
              armChatTransport(record,context.controller)
              continue
            }
            if (!identity) continue
            const rev=data.state_revision || identity.state_revision
            const effective=data.effective_generation_id || identity.effective_generation_id
            const stale=(record.state_revision && (ChatSubmissions.compareRevision(rev,record.state_revision)===null || ChatSubmissions.compareRevision(rev,record.state_revision)<0)) ||
              (effective && record.effective_generation_id && effective!==record.effective_generation_id) ||
              (data.generation_id && data.generation_id!==effective) || record.terminal ||
              (record.source_messages || []).some(m=>{
                const v=chatRowVersions.get('user:'+m.id)
                return v && (ChatSubmissions.compareRevision(rev,v.revision)===null || ChatSubmissions.compareRevision(rev,v.revision)<0 || v.terminal)
              })
            if (stale) continue
            if (data.type==='delta') {
              aiBubble.appendTextAt(Number.isInteger(data.message_index)?data.message_index:0,data.content || '')
              scrollToBottom()
            } else if (data.type==='done') {
              aiBubble.removeRow()
              terminal=chatSubmissions.apply(record,{...identity,...data,admission_state:'accepted',processing_state:'success',
                result:{round_id:data.round_id,messages:data.messages || [],emotion:data.emotion},can_resend:false}) && record.terminal
              if (data.leveled_up) showLevelUpTip(data.new_level_name || '')
            } else if (data.type==='failed' || data.type==='obsolete') {
              // A stream error does not assert current ownership/eligibility: read the authoritative GET.
              aiBubble.removeRow();chatSubmissions.wake();return
            }
          }
        }
      } finally {
        readers.delete(reader);reader.cancel().catch(()=>{});reader.releaseLock()
        if (!terminal) {
          aiBubble.removeRow()
          if (isCurrentChatSubmission(context)) { markChatUnverified(context.record);chatSubmissions.wake() }
        }
      }
    }

    async function submitChatRequest(operation, content, userRow, button) {
      if (!chatTimingReady || !currentChatUser()) { if (userRow) userRow.remove(); alert('聊天连接准备中，请稍后再试');return }
      if (chatSubmissions.user!==currentChatUser()) chatSubmissions.restore(currentChatUser())
      if (chatSendAbort) chatSendAbort.abort()
      const sessionAtStart=++chatSendSession
      removeAiInFlightRows()
      const controller=new AbortController();chatSendAbort=controller
      const id=(crypto.randomUUID && crypto.randomUUID()) || ('chat-'+Date.now()+'-'+Math.random().toString(36).slice(2))
      let record
      try { record=chatSubmissions.start(operation,id) } catch (_) {
        if (userRow) userRow.remove();alert('无法保存请求标识，请检查浏览器存储后再试');return
      }
      if (userRow) userRow.dataset.requestId=id
      if (button) button.disabled=true
      const aiBubble=appendAIThinkingBubble();record.bubble=aiBubble;scrollToBottom()
      const context={record,controller,owner:chatSubmissions.user,uiEpoch:chatUiEpoch,session:sessionAtStart}
      armChatTransport(record,controller)
      try {
        const response=await fetch(API_BASE+'/api/chat/'+operation,{
          method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+services.auth.readToken(),'Idempotency-Key':id},
          body:JSON.stringify(operation==='send'?{content,client_message_id:id}:{client_resend_id:id}),signal:controller.signal
        })
        if (!isCurrentChatSubmission(context) || !chatSubmissions.active()) return
        if (response.status===401) {
          rollbackChatSendForUnauthorized(userRow,aiBubble,content)
          await handleUnauthorized(chatInteractiveAuthOptions(),response);return
        }
        if (!response.ok) throw new Error('chat_http_'+response.status)
        if ((response.headers.get('content-type') || '').includes('application/json')) {
          const body=await response.json()
          if (!isCurrentChatSubmission(context) || !chatSubmissions.active()) return
          aiBubble.removeRow()
          if (body.data && body.data.operation) chatSubmissions.apply(record,body.data)
          if ([10100,10101,10104,10105,10107,10109].includes(body.code) && !(body.data && body.data.admission_state==='accepted')) {
            record.terminal=true;chatSubmissions.save()
            if (userRow) userRow.remove()
            alert(body.message || '请求未被接受');return
          }
          markChatUnverified(record);return
        }
        await consumeChatSse(response,aiBubble,context)
      } catch (_) {
        aiBubble.removeRow()
        if (isCurrentChatSubmission(context)) markChatUnverified(record)
      } finally {
        if (sessionAtStart===chatSendSession) {
          clearTimeout(chatTransportTimer);chatTransportTimer=null;chatSendAbort=null
        }
        if (isCurrentChatSubmission(context)) chatSubmissions.wake()
      }
    }
    async function handleSend() {
      if (!isChatAuthenticated()) { openChatLoginModal();return }
      const input=byId('msg-input'),content=input.value.trim()
      if (!content) return
      const {pending,hasBang}=countOpenPendingUsers()
      if (pending>=5 && !hasBang) { alert('待处理消息过多，请先等待回复或处理失败提示后再发');return }
      const now=Date.now();if (now-lastSendOrResendAt<CHAT_SEND_DEBOUNCE_MS) return
      lastSendOrResendAt=now
      const row=appendUserBubble(content,'pending_llm')
      input.value='';input.style.height='auto';updateSendBtn();clearDraft()
      await submitChatRequest('send',content,row,null)
    }
    listen(byId('chat-messages'),'click',async e=>{
      const button=e.target.closest('.msg-bang')
      if (!button || button.disabled) return
      if (!isChatAuthenticated()) { openChatLoginModal();return }
      if (button.closest('.msg-row').dataset.canResend!=='true') return
      const now=Date.now();if (now-lastSendOrResendAt<CHAT_SEND_DEBOUNCE_MS) return
      lastSendOrResendAt=now
      await submitChatRequest('resend',null,null,button)
    })

    /* ====== 加载统一时间线 ====== */
    VoiceCallCards.configureResourceRefresh(async callId => {
      if (!isChatAuthenticated()) return null
      const res = await request('GET', '/api/voice/calls/' + encodeURIComponent(callId), undefined, chatSilentAuthOptions())
      return res.code === 0 && res.data ? res.data.crisis : null
    })
    const callCardRefresh = VoiceCallCards.pendingRefresh({
      schedule: (callback, delay) => setTimeout(callback, delay),
      cancel: timer => clearTimeout(timer),
      active: () => isChatAuthenticated(),
      fetch: async url => {
        const response = await request('GET', url + (url.includes('?') ? '&' : '?') + 'pending_reload=true', undefined, chatSilentAuthOptions())
        return response.code === 0 && response.data ? response.data.items || [] : []
      },
      update: items => {
        const rows = Array.from(root.querySelectorAll('#chat-messages .voice-call-row'))
        items.filter(item => item.source === 'call').forEach(item => {
          const old = rows.find(row => row.dataset.callId === item.call_id)
          if (old) old.replaceWith(renderTimelineItem(item))
        })
      }
    })
    async function loadTimeline(isFirstPage) {
      if (!isChatAuthenticated() || loadingTimeline || noMoreTimeline) return
      loadingTimeline = true
      const epoch=chatUiEpoch,user=currentChatUser()

      let url = '/api/chat/timeline?limit=20'
      if (timelineCursor !== null) {
        url += '&cursor=' + timelineCursor
      }

      const res = await request('GET', url, undefined, chatSilentAuthOptions())
      if (!isChatAuthenticated() || epoch!==chatUiEpoch || user!==currentChatUser()) return
      if (res.code === 0 && res.data) {
        const items = res.data.items || []
        timelinePages++
        if (items.length === 0) {
          noMoreTimeline = true
          loadingTimeline = false
          return
        }

        if (!res.data.has_more) {
          noMoreTimeline = true
        }

        if (res.data.next_cursor !== null && res.data.next_cursor !== undefined) {
          timelineCursor = res.data.next_cursor
        }

        const container = byId('chat-messages')
        const sentinel = byId('top-sentinel')

        if (isFirstPage) {
          const firstRow=container.querySelector('.msg-row')
          const before=firstRow && firstRow.previousElementSibling && firstRow.previousElementSibling.classList.contains('msg-time-divider')?firstRow.previousElementSibling:firstRow
          insertTimelineBatch(container, items, before)
        } else {
          const oldScrollHeight = container.scrollHeight
          let firstMsgNode = sentinel.nextElementSibling
          while (firstMsgNode && firstMsgNode.classList &&
                 firstMsgNode.classList.contains('msg-time-divider')) {
            firstMsgNode = firstMsgNode.nextElementSibling
          }
          insertTimelineBatch(container, items, firstMsgNode || null)
          container.scrollTop = container.scrollHeight - oldScrollHeight
        }
        chatSubmissions.records.forEach(r=>{ if (r.lastStatus) applyChatStatus(r,r.lastStatus) })
        refreshChatResendEligibility()
        callCardRefresh.observe(items, url)
      }

      loadingTimeline = false
    }

    let chatEligibilityAbort=null
    async function refreshChatResendEligibility() {
      if (!isChatAuthenticated() || !navigator.onLine || document.visibilityState!=='visible') return
      if (chatEligibilityAbort) chatEligibilityAbort.abort()
      const controller=new AbortController();chatEligibilityAbort=controller
      const epoch=chatUiEpoch,user=currentChatUser(),statusEpoch=chatStatusEpoch
      const timer=setTimeout(()=>controller.abort(),chatTiming.text_status_probe_timeout_ms)
      try {
        const response=await fetch(API_BASE+'/api/chat/resend-eligibility',{headers:{Authorization:'Bearer '+services.auth.readToken()},signal:controller.signal})
        if (response.status===401) { if (epoch===chatUiEpoch) await handleUnauthorized(chatSilentAuthOptions(),response);return }
        if (!response.ok) return
        const result=await response.json()
        if (epoch!==chatUiEpoch || user!==currentChatUser() || statusEpoch!==chatStatusEpoch || result.code!==0 || !result.data) return
        const ids=result.data.can_resend===true && Array.isArray(result.data.message_ids)?result.data.message_ids.map(String):[]
        root.querySelectorAll('#chat-messages .msg-row.user').forEach(row=>{
          const allowed=ids.includes(row.dataset.messageId)
          row.dataset.canResend=String(allowed)
          row.querySelectorAll('.msg-bang').forEach(b=>b.remove())
          if (allowed) ensureUserRowBangButton(row)
        })
      } catch (_) {
        if (epoch===chatUiEpoch && statusEpoch===chatStatusEpoch) root.querySelectorAll('#chat-messages .msg-bang').forEach(b=>b.remove())
      } finally { clearTimeout(timer);if(chatEligibilityAbort===controller)chatEligibilityAbort=null }
    }

    function renderTimelineItem(item, ts) {
      const createdTs = ts != null ? ts : parseMessageTimestamp(item.created_at)
      if (item.source === 'call') {
        const row=VoiceCallCards.render(item,createdTs,parseMessageTimestamp(item.created_at,null))
        row.dataset.messageSource='call';row.dataset.messageId=String(item.call_id);row.dataset.sortSeq=item.sort_seq||'';return row
      }
      const row = document.createElement('div')
      row.setAttribute('data-created-at', String(createdTs))
      row.dataset.messageSource=item.source;row.dataset.messageId=String(item.id);row.dataset.sortSeq=item.sort_seq || ''
      if (item.source === 'user') {
        row.className = 'msg-row user'
        const ds = item.delivery_status || ''
        if (ds) row.setAttribute('data-delivery', ds)
        // Timeline has no authoritative resend eligibility. A status GET supplies it.
        const needBang = false
        const bangBtn = needBang
          ? `<button type="button" class="msg-bang" title="重试">!</button>`
          : ''
        row.innerHTML = `
          <img class="msg-avatar" src="${USER_AVATAR_SRC}" alt="">
          <div class="msg-user-with-side">
            ${bangBtn}
            <div class="msg-body">
              <div class="msg-bubble">${escapeHtml(item.content)}</div>
            </div>
          </div>
        `
      } else {
        const isAgent = item.source === 'agent'
        const isUnread = isAgent && item.is_read === false
        row.className = 'msg-row ai' + (isAgent ? ' agent' : '')
        row.innerHTML = `
          <img class="msg-avatar" src="/static/images/avatar/default.png" alt="">
          <div class="msg-body">
            <div class="msg-bubble">
              ${isUnread ? '<span class="msg-unread-tag">未读</span>' : ''}
              ${escapeHtml(item.content)}
            </div>
          </div>
        `
        if (item.emotion_label) {
          row.setAttribute('data-emotion', item.emotion_label)
        }
      }
      return row
    }

    /* ====== 加载未读主动消息提示条 ====== */
    async function loadAgentTip() {
      if (!isChatAuthenticated()) return
      const epoch=chatUiEpoch,user=currentChatUser()
      const res = await request(
        'GET',
        '/api/agent/messages',
        undefined,
        chatSilentAuthOptions()
      )
      if (!isChatAuthenticated() || epoch!==chatUiEpoch || user!==currentChatUser() || res.code !== 0 || !res.data) return

      const messages = res.data.messages || res.data || []
      if (messages.length === 0) return

      const unreadMessages = messages.filter(m => !m.is_read)
      if (unreadMessages.length > 0) {
        const latest = unreadMessages[unreadMessages.length - 1]
        agentTipMessageId = latest.id
        const tipEl = byId('agent-tip')
        const tipContent = byId('tip-content')
        let text = latest.content || ''
        if (text.length > 30) text = text.substring(0, 30) + '...'
        tipContent.textContent = text
        tipEl.classList.remove('hidden')

        const chatMessages = byId('chat-messages')
        chatMessages.classList.add('has-tip')
      }
    }

    /* ====== 提示条交互 ====== */
    listen(byId('agent-tip'),'click', async function (e) {
      if (e.target.id === 'tip-close' || e.target.closest('#tip-close')) {
        return
      }

      if (!isChatAuthenticated()) {
        openChatLoginModal()
        return
      }

      if (agentTipMessageId) {
        const res = await request(
          'POST',
          '/api/agent/messages/' + agentTipMessageId + '/read',
          undefined,
          chatInteractiveAuthOptions()
        )
        if (res.code === 401) return
      }
      hideAgentTip()
      scrollToBottom()
    })

    listen(byId('tip-close'),'click', function (e) {
      e.stopPropagation()
      hideAgentTip()
    })

    function hideAgentTip() {
      const tipEl = byId('agent-tip')
      tipEl.classList.add('hidden')
      byId('chat-messages').classList.remove('has-tip')
    }

    /* ====== 上滑加载更多 ====== */
    function setupScrollObserver() {
      if (!isChatAuthenticated() || chatScrollObserver) return
      const sentinel = byId('top-sentinel')
      chatScrollObserver = new IntersectionObserver(entries => {
        if (isChatAuthenticated() && entries[0].isIntersecting && !loadingTimeline && !noMoreTimeline) {
          run(loadTimeline(false))
        }
      }, { root: byId('chat-messages'), threshold: 0 })
      chatScrollObserver.observe(sentinel)
      const observer=chatScrollObserver;pageContext.cleanup(()=>observer.disconnect())
    }

    /* ====== 键盘弹起适配 ====== */
    if (window.visualViewport) {
      listen(window.visualViewport,'resize', () => {
        const bottomBar = root.querySelector('.input-area')
        bottomBar.style.bottom = (window.innerHeight - window.visualViewport.height) + 'px'
        syncChatBottomPadding()
        scrollToBottom()
      })
    }

    listen(window,'resize', () => syncChatBottomPadding())

    /* ====== 升级提示条 ====== */
    function showLevelUpTip(levelName) {
      const existing = root.querySelector('.levelup-tip')
      if (existing) existing.remove()

      const tip = document.createElement('div')
      tip.className = 'levelup-tip'
      tip.innerHTML =
        '<div class="lt-text">🎉 恭喜！我们升级为「' + levelName + '」了</div>' +
        '<div class="lt-btn">查看 →</div>'
      listen(tip,'click',()=>pageContext.router.navigate('/pages/relationship.html?just_leveled_up=true'))
      root.appendChild(tip)
      pageContext.cleanup(()=>tip.remove())

      setTimeout(function() {
        if (tip.parentNode) {
          tip.style.animation = 'toast-out 0.3s forwards'
          listen(tip,'animationend', function() { tip.remove() })
        }
      }, 6000)
    }

    /* ====== 页面初始化 ====== */
    /** 朋友圈角标：未读回复 + 新动态之和 */
    chatFeedBadge = { unread: 0, newCount: 0 }

    async function loadChatFeedBadge() {
      if (!isChatAuthenticated()) return
      const epoch=chatUiEpoch,user=currentChatUser()
      try {
        const res = await request(
          'GET',
          '/api/feed/badge',
          undefined,
          chatSilentAuthOptions()
        )
        if (!isChatAuthenticated() || epoch!==chatUiEpoch || user!==currentChatUser()) return
        let unread = 0
        let newCount = 0
        if (res && res.code === 0 && res.data) {
          unread = Number(res.data.unread_reply_count) || 0
          newCount = Number(res.data.new_post_count) || 0
        }
        chatFeedBadge = { unread: unread, newCount: newCount }
        const total = unread + newCount
        const badge = byId('feed-badge')
        if (!badge) return
        if (total > 0) {
          badge.textContent = formatBadgeCount(total)
          badge.classList.add('is-on')
          badge.setAttribute('aria-hidden', 'false')
        } else {
          badge.textContent = '0'
          badge.classList.remove('is-on')
          badge.setAttribute('aria-hidden', 'true')
        }
      } catch (e) {
        /* 角标失败不影响聊天 */
      }
    }

    /** 点击朋友圈：有未读回复则带 focus，否则进列表顶部 */
    function goChatFeed() {
      const b = chatFeedBadge || {}
      if ((b.unread || 0) > 0) {
        pageContext.router.navigate('/pages/feed.html?focus=unread_reply')
      } else {
        pageContext.router.navigate('/pages/feed.html')
      }
    }

    function initializeChatShell() {
      if (chatShellInitialized) return
      chatShellInitialized = true
      syncChatBottomPadding()
      setupInputAreaBottomSync()
      setupSendBtnKeepKeyboard()
      updateChatBackgroundEmotion('平静')
    }

    function resetPrivateChatUi(options = {}) {
      chatUiEpoch++
      stopChatObservation()
      byId('chat-sync-note').hidden=true
      chatRowVersions.clear()
      callCardRefresh.reset()
      timelineCursor = null
      loadingTimeline = false
      noMoreTimeline = false
      timelinePages = 0
      agentTipMessageId = null

      if (chatScrollObserver) {
        chatScrollObserver.disconnect()
        chatScrollObserver = null
      }

      root.querySelectorAll('#chat-messages .msg-row, #chat-messages .msg-time-divider')
        .forEach(function (node) { node.remove() })
      hideAgentTip()

      chatFeedBadge = { unread: 0, newCount: 0 }
      const badge = byId('feed-badge')
      badge.textContent = '0'
      badge.classList.remove('is-on')
      badge.setAttribute('aria-hidden', 'true')

      if (!options.preserveInput) {
        const input = byId('msg-input')
        input.value = ''
        input.style.height = 'auto'
        updateSendBtn()
      }
      updateChatBackgroundEmotion('平静')
      syncChatBottomPadding()
    }

    function switchChatToVisitor(options = {}) {
      chatTimingReady=false
      clearDraft()
      chatSubmissions.detach()
      chatAuthMode = 'visitor'
      if (chatSendAbort) {
        chatSendSession += 1
        chatSendAbort.abort()
        chatSendAbort = null
      }
      resetPrivateChatUi(options)
    }

    function initVisitorChat() {
      initializeChatShell()
      switchChatToVisitor({preserveInput:true})
      return visitorChatRequests
    }

    async function resumeAuthenticatedChat() {
      if (!services.auth.readToken()) {
        initVisitorChat()
        return
      }
      const user=currentChatUser()
      if (chatResumePromise && chatResumeUser===user) return chatResumePromise
      chatResumeUser=user
      const promise = (async function () {
        initializeChatShell()
        chatAuthMode = 'authenticated'
        resetPrivateChatUi({ preserveInput: true })
        const epoch=chatUiEpoch
        loadDraft()
        const timingResponse=await request('GET','/api/chat/client-timing',undefined,chatSilentAuthOptions())
        if (!isChatAuthenticated() || currentChatUser()!==user || epoch!==chatUiEpoch || timingResponse.code!==0 || !timingResponse.data) return
        chatTiming=Object.freeze(timingResponse.data);chatTimingReady=true
        chatSubmissions.configure(chatTiming)
        chatSubmissions.restore(currentChatUser())

        await Promise.all([loadChatFeedBadge(), loadTimeline(true)])
        if (!isChatAuthenticated() || currentChatUser()!==user || epoch!==chatUiEpoch) return

        // Re-read only as many historical pages as this entry previously displayed.
        // A deleted anchor falls back safely without walking the entire conversation.
        const savedPages=pageContext.state?.anchor?.pages
        const anchor=pageContext.state?.scroll?.anchor
        while(Number.isSafeInteger(savedPages)&&timelinePages<savedPages&&!noMoreTimeline&&!restoreSuppressed&&pageContext.valid()) {
          if(anchor&&findChatMessageRow(anchor.source,anchor.id))break
          const before=timelineCursor
          await loadTimeline(false)
          if(timelineCursor===before)break
        }
        if(!pageContext.valid())return

        await loadAgentTip()
        if (!isChatAuthenticated() || currentChatUser()!==user || epoch!==chatUiEpoch) return

        syncChatBottomPadding()
        if(!pageContext.state?.scroll)scrollToBottom()

        // 用最新 AI 消息的情绪初始化头像
        const aiMessages = root.querySelectorAll('.msg-row.ai')
        if (aiMessages.length > 0) {
          const lastAiRow = aiMessages[aiMessages.length - 1]
          const emotionAttr = lastAiRow.getAttribute('data-emotion')
          updateChatBackgroundEmotion(emotionAttr || '平静')
        } else {
          updateChatBackgroundEmotion('平静')
        }

        setupScrollObserver()
        if(pageContext.valid()&&!restoreSuppressed&&pageContext.state?.scroll)await services.history.restore(pageContext.router.current)
      })()

      chatResumePromise=promise
      try {
        await promise
      } finally {
        if(chatResumePromise===promise)chatResumePromise=null
      }
    }

    function initChat() {
      if (chatAuthMode === 'authenticated') {
        return resumeAuthenticatedChat()
      } else {
        initVisitorChat()
      }
    }

    async function recoverChatObservation() {
      if (!isChatAuthenticated() || document.visibilityState!=='visible' || !navigator.onLine) return
      if (!chatTimingReady || chatSubmissions.user!==currentChatUser()) {
        // Same-account resume promises coalesce preparation; restore keeps the saved timestamps/windows.
        await resumeAuthenticatedChat()
        return
      }
      loadChatFeedBadge();chatSubmissions.wake(true);refreshChatResendEligibility()
    }

    listen(window,'offline',stopChatObservation)
    listen(window,'online',()=>run(recoverChatObservation()))

  const input=byId('msg-input');if(typeof pageContext.state?.draft==='string')input.value=pageContext.state.draft;
  const inputChanged=()=>{autoResize(input);updateSendBtn();saveDraft()};
  listen(input,'input',inputChanged);
  listen(input,'compositionstart',()=>{inputComposing=true});
  listen(input,'compositionend',()=>{inputComposing=false;inputChanged()});
  listen(input,'keyup',updateSendBtn);listen(input,'keydown',handleEnterKey);
  listen(root,'click',event=>{const button=event.target.closest('[data-chat-action]');if(!button)return;
    const action=button.dataset.chatAction;
    if(action==='back')pageContext.router.back();
    else if(action==='feed')goChatFeed();else if(action==='memory')goChatProtected('/pages/memory.html');else if(action==='send')run(handleSend());
  });
  listen(root,'error',event=>{const image=event.target;if(image.tagName!=='IMG'||image.dataset.fallbackDone)return;
    image.dataset.fallbackDone='1';const fallback=image.closest('.user')?USER_AVATAR_FALLBACK:'/static/images/avatar/default.png';
    if(new URL(image.src,location.href).pathname!==fallback)image.src=fallback;
  },true);
  pageContext.cleanup(()=>{stopChatObservation();chatUiEpoch++;chatSubmissions.detach();callCardRefresh.reset();chatScrollObserver?.disconnect();VoiceCallCards.destroy()},{priority:100});
  const audioPage=services.audio.attachPage(pageContext,'content');const bubble=BgmBubble.mount(audioPage);if(bubble)pageContext.cleanup(()=>bubble.destroy());
  run(initChat());autoResize(input);updateSendBtn();
  return{unmount(){},captureState:()=>({draft:input.value,anchor:{pages:timelinePages},submissionKeys:[...chatSubmissions.records.keys()]})};
}

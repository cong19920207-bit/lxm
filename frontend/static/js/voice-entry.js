/* Home call entry with M3 PCM transport and renderer acknowledgements. */
(() => {
  'use strict';
  const messages = {
    microphone_denied: ['还听不见你的声音', '允许麦克风后，才能继续和她通话。'],
    browser_unsupported: ['换个浏览器，再和她说话', '请使用 Safari 或 Chrome 打开本页，再试一次。'],
    quota_empty: ['今天先聊到这里', '今天能聊的时间用完啦，之后再来找她吧。'],
    user_banned: ['暂时无法发起通话', '当前账号暂时无法使用语音通话。'],
    not_allowlisted: ['语音通话暂未开放', '这项功能还在逐步准备中，先回聊天找她吧。'],
    disabled: ['语音通话暂未开放', '这项功能还在逐步准备中，先回聊天找她吧。'],
    soft_stop: ['暂时无法接通', '通话服务暂时休息一下，请稍后再试。'],
    maintenance: ['暂时无法接通', '通话服务正在维护，请稍后再试。'],
    capacity_full: ['现在有点忙', '请稍后再试。'],
    user_busy: ['你已有一通进行中的通话', '请先结束原来的通话。'],
    dial_cooldown: ['稍等一下', '上一通刚结束，请稍后再试。'],
    provider_unavailable: ['暂时无法接通', '通话服务暂时不可用，请稍后再试。'],
    crisis_config_unavailable: ['暂时无法接通', '通话服务正在准备中，请稍后再试，或先回聊天找她。'],
    network: ['暂时没有收到结果', '可以重新检查，本次请求会沿用原来的编号。'],
    default: ['暂时无法接通', '请稍后再试，或先回聊天找她。'],
  };
  let panel, title, description, primary, secondary, closeButton, guide, clockLabel, controls, muteButton, outputButton, hangupButton;
  let attempt = null, stream = null, socket = null, heartbeat = null, audio = null;
  let busy = false, closed = true, callId = null, seq = 0, returnFocus = null;
  let hasConnected = false, reconnecting = false, reconnectWindowMs = 0, reconnectDeadline = null, recoveryRun = null;
  let callFinished = false, endingRequest = false, cleanupUnconfirmed = false, visibleCallState = '';
  let crisisBanner, crisisRequest = 0;
  let permissionRun = null, returningToChat = false;
  let terminalResultRun = null;
  function clearCrisis() {
    crisisRequest++;
    if (crisisBanner) { crisisBanner.textContent = ''; crisisBanner.hidden = true; }
    panel?.classList.remove('has-crisis');
  }
  function showCrisis(text) {
    crisisBanner.textContent = text; crisisBanner.hidden = !text;
    panel.classList.toggle('has-crisis', !!text);
  }
  async function refreshCrisis() {
    const id = callId, request = ++crisisRequest;
    try {
      const result = await http('/api/voice/calls/' + id, {cache:'no-store'});
      if (closed || callFinished || callId !== id || request !== crisisRequest) return;
      const crisis = result.body.data?.crisis;
      const visible = result.response.ok && crisis && Date.parse(crisis.expires_at) > Date.now() && typeof crisis.banner === 'string';
      showCrisis(visible ? crisis.banner : '');
    } catch (_) { /* Keep an already verified banner during a transient reconnect. */ }
  }
  const api = () => {
    // 语音默认跟随同域入口；分端口开发可显式设置 VOICE_API_BASE。
    if (typeof window.VOICE_API_BASE === 'string') return window.VOICE_API_BASE;
    const base = typeof API_BASE === 'string' ? API_BASE : '';
    return location.hostname === 'localhost' && base === 'http://localhost:8000' ? '' : base;
  };
  const releaseMic = () => { stream?.getTracks().forEach(track => track.stop()); stream = null; const previous = audio; audio = null; previous?.close().catch(() => {}); };
  const sendFrame = frame => {
    if (!socket || socket.readyState !== window.WebSocket?.OPEN) throw new Error('通话连接已断开');
    socket.send(JSON.stringify({...frame, v: 1, seq: ++seq}));
  };
  const send = type => { try { sendFrame({type}); } catch (_) {} };
  function elements() {
    if (panel) return;
    panel = document.createElement('section');
    panel.className = 'voice-entry'; panel.hidden = true;
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'voice-entry-title');
    panel.innerHTML = `<button class="voice-entry-close" type="button" aria-label="关闭通话">×</button>
      <time class="voice-call-clock" hidden aria-label="已通话">00:00</time>
      <div class="voice-entry-card"><p class="voice-entry-label">林小梦 · 语音通话</p>
      <h1 id="voice-entry-title"></h1><p class="voice-entry-description" aria-live="polite"></p>
      <div class="voice-entry-guide" hidden>在浏览器的网站权限中允许麦克风。如果系统权限也被关闭，请在系统设置中允许浏览器访问麦克风，然后回来重新检测。</div>
      <button class="voice-entry-primary" type="button"></button><button class="voice-entry-secondary" type="button"></button></div>
      <div class="voice-call-controls" hidden role="group" aria-label="通话控制">
        <button class="voice-call-mute" type="button" aria-pressed="false"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-3.1A7 7 0 0 0 19 11h-2Z"/></svg></span><b>静音</b></button>
        <button class="voice-call-hangup" type="button"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08c-.18-.17-.29-.42-.29-.7 0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28-.79-.74-1.69-1.36-2.67-1.85-.33-.16-.56-.5-.56-.9v-3.1C15.15 9.25 13.6 9 12 9Z"/></svg></span><b>挂断</b></button>
        <button class="voice-call-output" type="button" aria-pressed="false"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10v4h2.2L9 18V6L5.2 10H3Zm10 2a3 3 0 0 0-1.7-2.7v5.4A3 3 0 0 0 13 12Zm-1.7-7v1.7A6.3 6.3 0 0 1 16.5 12a6.3 6.3 0 0 1-5.2 6.3V20A8 8 0 0 0 18.2 12a8 8 0 0 0-6.9-7Z"/></svg></span><b>扬声器</b></button>
      </div>`;
    document.body.appendChild(panel);
    crisisBanner = document.createElement('p');
    crisisBanner.className = 'voice-crisis-banner'; crisisBanner.hidden = true;
    crisisBanner.setAttribute('role', 'status'); panel.appendChild(crisisBanner);
    new ResizeObserver(() => panel.style.setProperty('--voice-crisis-height', crisisBanner.getBoundingClientRect().height + 'px')).observe(crisisBanner);
    title = panel.querySelector('h1'); description = panel.querySelector('.voice-entry-description');
    primary = panel.querySelector('.voice-entry-primary'); secondary = panel.querySelector('.voice-entry-secondary');
    closeButton = panel.querySelector('.voice-entry-close'); guide = panel.querySelector('.voice-entry-guide');
    clockLabel = panel.querySelector('.voice-call-clock'); controls = panel.querySelector('.voice-call-controls');
    muteButton = panel.querySelector('.voice-call-mute'); outputButton = panel.querySelector('.voice-call-output');
    hangupButton = panel.querySelector('.voice-call-hangup');
    closeButton.onclick = () => hasConnected && !callFinished && !closed ? hangup() : close();
    hangupButton.onclick = hangup;
    muteButton.onclick = () => {
      if (endingRequest || !audio) return;
      try {
        const muted = audio.setMuted(!audio.muted);
        muteButton.setAttribute('aria-pressed', String(muted));
        muteButton.querySelector('b').textContent = muted ? '已静音' : '静音';
      } catch (_) { description.textContent = '麦克风未能切换，请检查设备权限。'; }
    };
    outputButton.onclick = async () => {
      if (endingRequest || !audio) return;
      outputButton.disabled = true;
      try {
        const label = await audio.selectOutput();
        if (closed || callFinished) return;
        outputButton.setAttribute('aria-pressed', 'true');
        outputButton.querySelector('b').textContent = label;
      } catch (_) { if (!closed) description.textContent = '音频输出未改变，可通过设备切换。'; }
      finally { if (!closed) outputButton.disabled = !audio?.supportsOutputSelection(); }
    };
    panel.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); closeButton.onclick(); }
      if (event.key === 'Tab') {
        const buttons = [...panel.querySelectorAll('button')].filter(b => !b.hidden && !b.disabled && b.getClientRects().length > 0);
        const first = buttons[0], last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
  }
  function show(head, text, label, action, secondLabel = '暂时不用', secondAction = close) {
    if (returningToChat) return;
    elements(); panel.hidden = false; panel.classList.remove('is-in-call'); controls.hidden = true; clockLabel.hidden = true;
    title.textContent = head; description.textContent = text;
    guide.hidden = true; primary.textContent = label; primary.onclick = action;
    primary.hidden = !label; primary.disabled = !action; primary.removeAttribute('aria-busy');
    secondary.disabled = false; closeButton.disabled = false;
    secondary.textContent = secondLabel; secondary.onclick = secondAction; secondary.hidden = !secondLabel;
  }
  function blocked(reason) {
    busy = false; releaseMic();
    const copy = messages[reason] || messages.default;
    if (reason === 'microphone_denied') {
      show(...copy, '查看开启方法', () => { guide.hidden = false; primary.textContent = '重新检测'; primary.onclick = begin; });
    } else if (reason === 'browser_unsupported') {
      show(...copy, '回聊天找她', returnToChat);
    } else if (reason === 'quota_empty') {
      show(...copy, '回聊天找她', returnToChat, '稍后再说', close);
    } else {
      show(...copy, reason === 'network' ? '重新检查' : '稍后重试', begin, '回聊天找她', returnToChat);
    }
  }
  async function http(path, options = {}, isCurrent = null) {
    const response = await fetch(api() + path, {...options, headers: {'Content-Type':'application/json',
      'Authorization':'Bearer ' + (localStorage.getItem('token') || ''), ...options.headers}});
    const body = await response.json();
    // A late result must not close a newer call or reopen its login modal.
    if (isCurrent && !isCurrent()) return {response, body};
    if (response.status === 401) {
      if (body.detail === '账号已被禁用') {
        return {response, body:{code:401,data:{block_reason:'user_banned'}}};
      }
      close(); if (typeof openHomeLoginModal === 'function') openHomeLoginModal();
      throw Object.assign(new Error('unauthorized'), {unauthorized: true});
    }
    return {response, body};
  }
  async function endKnownCall(id) {
    if (!id) return;
    const result = await http('/api/voice/calls/' + id + '/end', {method:'POST'});
    if (!result.response.ok || result.body.code !== 0 || result.body.data?.cleanup_pending !== false) throw new Error('结束待确认');
  }
  function resolveKnownCall(canReconnect = false) {
    const id = callId, current = socket;
    const isCurrent = () => !closed && socket === current && callId === id;
    const finalStates = ['ended', 'failed', 'missed', 'cancelled'];
    let checking = false, cleanupRequested = false;
    busy = true;
    const readStatus = async () => {
      const result = await http('/api/voice/calls/' + id, {cache: 'no-store'});
      if (!result.response.ok || result.body.code !== 0 || !result.body.data) throw new Error('结果待确认');
      return result.body.data;
    };
    const check = async () => {
      if (checking || !isCurrent()) return;
      checking = true;
      try {
        let data = await readStatus();
        if (!isCurrent()) return;
        // The conditional endpoint locks and refuses a call that has connected
        // since this read. Never turn a stale startup cancellation into hangup.
        if (['deciding', 'ringing'].includes(data.status) ||
            (cleanupRequested && !data.has_connected && finalStates.includes(data.status))) {
          cleanupRequested = true;
          const ended = await http('/api/voice/calls/' + id + '/end?only_if_unconnected=true', {method: 'POST'});
          if (!isCurrent()) return;
          if (!ended.response.ok || ended.body.code !== 0 || ended.body.data?.cleanup_pending !== false) throw new Error('结束待确认');
          data = await readStatus();
          if (!isCurrent()) return;
        }
        if (finalStates.includes(data.status)) {
          if (cleanupRequested && data.status === 'cancelled') {
            releaseMic(); callFinished = true; busy = false; attempt = null; socket = null; callId = null;
            show('暂时无法接通', '通话连接未能建立，请稍后重试。', '重新尝试', begin, '返回聊天', returnToChat);
          } else renderResult(data);
          return;
        }
        // A replay may resume only through the existing device-bound reconnect
        // endpoint. Connected/ending calls are checked, never silently ended.
        if (canReconnect && data.status === 'reconnecting' && audio && stream) {
          const restored = await http('/api/voice/calls/' + id + '/reconnect', {
            method: 'POST', body: JSON.stringify({device_id: attempt.payload.device_id})});
          if (!isCurrent()) return;
          if (restored.response.ok && restored.body.code === 0 && restored.body.data?.call_ticket) {
            connect(restored.body.data, true); return;
          }
        }
        releaseMic();
        show('正在确认原来的通话', '原来的通话仍在处理中，请稍后重新检查。', '重新检查', check, '返回聊天', returnToChat);
      } catch (_) {
        if (isCurrent()) {
          releaseMic();
          show('正在确认通话结果', '暂时无法确认结果，请稍后重新检查。', '重新检查', check, '返回聊天', returnToChat);
        }
      } finally { checking = false; }
    };
    return check();
  }
  function connect(call, restoring = false) {
    callId = call.call_id;
    if (!call.call_ticket) return resolveKnownCall(true);
    const url = new URL(api() || location.origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/api/voice/calls/' + callId + (restoring ? '/reconnect-stream' : '/stream'); url.search = ''; url.hash = '';
    const current = new WebSocket(url, ['voice.v1', 'ticket.' + call.call_ticket, 'device.' + attempt.payload.device_id]);
    let terminal = false;
    socket = current; seq = 0;
    current.onopen = () => {
      if (closed || socket !== current) { current.close(); return; }
      heartbeat = setInterval(() => send('heartbeat'), 1000);
    };
    let incoming = Promise.resolve();
    current.onmessage = event => { incoming = incoming.then(async () => {
      if (closed || socket !== current) return;
      let frame; try { frame = JSON.parse(event.data); } catch (_) { return; }
      if (frame.v !== 1) return;
      if (cleanupUnconfirmed) return;
      if (frame.type !== 'state') {
        if (frame.type === 'crisis_detected' && frame.call_id === callId) {
          if (typeof frame.banner === 'string' && frame.banner.trim()) { crisisRequest++; showCrisis(frame.banner); }
          else refreshCrisis();
          return;
        }
        audio?.frame(frame);
        if (frame.type === 'clock' && Number.isInteger(frame.duration_seconds) && frame.duration_seconds >= 0) clockLabel.textContent = formatDuration(frame.duration_seconds);
        if (frame.type === 'stop_playback') renderCallState('listening');
        if (frame.type === 'provider_event' && frame.metadata.kind === 'asr_final' && !audio?.isPlaying()) renderCallState('thinking');
        return;
      }
      if (frame.status === 'deciding') show('正在呼叫林小梦', '正在等待回应…', '取消', close, '');
      if (frame.status === 'ringing') {
        if (frame.phase === 'connecting') show('林小梦', '正在接通', '取消', close, '');
        else show('正在等待她接听', '稍等，她正在准备接听。', '取消', close, '');
      }
      if (frame.status === 'reconnecting') { audio?.pause(); renderCallState('reconnecting'); }
      if (frame.status === 'connected') {
        hasConnected = true;
        reconnectWindowMs = frame.reconnect_timeout_ms;
        reconnectDeadline = null;
        await audio.start(callId, stream);
        audio.resumeTransport();
        if (closed || socket !== current) return;
        renderCallState('listening');
        refreshCrisis();
        window.dispatchEvent(new CustomEvent('voice:connected', {detail:{callId, stream}}));
      }
      if (['failed','missed','cancelled','ended'].includes(frame.status)) {
        terminal = true;
        if (frame.status === 'cancelled') close();
        else await resolveTerminalResult(callId, attempt);
      }
    }).catch(() => { if (!closed && socket === current) { close(); blocked('browser_unsupported'); } }); };
    current.onclose = () => {
      if (socket !== current) return;
      clearInterval(heartbeat);
      if (endingRequest || cleanupUnconfirmed || callFinished) return;
      if (!closed && !terminal && hasConnected) { recover(); return; }
      releaseMic();
      if (!closed && socket === current && !terminal) {
        resolveKnownCall();
      } else { busy = false; attempt = null; }
    };
  }
  function formatDuration(seconds) {
    seconds = Number.isInteger(seconds) && seconds >= 0 ? seconds : 0;
    return String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
  }
  function renderCallState(state) {
    if (closed || callFinished || !hasConnected || endingRequest) return;
    if (visibleCallState === state && panel.classList.contains('is-in-call')) return;
    const moveFocus = state === 'reconnecting' && [muteButton, outputButton].includes(document.activeElement);
    visibleCallState = state;
    panel.classList.add('is-in-call'); panel.dataset.callState = state;
    title.textContent = '林小梦';
    description.textContent = {listening:'在听',thinking:'想一下',speaking:'正在说',reconnecting:'正在重新连接…'}[state] || '在听';
    primary.hidden = true; secondary.hidden = true; controls.hidden = false; clockLabel.hidden = false;
    muteButton.hidden = state === 'reconnecting'; outputButton.hidden = state === 'reconnecting';
    muteButton.disabled = !audio || !audio.track || audio.track.readyState !== 'live';
    outputButton.disabled = !audio?.supportsOutputSelection();
    outputButton.title = outputButton.disabled ? '当前浏览器的音频输出由设备控制' : '选择音频输出设备';
    if (outputButton.disabled) outputButton.querySelector('b').textContent = '设备控制';
    hangupButton.disabled = false;
    if (moveFocus) hangupButton.focus();
  }
  function renderResult(data) {
    if (closed || cleanupUnconfirmed) return;
    terminalResultRun = null;
    clearCrisis();
    callFinished = true; endingRequest = false;
    if (data.show_end_page === false || data.status === 'cancelled') { close(); return; }
    clearInterval(heartbeat); releaseMic();
    socket?.close(); socket = null; busy = false; attempt = null;
    const head = data.status === 'missed' ? '她这次没有接听' : data.has_connected ? '通话已结束' : '暂时无法接通';
    show(head, data.end_message || head, '返回聊天', returnToChat,
      data.status === 'failed' && !data.has_connected ? '重新尝试' : '', begin);
    if (data.has_connected) { clockLabel.hidden = false; clockLabel.textContent = formatDuration(data.duration_seconds); }
  }
  async function loadResult(id, isCurrent) {
    const pending = attempt;
    isCurrent = isCurrent || (() => !closed && callId === id && attempt === pending);
    if (!isCurrent()) return false;
    const result = await http('/api/voice/calls/' + id, {cache:'no-store'}, isCurrent);
    if (isCurrent() && result.response.ok && result.body?.code === 0 && result.body.data && ['ended','failed','missed','cancelled'].includes(result.body.data.status)) {
      renderResult(result.body.data); return true;
    }
    return false;
  }
  function resolveTerminalResult(id, pending) {
    if (closed || callId !== id || attempt !== pending || cleanupUnconfirmed) return;
    if (terminalResultRun) return terminalResultRun.check();
    const run = {}; terminalResultRun = run;
    const isCurrent = () => !closed && terminalResultRun === run && callId === id && attempt === pending;
    // The server has ended the call. Result reads must never redial or retry end.
    callFinished = true; endingRequest = false; busy = true;
    recoveryRun = null; reconnecting = false;
    clearCrisis(); clearInterval(heartbeat); releaseMic();
    const previous = socket; socket = null; previous?.close();
    let checking = false;
    const check = async () => {
      if (checking || !isCurrent()) return;
      checking = true;
      show('正在确认通话结果', '正在获取本次通话的结果…', '重新检查', check, '返回聊天', returnToChat);
      primary.disabled = true; primary.setAttribute('aria-busy', 'true');
      try {
        if (await loadResult(id, isCurrent)) return;
      } catch (_) { /* Network/data failures stay in this call's result flow. */ }
      finally { checking = false; }
      if (isCurrent()) {
        show('正在确认通话结果', '暂时无法确认结果，请稍后重新检查。', '重新检查', check, '返回聊天', returnToChat);
      }
    };
    run.check = check;
    return check();
  }
  async function hangup() {
    if (closed || endingRequest || callFinished) return;
    endingRequest = true; cleanupUnconfirmed = true; busy = true;
    recoveryRun = null; reconnecting = false;
    hangupButton.disabled = true; muteButton.disabled = true; outputButton.disabled = true;
    description.textContent = '正在结束通话…';
    const id = callId; send('cancel'); releaseMic();
    try {
      await endKnownCall(id);
      if (!closed && callId === id) cleanupUnconfirmed = false;
      if (!closed && callId === id && !await loadResult(id)) throw new Error('结果待确认');
    } catch (_) {
      if (!closed && callId === id) {
        endingRequest = false;
        show('正在确认通话结果', '暂时无法获取结果，请恢复网络后再查看。', '重新检查', () => hangup(), '返回聊天', returnToChat);
      }
    }
  }
  async function recover() {
    if (closed || reconnecting) return;
    const run = {}; recoveryRun = run;
    const recoveringId = callId, recoveringAttempt = attempt;
    const isCurrent = () => !closed && recoveryRun === run && callId === recoveringId && attempt === recoveringAttempt;
    reconnecting = true; audio?.pause();
    renderCallState('reconnecting');
    if (reconnectDeadline === null) reconnectDeadline = performance.now() + reconnectWindowMs;
    try {
      while (isCurrent() && performance.now() < reconnectDeadline) {
        try {
          const result = await http('/api/voice/calls/' + callId + '/reconnect', {
            method:'POST', body:JSON.stringify({device_id:attempt.payload.device_id})});
          if (!isCurrent()) return;
          if (result.response.ok && result.body.code === 0) { connect(result.body.data, true); return; }
          const status = await http('/api/voice/calls/' + callId);
          if (!isCurrent()) return;
          if (status.body.data && ['ended','failed','cancelled','missed'].includes(status.body.data.status)) {
            renderResult(status.body.data);
            return;
          }
        } catch (_) { if (!isCurrent()) return; }
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      if (isCurrent()) {
        releaseMic(); busy = false;
        show('连接已中断', '暂时无法获取通话结果，请恢复网络后查看。', '回聊天找她', returnToChat);
      }
    } finally { if (recoveryRun === run) reconnecting = false; }
  }
  async function begin() {
    if (returningToChat) return;
    if (busy) return;
    elements(); closed = false; busy = true; hasConnected = false; callFinished = false; endingRequest = false; cleanupUnconfirmed = false; visibleCallState = ''; reconnectDeadline = null; returnFocus = document.activeElement;
    clockLabel.textContent = '00:00';
    muteButton.setAttribute('aria-pressed', 'false'); muteButton.querySelector('b').textContent = '静音';
    outputButton.setAttribute('aria-pressed', 'false'); outputButton.querySelector('b').textContent = '扬声器';
    show('准备通话', '正在检查麦克风权限…', '', null); closeButton.focus();
    if (/MicroMessenger/i.test(navigator.userAgent) || !window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.WebSocket || !window.crypto?.randomUUID || !(window.AudioContext || window.webkitAudioContext) || !window.VoiceAudioTransport || !window.AudioWorkletNode) {
      blocked('browser_unsupported'); return;
    }
    const run = {}; permissionRun = run;
    let permission = 'prompt';
    try { permission = (await navigator.permissions?.query({name:'microphone'}))?.state || 'prompt'; }
    catch (_) { /* An unavailable Permissions API still needs the purpose explanation. */ }
    if (closed || permissionRun !== run) return;
    if (permission === 'granted') { permissionRun = null; return prepareCall(); }
    if (permission === 'denied') { permissionRun = null; blocked('microphone_denied'); return; }
    show('打开麦克风，她才能听见你', '麦克风仅在通话中启用。通话会生成文字记录和摘要，用来延续聊天。', '允许麦克风', () => {
      if (closed || permissionRun !== run) return;
      permissionRun = null;
      show('准备通话', '正在请求麦克风权限…', '', null);
      prepareCall();
    }, '先不打了', close);
  }
  async function prepareCall() {
    try {
      const context = new (window.AudioContext || window.webkitAudioContext)();
      if (!context.audioWorklet || !window.VoiceAudioTransport || !window.AudioWorkletNode) {
        await context.close(); blocked('browser_unsupported'); return;
      }
      audio = new window.VoiceAudioTransport({context, send:sendFrame, onState:renderCallState});
      await context.resume();
      stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:true}, video: false});
      if (closed) { releaseMic(); busy = false; return; }
    } catch (_) { if (!closed) blocked('microphone_denied'); else busy = false; return; }
    if (!attempt) {
      let device = localStorage.getItem('voice_device_id');
      if (!device || !/^[0-9a-f-]{36}$/.test(device)) { device = crypto.randomUUID(); localStorage.setItem('voice_device_id', device); }
      attempt = {key:crypto.randomUUID(), payload:{source:'home',device_id:device,browser_supported:true,microphone_granted:true}};
    }
    const pending = attempt;
    show('正在呼叫林小梦', '正在连接…', '取消', close, '');
    try {
      const {response,body} = await http('/api/voice/calls', {method:'POST',headers:{'Idempotency-Key':pending.key},body:JSON.stringify(pending.payload)});
      if (closed) {
        if (body.data?.call_id) await endKnownCall(body.data.call_id).catch(() => {});
        if (attempt === pending) attempt = null;
        return;
      }
      if (!response.ok || body.code !== 0) { attempt = null; blocked(body.data?.block_reason || 'default'); return; }
      await connect(body.data);
    } catch (error) { if (!closed && !error.unauthorized) blocked('network'); }
    finally { if (closed) busy = false; }
  }
  function returnToChat() {
    if (returningToChat) return;
    close();
    returningToChat = true;
    // Keep feedback visible while navigation is pending; all resources are released.
    panel.hidden = false;
    primary.textContent = '正在返回聊天…';
    primary.setAttribute('aria-busy', 'true');
    primary.disabled = secondary.disabled = closeButton.disabled = true;
    location.href = '/pages/chat.html';
  }
  window.addEventListener('pageshow', event => {
    if (event.persisted && returningToChat) {
      returningToChat = false;
      if (panel) panel.hidden = true;
    }
  });
  function close() {
    if (returningToChat) return;
    if (permissionRun) { permissionRun = null; busy = false; }
    terminalResultRun = null; clearCrisis();
    closed = true; recoveryRun = null; reconnecting = false; clearInterval(heartbeat); send('cancel'); socket?.close(); socket = null;
    releaseMic(); const id = callId; callId = null;
    if (panel) panel.hidden = true;
    if (id) {
      if (!callFinished) endKnownCall(id).catch(() => {});
      attempt = null; busy = false;
    }
    // Pending create resolves to its original call and cancels it; no new key/retry.
    returnFocus?.focus?.();
  }
  window.addEventListener('pagehide', () => {
    if (permissionRun) { permissionRun = null; busy = false; if (panel) panel.hidden = true; }
    terminalResultRun = null; clearCrisis(); closed = true; clearInterval(heartbeat); socket?.close(); releaseMic();
  });
  window.VoiceEntry = Object.freeze({begin});
})();

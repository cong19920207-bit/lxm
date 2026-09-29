(function (root) {
  'use strict';
  var resourceFetcher = null, resourceGeneration = 0;
  function appendResource(row, crisis) {
    if (!crisis || typeof crisis.resource !== 'string' || !(Date.parse(crisis.expires_at) > Date.now())) return;
    var resource = document.createElement('aside');
    resource.className = 'voice-crisis-resource'; resource.textContent = crisis.resource;
    resource.dataset.expiresAt = crisis.expires_at; row.appendChild(resource);
  }
  function render(item, timestamp, createdTimestamp = timestamp) {
    var row = document.createElement('div');
    row.className = 'msg-row voice-call-row';
    row.dataset.callId = item.call_id;
    row.setAttribute('data-created-at', String(timestamp));
    var ready = item.call_status !== 'missed' && item.summary_status === 'ready' && typeof item.call_summary === 'string' && item.call_summary.trim();
    var card = document.createElement(ready ? 'button' : 'article');
    if (ready) card.type = 'button';
    card.className = 'voice-call-card' + (item.call_status === 'missed' ? ' is-missed' : '');
    var title = document.createElement('span');
    title.className = 'voice-call-title';
    var seconds = Math.max(0, Math.floor(Number(item.duration_seconds) || 0));
    title.textContent = item.call_status === 'missed' ? '语音通话 · 未接听' :
      '语音通话 · ' + String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
    card.appendChild(title);
    if (item.call_status === 'missed' && typeof createdTimestamp === 'number' && Number.isFinite(createdTimestamp)) {
      var date = new Date(createdTimestamp);
      if (Number.isFinite(date.getTime())) {
        var time = document.createElement('time');
        time.className = 'voice-call-created'; time.dateTime = date.toISOString();
        time.textContent = String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0');
        time.setAttribute('aria-label', '发起时间：' + date.toLocaleString('zh-CN'));
        card.appendChild(time);
      }
    }
    if (item.call_status !== 'missed') {
      if (item.summary_status === 'pending') {
        var description = document.createElement('span');
        description.className = 'voice-call-static'; description.textContent = '刚刚聊了一会儿';
        card.appendChild(description);
      }
      var summary = document.createElement('span');
      summary.className = 'voice-call-summary';
      summary.textContent = ready ? item.call_summary : item.summary_status === 'pending' ? '摘要整理中' : '刚刚聊了一会儿';
      if (ready) {
        var toggle = document.createElement('span');
        toggle.className = 'voice-call-expand';
        toggle.textContent = '展开摘要';
        toggle.setAttribute('aria-hidden', 'true');
        card.setAttribute('aria-expanded', 'false');
        card.addEventListener('click', function () {
          var expanded = card.getAttribute('aria-expanded') !== 'true';
          card.setAttribute('aria-expanded', String(expanded));
          toggle.textContent = expanded ? '收起摘要' : '展开摘要';
          summary.classList.toggle('is-expanded', expanded);
        });
        card.appendChild(summary);
        card.appendChild(toggle);
      } else {
        card.appendChild(summary);
      }
    }
    row.appendChild(card);
    appendResource(row, item.crisis_resource);
    return row;
  }
  function pendingRefresh(options) {
    var timer = null, used = false, generation = 0;
    return {
      observe: function (items, context) {
        if (used || timer !== null || !items.some(function (item) {
          return item.source === 'call' && item.summary_status === 'pending';
        })) return;
        var current = generation;
        timer = options.schedule(async function () {
          if (current !== generation) return;
          timer = null;
          used = true;
          if (current !== generation || !options.active()) return;
          try {
            var result = await options.fetch(context);
            if (current === generation && options.active()) options.update(result);
          } catch (_) { /* One bounded refresh; a failure never retries itself. */ }
        }, 3000);
      },
      reset: function () {
        generation += 1;
        if (timer !== null) options.cancel(timer);
        timer = null;
        used = false;
      }
    };
  }
  root.VoiceCallCards = { render: render, pendingRefresh: pendingRefresh,
    configureResourceRefresh: function (fetcher) { resourceFetcher = fetcher; } };
  function clearResources() {
    resourceGeneration++;
    document.querySelectorAll('.voice-crisis-resource').forEach(function (node) { node.remove(); });
  }
  async function refreshResources() {
    clearResources();
    if (!resourceFetcher || !navigator.onLine) return;
    var current = resourceGeneration;
    await Promise.all(Array.from(document.querySelectorAll('.voice-call-row')).map(async function (row) {
      try {
        var crisis = await resourceFetcher(row.dataset.callId);
        if (current === resourceGeneration && navigator.onLine && row.isConnected) appendResource(row, crisis);
      } catch (_) { /* An unavailable/deleted source never restores a cached card. */ }
    }));
  }
  root.addEventListener('pagehide', clearResources);
  root.addEventListener('offline', clearResources);
  root.addEventListener('online', refreshResources);
  root.addEventListener('pageshow', function (event) { if (event.persisted) refreshResources(); });
  root.setInterval(function () {
    document.querySelectorAll('.voice-crisis-resource').forEach(function (node) {
      if (Date.parse(node.dataset.expiresAt) <= Date.now()) node.remove();
    });
  }, 1000);
})(globalThis);

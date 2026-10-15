/* Owned receipts for existing source CRUD. Only unresolved identity/source lives
 * in sessionStorage; body and credentials stay in the current form only. */
(function () {
  'use strict';
  var storageKey = 'memory_write_unresolved', pending = {}, contexts = {}, clock = null;
  var panel;
  function saved() {
    try { return JSON.parse(sessionStorage.getItem(storageKey) || '[]').filter(function (x) {
      return x && typeof x.operation_id === 'string' && typeof x.source === 'string';
    }); } catch (e) { return []; }
  }
  saved().forEach(function (entry) { pending[entry.source] = entry.operation_id; contexts[entry.source] = {id:entry.operation_id, sequence:0}; });
  function persist() {
    var entries = Object.keys(pending).map(function (source) { return { operation_id: pending[source], source: source }; });
    if (entries.length) sessionStorage.setItem(storageKey, JSON.stringify(entries));
    else sessionStorage.removeItem(storageKey);
  }
  function uuid7(now) {
    var bytes = crypto.getRandomValues(new Uint8Array(16));
    for (var i = 5; i >= 0; i--) { bytes[i] = now % 256; now = Math.floor(now / 256); }
    bytes[6] = (bytes[6] & 15) | 112; bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.from(bytes).map(function (n) { return n.toString(16).padStart(2, '0'); }).join('');
    return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
  }
  function ensurePanel() {
    if (!panel) {
      panel = document.createElement('div'); panel.id = 'memory-write-results'; panel.setAttribute('aria-live','polite');
      panel.style.cssText = 'margin:12px 0;padding:12px;border:1px solid #faad14;background:#fffbe6;overflow-wrap:anywhere';
      var content = document.querySelector('.admin-content') || document.body; content.appendChild(panel);
    }
    return panel;
  }
  function display(data, source) {
    var box = ensurePanel(), old = Array.from(box.children).find(function (node) { return node.dataset.source === source; });
    var section = old || document.createElement('div'); section.dataset.source = source; section.replaceChildren();
    if (!old) box.appendChild(section);
    var result = data.write_result || {source_state:'unknown',index_state:'unknown'}, state = result.source_state;
    var message = document.createElement('div');
    if (data.source_counts) {
      var c = data.source_counts;
      message.textContent = '源结果：成功 '+c.succeeded+'，失败 '+c.failed+'，待核实 '+c.unknown+'，处理中 '+c.pending+'；唯一输入 '+(c.succeeded+c.failed+c.unknown+c.pending)+' 项。索引单独展示。';
    } else {
      message.textContent = state === 'succeeded' ? (result.index_state === 'ready' ? '源操作已成功，索引已就绪' : '记忆已保存，BM25索引待修复') :
        state === 'failed' ? '源操作失败，输入已保留，可修正后提交' :
        state === 'not_accepted' ? '本次请求未受理：服务器时间窗口拒绝，输入已保留，请校时后手动提交' :
        state === 'unavailable' ? '服务器校时不可用，暂不可提交；输入已保留，请稍后手动重试' : '源结果待核实，请勿再次提交；可关闭表单并只读核实';
      message.textContent += '（源：'+state+'；索引：'+result.index_state+'）';
    }
    section.appendChild(message);
    (data.items || []).forEach(function (item) {
      var line = document.createElement('div');
      line.textContent = item.requested_doc_id+' — 源：'+item.source_state+'；索引：'+item.index_state;
      section.appendChild(line);
    });
    if (result.operation_id) {
      var identity = document.createElement('small'); identity.textContent = '操作 '+result.operation_id+' · 核实 '+(result.observed_at || '待核实'); section.appendChild(identity);
    }
    if (result.maintenance_task_id && ['super_admin','ai_trainer','observer'].includes(getAdminRole())) {
      var link = document.createElement('a'); link.textContent = ' 查看索引维护';
      link.href = '/admin/pages/memory-index-maintenance.html?task_id='+encodeURIComponent(result.maintenance_task_id); section.appendChild(link);
    }
    if (state === 'unknown' || state === 'pending' || (data.source_counts && (data.source_counts.unknown || data.source_counts.pending))) {
      var button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-default'; button.textContent = '只读核实';
      var original = contexts[source], originalId = result.operation_id;
      button.onclick = function () { if (current(source, original) && original.id === originalId) observe(source, false, original); }; section.appendChild(button);
      var note = document.createElement('small'); note.textContent = ' 自动观察最多60秒，其后请手动核实'; section.appendChild(note);
    }
  }
  function unresolved(data) {
    return data.source_counts ? Boolean(data.source_counts.unknown || data.source_counts.pending) : ['unknown','pending'].includes(data.write_result.source_state);
  }
  function current(source, context) {
    return Boolean(context && contexts[source] === context && context.id && pending[source] === context.id);
  }
  function finish(source, context) {
    if (!current(source,context)) return;
    clearTimeout(context.timer); delete pending[source]; delete contexts[source]; persist();
  }
  function classify(response, operationId) {
    if (response && response.code === 20123) {
      if (response.message === 'operation_id_outside_window' && !response.data) {
        return {write_result:{operation_id:operationId,source_state:'not_accepted',index_state:'not_executed'}};
      }
      // An expired existing receipt cannot prove whether the source was saved.
      return {write_result:{operation_id:operationId,source_state:'unknown',index_state:'unknown'}};
    }
    if (response && response.data && response.data.write_result) return response.data;
    if (response && response.code !== 0 && ![20122,20125,20129].includes(response.code)) {
      return {write_result:{operation_id:operationId,source_state:'failed',index_state:'not_executed'}};
    }
    return {write_result:{operation_id:operationId,source_state:'unknown',index_state:'unknown'}};
  }
  function clockPath(path) {
    var match = path.match(/^\/api\/admin\/users\/\d+\/(user-memories|private-settings)/);
    return (match ? match[0] : path.includes('/memories/batch-delete') ? '/api/admin/memories/global' : '/api/admin/character-knowledge')+'?page=1&page_size=1';
  }
  async function calibrate(path) {
    var response = await adminRequest('GET',clockPath(path),null,false,
      {silentErrorToast:true,returnErrorResponse:true,timeoutMs:10000});
    var server = response && response.code === 0 && response.data && Date.parse(response.data.server_time);
    if (typeof server !== 'number' || !Number.isFinite(server)) return null;
    // Monotonic elapsed time avoids the client's wall-clock offset and jumps.
    clock = {server:server, received:performance.now()};
    return clock;
  }
  async function observe(source, automatic, context) {
    context = context || contexts[source]; if (!current(source,context)) return;
    var id = context.id, started = context.started || (context.started = performance.now());
    if (automatic && performance.now()-started >= 60000) return;
    clearTimeout(context.timer);
    var sequence = ++context.sequence;
    var response = await adminRequest('GET','/api/admin/memory-write-operations/'+encodeURIComponent(id),null,false,
      {silentErrorToast:true,returnErrorResponse:true,timeoutMs:automatic ? Math.min(10000,60000-(performance.now()-started)) : 10000});
    if (!current(source,context) || context.sequence !== sequence) return;
    // GET code0 means successful reading; only its source_state confirms writing.
    var data = response && response.code === 0 && response.data && response.data.write_result && response.data.write_result.receipt_state !== 'expired' ? response.data :
      {write_result:{operation_id:id,source_state:'unknown',index_state:'unknown'}};
    display(data,source);
    if (!unresolved(data)) {
      finish(source,context);
      if (context.complete) context.complete(data);
      return;
    }
    if (performance.now()-started < 60000) context.timer = setTimeout(function () {
      if (current(source,context) && context.sequence === sequence) observe(source,true,context);
    },5000);
  }
  async function submit(options) {
    var source = options.source || options.path, button = options.button;
    if (contexts[source]) {
      if (button) button.disabled = true;
      if (pending[source]) display({write_result:{operation_id:pending[source],source_state:'unknown',index_state:'unknown'}},source);
      return {state:pending[source] ? 'unknown' : 'calibrating'};
    }
    // Reserve this source even before its ID exists: a calibration await cannot
    // let two forms/double clicks allocate and send two distinct operations.
    var context = {id:null,sequence:0}; contexts[source] = context;
    if (button) button.disabled = true;
    var synchronized = await calibrate(options.path);
    if (contexts[source] !== context || pending[source]) return {state:'stale'};
    if (!synchronized) {
      delete contexts[source]; if (button && button.isConnected) button.disabled = false;
      var unavailable = {write_result:{source_state:'unavailable',index_state:'not_executed'}};
      display(unavailable,source); return {state:'unavailable',data:unavailable};
    }
    var id = uuid7(Math.floor(synchronized.server + performance.now()-synchronized.received));
    context.id = id; pending[source] = id; persist();
    context.complete = function (data) {
      if (button && button.isConnected) button.disabled = false;
      if (data.write_result.source_state === 'succeeded' && options.success) options.success(data);
    };
    var response = await adminRequest(options.method,options.path,options.body || null,false,
      {idempotencyKey:id,silentErrorToast:true,returnErrorResponse:true,timeoutMs:15000});
    if (!current(source,context)) return {state:'stale'};
    var data = classify(response,id); display(data,source);
    if (unresolved(data)) {
      if (data.source_counts && data.source_counts.succeeded && options.partialSuccess) options.partialSuccess(data);
      if (current(source,context)) observe(source,true,context);
      return {state:'unknown',data:data};
    }
    finish(source,context); context.complete(data);
    return {state:data.write_result.source_state,data:data};
  }
  function start() {
    Object.keys(pending).forEach(function (source) {
      var page = location.pathname, matches = page.includes('knowledge') ? source.includes('character-knowledge') :
        page.includes('user-detail') ? source.includes('/users/'+new URLSearchParams(location.search).get('id')+'/') : source.includes('/memories/batch-delete');
      if (matches) { display({write_result:{operation_id:pending[source],source_state:'unknown',index_state:'unknown'}},source); observe(source,true,contexts[source]); }
    });
  }
  window.MemoryWriteFeedback = {submit:submit,blocked:function (source) {return Boolean(contexts[source]);},start:start};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start); else start();
})();

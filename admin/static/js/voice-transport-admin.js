/* Reads the runtime trust snapshot and probes the actual /api/voice/ ingress. */
(function () {
  'use strict';
  if (!checkAdminLogin()) return;
  var writable = ['super_admin', 'tech_ops'].indexOf(getAdminRole()) >= 0;
  var data = null, active = false, serial = 0, socket = null, localFailure = '';
  var base = '/api/admin/voice/master-switch/diagnostics';
  var refreshButton = document.getElementById('btn-voice-diag-refresh');
  var testButton = document.getElementById('btn-voice-diag-test');
  document.getElementById('voice-diag-role').hidden = writable;
  function text(id, value, health) {
    var el = document.getElementById(id); el.textContent = value; el.dataset.health = health || '';
  }
  function time(value) { return value ? new Date(value).toLocaleString() : '尚无记录'; }
  function reason(code) {
    return ({socket_origin_or_url_rejected:'来源或转发协议校验未通过。请检查同域入口、Nginx 的 Host / X-Forwarded-Proto 和当前代理信任地址。',
      wss_required:'服务端未识别到安全连接。请检查 HTTPS 入口及 Nginx 的协议转发。',
      diagnostic_connection_failed:'消息往返未完成。请检查网络、WebSocket 转发和诊断存储后重试。',
      diagnostic_ack_invalid:'浏览器未返回有效确认，请刷新页面后重试。'})[code] || '连接检测未通过，请查看代理状态及通话指标。';
  }
  function render() {
    refreshButton.disabled = active; testButton.disabled = active || !writable;
    testButton.textContent = active ? '检测中…' : '重新检测';
    var proxy = data && data.proxy, last = data && data.last_probe;
    var proxyAge = proxy && proxy.checked_at ? Date.now() - Date.parse(proxy.checked_at) : Infinity;
    var ready = proxy && proxy.status === 'ready' && proxyAge < proxy.refresh_seconds * 2000;
    text('voice-diag-proxy', !proxy ? '状态不可用' : ready ? '正常 · 自动更新已启用' : proxy.status === 'error'
      ? '解析失败 · 请检查 Docker 网络及 nginx 服务' : '尚未获取或状态已过期，请刷新', ready ? 'ready' : proxy && proxy.status === 'error' ? 'error' : '');
    text('voice-diag-addresses', proxy ? '发现：' + (proxy.discovered_addresses.join('、') || '无') + '；生效：' +
      (proxy.trusted_addresses.join('、') || '无') + '；实例 ' + proxy.instance + ' / 版本 ' + proxy.generation +
      (proxyAge >= proxy.refresh_seconds * 2000 ? '（历史快照，请刷新）' : '') : '未知');
    var age = last && last.checked_at ? Date.now() - Date.parse(last.checked_at) : Infinity;
    var sameRuntime = last && last.proxy && proxy && last.proxy.instance === proxy.instance && last.proxy.generation === proxy.generation;
    var stale = age > ((data && data.probe_valid_seconds) || 60) * 1000 || (last && last.status === 'passed' && !sameRuntime);
    var link = '尚未检测', health = '', hint = '';
    if (active) link = '正在检测当前浏览器连接…';
    else if (localFailure) { link = '本次检测未完成'; hint = localFailure; health = 'error'; }
    else if (!data) { link = '诊断状态不可用'; hint = '无法读取诊断接口，请检查后台服务及网络后刷新。'; health = 'error'; }
    else if (data.probe_storage === 'unavailable') { link = '诊断记录不可用'; hint = '无法读取诊断存储，请检查 Redis 后重新检测。'; health = 'error'; }
    else if (last && stale) { link = '检测记录已过期或运行实例已变化，请重新检测'; }
    else if (last && last.status === 'passed') {
      link = last.local_insecure ? '本地 HTTP 开发链路通过（未验证 HTTPS）' : 'HTTPS / WebSocket 握手及消息往返通过';
      health = last.local_insecure ? '' : 'ready';
    } else if (last && last.status === 'failed') { link = '连接检测失败'; hint = reason(last.reason); health = 'error'; }
    else if (last && last.status === 'pending') { link = '检测尚未完成'; hint = '如果长时间未完成，请检查 Nginx 的 /api/voice/ 转发后重新检测。'; }
    text('voice-diag-link', link, health);
    var recent = data && data.recent_rejections;
    var names = {origin:'来源校验',tls:'安全协议',ticket:'连接票据',connection:'连接异常'};
    text('voice-diag-rejections', recent && recent.status === 'available'
      ? recent.samples.map(function (sample) { return (names[sample.dimensions.reason] || sample.dimensions.reason) +
        '（' + (sample.dimensions.channel === 'initial' ? '首连' : '重连') + '）' + sample.value + ' 次'; }).join('；') + ' · UTC ' + recent.utc_day + '，仅保留的观测样本'
      : '暂无可用观测样本，不能据此判断没有异常');
    text('voice-diag-time', '代理：' + time(proxy && proxy.checked_at) + '；链路：' + time(last && last.checked_at) +
      (last && last.host ? ' · 检测入口 ' + last.host : ''));
    text('voice-diag-message', hint || (!ready ? '自动发现不可用或记录已过期。先刷新状态；持续失败时检查 nginx 与 backend 是否位于同一 Docker 网络。' :
      '代理地址会自动适应容器重建；需要核对当前浏览器链路时，点击“重新检测”。'));
  }
  async function request(method, path) {
    return adminRequest(method, path, null, false, {silentErrorToast:true,returnErrorResponse:true,timeoutMs:10000});
  }
  async function read(id) {
    var result = await request('GET', base);
    if (id !== serial) return;
    data = result && result.code === 0 && result.data && result.data.proxy ? result.data : null;
  }
  async function refresh() {
    if (active) return;
    var id = ++serial; localFailure = '';
    await read(id); if (id === serial) render();
  }
  function handshake(info) {
    return new Promise(function (resolve) {
      var done = false, timer;
      function finish() { if (done) return; done = true; clearTimeout(timer); if (socket) socket.close(); socket = null; resolve(); }
      try {
        var url = new URL(info.path, window.location.origin);
        url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(url.href, ['voice.v1', 'ticket.' + info.ticket, 'device.diagnostic']);
        timer = setTimeout(finish, 8000);
        socket.onmessage = function (event) {
          try {
            var message = JSON.parse(event.data);
            if (message.type === 'diagnostic.ready') socket.send(JSON.stringify({type:'diagnostic.ack'}));
            if (message.type === 'diagnostic.result') finish();
          } catch (_) { finish(); }
        };
        socket.onclose = finish; socket.onerror = finish;
      } catch (_) { finish(); }
    });
  }
  async function test() {
    if (active || !writable) return;
    var id = ++serial; active = true; localFailure = ''; render();
    try {
      var started = await request('POST', base + '/probes');
      if (!started || started.code !== 0) throw new Error(started && (started.message || (typeof started.detail === 'string' && started.detail)) || '无法启动检测，请检查后台连接后重试。');
      await handshake(started.data);
      if (id !== serial) return;
      var result = await request('GET', base + '/probes/' + started.data.probe_id);
      await read(id);
      if (id !== serial) return;
      if (!result || result.code !== 0 || !result.data || result.data.status === 'pending') {
        localFailure = '未收到完整检测结果。请检查网络及 Nginx WebSocket 转发后重试；当前不能判定连接正常。';
      } else if (data) data.last_probe = result.data;
    } catch (e) { if (id === serial) localFailure = e.message || '检测失败，请重试。'; }
    finally { if (id === serial) { active = false; render(); } }
  }
  refreshButton.addEventListener('click', refresh); testButton.addEventListener('click', test);
  var ticker = setInterval(render, 5000);
  window.addEventListener('pagehide', function () {
    ++serial; if (socket) socket.close(); clearInterval(ticker);
    active = false; data = null; localFailure = ''; render();
  });
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) { ticker = setInterval(render, 5000); refresh(); }
  });
  refresh();
})();

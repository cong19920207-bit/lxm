/* Independent call operations page. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    if (!checkAdminLogin()) return;
    var role = getAdminRole();
    if (['super_admin', 'tech_ops', 'observer'].indexOf(role) < 0) {
      window.location.replace('error.html?type=403');
      return;
    }
    document.getElementById('sidebar-mount').innerHTML = renderSidebar('voice-ops');
    document.getElementById('header-mount').innerHTML = renderHeader('通话运维');
    var canWrite = ['super_admin', 'tech_ops'].indexOf(role) >= 0;
    var busy = false;
    var card = document.getElementById('voice-ops-card');
    var result = document.getElementById('voice-ops-result');
    var state = document.getElementById('voice-ops-state');
    var outcomeHost = document.getElementById('voice-ops-outcomes');
    var confirmation = document.getElementById('voice-ops-confirm');
    var outcomes = new Map();
    var reasons = {
      VOICE_END_CLEANUP_PENDING: '通话已结束，资源清理待完成',
      VOICE_END_SETTLEMENT_REVIEW_REQUIRED: '结算依据缺失或不一致，需人工核查后重试',
      VOICE_END_STATE_INVALID: '通话终态校验未通过，需核查后台日志后重试',
      VOICE_END_DATABASE_UNAVAILABLE: '数据库处理未完成',
      VOICE_END_DEPENDENCY_UNAVAILABLE: '通话依赖服务暂不可用',
      VOICE_END_FAILED: '结束未完成；持续失败需核查后台日志',
      VOICE_CALL_NOT_FOUND: '通话不存在，请核对编号'
    };
    card.hidden = false;
    document.getElementById('voice-ops-write').hidden = !canWrite;

    function setBusy(value) {
      busy = value;
      card.querySelectorAll('[data-write-action]').forEach(function (node) { node.disabled = value || !canWrite; });
      document.getElementById('voice-ops-refresh').disabled = value;
    }
    function forcePath(id) { return '/calls/' + encodeURIComponent(id) + '/force-end'; }
    function remember(id, ended, detail) {
      if (ended && ended.cleanup_pending === false) {
        outcomes.set(id, {status: 'completed', message: '通话已结束，清理已完成', retryable: false});
      } else if (ended && ended.cleanup_pending === true) {
        outcomes.set(id, {status: 'pending', message: reasons.VOICE_END_CLEANUP_PENDING, retryable: true});
      } else if (detail && Object.prototype.hasOwnProperty.call(reasons, detail.error_code)) {
        outcomes.set(id, {status: 'failed', message: reasons[detail.error_code], retryable: detail.retryable === true});
      } else {
        outcomes.set(id, {status: 'unknown', message: '结果待确认，可重试此通话以确认结束和清理状态', retryable: true});
      }
    }
    function renderOutcomes() {
      outcomeHost.replaceChildren();
      var counts = {completed: 0, pending: 0, failed: 0, unknown: 0};
      outcomes.forEach(function (outcome, id) {
        counts[outcome.status]++;
        var row = document.createElement('p');
        var label = document.createElement('span');
        label.textContent = id + '：' + outcome.message + '。 ';
        row.appendChild(label);
        if (canWrite && outcome.retryable) {
          var button = document.createElement('button');
          button.type = 'button'; button.className = 'btn btn-default';
          button.textContent = outcome.status === 'pending' ? '重试清理' : '重试此通话';
          button.setAttribute('data-write-action', ''); button.disabled = busy;
          button.onclick = function () { stop(forcePath(id), id); };
          row.appendChild(button);
        }
        outcomeHost.appendChild(row);
      });
      result.textContent = '完成 ' + counts.completed + ' 通；清理待完成 ' + counts.pending +
        ' 通；失败 ' + counts.failed + ' 通；结果待确认 ' + counts.unknown + ' 通。';
    }
    async function refresh() {
      try {
        var response = await adminRequest('GET', '/api/admin/voice/ops/active-calls');
        if (!response || response.code !== 0) throw new Error('unavailable');
        var host = document.getElementById('voice-ops-calls');
        host.replaceChildren();
        response.data.calls.forEach(function (call) {
          var row = document.createElement('tr');
          [call.call_id, call.user_id, call.status].forEach(function (value) {
            var cell = document.createElement('td'); cell.textContent = String(value); row.appendChild(cell);
          });
          var action = document.createElement('td');
          if (canWrite) {
            var button = document.createElement('button');
            button.type = 'button'; button.className = 'btn btn-danger'; button.textContent = '结束此通话';
            button.setAttribute('data-write-action', ''); button.disabled = busy;
            button.onclick = function () { stop(forcePath(call.call_id), call.call_id); };
            action.appendChild(button);
          } else { action.textContent = '只读'; }
          row.appendChild(action); host.appendChild(row);
        });
        state.textContent = '进行中 ' + response.data.database_count + ' 通，租约计数 ' + response.data.lease_count + '。';
      } catch (error) { state.textContent = '通话状态读取失败，请稍后刷新。'; }
    }
    async function stop(path, callId) {
      if (!canWrite || busy) return;
      if (confirmation.value !== 'CONFIRM') { result.textContent = '请精确输入 CONFIRM 后再操作。'; return; }
      setBusy(true); confirmation.value = '';
      result.textContent = '正在处理，请稍候…';
      try {
        // Keep structured partial-failure bodies from HTTP 409/503. The shared
        // request helper already supports this; other admin pages are unaffected.
        var response = await adminRequest('POST', '/api/admin/voice' + path, {confirm_text: 'CONFIRM'}, false,
          {returnErrorResponse: true, silentErrorToast: true});
        var data = response && response.data;
        if (callId) {
          remember(callId, response && response.code === 0 ? data : null, data);
          renderOutcomes();
        } else if (path === '/ops/hard-stop' && data && Array.isArray(data.targets)) {
          var ended = new Map((data.results || []).map(function (item) { return [item.call_id, item]; }));
          var failures = new Map((data.failure_details || []).map(function (item) { return [item.call_id, item]; }));
          data.targets.forEach(function (id) { remember(id, ended.get(id), failures.get(id)); });
          renderOutcomes();
          if (data.targets.length === 0) result.textContent = '本次没有需要结束的进行中通话。';
        } else if (path === '/ops/soft-stop' && response && response.code === 0) {
          result.textContent = data && data.idempotent ? '已处于停止新拨打状态。' : '已停止新拨打。';
        } else {
          result.textContent = '操作结果待确认，请刷新状态后核查；不会自动重发批量操作。';
        }
      } catch (error) {
        if (callId) { remember(callId, null, null); renderOutcomes(); }
        else result.textContent = '操作结果待确认，请刷新状态后核查；不会自动重发批量操作。';
      } finally {
        // Refresh list/counts without erasing operation outcomes or fixed IDs.
        await refresh();
        setBusy(false);
      }
    }
    document.getElementById('voice-ops-refresh').onclick = refresh;
    document.getElementById('voice-ops-soft').onclick = function () { stop('/ops/soft-stop'); };
    document.getElementById('voice-ops-hard').onclick = function () { stop('/ops/hard-stop'); };
    refresh();
  });
})();

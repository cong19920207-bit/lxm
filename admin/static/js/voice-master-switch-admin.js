/* Independent switch: render only authoritative state, never publish other drafts. */
(function () {
  'use strict';
  if (!checkAdminLogin()) return;
  document.getElementById('sidebar-mount').innerHTML = renderSidebar('voice-master-switch');
  document.getElementById('header-mount').innerHTML = renderHeader('语音通话总开关');
  var writable = ['super_admin', 'tech_ops'].indexOf(getAdminRole()) >= 0;
  var effective = null, available = false, busy = false, confirming = false;
  var toggle = document.getElementById('voice-master-enabled');
  var status = document.getElementById('voice-master-status');
  var error = document.getElementById('voice-master-error');
  var reload = document.getElementById('btn-voice-master-reload');
  document.getElementById('voice-master-role').hidden = writable;
  function showError(message) { error.textContent = message || ''; error.hidden = !message; }
  function render() {
    toggle.checked = !!(effective && effective.enabled);
    toggle.disabled = !writable || !available || busy || confirming;
    reload.disabled = busy || confirming;
    status.textContent = busy ? '正在处理…' : !available ? '状态不可用' : '当前生效：已' + (effective.enabled ? '开启' : '关闭');
    document.getElementById('voice-master-updated').textContent = effective
      ? '版本 ' + effective.version + ' · 更新人：' + (effective.updated_by || '系统') + ' · 更新时间：' + effective.updated_at : '';
  }
  async function readState() {
    var result = await adminRequest('GET', '/api/admin/voice/master-switch', null, false, {silentErrorToast:true,returnErrorResponse:true});
    var value = result && result.code === 0 && result.data;
    available = !!(value && typeof value.enabled === 'boolean' && Number.isInteger(value.version) && value.version >= 1);
    if (available) effective = value;
    return available;
  }
  async function refresh() {
    if (busy || confirming) return;
    busy = true; showError(''); render();
    if (!await readState()) showError('无法读取当前状态，请稍后刷新。');
    busy = false; render();
  }
  async function publish(target, version) {
    confirming = false; busy = true; showError(''); render();
    var result = await adminRequest('POST', '/api/admin/voice/master-switch/publish',
      {enabled:target,expected_version:version}, false, {silentErrorToast:true,returnErrorResponse:true});
    // A response can be lost after commit. Always reread, never blindly retry.
    if (!await readState()) {
      showError('暂时无法确认生效状态，请刷新后查看。');
    } else if (effective.enabled !== target) {
      showError(result && result.code !== 0 && result.message || '操作未生效或状态已被更新，已显示当前生效状态。');
    } else if (!result || result.code !== 0) {
      showError('操作响应未确认，已重新读取并显示当前生效状态。');
    }
    busy = false; render();
  }
  toggle.addEventListener('change', function () {
    if (!available || !writable || busy || confirming) { render(); return; }
    var target = !effective.enabled, version = effective.version;
    confirming = true; render();
    showConfirm(target ? '确认开启语音通话？将检查已发布的语音设置，通过后立即生效。' : '确认关闭语音通话？关闭后停止接受新通话，当前通话继续。',
      function () { publish(target, version); },
      function () { confirming = false; render(); },
      {title: target ? '开启语音通话' : '关闭语音通话', danger: !target});
  });
  reload.addEventListener('click', refresh);
  refresh();
})();

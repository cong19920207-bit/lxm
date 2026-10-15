(function (root) {
  'use strict';
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
    });
  }
  function html(item, role) {
    if (!item.index_state || item.index_state === 'ready') return '';
    var detail = item.index_maintenance || {};
    var labels = {pending:'等待处理', running:'处理中', retry_wait:'等待重试',
      manual_required:'需人工处理', completed:'状态待核实', unavailable:'状态待核实'};
    var title = labels[detail.state] || '索引未就绪';
    if (detail.overdue) title += '（已超时）';
    var content = '<div class="memory-index-status" role="note"><strong>BM25 索引：' + esc(title) + '</strong>';
    content += '<div>' + esc(detail.reason || '原因暂不可用') +
      (detail.reason_code ? ' <code>' + esc(detail.reason_code) + '</code>' : '') + '</div>';
    if (Number.isInteger(detail.attempt_count) && detail.attempt_count >= 0) {
      content += '<small>索引写入尝试：' + detail.attempt_count + ' 次</small>';
    }
    if (detail.next_attempt_at && !detail.overdue) {
      var date = new Date(detail.next_attempt_at);
      content += '<small>下次计划：' + esc(isNaN(date.getTime()) ? '待核实' : date.toLocaleString('zh-CN')) + '</small>';
    }
    if (['super_admin','ai_trainer','observer'].includes(role) &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(detail.task_id || '')) {
      content += '<a href="/admin/pages/memory-index-maintenance.html?task_id=' +
        encodeURIComponent(detail.task_id) + '">查看索引维护</a>';
    }
    return content + '</div>';
  }
  root.MemoryIndexStatus = {html:html};
})(window);

// 生活流后台页面公共辅助（STEP-030~036）

function lfEscapeHtml(text) {
  return String(text == null ? '' : text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function lfPickValue(item) {
  if (!item) return null;
  if (item.has_draft) return item.draft;
  return item.active;
}

async function lfSaveDraft(configKey, configValue) {
  var res = await adminRequest('PUT', '/api/admin/life-config/draft', {
    config_key: configKey,
    config_value: configValue
  });
  if (res && res.code === 0) {
    showToast('草稿已保存', 'success');
    return true;
  }
  return false;
}

function lfPublishConfig(configKey, configValue, onDone) {
  showConfirmInput(
    '发布配置：' + configKey,
    '发布后将立即生效并开启 5 分钟监控窗口，请确认配置无误。',
    '确认发布',
    async function () {
      var res = await adminRequest('POST', '/api/admin/life-config/publish', {
        config_key: configKey,
        config_value: configValue,
        confirm_text: 'CONFIRM'
      });
      if (res && res.code === 0) {
        showToast('已发布，5 分钟监控窗口已开启', 'success');
        if (onDone) onDone();
      }
    }
  );
}

/** 初始化生活流页面：鉴权 + 侧栏 + 顶栏 + 只读模式隐藏编辑按钮 */
function initLifeFeedPage(activeKey, pageTitle, allowedRoles) {
  if (!checkAdminLogin()) return false;
  allowedRoles = allowedRoles || ['super_admin', 'ai_trainer'];
  if (allowedRoles.indexOf(getAdminRole()) < 0 &&
      !(LIFE_FEED_MENU[getAdminRole()] || []).some(function (m) { return m.key === activeKey; })) {
    window.location.href = '/admin/pages/error.html?type=403';
    return false;
  }
  document.getElementById('sidebar-mount').innerHTML = renderSidebar(activeKey);
  document.getElementById('header-mount').innerHTML = renderHeader(pageTitle);
  if (isLifeFeedReadOnly(activeKey)) {
    document.querySelectorAll('[data-edit-only]').forEach(function (el) {
      el.style.display = 'none';
    });
  }
  return true;
}

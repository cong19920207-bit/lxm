const ADMIN_API_BASE = '';

// ─── Token 管理（sessionStorage，关闭浏览器自动清除）───

function saveAdminToken(token, username, role) {
  sessionStorage.setItem('admin_token', token);
  sessionStorage.setItem('admin_username', username);
  sessionStorage.setItem('admin_role', role);
}

function getAdminToken() {
  return sessionStorage.getItem('admin_token');
}

function getAdminUsername() {
  return sessionStorage.getItem('admin_username') || '管理员';
}

function getAdminRole() {
  return sessionStorage.getItem('admin_role') || '';
}

function isObserver() {
  return getAdminRole() === 'observer';
}

/**
 * observer 前端请求兜底。后端统一鉴权仍是最终权限边界。
 * 只允许 GET/HEAD，以及两个精确的账号自助 POST。
 */
function isObserverRequestAllowed(method, path) {
  if (!isObserver()) return true;
  method = String(method || 'GET').toUpperCase();
  var exactPath = String(path || '').split('?')[0].split('#')[0];
  if (method === 'GET' || method === 'HEAD') return true;
  if (method !== 'POST') return false;
  return exactPath === '/api/admin/auth/logout' ||
    exactPath === '/api/admin/auth/change-password';
}

/**
 * 对带 data-write-action 的静态或动态节点应用 observer 只读策略。
 * 不扫描无标记的普通按钮/表单，避免破坏搜索、筛选、分页、Tab、详情、复制和 GET 刷新。
 */
function applyObserverReadOnly(root) {
  if (!isObserver()) return;
  root = root || document;

  var markers = [];
  if (root.nodeType === 1 && root.matches && root.matches('[data-write-action]')) {
    markers.push(root);
  }
  if (root.querySelectorAll) {
    root.querySelectorAll('[data-write-action]').forEach(function (node) {
      markers.push(node);
    });
  }

  var controlSelector = 'button, a, input, textarea, select, [role="button"], [role="switch"]';
  markers.forEach(function (marker) {
    var controls = [];
    if (marker.matches && marker.matches(controlSelector)) controls.push(marker);
    marker.querySelectorAll(controlSelector).forEach(function (control) {
      controls.push(control);
    });

    controls.forEach(function (control) {
      var tagName = String(control.tagName || '').toLowerCase();
      var inputType = String(control.type || '').toLowerCase();
      var role = control.getAttribute('role');
      var isHiddenWriteTrigger = tagName === 'button' || tagName === 'a' ||
        role === 'button' || ['button', 'submit', 'reset', 'image'].indexOf(inputType) >= 0;

      if (isHiddenWriteTrigger) {
        control.classList.add('observer-write-hidden');
        control.setAttribute('aria-hidden', 'true');
        control.setAttribute('tabindex', '-1');
        return;
      }

      var isDisabledControl = tagName === 'select' || role === 'switch' ||
        ['checkbox', 'radio', 'file', 'range'].indexOf(inputType) >= 0;
      if (isDisabledControl) {
        control.disabled = true;
        control.setAttribute('aria-disabled', 'true');
        control.classList.add('observer-control-disabled');
        return;
      }

      if (tagName === 'input' || tagName === 'textarea') {
        control.readOnly = true;
        control.setAttribute('aria-readonly', 'true');
        control.classList.add('observer-control-readonly');
      }
    });
  });
}

var observerReadOnlyMutationObserver = null;

function initObserverReadOnly() {
  if (!isObserver()) return;
  applyObserverReadOnly(document);
  if (observerReadOnlyMutationObserver || typeof MutationObserver === 'undefined') return;

  observerReadOnlyMutationObserver = new MutationObserver(function (records) {
    records.forEach(function (record) {
      record.addedNodes.forEach(function (node) {
        if (node.nodeType === 1) applyObserverReadOnly(node);
      });
    });
  });
  observerReadOnlyMutationObserver.observe(document.documentElement || document.body, {
    childList: true,
    subtree: true
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initObserverReadOnly);
} else {
  initObserverReadOnly();
}

function clearAdminToken() {
  sessionStorage.clear();
}

function checkAdminLogin() {
  if (!getAdminToken()) {
    window.location.href = '/admin/pages/login.html';
    return false;
  }
  return true;
}

// ─── 统一请求函数 ───
// requestExtra：可选；{ silentErrorToast: true } 时不在此函数内对 code≠0 弹 Toast，由调用方处理（如按 20012/20013 定制文案）。

async function adminRequest(method, path, data = null, isFile = false, requestExtra = null) {
  method = String(method || 'GET').toUpperCase();
  if (!isObserverRequestAllowed(method, path)) {
    showToast('观察者仅允许执行只读操作', 'warning');
    return null;
  }
  const silentErrorToast = requestExtra && requestExtra.silentErrorToast;
  const fetchOpts = {
    method,
    headers: {
      'Authorization': 'Bearer ' + getAdminToken()
    }
  };

  if (isFile) {
    // 文件上传：直接传 FormData，浏览器自动设置 Content-Type
    fetchOpts.body = data;
  } else if (data) {
    fetchOpts.headers['Content-Type'] = 'application/json';
    fetchOpts.body = JSON.stringify(data);
  }

  try {
    const resp = await fetch(ADMIN_API_BASE + path, fetchOpts);

    if (resp.status === 401) {
      clearAdminToken();
      window.location.href = '/admin/pages/login.html';
      return null;
    }

    if (resp.status === 403) {
      showToast('权限不足，无法执行此操作', 'error');
      return null;
    }

    if (!resp.ok) {
      showToast('请求异常，请稍后重试', 'error');
      return null;
    }

    // 文件下载响应：content-type 含 spreadsheetml 或 octet-stream 时触发浏览器下载
    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('spreadsheetml') || contentType.includes('octet-stream')) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = resp.headers.get('content-disposition') || '';
      const fileNameMatch = disposition.match(/filename=(.+)/);
      a.download = fileNameMatch ? decodeURIComponent(fileNameMatch[1]) : 'export.xlsx';
      a.click();
      URL.revokeObjectURL(url);
      return { code: 0 };
    }

    const result = await resp.json();
    if (result.code !== 0 && !silentErrorToast) {
      showToast(result.message || '操作失败', 'error');
    }
    return result;
  } catch (e) {
    showToast('网络请求失败，请检查网络连接', 'error');
    return null;
  }
}

// ─── Toast 提示 ───

function showToast(message, type = 'info', duration = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const colors = { info: '#1890ff', success: '#52c41a', error: '#ff4d4f', warning: '#faad14' };
  const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };

  const toast = document.createElement('div');
  toast.className = 'toast-item';
  toast.style.borderLeft = '4px solid ' + (colors[type] || colors.info);
  toast.innerHTML = '<span style="margin-right:8px">' + (icons[type] || icons.info) + '</span>' + message;
  container.appendChild(toast);

  setTimeout(function () {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s';
    setTimeout(function () {
      if (toast.parentNode) container.removeChild(toast);
    }, 300);
  }, duration);
}

// ─── 普通确认弹窗 ───

// options：可选 { danger: true } — 危险操作（顶部强调色 + 确认钮 btn-danger）；默认确认钮为 btn-primary
function showConfirm(message, onConfirm, onCancel, options) {
  var opts = options || {};
  var isDanger = opts.danger === true;
  var titleText = opts.title || (isDanger ? '危险操作' : '确认操作');
  var okBtnClass = isDanger ? 'btn btn-danger' : 'btn btn-primary';
  var contentClass = 'modal-content' + (isDanger ? ' modal-content--danger' : '');

  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay show';
  overlay.innerHTML =
    '<div class="' + contentClass + '" style="min-width:360px;max-width:440px">' +
      '<div class="modal-header">' +
        '<h3>' + titleText + '</h3>' +
        '<button class="btn btn-link" id="__confirm_close">✕</button>' +
      '</div>' +
      '<div class="modal-body">' +
        '<p style="margin:0;color:#333;font-size:14px;line-height:1.6">' + message + '</p>' +
      '</div>' +
      '<div class="modal-footer">' +
        '<button class="btn btn-default" id="__confirm_cancel">取消</button>' +
        '<button class="' + okBtnClass + '" id="__confirm_ok">确认</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);

  function close() { overlay.remove(); }

  overlay.querySelector('#__confirm_close').onclick = function () { close(); if (onCancel) onCancel(); };
  overlay.querySelector('#__confirm_cancel').onclick = function () { close(); if (onCancel) onCancel(); };
  overlay.querySelector('#__confirm_ok').onclick = function () { close(); onConfirm(); };
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) { close(); if (onCancel) onCancel(); }
  });
}

// ─── CONFIRM 输入验证弹窗（发布/回滚等高风险操作专用）───

function showConfirmInput(title, warningMessage, confirmBtnText, onConfirm) {
  if (typeof confirmBtnText === 'function') {
    onConfirm = confirmBtnText;
    confirmBtnText = '确认发布';
  }

  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay show';
  overlay.innerHTML =
    '<div class="modal-content" style="min-width:440px;max-width:540px">' +
      '<div class="modal-header">' +
        '<h3>' + title + '</h3>' +
        '<button class="btn btn-link" id="__ci_close">✕</button>' +
      '</div>' +
      '<div class="modal-body">' +
        '<div class="alert alert-warning" style="margin-bottom:16px">' + warningMessage + '</div>' +
        '<div class="form-item" style="margin-bottom:0">' +
          '<label>请在下方输入 <code style="background:#f5f5f5;padding:2px 6px;border-radius:3px;color:#d4380d">CONFIRM</code> 确认操作：</label>' +
          '<input type="text" id="__ci_input" class="form-control" placeholder="输入 CONFIRM" autocomplete="off">' +
        '</div>' +
      '</div>' +
      '<div class="modal-footer">' +
        '<button class="btn btn-default" id="__ci_cancel">取消</button>' +
        '<button class="btn btn-danger" id="__ci_ok" disabled>' + confirmBtnText + '</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);

  var input = overlay.querySelector('#__ci_input');
  var okBtn = overlay.querySelector('#__ci_ok');

  input.addEventListener('input', function () {
    okBtn.disabled = input.value !== 'CONFIRM';
  });

  overlay.querySelector('#__ci_close').onclick = function () { overlay.remove(); };
  overlay.querySelector('#__ci_cancel').onclick = function () { overlay.remove(); };
  okBtn.onclick = function () { overlay.remove(); onConfirm(); };

  setTimeout(function () { input.focus(); }, 100);
}

// ─── 侧边栏菜单配置（按角色）───

// 一级菜单顺序：运营总览 → AI 对话配置 → 对话流 Prompt → 生活流 Prompt → 系统与账号
// 占位项仅控制分组插入位置，不渲染为普通菜单项
var MENU_CONFIG = {
  super_admin: [
    { key: 'dashboard',       label: '📊 数据看板',   href: 'dashboard.html' },
    { key: 'users',           label: '👥 用户管理',   href: 'users.html' },
    { key: 'report',          label: '📈 数据报表',   href: 'data-report.html' },
    { key: 'diary-history',   label: '📜 AI 日记历史', href: 'diary-history.html' },
    { key: 'persona',         label: '🎭 人格管理',   href: 'persona.html' },
    { key: 'chat-prompt-group', group: 'chat_prompt' },
    { key: 'life-feed-group', group: 'life_feed' },
    { key: 'knowledge',       label: '📚 角色知识库', href: 'knowledge.html' },
    { key: 'vector-token',    label: '🔎 召回与 Token', href: 'vector-token-config.html' },
    { key: 'agent',           label: '🤖 Agent配置',  href: 'agent-rules.html' },
    { key: 'relationship',    label: '💞 关系成长',   href: 'relationship-rules.html' },
    { key: 'diary',           label: '📔 日记规则',   href: 'diary-rules.html' },
    { key: 'safety',          label: '🛡️ 内容安全',  href: 'safety-rules.html' },
    { key: 'test',            label: '🧪 AI测试工具', href: 'test-tool.html' },
    { key: 'system',          label: '⚙️ 系统监控',  href: 'system-monitor.html' },
    { key: 'third-party',     label: '🔌 第三方服务', href: 'third-party.html' },
    { key: 'system-logs',     label: '📋 系统日志',   href: 'system-logs.html' },
    { key: 'operation-logs',  label: '🗒️ 操作日志',  href: 'operation-logs.html' },
    { key: 'accounts',        label: '🔑 账号管理',   href: 'accounts.html' }
  ],
  ops_admin: [
    { key: 'dashboard',       label: '📊 数据看板',   href: 'dashboard.html' },
    { key: 'users',           label: '👥 用户管理',   href: 'users.html' },
    { key: 'report',          label: '📈 数据报表',   href: 'data-report.html' },
    { key: 'diary-history',   label: '📜 AI 日记历史', href: 'diary-history.html' },
    { key: 'life-feed-group', group: 'life_feed' },
    { key: 'operation-logs',  label: '🗒️ 操作日志',  href: 'operation-logs.html' }
  ],
  ai_trainer: [
    { key: 'dashboard',       label: '📊 数据看板',   href: 'dashboard.html' },
    { key: 'persona',         label: '🎭 人格管理',   href: 'persona.html' },
    { key: 'chat-prompt-group', group: 'chat_prompt' },
    { key: 'life-feed-group', group: 'life_feed' },
    { key: 'knowledge',       label: '📚 角色知识库', href: 'knowledge.html' },
    { key: 'vector-token',    label: '🔎 召回与 Token', href: 'vector-token-config.html' },
    { key: 'agent',           label: '🤖 Agent配置',  href: 'agent-rules.html' },
    { key: 'relationship',    label: '💞 关系成长',   href: 'relationship-rules.html' },
    { key: 'diary',           label: '📔 日记规则',   href: 'diary-rules.html' },
    { key: 'safety',          label: '🛡️ 内容安全',  href: 'safety-rules.html' },
    { key: 'test',            label: '🧪 AI测试工具', href: 'test-tool.html' }
  ],
  tech_ops: [
    { key: 'dashboard',       label: '📊 数据看板',   href: 'dashboard.html' },
    { key: 'life-feed-group', group: 'life_feed' },
    { key: 'system',          label: '⚙️ 系统监控',  href: 'system-monitor.html' },
    { key: 'third-party',     label: '🔌 第三方服务', href: 'third-party.html' },
    { key: 'system-logs',     label: '📋 系统日志',   href: 'system-logs.html' },
    { key: 'operation-logs',  label: '🗒️ 操作日志',  href: 'operation-logs.html' }
  ]
};

// ─── 生活流 Prompt 子菜单（原「生活宇宙」）───
// super_admin / ai_trainer：全部；ops_admin：只读内容/评论/感知；tech_ops：仅系统参数
// 子项顺序：生活计划 → 生活流人格拓展 → 内容/评论/感知 → 宇宙 → Prompt → 系统

// ─── 对话流 Prompt 子菜单（只读页 + 链到现有可编辑页）───
var CHAT_PROMPT_MENU = {
  super_admin: [
    { key: 'cp-step15', label: '🔍 Step1.5 查询重写', href: 'chat-prompt-step15.html' },
    { key: 'cp-step3',  label: '🧩 Step3 Prompt拼装', href: 'chat-prompt-step3.html' },
    { key: 'cp-step5',  label: '💬 Step5 主对话', href: 'prompt.html?tab=step5' },
    { key: 'cp-step55', label: '✨ Step5.5 润色', href: 'prompt.html?tab=step55' },
    { key: 'cp-step55-switch', label: '⚡ Step5.5 开关', href: 'step5-5-switch.html' },
    { key: 'cp-step6',  label: '🧠 Step6 记忆拆解', href: 'memory-rules.html?nav=cp-step6' },
    { key: 'cp-step8',  label: '⏰ Step8 Future主动', href: 'chat-prompt-step8.html' },
    { key: 'cp-agent',  label: '📣 Agent主动 P0～P4', href: 'chat-prompt-agent.html' }
  ],
  ai_trainer: [
    { key: 'cp-step15', label: '🔍 Step1.5 查询重写', href: 'chat-prompt-step15.html' },
    { key: 'cp-step3',  label: '🧩 Step3 Prompt拼装', href: 'chat-prompt-step3.html' },
    { key: 'cp-step5',  label: '💬 Step5 主对话', href: 'prompt.html?tab=step5' },
    { key: 'cp-step55', label: '✨ Step5.5 润色', href: 'prompt.html?tab=step55' },
    { key: 'cp-step55-switch', label: '⚡ Step5.5 开关', href: 'step5-5-switch.html' },
    { key: 'cp-step6',  label: '🧠 Step6 记忆拆解', href: 'memory-rules.html?nav=cp-step6' },
    { key: 'cp-step8',  label: '⏰ Step8 Future主动', href: 'chat-prompt-step8.html' },
    { key: 'cp-agent',  label: '📣 Agent主动 P0～P4', href: 'chat-prompt-agent.html' }
  ]
};

var LIFE_FEED_MENU = {
  super_admin: [
    { key: 'life-plan',           label: '📅 生活计划',           href: 'life-plan.html' },
    { key: 'life-feed-global',    label: '🧬 生活流人格拓展',     href: 'life-feed-global.html' },
    { key: 'feed-posts',          label: '📷 朋友圈 · 内容',      href: 'feed-posts.html' },
    { key: 'feed-comments',       label: '💬 朋友圈 · 评论',      href: 'feed-comments.html' },
    { key: 'agent-aware',         label: '🔔 感知消息',           href: 'agent-aware.html' },
    { key: 'worldview',           label: '🌌 她的宇宙',           href: 'worldview.html' },
    { key: 'life-feed-prompts',   label: '✍️ Prompt · 生活流',    href: 'life-feed-prompts.html' },
    { key: 'life-feed-system',    label: '🚀 发布 & 系统参数',    href: 'life-feed-system.html' }
  ],
  ai_trainer: [
    { key: 'life-plan',           label: '📅 生活计划',           href: 'life-plan.html' },
    { key: 'life-feed-global',    label: '🧬 生活流人格拓展',     href: 'life-feed-global.html' },
    { key: 'feed-posts',          label: '📷 朋友圈 · 内容',      href: 'feed-posts.html' },
    { key: 'feed-comments',       label: '💬 朋友圈 · 评论',      href: 'feed-comments.html' },
    { key: 'agent-aware',         label: '🔔 感知消息',           href: 'agent-aware.html' },
    { key: 'worldview',           label: '🌌 她的宇宙',           href: 'worldview.html' },
    { key: 'life-feed-prompts',   label: '✍️ Prompt · 生活流',    href: 'life-feed-prompts.html' },
    { key: 'life-feed-system',    label: '🚀 发布 & 系统参数',    href: 'life-feed-system.html' }
  ],
  ops_admin: [
    { key: 'life-plan',     label: '📅 生活计划',     href: 'life-plan.html', readonly: true },
    { key: 'feed-posts',    label: '📷 朋友圈 · 内容', href: 'feed-posts.html', readonly: true },
    { key: 'feed-comments', label: '💬 朋友圈 · 评论', href: 'feed-comments.html', readonly: true },
    { key: 'agent-aware',   label: '🔔 感知消息',     href: 'agent-aware.html', readonly: true },
    { key: 'worldview',     label: '🌌 她的宇宙',     href: 'worldview.html', readonly: true }
  ],
  tech_ops: [
    { key: 'life-feed-system', label: '🚀 发布 & 系统参数', href: 'life-feed-system.html', readonly: true }
  ]
};

// observer 复用 super_admin 的业务读取导航，但不暴露账号管理。
MENU_CONFIG.observer = MENU_CONFIG.super_admin.filter(function (item) {
  return item.key !== 'accounts';
});
CHAT_PROMPT_MENU.observer = CHAT_PROMPT_MENU.super_admin.slice();
LIFE_FEED_MENU.observer = LIFE_FEED_MENU.super_admin.map(function (item) {
  var observerItem = Object.assign({}, item);
  observerItem.readonly = true;
  return observerItem;
});

/** 侧栏滚动位置记忆 key（仅左侧，不记右侧内容区） */
var ADMIN_SIDEBAR_SCROLL_KEY = 'admin_sidebar_scroll';

/** 跳转前保存侧栏 scrollTop，再整页跳转 */
function navigateAdminPage(href) {
  var sidebar = document.querySelector('.sidebar');
  if (sidebar) {
    try {
      sessionStorage.setItem(ADMIN_SIDEBAR_SCROLL_KEY, String(sidebar.scrollTop));
    } catch (e) { /* ignore */ }
  }
  window.location.href = '/admin/pages/' + href;
}

/** 注入侧栏后恢复滚动位置 */
function restoreSidebarScroll() {
  var sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  try {
    var saved = sessionStorage.getItem(ADMIN_SIDEBAR_SCROLL_KEY);
    if (saved !== null && saved !== '') {
      sidebar.scrollTop = parseInt(saved, 10) || 0;
    }
  } catch (e) { /* ignore */ }
}

/** 生活流 Prompt 分组标题：仅展开/收起，不跳转 */
function toggleLifeFeedMenu(titleEl) {
  var group = titleEl && titleEl.parentElement;
  if (!group || !group.classList.contains('menu-group')) return;
  group.classList.toggle('expanded');
}

/** 对话流 Prompt 分组标题：仅展开/收起 */
function toggleChatPromptMenu(titleEl) {
  var group = titleEl && titleEl.parentElement;
  if (!group || !group.classList.contains('menu-group')) return;
  group.classList.toggle('expanded');
}

/** 生活流页面是否只读（observer 全部；ops_admin / tech_ops 部分页） */
function isLifeFeedReadOnly(activeKey) {
  var role = getAdminRole();
  var items = LIFE_FEED_MENU[role] || [];
  for (var i = 0; i < items.length; i++) {
    if (items[i].key === activeKey) return !!items[i].readonly;
  }
  return role === 'observer' || role === 'ops_admin' || role === 'tech_ops';
}

/** 当前 key 是否属于生活流 Prompt 分组（用于侧栏默认展开） */
function isLifeFeedKey(activeKey) {
  var all = ['life-feed-global', 'life-plan', 'worldview', 'feed-posts', 'feed-comments',
    'agent-aware', 'life-feed-prompts', 'life-feed-system'];
  return all.indexOf(activeKey) >= 0;
}

/** 当前 key 是否属于对话流 Prompt 分组 */
function isChatPromptKey(activeKey) {
  var all = [
    'cp-step15', 'cp-step3', 'cp-step5', 'cp-step55', 'cp-step55-switch',
    'cp-step6', 'cp-step8', 'cp-agent',
    // 兼容旧书签：仍可能直接打开 prompt / step55switch
    'prompt', 'step55switch'
  ];
  return all.indexOf(activeKey) >= 0;
}

/** 渲染「生活流 Prompt」可折叠分组 HTML */
function renderLifeFeedGroupHtml(activeKey, lfMenus) {
  if (!lfMenus || lfMenus.length === 0) return '';
  // 当前页属本分组 → 强制展开；否则默认收起
  var lfExpanded = isLifeFeedKey(activeKey) ? ' expanded' : '';
  var html = '<div class="menu-group' + lfExpanded + '">';
  // 标题仅展开/收起，不跳转
  html +=
    '<div class="menu-group-title" onclick="toggleLifeFeedMenu(this)">' +
      '<span class="menu-group-label">🌿 生活流 Prompt</span>' +
      '<span class="menu-group-arrow"></span>' +
    '</div>';
  html += '<div class="menu-group-body">';
  for (var j = 0; j < lfMenus.length; j++) {
    var lm = lfMenus[j];
    var isActive = activeKey === lm.key;
    html +=
      '<div class="menu-item menu-sub' + (isActive ? ' active' : '') + '"' +
      ' onclick="navigateAdminPage(\'' + lm.href + '\')">' +
      lm.label +
      '</div>';
  }
  html += '</div></div>';
  return html;
}

/** 渲染「对话流 Prompt」可折叠分组 HTML */
function renderChatPromptGroupHtml(activeKey, cpMenus) {
  if (!cpMenus || cpMenus.length === 0) return '';
  var expanded = isChatPromptKey(activeKey) ? ' expanded' : '';
  var html = '<div class="menu-group' + expanded + '">';
  html +=
    '<div class="menu-group-title" onclick="toggleChatPromptMenu(this)">' +
      '<span class="menu-group-label">🗣️ 对话流 Prompt</span>' +
      '<span class="menu-group-arrow"></span>' +
    '</div>';
  html += '<div class="menu-group-body">';
  for (var j = 0; j < cpMenus.length; j++) {
    var cm = cpMenus[j];
    var isActive = activeKey === cm.key;
    // 兼容：旧 activeKey=prompt 时高亮 Step5
    if (!isActive && activeKey === 'prompt' && cm.key === 'cp-step5') isActive = true;
    if (!isActive && activeKey === 'step55switch' && cm.key === 'cp-step55-switch') isActive = true;
    html +=
      '<div class="menu-item menu-sub' + (isActive ? ' active' : '') + '"' +
      ' onclick="navigateAdminPage(\'' + cm.href + '\')">' +
      cm.label +
      '</div>';
  }
  html += '</div></div>';
  return html;
}

// ─── 侧边栏渲染 ───

function renderSidebar(activeKey) {
  var role = getAdminRole();
  var menus = MENU_CONFIG[role] || [];
  var lfMenus = LIFE_FEED_MENU[role] || [];
  var cpMenus = CHAT_PROMPT_MENU[role] || [];
  var items = '';
  var lifeFeedInserted = false;
  var chatPromptInserted = false;

  for (var i = 0; i < menus.length; i++) {
    var m = menus[i];
    if (m.group === 'life_feed') {
      items += renderLifeFeedGroupHtml(activeKey, lfMenus);
      lifeFeedInserted = true;
      continue;
    }
    if (m.group === 'chat_prompt') {
      items += renderChatPromptGroupHtml(activeKey, cpMenus);
      chatPromptInserted = true;
      continue;
    }
    items +=
      '<div class="menu-item' + (activeKey === m.key ? ' active' : '') + '"' +
      ' onclick="navigateAdminPage(\'' + m.href + '\')">' +
      m.label +
      '</div>';
  }

  if (!lifeFeedInserted && lfMenus.length > 0) {
    items += renderLifeFeedGroupHtml(activeKey, lfMenus);
  }
  if (!chatPromptInserted && cpMenus.length > 0) {
    items += renderChatPromptGroupHtml(activeKey, cpMenus);
  }

  // 注入完成后恢复侧栏滚动（不改各业务页调用方）
  setTimeout(restoreSidebarScroll, 0);

  return (
    '<div class="sidebar">' +
      '<div class="sidebar-title">林小梦管理后台</div>' +
      items +
    '</div>'
  );
}

// ─── 顶栏渲染 ───

function renderHeader(pageTitle) {
  var roleLabels = {
    super_admin: '超级管理员',
    ops_admin: '运营管理员',
    ai_trainer: 'AI训练师',
    tech_ops: '技术运维',
    observer: '观察者'
  };
  var roleText = roleLabels[getAdminRole()] || getAdminRole();

  return (
    '<div class="admin-header">' +
      '<span style="font-size:18px;font-weight:bold;color:#333">' + pageTitle + '</span>' +
      '<div style="display:flex;align-items:center;gap:12px">' +
        '<span class="tag tag-blue">' + roleText + '</span>' +
        '<span style="color:#333;font-size:14px">' + getAdminUsername() + '</span>' +
        '<button type="button" class="btn btn-default" onclick="showChangePasswordModal()">修改密码</button>' +
        '<button type="button" class="btn btn-default" onclick="handleAdminLogout()">退出登录</button>' +
      '</div>' +
    '</div>'
  );
}

// ─── 修改密码（当前登录用户，调用 POST /api/admin/auth/change-password）───

function showChangePasswordModal() {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay show';
  overlay.innerHTML =
    '<div class="modal-content" style="min-width:400px;max-width:480px">' +
      '<div class="modal-header">' +
        '<h3>修改密码</h3>' +
        '<button type="button" class="btn btn-link" id="__cp_close">✕</button>' +
      '</div>' +
      '<div class="modal-body">' +
        '<p style="margin:0 0 12px;font-size:13px;color:#666;line-height:1.5">' +
          '新密码须≥12位，且含大写字母、小写字母、数字、特殊字符（非字母数字），与创建管理员账号规则一致。' +
        '</p>' +
        '<div class="form-item" style="margin-bottom:12px">' +
          '<label>当前密码</label>' +
          '<input type="password" id="__cp_old" class="form-control" autocomplete="current-password">' +
        '</div>' +
        '<div class="form-item" style="margin-bottom:12px">' +
          '<label>新密码</label>' +
          '<input type="password" id="__cp_new" class="form-control" autocomplete="new-password">' +
        '</div>' +
        '<div class="form-item" style="margin-bottom:0">' +
          '<label>确认新密码</label>' +
          '<input type="password" id="__cp_confirm" class="form-control" autocomplete="new-password">' +
        '</div>' +
      '</div>' +
      '<div class="modal-footer">' +
        '<button type="button" class="btn btn-default" id="__cp_cancel">取消</button>' +
        '<button type="button" class="btn btn-primary" id="__cp_ok">保存</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);

  function close() {
    overlay.remove();
  }

  overlay.querySelector('#__cp_close').onclick = close;
  overlay.querySelector('#__cp_cancel').onclick = close;
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) close();
  });

  overlay.querySelector('#__cp_ok').onclick = async function () {
    var oldP = overlay.querySelector('#__cp_old').value;
    var newP = overlay.querySelector('#__cp_new').value;
    var cfm = overlay.querySelector('#__cp_confirm').value;
    if (!oldP || !newP || !cfm) {
      showToast('请填写完整', 'error');
      return;
    }
    if (newP !== cfm) {
      showToast('两次新密码不一致', 'error');
      return;
    }
    var result = await adminRequest('POST', '/api/admin/auth/change-password', {
      old_password: oldP,
      new_password: newP,
      confirm_password: cfm
    });
    if (result && result.code === 0) {
      close();
      showToast('密码已修改，请重新登录', 'success');
      clearAdminToken();
      window.location.href = '/admin/pages/login.html';
    }
  };

  setTimeout(function () {
    overlay.querySelector('#__cp_old').focus();
  }, 100);
}

// ─── 退出登录 ───

async function handleAdminLogout() {
  showConfirm('确定要退出登录吗？', async function () {
    await adminRequest('POST', '/api/admin/auth/logout');
    clearAdminToken();
    window.location.href = '/admin/pages/login.html';
  });
}

// ─── 分页器渲染 ───

function renderPagination(containerId, currentPage, total, pageSize, onPageChange) {
  var totalPages = Math.ceil(total / pageSize);
  var container = document.getElementById(containerId);
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  var html = '<div class="pagination">';
  html += '<span style="color:#666;font-size:13px;margin-right:8px">共 ' + total + ' 条</span>';

  html += '<button class="page-btn"' + (currentPage <= 1 ? ' disabled' : '') +
    ' onclick="(' + onPageChange + ')(' + (currentPage - 1) + ')">＜</button>';

  var start = Math.max(1, currentPage - 2);
  var end = Math.min(totalPages, currentPage + 2);

  if (start > 1) {
    html += '<button class="page-btn" onclick="(' + onPageChange + ')(1)">1</button>';
  }
  if (start > 2) {
    html += '<span style="padding:0 4px">...</span>';
  }

  for (var i = start; i <= end; i++) {
    html += '<button class="page-btn' + (i === currentPage ? ' active' : '') + '"' +
      ' onclick="(' + onPageChange + ')(' + i + ')">' + i + '</button>';
  }

  if (end < totalPages - 1) {
    html += '<span style="padding:0 4px">...</span>';
  }
  if (end < totalPages) {
    html += '<button class="page-btn" onclick="(' + onPageChange + ')(' + totalPages + ')">' + totalPages + '</button>';
  }

  html += '<button class="page-btn"' + (currentPage >= totalPages ? ' disabled' : '') +
    ' onclick="(' + onPageChange + ')(' + (currentPage + 1) + ')">＞</button>';

  html += '</div>';
  container.innerHTML = html;
}

// ─── 时间格式化 ───

function formatDateTime(isoStr) {
  if (!isoStr) return '-';
  var d = new Date(isoStr);
  var pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function formatDate(isoStr) {
  if (!isoStr) return '-';
  var d = new Date(isoStr);
  var pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

// ─── 防抖函数 ───

function debounce(fn, delay) {
  if (delay === undefined) delay = 300;
  var timer;
  return function () {
    var ctx = this;
    var args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
  };
}

// ─── 标签页切换 ───

function initTabs(tabsContainerId) {
  var container = document.getElementById(tabsContainerId);
  if (!container) return;
  var tabItems = container.querySelectorAll('.tab-item');
  tabItems.forEach(function (item) {
    item.addEventListener('click', function () {
      tabItems.forEach(function (t) { t.classList.remove('active'); });
      item.classList.add('active');
      var target = item.dataset.target;
      document.querySelectorAll('.tab-pane').forEach(function (p) {
        if (p.id === target) {
          p.classList.add('active');
        } else {
          p.classList.remove('active');
        }
      });
    });
  });
}

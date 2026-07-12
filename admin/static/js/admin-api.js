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

// 一级菜单顺序：运营总览 → AI 对话配置 → 生活宇宙（占位 group:'life_feed'）→ 系统与账号
// 占位项仅控制「生活宇宙」插入位置，不渲染为普通菜单项
var MENU_CONFIG = {
  super_admin: [
    { key: 'dashboard',       label: '📊 数据看板',   href: 'dashboard.html' },
    { key: 'users',           label: '👥 用户管理',   href: 'users.html' },
    { key: 'report',          label: '📈 数据报表',   href: 'data-report.html' },
    { key: 'diary-history',   label: '📜 AI 日记历史', href: 'diary-history.html' },
    { key: 'persona',         label: '🎭 人格管理',   href: 'persona.html' },
    { key: 'prompt',          label: '📝 Prompt管理', href: 'prompt.html' },
    { key: 'memory',          label: '🧠 记忆规则',   href: 'memory-rules.html' },
    { key: 'knowledge',       label: '📚 角色知识库', href: 'knowledge.html' },
    { key: 'vector-token',    label: '🔎 召回与 Token', href: 'vector-token-config.html' },
    { key: 'agent',           label: '🤖 Agent配置',  href: 'agent-rules.html' },
    { key: 'relationship',    label: '💞 关系成长',   href: 'relationship-rules.html' },
    { key: 'diary',           label: '📔 日记规则',   href: 'diary-rules.html' },
    { key: 'safety',          label: '🛡️ 内容安全',  href: 'safety-rules.html' },
    { key: 'step55switch',    label: '⚡ Step5.5开关', href: 'step5-5-switch.html' },
    { key: 'test',            label: '🧪 AI测试工具', href: 'test-tool.html' },
    { key: 'life-feed-group', group: 'life_feed' },
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
    { key: 'prompt',          label: '📝 Prompt管理', href: 'prompt.html' },
    { key: 'memory',          label: '🧠 记忆规则',   href: 'memory-rules.html' },
    { key: 'knowledge',       label: '📚 角色知识库', href: 'knowledge.html' },
    { key: 'vector-token',    label: '🔎 召回与 Token', href: 'vector-token-config.html' },
    { key: 'agent',           label: '🤖 Agent配置',  href: 'agent-rules.html' },
    { key: 'relationship',    label: '💞 关系成长',   href: 'relationship-rules.html' },
    { key: 'diary',           label: '📔 日记规则',   href: 'diary-rules.html' },
    { key: 'safety',          label: '🛡️ 内容安全',  href: 'safety-rules.html' },
    { key: 'step55switch',    label: '⚡ Step5.5开关', href: 'step5-5-switch.html' },
    { key: 'test',            label: '🧪 AI测试工具', href: 'test-tool.html' },
    { key: 'life-feed-group', group: 'life_feed' }
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

// ─── 生活宇宙子菜单（STEP-038，侧栏展示名「生活宇宙」）───
// super_admin / ai_trainer：全部；ops_admin：只读内容/评论/感知；tech_ops：仅系统参数
// 子项顺序：运营优先（内容→评论→感知→计划→宇宙→全局→Prompt→系统）

var LIFE_FEED_MENU = {
  super_admin: [
    { key: 'feed-posts',          label: '📷 朋友圈 · 内容',      href: 'feed-posts.html' },
    { key: 'feed-comments',       label: '💬 朋友圈 · 评论',      href: 'feed-comments.html' },
    { key: 'agent-aware',         label: '🔔 感知消息',           href: 'agent-aware.html' },
    { key: 'life-plan',           label: '📅 生活计划',           href: 'life-plan.html' },
    { key: 'worldview',           label: '🌌 她的宇宙',           href: 'worldview.html' },
    { key: 'life-feed-global',    label: '⚙️ 全局配置',           href: 'life-feed-global.html' },
    { key: 'life-feed-prompts',   label: '✍️ Prompt · 生活流',    href: 'life-feed-prompts.html' },
    { key: 'life-feed-system',    label: '🚀 发布 & 系统参数',    href: 'life-feed-system.html' }
  ],
  ai_trainer: [
    { key: 'feed-posts',          label: '📷 朋友圈 · 内容',      href: 'feed-posts.html' },
    { key: 'feed-comments',       label: '💬 朋友圈 · 评论',      href: 'feed-comments.html' },
    { key: 'agent-aware',         label: '🔔 感知消息',           href: 'agent-aware.html' },
    { key: 'life-plan',           label: '📅 生活计划',           href: 'life-plan.html' },
    { key: 'worldview',           label: '🌌 她的宇宙',           href: 'worldview.html' },
    { key: 'life-feed-global',    label: '⚙️ 全局配置',           href: 'life-feed-global.html' },
    { key: 'life-feed-prompts',   label: '✍️ Prompt · 生活流',    href: 'life-feed-prompts.html' },
    { key: 'life-feed-system',    label: '🚀 发布 & 系统参数',    href: 'life-feed-system.html' }
  ],
  ops_admin: [
    { key: 'feed-posts',    label: '📷 朋友圈 · 内容', href: 'feed-posts.html', readonly: true },
    { key: 'feed-comments', label: '💬 朋友圈 · 评论', href: 'feed-comments.html', readonly: true },
    { key: 'agent-aware',   label: '🔔 感知消息',     href: 'agent-aware.html', readonly: true },
    { key: 'life-plan',     label: '📅 生活计划',     href: 'life-plan.html', readonly: true },
    { key: 'worldview',     label: '🌌 她的宇宙',     href: 'worldview.html', readonly: true }
  ],
  tech_ops: [
    { key: 'life-feed-system', label: '🚀 发布 & 系统参数', href: 'life-feed-system.html', readonly: true }
  ]
};

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

/** 生活宇宙分组标题：仅展开/收起，不跳转 */
function toggleLifeFeedMenu(titleEl) {
  var group = titleEl && titleEl.parentElement;
  if (!group || !group.classList.contains('menu-group')) return;
  group.classList.toggle('expanded');
}

/** 生活流页面是否只读（ops_admin / tech_ops 部分页） */
function isLifeFeedReadOnly(activeKey) {
  var role = getAdminRole();
  var items = LIFE_FEED_MENU[role] || [];
  for (var i = 0; i < items.length; i++) {
    if (items[i].key === activeKey) return !!items[i].readonly;
  }
  return role === 'ops_admin' || role === 'tech_ops';
}

/** 当前 key 是否属于生活宇宙分组（用于侧栏默认展开） */
function isLifeFeedKey(activeKey) {
  var all = ['life-feed-global', 'life-plan', 'worldview', 'feed-posts', 'feed-comments',
    'agent-aware', 'life-feed-prompts', 'life-feed-system'];
  return all.indexOf(activeKey) >= 0;
}

/** 渲染「生活宇宙」可折叠分组 HTML */
function renderLifeFeedGroupHtml(activeKey, lfMenus) {
  if (!lfMenus || lfMenus.length === 0) return '';
  // 当前页属生活宇宙 → 强制展开；否则默认收起
  var lfExpanded = isLifeFeedKey(activeKey) ? ' expanded' : '';
  var html = '<div class="menu-group' + lfExpanded + '">';
  // 标题仅展开/收起，不跳转；侧栏展示名「生活宇宙」
  html +=
    '<div class="menu-group-title" onclick="toggleLifeFeedMenu(this)">' +
      '<span class="menu-group-label">🌿 生活宇宙</span>' +
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

// ─── 侧边栏渲染 ───

function renderSidebar(activeKey) {
  var role = getAdminRole();
  var menus = MENU_CONFIG[role] || [];
  var lfMenus = LIFE_FEED_MENU[role] || [];
  var items = '';
  var lifeFeedInserted = false;

  for (var i = 0; i < menus.length; i++) {
    var m = menus[i];
    // 占位项：在此位置插入「生活宇宙」分组
    if (m.group === 'life_feed') {
      items += renderLifeFeedGroupHtml(activeKey, lfMenus);
      lifeFeedInserted = true;
      continue;
    }
    items +=
      '<div class="menu-item' + (activeKey === m.key ? ' active' : '') + '"' +
      ' onclick="navigateAdminPage(\'' + m.href + '\')">' +
      m.label +
      '</div>';
  }

  // 兜底：若某角色未配置占位但仍有子菜单，仍挂到末尾（避免漏显）
  if (!lifeFeedInserted && lfMenus.length > 0) {
    items += renderLifeFeedGroupHtml(activeKey, lfMenus);
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
    tech_ops: '技术运维'
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

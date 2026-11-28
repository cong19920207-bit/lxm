/* Read-only H5 visitor metrics, reports and device details. */
window.VisitorAnalytics = (() => {
  const base = '/api/admin/stats/';
  const pagination = Object.create(null);
  const format = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'medium' });
  const time = v => v ? format.format(new Date(v)) : '已过期';
  const identity = v => v === 'guest' ? '游客' : v === 'unknown' ? '身份未知' : '账号 ' + v;
  const pages = { index:'首页', chat:'聊天', feed:'朋友圈', diary:'日记', memory:'记忆', relationship:'关系', settings:'设置', login:'登录', pet:'养宠' };
  const entry = v => v === 'public/feed' ? '手机公开朋友圈' : '主站 · ' + (pages[v.split('/')[1]] || v);
  function network(row) {
    const v = row.network;
    const value = !v ? '已过期' : !v.ip ? '来源未知' : v.ip + '（' + v.region + '）';
    return value + (row.delayed ? ' · 补报时 IP' : '');
  }
  function el(tag, value, cls) {
    const node = document.createElement(tag);
    if (value != null) node.textContent = value;
    if (cls) node.className = cls;
    return node;
  }
  function button(label, fn, cls = 'btn btn-default') {
    const node = el('button', label, cls); node.type = 'button'; node.onclick = fn; return node;
  }
  function initNavigation() {
    const sidebar = document.querySelector('.sidebar');
    const toggle = button('导航', () => {
      toggle.setAttribute('aria-expanded', String(sidebar.classList.toggle('mobile-open')));
    }, 'btn btn-default visitor-nav');
    toggle.setAttribute('aria-expanded', 'false');
    document.querySelector('.admin-header').prepend(toggle);
  }
  function fieldList(fields, cls) {
    const list = el('dl', null, cls);
    for (const [label, value] of fields) {
      const pair = el('div');
      pair.append(el('dt', label), el('dd', value ?? '未提供'));
      list.append(pair);
    }
    return list;
  }
  function stacked(primary, secondary) {
    const stack = el('div', null, 'device-stack');
    stack.append(el('span', primary), el('small', secondary));
    return stack;
  }
  function deviceTable(data) {
    const grid = el('table', null, 'visitor-table');
    grid.setAttribute('aria-label', '所选日期的设备');
    const columns = ['设备 / 编号','最近访问 IP','最近身份','当日来访','当日打开','当日首次 / 最近来访','累计来访 / 打开'];
    const head = grid.createTHead().insertRow(), body = grid.createTBody();
    for (const label of columns) head.append(el('th', label));
    for (const row of data.list) {
      const device = row.device, profile = device?.profile || {};
      const info = stacked([profile.device, profile.os, profile.os_version].filter(Boolean).join(' · ') || '设备信息未提供',
        [profile.environment, profile.browser, profile.browser_version].filter(Boolean).join(' · '));
      const open = () => showDevice(row.visitor_id, data.day);
      info.append(button(row.visitor_id, open, 'visitor-open'));
      const latest = device ? stacked(identity(device.identity), time(device.last_at)) : '未提供';
      let address = '未提供';
      if (device) {
        const net = device.network;
        address = net?.ip ? stacked(net.ip, '（' + net.region + '）') : network(device);
      }
      const cells = [info, address, latest,
        row.visits, row.opens, stacked(time(row.first_at), time(row.last_at)),
        device ? device.visits + ' / ' + device.opens : '未提供'];
      const tr = body.insertRow();
      cells.forEach((value, index) => {
        const cell = tr.insertCell();
        cell.dataset.label = columns[index];
        cell.append(value instanceof Node ? value : String(value));
      });
      tr.onclick = e => { if (!e.target.closest('button')) open(); };
    }
    if (!data.list.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = columns.length; cell.className = 'device-empty';
      cell.textContent = data.state === 'expired' ? '逐次明细已过期' : data.state === 'empty' ? '当日无访问' : '当日没有可识别的设备';
    }
    return grid;
  }
  function pager(root, id, data, change) {
    const mount = el('div'); mount.id = id; root.append(mount);
    const key = id.replaceAll('-', '_');
    pagination[key] = change;
    renderPagination(id, data.page, data.total, data.page_size, 'window.VisitorAnalytics.pagination.' + key);
  }
  function failure(root, retry) {
    const error = el('div', null, 'visitor-error');
    error.setAttribute('role', 'alert'); error.append(el('span', '查询失败'), button('重试', retry));
    root.replaceChildren(error);
  }
  async function get(path) {
    const reply = await adminRequest('GET', base + path);
    return reply && reply.code === 0 ? reply.data : null;
  }
  function metricCards(data) {
    const cards = el('div', null, 'visitor-metrics');
    for (const [label, value] of [['独立访客数', data.visitors], ['来访次数', data.visits], ['打开次数', data.opens]]) {
      const card = el('div', null, 'stat-card');
      card.append(el('div', label, 'stat-label'), el('strong', value, 'stat-value'));
      cards.append(card);
    }
    return cards;
  }
  async function overview(root, renderCards) {
    if (root.getAttribute('aria-busy') === 'true') return;
    root.setAttribute('aria-busy', 'true');
    try {
      const data = await get('visitors/summary');
      if (data) root.innerHTML = renderCards(data);
      else failure(root, () => overview(root, renderCards));
    } finally {
      root.setAttribute('aria-busy', 'false');
    }
  }
  function dialog(id) {
    document.querySelector('dialog.visitor-dialog')?.close();
    const d = el('dialog', null, 'visitor-dialog'), head = el('header'), body = el('div');
    const title = '设备 ' + id;
    const label = el('div');
    label.append(el('h2', '设备详情'), el('small', id));
    head.append(label, button('关闭', () => d.close()));
    body.className = 'visitor-dialog-body';
    d.setAttribute('aria-label', title); d.append(head, body); document.body.append(d);
    d.addEventListener('close', () => d.remove(), { once: true }); d.showModal(); return body;
  }
  function history(root, changes) {
    if (!changes.length) return;
    root.append(el('h4', '身份变化'));
    for (const r of changes) root.append(fieldList([
      ['发生时间',time(r.occurred_at)], ['变更后身份',identity(r.identity)], ['当次 IP（归属地）',network(r)]
    ], 'visitor-record identity-record'));
  }
  function opens(root, rows) {
    root.append(el('h4', '逐次打开'));
    if (!rows.length) { root.append(el('p', '没有可查的打开记录')); return; }
    for (const r of rows) root.append(fieldList([
      ['打开时间',time(r.occurred_at)], ['入口',entry(r.entry)], ['打开时身份',identity(r.identity)],
      ['当次 IP（归属地）',network(r)], ['首次接收',time(r.received_at)], ['所属来访',r.visit_id]
    ], 'visitor-record open-record'));
  }
  function visitGroups(root, visits) {
    if (!visits.length) root.append(el('p', '该日无可查的来访明细'));
    for (const [i, visit] of visits.entries()) {
      const group = el('section', null, 'visitor-visit');
      group.append(el('h3', '第 ' + (i+1) + ' 次来访'));
      const s = visit.start;
      group.append(el('p', s ? [time(s.occurred_at), entry(s.entry), identity(s.identity), network(s)].join('　') : '来访开始明细已过期'));
      history(group, visit.changes); opens(group, visit.opens); root.append(group);
    }
  }
  function devices(root) {
    const tools = el('div', null, 'visitor-tools'), date = el('input', null, 'form-control');
    date.type = 'date'; date.setAttribute('aria-label', '统计日期');
    const range = el('small'), sort = el('select', null, 'form-control'), content = el('div');
    sort.setAttribute('aria-label','按来访次数排序');
    for (const [key, name] of [['desc','来访次数从多到少'], ['asc','来访次数从少到多']]) sort.add(new Option(name, key));
    const label = el('label','统计日期');
    date.id = 'device-stat-date'; label.htmlFor = date.id;
    const heading = el('div', null, 'device-filter-heading');
    heading.append(label, range);
    const sortControl = el('div', null, 'device-sort');
    sortControl.append(sort);
    tools.append(heading, date, sortControl); root.append(tools, content);
    let page = 1, version = 0, selectedDay;
    async function load() {
      const current = ++version, args = new URLSearchParams({ page, order: sort.value });
      if (date.value) args.set('day', date.value);
      content.replaceChildren(el('p', '查询中…'));
      const d = await get('visitors?' + args);
      if (current !== version) return;
      if (!d) { failure(content, load); return; }
      selectedDay = d.day;
      date.min = d.first_day; date.max = d.today; date.value = d.day; range.textContent = '北京时间 · 最早可查 ' + d.first_day;
      content.replaceChildren(metricCards(d));
      if (d.unidentified_opens) content.append(el('p', '无法识别设备的打开次数 ' + d.unidentified_opens));
      const panel = el('section', null, 'device-panel');
      const title = el('header');
      title.append(el('h2', '访问设备'), el('small', d.state === 'expired' ? '明细保留 30 天' : '共 ' + d.total + ' 个设备编号'));
      panel.append(title, deviceTable(d)); content.append(panel);
      if (d.list.length) pager(panel, 'visitor-report-pager', d, value => { page = value; void load(); });
    }
    date.onchange = sort.onchange = () => {
      if (!date.validity.valid) { date.value = selectedDay || ''; return; }
      page = 1; void load();
    };
    return load();
  }
  const profileLabels = {device:'设备类型',os:'系统',os_version:'系统版本',model:'具体机型',browser:'浏览器',
    browser_version:'浏览器主版本',environment:'打开环境',screen_width:'屏幕宽（CSS px）',screen_height:'屏幕高（CSS px）',
    viewport_width:'可视区域宽（CSS px）',viewport_height:'可视区域高（CSS px）',orientation:'方向',pixel_ratio:'像素比',processors:'逻辑处理器数量'};
  function deviceProfile(profile) {
    return fieldList(Object.entries(profileLabels).map(([key, label]) => [label, profile[key]]), 'visitor-profile');
  }
  function showDevice(id, day) {
    const root = dialog(id);
    async function load() {
      root.replaceChildren(el('p', '查询中…'));
      const device = await get('devices/' + id + '?page=1');
      if (!root.isConnected) return;
      if (!device) { failure(root, load); return; }
      const tools = el('div', null, 'visitor-switch'), records = el('div');
      const daily = button('按日来访 · ' + day, () => show('day'));
      const all = button('近 30 天打开记录', () => show('all'));
      tools.append(daily, all);
      root.replaceChildren(fieldList([['首次访问',time(device.first_at)], ['最近访问',time(device.last_at)],
        ['累计来访',device.visits + ' 次'], ['累计打开',device.opens + ' 次']], 'visitor-facts'),
        el('h4','最近设备资料'), deviceProfile(device.profile), tools, records);
      let version = 0;
      async function show(scope, page = 1) {
        const current = ++version;
        daily.setAttribute('aria-pressed', String(scope === 'day'));
        all.setAttribute('aria-pressed', String(scope === 'all'));
        records.replaceChildren(el('p', '查询中…'));
        let data = device;
        if (scope === 'day') data = await get('visitors/' + id + '?day=' + day);
        else if (page > 1) data = await get('devices/' + id + '?page=' + page);
        if (!root.isConnected || current !== version) return;
        if (!data) { failure(records, () => show(scope, page)); return; }
        records.replaceChildren();
        if (scope === 'day') {
          visitGroups(records, data.visits);
        } else {
          opens(records, data.list);
          pager(records, 'visitor-opens-pager', data, next => show('all', next));
          history(records, data.changes);
        }
      }
      void show('day');
    }
    void load();
  }
  return { overview, devices, pagination, initNavigation };
})();

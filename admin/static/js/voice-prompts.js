(function () {
  'use strict';
  var READ_ROLES = ['super_admin', 'ai_trainer', 'observer'];
  var API = '/api/admin/voice/prompt-view';
  var groups = [], cache = new Map(), remembered = new Map();
  var selected = '', generation = 0, currentContent = '';
  function el(id) { return document.getElementById(id); }

  async function read(path) {
    var result = await adminRequest('GET', path, null, false, {silentErrorToast: true});
    if (!result || result.code !== 0 || !result.data || result.data.readonly !== true) {
      throw new Error('提示词加载失败，请稍后重试。');
    }
    return result.data;
  }

  function groupFor(key) {
    return groups.find(function (group) { return group.items.some(function (item) { return item.key === key; }); });
  }

  function tabButton(key, label, prefix) {
    var button = document.createElement('button');
    button.type = 'button';
    button.id = prefix + key;
    button.dataset.key = key;
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', 'vp-panel');
    button.setAttribute('aria-selected', 'false');
    button.tabIndex = -1;
    button.textContent = label;
    return button;
  }

  function selectState(container, key) {
    container.querySelectorAll('[role="tab"]').forEach(function (button) {
      var active = button.dataset.key === key;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
  }

  function bindTabs(container, select) {
    container.addEventListener('click', function (event) {
      var button = event.target.closest('[role="tab"]');
      if (button && container.contains(button)) select(button.dataset.key);
    });
    container.addEventListener('keydown', function (event) {
      if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) < 0) return;
      var buttons = Array.from(container.querySelectorAll('[role="tab"]'));
      var index = buttons.indexOf(event.target);
      if (index < 0) return;
      event.preventDefault();
      index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
        (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
      buttons[index].focus();
      buttons[index].scrollIntoView({block: 'nearest', inline: 'nearest'});
      select(buttons[index].dataset.key);
    });
  }

  function updateTabs(key) {
    var group = groupFor(key);
    selectState(el('vp-tabs'), group.key);
    var variants = el('vp-variants');
    if (variants.dataset.group !== group.key) {
      variants.replaceChildren();
      group.items.forEach(function (item) { variants.appendChild(tabButton(item.key, item.label, 'vp-variant-')); });
      variants.dataset.group = group.key;
    }
    el('vp-variants-wrap').hidden = group.items.length < 2;
    selectState(variants, key);
    el('vp-panel').setAttribute('aria-labelledby', group.items.length > 1 ? 'vp-variant-' + key : 'vp-tab-' + group.key);
    el('vp-stage').textContent = group.stage;
  }

  function renderContent(text) {
    var pre = el('vp-content');
    pre.replaceChildren();
    var pattern = /\{\{[^{}]+\}\}/g, match, last = 0;
    while ((match = pattern.exec(text))) {
      pre.appendChild(document.createTextNode(text.slice(last, match.index)));
      var span = document.createElement('span');
      span.className = 'vp-placeholder';
      span.textContent = match[0];
      pre.appendChild(span);
      last = match.index + match[0].length;
    }
    pre.appendChild(document.createTextNode(text.slice(last)));
    pre.scrollTop = 0;
  }

  function render(data) {
    currentContent = data.content;
    el('vp-title').textContent = data.title;
    el('vp-description').textContent = data.description;
    el('vp-trigger').textContent = data.trigger;
    el('vp-output').textContent = data.output;
    el('vp-key').textContent = data.prompt_key;
    el('vp-char-count').textContent = Array.from(data.content).length.toLocaleString() + ' 字符';
    renderContent(data.content);
    el('vp-inputs').replaceChildren();
    (data.inputs || []).forEach(function (input) {
      var row = document.createElement('div'), term = document.createElement('dt'), definition = document.createElement('dd');
      term.textContent = input.name;
      definition.textContent = input.description;
      row.append(term, definition);
      el('vp-inputs').appendChild(row);
    });
    el('vp-empty-inputs').hidden = !!(data.inputs || []).length;
    el('vp-notes').replaceChildren();
    (data.notes || []).forEach(function (note) {
      var li = document.createElement('li');
      li.textContent = note;
      el('vp-notes').appendChild(li);
    });
    el('vp-notes').parentElement.hidden = !(data.notes || []).length;
    el('vp-sources').replaceChildren();
    (data.source_files || []).forEach(function (source) {
      var li = document.createElement('li');
      li.textContent = source;
      el('vp-sources').appendChild(li);
    });
    el('vp-panel').hidden = false;
    el('vp-status').hidden = true;
    el('vp-copy').disabled = false;
  }

  async function loadPrompt(key, refresh) {
    var group = groupFor(key);
    if (!group) return;
    selected = key;
    remembered.set(group.key, key);
    updateTabs(key);
    var url = new URL(window.location.href);
    url.searchParams.set('prompt', key);
    window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    var ticket = ++generation;
    currentContent = '';
    el('vp-copy').disabled = true;
    el('vp-panel').hidden = true;
    el('vp-error').hidden = true;
    el('vp-status').textContent = '正在加载提示词…';
    el('vp-status').hidden = false;
    el('vp-panel').setAttribute('aria-busy', 'true');
    try {
      var data = !refresh && cache.has(key) ? cache.get(key) : await read(API + '/' + encodeURIComponent(key));
      if (data.prompt_key !== key || typeof data.content !== 'string') throw new Error('提示词内容不完整，请重新加载。');
      cache.set(key, data);
      if (ticket === generation) render(data);
    } catch (error) {
      if (ticket !== generation) return;
      cache.delete(key);
      el('vp-error-message').textContent = error.message;
      el('vp-error').hidden = false;
      el('vp-status').hidden = true;
    } finally {
      if (ticket === generation) el('vp-panel').setAttribute('aria-busy', 'false');
    }
  }

  async function loadCatalog() {
    el('vp-error').hidden = true;
    el('vp-status').hidden = false;
    try {
      var data = await read(API);
      if (!Array.isArray(data.groups) || !data.groups.length) throw new Error('暂无可展示的提示词。');
      groups = data.groups;
      el('vp-tabs').replaceChildren();
      groups.forEach(function (group) { el('vp-tabs').appendChild(tabButton(group.key, group.label, 'vp-tab-')); });
      el('vp-group-count').textContent = groups.length;
      el('vp-prompt-count').textContent = groups.reduce(function (sum, group) { return sum + group.items.length; }, 0);
      var requested = new URLSearchParams(window.location.search).get('prompt');
      await loadPrompt(groupFor(requested) ? requested : groups[0].items[0].key);
    } catch (error) {
      el('vp-error-message').textContent = error.message;
      el('vp-error').hidden = false;
      el('vp-status').hidden = true;
    }
  }

  async function copyPrompt() {
    if (!currentContent) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(currentContent);
      } else {
        var selection = window.getSelection(), range = document.createRange();
        range.selectNodeContents(el('vp-content'));
        selection.removeAllRanges();
        selection.addRange(range);
        var copied = document.execCommand('copy');
        selection.removeAllRanges();
        if (!copied) throw new Error('clipboard_unavailable');
      }
      showToast('提示词已复制', 'success');
    } catch (_) {
      showToast('复制未成功，请选中正文手动复制', 'warning');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!checkAdminLogin()) return;
    if (READ_ROLES.indexOf(getAdminRole()) < 0) {
      window.location.href = '/admin/pages/error.html?type=403';
      return;
    }
    el('sidebar-mount').innerHTML = renderSidebar('voice-prompts');
    el('header-mount').innerHTML = renderHeader('语音 Prompt');
    bindTabs(el('vp-tabs'), function (key) {
      var group = groups.find(function (item) { return item.key === key; });
      if (group) loadPrompt(remembered.get(key) || group.items[0].key);
    });
    bindTabs(el('vp-variants'), function (key) { loadPrompt(key); });
    el('vp-copy').addEventListener('click', copyPrompt);
    el('vp-refresh').addEventListener('click', function () { loadPrompt(selected, true); });
    el('vp-retry').addEventListener('click', function () { selected ? loadPrompt(selected, true) : loadCatalog(); });
    loadCatalog();
  });
})();

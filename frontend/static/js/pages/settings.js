import { tiltUnavailable, requestTiltPermission } from '../app/tilt-permission.js';

export async function mount(context) {
  const {root, services} = context, byId = id => root.querySelector('#' + id);
  const routeCurrent = () => context.router.current?.context.routeEpoch === context.routeEpoch;
  const request = (method, path, body) => services.auth.request(method, path, body, {
    authPolicy: 'silent-visitor', routeEpoch: context.routeEpoch, routeCurrent,
    isCurrent: context.valid, signal: context.signal
  });
  const run = promise => Promise.resolve(promise).catch(error => {
    if (context.valid() && !['AbortError', 'StaleRequestError'].includes(error.name)) services.ui.toast('操作失败，请稍后重试', 'error');
  });
  const showToast = (...args) => { if (context.valid()) services.ui.toast(...args); };
  const settingsToken = () => services.auth.readToken();
  const isSettingsAuthenticated = () => context.valid() && services.auth.snapshot().authenticated;
  const openSettingsLoginModal = () => services.ui.openLogin();
  await context.scope.adopt(services.resources.style('css/bgm.css'), release => release());
  for (const name of ['home-preferences', 'bgm-page', 'bgm-record', 'bgm-bubble', 'bgm-settings']) {
    await services.shared.script('js/' + name + '.js');
    if (!context.valid()) return {unmount() {}};
  }
  const audioPage = services.audio.attachPage(context, 'content'), bubble = BgmBubble.mount(audioPage);
  if (bubble) context.cleanup(() => bubble.destroy());
  const bgmSettings = BgmSettings.mount(audioPage, root);
  context.cleanup(() => bgmSettings.destroy());
  const settingsMotionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let settingsTiltEpoch = 0, settingsTiltPending = false, cancelTiltDeadline = null;
  let aboutLoaded = false, passwordBusy = false, settingBusy = false, logoutBusy = false;

  function clearPasswords() {
    for (const input of root.querySelectorAll('#password-form input')) { input.value = ''; input.type = 'password'; }
    for (const button of root.querySelectorAll('.pwd-eye-btn')) button.setAttribute('aria-label', '显示密码');
  }
  function setExpanded(id, rowId, expanded) {
    byId(id).classList.toggle('visible', expanded); byId(rowId).classList.toggle('expanded', expanded);
    byId(rowId).setAttribute('aria-expanded', String(expanded));
  }
  function setAgent(enabled) {
    byId('toggle-agent').classList.toggle('active', enabled); byId('toggle-agent').setAttribute('aria-checked', String(enabled));
  }
  function renderIdentity() {
    const authenticated = isSettingsAuthenticated();
    for (const section of root.querySelectorAll('[data-settings-private]')) section.hidden = !authenticated;
    byId('settings-account-title').textContent = authenticated ? '账号与关于' : '关于';
    byId('settings-auth-action').classList.toggle('is-login', !authenticated);
    byId('settings-auth-action-text').textContent = authenticated ? '退出登录' : '登录，继续陪伴';
    byId('profile-status').textContent = DEFAULT_STATUS_TEXT;
    clearPasswords(); setExpanded('password-form', 'pwd-row', false); setAgent(true);
  }
  async function loadProfile() {
    const res = await request('GET', '/api/relationship/status');
    if (!context.valid()) return;
    byId('profile-status').textContent = res.code === 0 ? resolveStatusText(res.data) : DEFAULT_STATUS_TEXT;
    if (res.code === 0 && res.data?.ai_current_emotion) {
      const image = new Image(), fallback = byId('linxiaomeng-avatar').src;
      const release = context.cleanup(() => {
        image.onload = image.onerror = null;
        // Completed images only need their handlers detached. Clearing src starts
        // another native image request and can retain a detached image.
        if (!image.complete) image.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
      }, {kind: 'image'});
      image.onload = () => { if (context.valid()) byId('linxiaomeng-avatar').src = image.src; release(); };
      image.onerror = () => { if (context.valid()) byId('linxiaomeng-avatar').src = fallback; release(); };
      image.src = AVATAR_MAP[res.data.ai_current_emotion] || AVATAR_MAP.default;
    }
  }
  async function loadSettings() {
    const res = await request('GET', '/api/user/settings');
    if (context.valid() && res.code === 0 && res.data) setAgent(res.data.agent_message_enabled !== false);
  }
  function togglePasswordForm() {
    if (!isSettingsAuthenticated()) return openSettingsLoginModal();
    const expanded = !byId('password-form').classList.contains('visible');
    setExpanded('password-form', 'pwd-row', expanded);
    if (!expanded) clearPasswords();
  }
  async function handleChangePassword() {
    if (!isSettingsAuthenticated()) return openSettingsLoginModal();
    if (passwordBusy) return;
    const oldPwd = byId('old-password').value, newPwd = byId('new-password').value, confirmPwd = byId('confirm-password').value;
    if (!oldPwd || !newPwd || !confirmPwd) return showToast('请填写完整', 'error');
    if (!/^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z0-9!@#$%^&*]{8,20}$/.test(newPwd)) return showToast('新密码需8-20位，含字母和数字', 'error');
    if (newPwd !== confirmPwd) return showToast('两次密码不一致', 'error');
    passwordBusy = true; root.querySelector('.save-pwd-btn').disabled = true;
    try {
      // Preserve TD-025's existing request contract and failure; do not turn this into an unsafe successful reset.
      const res = await request('POST', '/api/auth/reset-password', {
        username: services.auth.storage('getItem', 'username').value || '', old_password: oldPwd, new_password: newPwd
      });
      if (!context.valid()) return;
      showToast(res.code === 0 ? '密码修改成功' : res.message || '修改失败', res.code === 0 ? 'success' : 'error');
      if (res.code === 0) setExpanded('password-form', 'pwd-row', false);
    } finally {
      clearPasswords(); passwordBusy = false;
      if (context.valid()) root.querySelector('.save-pwd-btn').disabled = false;
    }
  }
  async function toggleSetting() {
    if (!isSettingsAuthenticated()) return openSettingsLoginModal();
    if (settingBusy) return;
    const button = byId('toggle-agent'), previous = button.getAttribute('aria-checked') === 'true';
    settingBusy = true; button.disabled = true; setAgent(!previous);
    try {
      const res = await request('PUT', '/api/user/settings', {agent_message_enabled: !previous});
      if (!context.valid()) return;
      if (res.code !== 0) { setAgent(previous); showToast(res.message || '设置失败', 'error'); }
    } finally { settingBusy = false; if (context.valid()) button.disabled = false; }
  }
    /* 主页动效是当前浏览器偏好，不调用账号设置接口。 */
    function renderHomeMotionSetting(preference) {
      const toggle = byId('toggle-home-motion')
      toggle.classList.toggle('active', preference.enabled)
      toggle.setAttribute('aria-checked', String(preference.enabled))
      byId('home-motion-storage-note').textContent = preference.note
      byId('home-motion-setting-desc').textContent = settingsMotionQuery?.matches
        ? '系统已减少动态，主页会保持静止'
        : '人物与场景的轻微动态'
      if (settingsTiltPending && (!preference.enabled || settingsMotionQuery?.matches)) cancelHomeTiltPermission()
      syncHomeTiltSetting()
    }

    function syncHomeMotionSetting(refreshSaved = false) {
      if (!window.HomePreferences) {
        byId('toggle-home-motion').disabled = true
        byId('home-motion-storage-note').textContent = '动效设置暂不可用，请刷新后重试'
        syncHomeTiltSetting()
        return
      }
      renderHomeMotionSetting(window.HomePreferences.readMotion(refreshSaved === true))
    }

    function toggleHomeMotionSetting() {
      if (!isSettingsAuthenticated()) {
        openSettingsLoginModal()
        return
      }
      const enabled = byId('toggle-home-motion').getAttribute('aria-checked') !== 'true'
      renderHomeMotionSetting(window.HomePreferences.writeMotion(enabled))
    }

    function syncHomeTiltSetting(preference = window.HomePreferences?.readTilt()) {
      const toggle = byId('toggle-home-tilt')
      const status = byId('home-tilt-setting-status')
      if (!preference) {
        toggle.disabled = true
        status.textContent = '倾斜设置暂不可用，请刷新后重试'
        return
      }
      toggle.classList.toggle('active', preference.enabled)
      toggle.setAttribute('aria-checked', String(preference.enabled))
      toggle.setAttribute('aria-busy', String(settingsTiltPending))
      const failure = preference.state === 'unavailable' && preference.message && preference.message !== preference.note
        ? preference.message.replace(/[。；]$/, '') + '；' : ''
      status.textContent = settingsTiltPending ? '正在等待倾斜授权…' : preference.note ? failure + preference.note :
        (preference.enabled && !window.HomePreferences.readMotion().enabled ? '主页动效已关闭，倾斜当前暂停' :
         preference.enabled && settingsMotionQuery?.matches ? '系统已减少动态，倾斜当前暂停' :
         preference.enabled ? '已开启，返回主页后轻转手机试试' :
         preference.message === '已关闭' ? '' : preference.message)
    }

    function cancelHomeTiltPermission() {
      settingsTiltEpoch++
      cancelTiltDeadline?.(); cancelTiltDeadline = null
      if (!settingsTiltPending) return
      settingsTiltPending = false
      window.HomePreferences?.reportTilt('off', '授权已取消，可主动重试')
      syncHomeTiltSetting()
    }

    function toggleHomeTiltSetting() {
      if (!isSettingsAuthenticated()) {
        openSettingsLoginModal()
        return
      }
      const preferences = window.HomePreferences
      if (!preferences) return
      const previous = preferences.readTilt()
      if (settingsTiltPending || previous.enabled) {
        cancelHomeTiltPermission()
        preferences.writeTilt(false)
        preferences.reportTilt('off', '已关闭')
        syncHomeTiltSetting(preferences.readTilt())
        return
      }
      const unavailable = tiltUnavailable(preferences)
      if (unavailable) {
        preferences.reportTilt(previous.state === 'legacy' ? 'legacy' : 'unavailable', unavailable)
        syncHomeTiltSetting()
        return
      }
      const run = ++settingsTiltEpoch, token = settingsToken()
      settingsTiltPending = true
      syncHomeTiltSetting()
      const permission = requestTiltPermission()
      cancelTiltDeadline = context.scope.timeout(() => {
        cancelHomeTiltPermission()
        preferences.reportTilt('unavailable', '倾斜授权等待超时，可主动重试')
        syncHomeTiltSetting()
      }, 10000)
      Promise.resolve(permission).then(result => {
        if (!context.valid() || run !== settingsTiltEpoch) return
        if (!isSettingsAuthenticated() || token !== settingsToken() || document.hidden) {
          cancelHomeTiltPermission()
          return
        }
        cancelTiltDeadline?.(); cancelTiltDeadline = null
        settingsTiltPending = false
        if (result !== 'granted') {
          preferences.reportTilt('unavailable', '未获得倾斜授权，可主动重试')
          syncHomeTiltSetting()
          return
        }
        const saved = preferences.writeTilt(true, true)
        preferences.reportTilt(saved.note ? 'unavailable' : 'waiting-data', saved.note || '返回主页后，轻转手机试试')
        syncHomeTiltSetting(saved)
      }).catch(() => {
        if (!context.valid() || run !== settingsTiltEpoch) return
        cancelTiltDeadline?.(); cancelTiltDeadline = null
        settingsTiltPending = false
        preferences.reportTilt('unavailable', '倾斜授权暂不可用，可主动重试')
        syncHomeTiltSetting()
      })
    }

  async function setAboutExpanded(expanded) {
    setExpanded('about-content', 'about-row', expanded);
    if (!expanded || aboutLoaded) return;
    aboutLoaded = true;
    const res = await request('GET', '/api/app/persona-background');
    if (!context.valid()) return;
    byId('about-text').classList.remove('loading');
    byId('about-text').textContent = res.code === 0 && res.data?.background ? res.data.background : '暂时无法加载，请稍后重试';
  }
  function toggleAbout() { return setAboutExpanded(!byId('about-content').classList.contains('visible')); }
  async function handleLogout() {
    if (!isSettingsAuthenticated()) return openSettingsLoginModal();
    if (logoutBusy) return;
    logoutBusy = true;
    try { await services.ui.logout(); } finally { logoutBusy = false; }
  }
  context.scope.listen(root, 'click', event => {
    const button = event.target.closest('[data-settings-action]');
    if (!button || !root.contains(button)) return;
    const action = button.dataset.settingsAction;
    if (action === 'back') return context.router.back();
    if (action === 'password') return togglePasswordForm();
    if (action === 'eye') {
      const input = byId(button.dataset.input), hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password'; button.setAttribute('aria-label', hidden ? '隐藏密码' : '显示密码'); return;
    }
    if (action === 'motion') return toggleHomeMotionSetting();
    if (action === 'tilt') return toggleHomeTiltSetting();
    if (action === 'about') return run(toggleAbout());
    if (action === 'agent') return run(toggleSetting());
    if (action === 'save-password') return run(handleChangePassword());
    if (action === 'auth') return run(handleLogout());
  });
  context.scope.listen(root, 'keydown', event => {
    const button = event.target.closest('[role="button"]');
    if (button && ['Enter', ' '].includes(event.key)) { event.preventDefault(); button.click(); }
  });
  context.scope.listen(window, 'storage', event => {
    if (event.key === null || [HomePreferences.motionKey, HomePreferences.tiltKey, HomePreferences.tiltStatusKey].includes(event.key)) {
      cancelHomeTiltPermission(); syncHomeMotionSetting(true);
    }
    bgmSettings.refresh();
  });
  if (settingsMotionQuery?.addEventListener) context.scope.listen(settingsMotionQuery, 'change', () => syncHomeMotionSetting());
  else if (settingsMotionQuery?.addListener) {
    const listener = context.scope.guard(() => syncHomeMotionSetting());
    settingsMotionQuery.addListener(listener); context.cleanup(() => settingsMotionQuery.removeListener(listener));
  }
  context.cleanup(() => { cancelHomeTiltPermission(); clearPasswords(); }, {priority: 80});
  // Document hide/freeze and identity changes dispose this same scope through the shell.
  renderIdentity(); syncHomeMotionSetting();
  if (context.state?.collapsed?.about === false) run(setAboutExpanded(true));
  if (isSettingsAuthenticated()) { run(loadProfile()); run(loadSettings()); }
  return {
    captureState() { return { collapsed: { about: !byId('about-content').classList.contains('visible') } }; },
    unmount() { clearPasswords(); }
  };
}

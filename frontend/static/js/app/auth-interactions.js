import { PageScope } from './page-context.js';
import { policies } from './auth-service.js';

// Static SVGs from the approved duotone design; no icon runtime or network dependency.
const logoutConfirmationMarkup = `<div class="modal-box logout-confirm-panel">
        <div class="logout-confirm-heading">
          <div class="logout-confirm-symbol" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m16 17 5-5-5-5"></path><path d="M21 12H9"></path><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path></svg></div>
          <div><div class="logout-confirm-eyebrow">账号登录</div><h2 class="modal-title">退出当前账号？</h2></div>
        </div>
        <p class="modal-content">退出后将以访客身份浏览。<br>再次聊天时，需要重新登录。</p>
        <div class="logout-confirm-kept">
          <div class="logout-confirm-kept-row"><span class="logout-confirm-kept-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg></span><span>聊天记录与记忆会保留</span></div>
          <div class="logout-confirm-kept-row"><span class="logout-confirm-kept-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="8" cy="18" r="4"></circle><path d="M12 18V2l7 4"></path></svg></span><span>本机音乐设置不会重置</span></div>
        </div>
        <div class="modal-actions"><button class="modal-cancel" type="button" data-action="cancel">取消</button><button class="modal-confirm" type="button" data-action="confirm">退出登录</button></div>
      </div>`;

export const formRules = Object.freeze({ username: /^[a-zA-Z0-9]{6,20}$/,
  password: /^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z0-9!@#$%^&*]{8,20}$/ });

// Shared modal and standalone page use one attempt protocol with deliberately different success semantics.
export class AuthFormSession {
  constructor({ auth, router, mode, ownerId, current, routeCurrent = current, clearSensitive = () => {}, submitting = () => {} }) {
    Object.assign(this, { auth, router, mode, ownerId, ownerCurrent: current, routeCurrent, clearSensitive, onSubmitting: submitting });
    this.closed = false; this.busy = false; this.attempt = null; this.controller = new AbortController();
  }
  current() { return !this.closed && this.ownerCurrent(); }
  cancel() {
    this.auth.cancelAttempt(this.attempt); this.controller.abort(); this.controller = new AbortController();
    this.busy = false; this.clearSensitive();
  }
  dispose() { if (this.closed) return; this.closed = true; this.cancel(); }
  async submit(panel, values, { remember = false } = {}) {
    if (!this.current() || this.busy) return { status: 'ignored' };
    if (!formRules.username.test(values.username) || !formRules.password.test(values.password) ||
        panel !== 'login' && values.password !== values.password2) return { status: 'invalid' };
    this.busy = true; this.onSubmitting(panel, true);
    const attempt = this.auth.beginAttempt({ ownerId: this.ownerId, current: () => this.current() });
    this.attempt = attempt;
    const body = panel === 'reset' ? { username: values.username, new_password: values.password, confirm_password: values.password2 }
      : { username: values.username, password: values.password, ...(panel === 'register' ? { confirm_password: values.password2 } : {}) };
    try {
      const result = await this.auth.request('POST', '/api/auth/' + (panel === 'reset' ? 'reset-password' : panel), body,
        { authPolicy: policies.SILENT_VISITOR, signal: this.controller.signal, isCurrent: () => this.auth.attemptCurrent(attempt) });
      if (!this.auth.attemptCurrent(attempt)) return { status: 'ignored' };
      if (result.code !== 0) return { status: 'error', result };
      if (panel === 'reset' || panel === 'register' && this.mode === 'standalone') {
        this.clearSensitive(); return { status: 'success', next: 'login', username: values.username, panel };
      }
      if (!result.data?.token) return { status: 'error', result: { message: '认证响应缺少登录凭据' } };
      if (remember) this.auth.storage('setItem', 'remember_username', values.username);
      else this.auth.storage('removeItem', 'remember_username');
      if (!this.auth.accept(result.data.token, { attempt })) return { status: 'ignored' };
      const acceptedEpoch = this.auth.authEpoch; this.clearSensitive();
      await this.auth.restoration;
      if (this.auth.authEpoch !== acceptedEpoch) return { status: 'ignored' };
      if (this.mode === 'standalone') {
        if (!this.routeCurrent()) return { status: 'ignored' };
        await this.router.navigate('/pages/index.html', { reason: 'login', safety: true });
      }
      return { status: 'accepted' };
    } catch (error) {
      if (error.name === 'AbortError' || error.name === 'StaleRequestError' || !this.current()) return { status: 'ignored' };
      return { status: 'error', result: { message: '网络连接失败，请检查网络后重试' } };
    } finally {
      if (this.attempt === attempt && this.current()) { this.busy = false; this.onSubmitting(panel, false); }
    }
  }
}

export class AuthInteractions {
  constructor({ auth, router, overlays, root, win = window }) {
    Object.assign(this, { auth, router, overlays, root, win }); this.session = null; this.serial = 0;
    this.unsubscribe = auth.subscribe(() => this.closeLogin('identity'));
  }
  owner() {
    const slot = this.router.current, epoch = this.auth.authEpoch;
    return { slot, epoch, routeCurrent: () => this.router.current === slot,
      current: () => this.router.current === slot && this.auth.authEpoch === epoch };
  }
  clearPasswords() {
    const overlay = this.win.document.getElementById('auth-login-modal');
    overlay?.querySelectorAll('input[id*="password"]').forEach(input => { input.value = ''; input.type = 'password'; });
  }
  openLogin(options = {}) {
    const owner = this.owner();
    const entry = this.router.services.entry;
    if (entry?.pending) {
      const deferred = { owner, options }; this.deferredLogin = deferred;
      entry.finished.then(entered => {
        if (this.deferredLogin !== deferred) return;
        this.deferredLogin = null;
        if (entered && owner.current()) this.openLogin(options);
      });
      return true;
    }
    if (this.session && this.session.owner.slot !== owner.slot) this.closeLogin();
    if (!this.session) {
      const session = { id: ++this.serial, owner, panel: 'login' };
      session.form = new AuthFormSession({ auth: this.auth, router: this.router, mode: 'modal', ownerId: `modal:${session.id}`,
        current: () => this.session === session && owner.current(), routeCurrent: owner.routeCurrent,
        clearSensitive: () => { if (!this.session || this.session === session) this.clearPasswords(); }, submitting: (panel, value) => this.win.setAuthModalSubmitting(panel, value) });
      this.session = session;
      const element = this.win.ensureLoginModal(); this.root.append(element);
      session.overlay = this.overlays.register({ kind: 'login', ownerId: owner.slot?.context.scope.ownerId || 'document',
        background: owner.slot?.root, element, open: () => {}, close: () => this.win.renderCloseLoginModal() });
      owner.slot?.context.cleanup(() => { if (this.session === session) this.closeLogin('route'); }, { kind: 'modal', priority: 50 });
    }
    this.win.renderLoginModal({ ...options, onSuccess: undefined });
    this.session.overlay.open(); return true;
  }
  closeLogin(reason = 'user') {
    this.deferredLogin = null;
    const session = this.session; if (!session) return;
    this.session = null; session.form.dispose(); session.overlay.close({ reason }); session.overlay.dispose(); this.win.renderCloseLoginModal();
  }
  switchPanel(panel) {
    const session = this.session;
    if (session && session.panel !== panel) {
      this.win.setAuthModalSubmitting(session.panel, false); session.form.cancel(); session.panel = panel;
    }
    return this.win.renderSwitchAuthModalPanel(panel);
  }
  async submit(panel, event) {
    event.preventDefault(); const session = this.session;
    if (!session || !this.win.validateAuthModalPanel(panel)) return;
    const values = this.win.authModalPanelValues(panel), remember = !!this.win.document.getElementById('auth-modal-remember-me')?.checked;
    const outcome = await session.form.submit(panel, values, { remember });
    if (this.session !== session || !session.owner.current()) return;
    if (outcome.status === 'success' && outcome.next === 'login') {
      this.switchPanel('login'); this.win.document.getElementById('auth-modal-login-username').value = outcome.username;
      this.win.updateAuthModalSubmitState('login'); this.toast('密码重置成功，请登录', 'success');
    } else if (outcome.status === 'error') {
      const seconds = outcome.result.data?.remaining_seconds;
      this.toast(seconds ? '密码错误次数过多，请' + Math.ceil(seconds / 60) + '分钟后重试' : outcome.result.message || '操作失败', 'error');
    }
  }
  confirm(title, content, confirmText = '确认', isDanger = false, cancelText = '取消', presentation = 'default') {
    const owner = this.owner(), scope = new PageScope({ current: owner.current });
    return new Promise(resolve => {
      const element = this.win.document.createElement('div'); element.className = presentation === 'logout' ? 'modal-overlay logout-confirm-overlay' : 'modal-overlay';
      element.innerHTML = presentation === 'logout' ? logoutConfirmationMarkup : '<div class="modal-box"><div class="modal-title"></div><div class="modal-content"></div><div class="modal-actions"><button type="button" class="modal-cancel">取消</button><button type="button" class="modal-confirm">确认</button></div></div>';
      element.querySelector('.modal-title').textContent = title; element.querySelector('.modal-content').textContent = content;
      const yes = element.querySelector('.modal-confirm'); yes.textContent = confirmText; yes.classList.toggle('danger', isDanger);
      element.querySelector('.modal-cancel').textContent = cancelText;
      const no = element.querySelector('.modal-cancel');
      element.setAttribute('role', 'dialog'); element.setAttribute('aria-modal', 'true');
      element.querySelector('.modal-title').id = 'app-confirm-' + (++this.serial);
      element.setAttribute('aria-labelledby', element.querySelector('.modal-title').id);
      element.querySelector('.modal-content').id = 'app-confirm-content-' + this.serial;
      element.setAttribute('aria-describedby', element.querySelector('.modal-content').id);
      let settled = false, overlay;
      const settle = value => { if (settled) return; settled = true; overlay?.close({ reason: owner.current() ? 'user' : 'owner-expired' }); scope.dispose(); resolve(value && owner.current()); };
      scope.own(() => element.remove());
      scope.own(this.auth.subscribe(() => settle(false)));
      owner.slot?.context.cleanup(() => settle(false), { kind: 'confirm', priority: 50 });
      scope.listen(yes, 'click', () => settle(true)); scope.listen(element.querySelector('.modal-cancel'), 'click', () => settle(false));
      scope.listen(element, 'click', event => { if (event.target === element) settle(false); });
      scope.listen(element, 'keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); settle(false); }
        if (event.key === 'Tab') { event.preventDefault(); (this.win.document.activeElement === no ? yes : no).focus(); }
      });
      this.root.append(element);
      overlay = this.overlays.register({ kind: 'confirm', ownerId: owner.slot?.context.scope.ownerId || 'document', element,
        background: this.win.document.querySelector('.voice-entry:not([hidden])') || owner.slot?.root });
      scope.own(() => overlay.dispose()); overlay.open(); no.focus();
    });
  }
  async logout() {
    const owner = this.router.current?.context;
    const context = this.auth.requestContext({ signal: owner?.signal || owner?.scope.signal });
    if (!await this.confirm('退出当前账号？', '退出后将以访客身份浏览。\n再次聊天时，需要重新登录。', '退出登录', true, '取消', 'logout')) return false;
    try {
      context.assert();
      await this.auth.request('POST', '/api/auth/logout', undefined, { requestContext: context, authPolicy: policies.SILENT_VISITOR });
      context.assert(); this.auth.storage('removeItem', 'username'); this.auth.clear('logout');
      await this.auth.restoration; return true;
    } catch (error) { if (!['AbortError', 'StaleRequestError'].includes(error.name)) throw error; return false; }
  }
  toast(message, type = 'info', duration = 2000) {
    const owner = this.owner(), scope = new PageScope({ current: owner.current });
    const container = this.win.document.createElement('div'); container.className = 'toast-container';
    const item = this.win.document.createElement('div'); item.className = 'toast-item toast-' + type; item.textContent = message;
    container.append(item); this.root.append(container); scope.own(() => container.remove());
    scope.own(this.auth.subscribe(() => scope.dispose())); owner.slot?.context.cleanup(() => scope.dispose(), { kind: 'toast' });
    scope.timeout(() => { item.classList.add('toast-out'); scope.timeout(() => scope.dispose(), 400); }, duration);
  }
  dispose() { this.closeLogin(); this.unsubscribe(); }
}

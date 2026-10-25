import { tiltUnavailable, requestTiltPermission } from './tilt-permission.js';
import { loadingMarkup, populateLoadingParticles } from './entry-loading.js';

// Document owner: route remounts and BFCache do not create another opening.
export class EntryExperience {
  constructor({ shell, host = window, doc = document }) {
    Object.assign(this, { shell, host, doc });
    this.phase = 'loading'; this.epoch = 0; this.pending = true; this.cleanups = [];
    this.finished = new Promise(resolve => { this.resolveFinished = resolve; });
    this.pageReady = false; this.audioReady = false;
    this.startedAt = Date.now();
    this.preferences = host.HomePreferences;
    // A remembered sensor choice never starts listening before this visit's choice.
    this.preferences.writeTilt(false);
    this.element = doc.createElement('section');
    this.element.id = 'app-entry'; this.element.className = 'app-entry';
    this.element.tabIndex = -1;
    this.element.setAttribute('role', 'dialog'); this.element.setAttribute('aria-modal', 'true');
    this.element.setAttribute('aria-labelledby', 'app-entry-title');
    this.element.innerHTML = loadingMarkup;
    shell.overlayRoot.append(this.element);
    this.primary = this.element.querySelector('#app-entry-primary');
    this.primaryLabel = this.element.querySelector('#app-entry-primary-label');
    this.direct = this.element.querySelector('#app-entry-direct');
    this.note = this.element.querySelector('#app-entry-note');
    this.loadingStage = this.element.querySelector('.app-entry-progress-stage');
    this.layout = this.element.querySelector('.app-entry-actions');
    this.progress = this.element.querySelector('#app-entry-progress');
    this.progressFill = this.element.querySelector('#home-loading-bar-fill');
    this.progressPercent = this.element.querySelector('#home-loading-percent');
    this.loadingMessage = this.element.querySelector('#home-loading-message');
    populateLoadingParticles(this.element, host.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
    this.listen(this.loadingStage, 'transitionend', event => {
      if (event.target === this.loadingStage && event.propertyName === 'opacity') this.finishLoading();
    });
    for (const image of this.element.querySelectorAll('img')) this.listen(image, 'error', () => { image.hidden = true; });
    this.overlay = shell.services.overlays.register({ kind: 'entry', ownerId: 'document-entry',
      element: this.element, background: shell.root, open() {}, close() {} });
    this.overlay.open();
    this.setPhase('loading');
    this.listen(this.primary, 'click', () => this.enter());
    this.listen(this.direct, 'click', () => this.skip());
    this.listen(doc, 'keydown', event => {
      if (!this.pending || this.phase === 'leaving' || event.key !== 'Tab') return;
      if (this.layout.inert) { event.preventDefault(); return; }
      const buttons = [this.primary, this.direct].filter(button => !button.disabled);
      if (!buttons.length) { event.preventDefault(); return; }
      const first = buttons[0], last = buttons.at(-1);
      if (event.shiftKey && (doc.activeElement === first || !this.element.contains(doc.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (doc.activeElement === last || !this.element.contains(doc.activeElement))) { event.preventDefault(); first.focus(); }
    });
    this.unsubscribeAuth = shell.services.auth.subscribe(() => this.cancelPermission());
    this.readyTimer = host.setTimeout(() => this.ready(true), 8000);
    this.progressTimer = host.setInterval(() => this.ready(), 60);
    Promise.resolve(shell.services.audio.prepareEntry()).finally(() => {
      if (!this.pending) return;
      this.audioReady = true; this.ready();
    });
    this.element.focus({ preventScroll: true });
  }
  listen(target, type, listener) { target.addEventListener(type, listener); this.cleanups.push(() => target.removeEventListener(type, listener)); }
  setPhase(phase) { this.phase = phase; this.element.dataset.phase = phase; this.doc.documentElement.dataset.appEntry = phase; }
  prepared() { if (!this.pending) return; this.pageReady = true; this.ready(); }
  ready(force = false) {
    if (!this.pending || this.phase !== 'loading') return;
    // Preserve the original loader cadence (3s fill + 500ms full-bar hold).
    // This is its visual preparation progress, not a byte download measurement.
    const elapsed = Date.now() - this.startedAt, prepared = this.pageReady && this.audioReady;
    this.loadingMessage.textContent = ['我在。别急。', '马上就见面了。', '来了？我等你一会儿了。'][Math.floor(elapsed / 1500) % 3];
    const complete = force || prepared && elapsed >= 3000;
    const progress = complete ? 100 : Math.min(97, elapsed / 3000 * (prepared ? 100 : 85));
    this.progressFill.style.width = progress + '%';
    this.progressPercent.textContent = Math.round(progress) + '%';
    this.progress.setAttribute('aria-valuenow', String(Math.round(progress)));
    if (!complete) return;
    this.host.clearInterval(this.progressTimer);
    this.host.clearTimeout(this.readyTimer); this.setPhase('settling');
    const reduced = this.host.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    this.element.querySelector('#home-loading-screen').setAttribute('aria-busy', 'false');
    // Only the footer crossfades; keep artwork, text and mask mounted in place.
    this.progressFillTimer = this.host.setTimeout(() => {
      if (!this.pending || this.phase !== 'settling') return;
      this.loadingStage.classList.add('is-fading'); this.layout.classList.add('is-visible');
      this.progressFadeTimer = this.host.setTimeout(() => this.finishLoading(), reduced ? 180 : 650);
    }, reduced ? 0 : 500);
  }
  finishLoading() {
    if (!this.pending || this.phase !== 'settling') return;
    this.host.clearTimeout(this.progressFadeTimer);
    this.loadingStage.hidden = true; this.layout.inert = false; this.layout.removeAttribute('aria-hidden'); this.setPhase('choice');
    this.primaryLabel.textContent = '开启并进入'; this.primary.disabled = false;
  }
  enter() {
    if (this.phase !== 'choice' || this.doc.hidden) return;
    const run = ++this.epoch, identity = this.shell.services.auth.authEpoch;
    this.setPhase('permission'); this.primary.disabled = true; this.direct.disabled = true;
    this.primaryLabel.textContent = '等待授权…';
    // Invoke both privileged APIs in this click. Never await one before the other.
    const unavailable = tiltUnavailable(this.preferences, this.host);
    const permission = unavailable ? Promise.resolve('unavailable') : requestTiltPermission(this.host);
    const music = this.shell.services.audio.enter({ music: true });
    Promise.resolve(music).catch(() => {}); // The player exposes its real failure/retry state.
    const current = () => this.pending && this.phase === 'permission' && run === this.epoch && !this.doc.hidden && identity === this.shell.services.auth.authEpoch;
    // Do not auto-enter behind a still-open system prompt. If the browser never
    // settles, expose an explicit skip after its existing permission wait budget.
    this.permissionTimer = this.host.setTimeout(() => {
      if (!current()) return;
      this.direct.disabled = false; this.note.textContent = '仍在等待系统授权，也可以直接进入。';
    }, 10000);
    Promise.resolve(permission).then(result => {
      if (!current()) return;
      if (result === 'granted') {
        const saved = this.preferences.writeTilt(true, true);
        this.preferences.reportTilt(saved.note ? 'unavailable' : 'waiting-data', saved.note || '轻转手机，正在等待方向数据…');
      } else {
        this.preferences.writeTilt(false);
        this.preferences.reportTilt('unavailable', unavailable || '未获得倾斜授权，可在设置中重试');
      }
      this.reveal();
    }, () => {
      if (!current()) return;
      this.preferences.writeTilt(false); this.preferences.reportTilt('unavailable', '倾斜授权暂不可用，可在设置中重试');
      this.reveal();
    });
  }
  skip() {
    if (!this.pending || this.phase === 'leaving' || this.layout.inert || this.direct.disabled) return;
    ++this.epoch; this.preferences.writeTilt(false); this.preferences.reportTilt('off', '已关闭');
    this.shell.services.audio.enter({ music: false }); this.reveal();
  }
  reveal() {
    if (!this.pending || this.phase === 'leaving') return;
    this.host.clearTimeout(this.readyTimer); this.host.clearTimeout(this.permissionTimer);
    this.host.clearTimeout(this.progressFillTimer); this.host.clearTimeout(this.progressFadeTimer);
    this.setPhase('leaving'); this.primary.disabled = true; this.direct.disabled = true;
    this.element.classList.add('is-leaving');
    const reduced = this.host.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    this.exitTimer = this.host.setTimeout(() => this.finish(), reduced ? 140 : 850);
  }
  finish() {
    if (!this.pending) return;
    this.pending = false; this.setPhase('done'); this.disposeView();
    // Home scene starts only after the veil has cleared, using the current angle as baseline.
    this.host.dispatchEvent(new Event('home-startup-change'));
    if (!this.doc.hidden) {
      const target = this.shell.overlayRoot.querySelector('.is-open button:not([disabled])') || this.shell.root.querySelector('button:not([disabled]), [tabindex="0"]');
      target?.focus({ preventScroll: true });
    }
    this.resolveFinished(true);
  }
  cancelPermission() {
    if (this.phase !== 'permission') return;
    ++this.epoch; this.host.clearTimeout(this.permissionTimer);
    this.shell.services.audio.holdEntry(); this.preferences.writeTilt(false);
    this.setPhase('choice'); this.primary.disabled = false; this.direct.disabled = false;
    this.primaryLabel.textContent = '开启并进入'; this.note.textContent = '授权已取消，可以重新开启或直接进入。';
  }
  suspend() { if (this.phase === 'leaving') this.finish(); else this.cancelPermission(); }
  disposeView() {
    this.host.clearInterval(this.progressTimer);
    for (const timer of [this.readyTimer, this.permissionTimer, this.progressFillTimer, this.progressFadeTimer, this.exitTimer]) this.host.clearTimeout(timer);
    this.unsubscribeAuth?.(); for (const cleanup of this.cleanups.splice(0)) cleanup();
    this.overlay.dispose(); this.element.remove();
  }
  destroy() {
    if (this.phase === 'destroyed') return;
    ++this.epoch; this.pending = false; this.phase = 'destroyed';
    this.disposeView(); this.resolveFinished(false); delete this.doc.documentElement.dataset.appEntry;
  }
}

export function createHomeStartup(context) {
  const { root, scope, services } = context;
  // The document opening owns the only loading/entry layer in AppShell.
  if (services.entry) root.querySelector('#home-loading-screen')?.remove();
  const savedStart = context.reason === 'resume' && context.state?.loaderStartedAt;
  const startedAt = Number.isFinite(savedStart) ? Math.min(savedStart, Date.now()) : Date.now();
  const state = { startedAt, coreDeadline: startedAt + 5000, overlayDeadline: startedAt + 8000,
    phase: 'loading', releases: 0, disposed: false, sceneMode: document.documentElement.dataset.homeSceneMode === 'legacy' ? 'legacy' : 'dynamic' };
  const legacyBackground = '/static/images/Index/Index.png';
  state.storage = (kind, operation, key, value) => {
    try { return { ok: true, value: window[kind][operation](key, value) }; } catch (_) { return { ok: false, value: null }; }
  };
  state.auth = () => { const auth = services.auth.refresh(); return { known: auth.known, token: services.auth.readToken(), available: auth.available, authEpoch: auth.authEpoch }; };
  state.rememberAuth = () => {}; // Identity writes belong only to AuthService.
  state.useLegacyScene = () => {
    if (!context.valid() || state.sceneMode === 'legacy') return;
    state.sceneMode = 'legacy'; document.documentElement.dataset.homeSceneMode = 'legacy';
    const background = root.querySelector('.home-scene-background');
    if (background) { background.hidden = false; background.src = legacyBackground; }
    root.querySelector('.home-scene-character')?.classList.remove('home-scene-core');
    const loader = root.querySelector('#home-loading-hero'); if (loader) { loader.hidden = false; loader.src = legacyBackground; }
    window.dispatchEvent(new Event('home-scene-mode-change'));
  };
  state.coreImageFailed = image => {
    if (!context.valid()) return;
    image.dataset.coreFailed = '1'; const images = [...root.querySelectorAll('.home-scene-core')];
    if (state.sceneMode === 'dynamic' && images.length === 2 && images.every(item => item.dataset.coreFailed === '1')) state.useLegacyScene();
  };
  state.mountScene = () => {
    const scene = root.querySelector('.home-scene'), template = root.querySelector('#home-scene-markup');
    if (!scene || !template) return;
    const content = template.content.cloneNode(true);
    if (state.sceneMode === 'legacy') {
      content.querySelector('.home-scene-background').src = legacyBackground;
      const character = content.querySelector('.home-scene-character'); character.removeAttribute('src'); character.classList.remove('home-scene-core'); character.hidden = true;
      content.querySelectorAll('[data-src]').forEach(image => image.removeAttribute('data-src'));
    }
    for (const image of content.querySelectorAll('.home-scene-core')) scope.listen(image, 'error', () => {
      image.hidden = true; if (image.classList.contains('home-scene-character')) image.parentElement.classList.add('home-scene-character-failed'); state.coreImageFailed(image);
    });
    scene.appendChild(content); template.remove();
    const loader = root.querySelector('#home-loading-hero');
    if (loader) { scope.listen(loader, 'error', () => { loader.hidden = true; }); loader.src = root.querySelector('.home-scene-background').src; }
  };
  state.complete = force => {
    if (state.disposed || !context.valid()) return;
    root.querySelector('#home-loading-screen')?.remove(); root.querySelector('#main-content')?.classList.add('content-loaded');
    root.querySelector('.h5-home-page')?.classList.add('is-enter-active', 'is-startup-ready');
    if (state.phase === 'ready') return;
    state.phase = 'ready'; state.releases++; state.forced = !!force; state.releasedAt = Date.now(); watchdog();
    state.storage('sessionStorage', 'setItem', 'lxm_home_loader_done', '1');
    services.audio.homeLoading = false; services.audio.preparation?.update?.();
    services.entry?.prepared();
    window.dispatchEvent(new Event('home-startup-change'));
  };
  state.checkDeadline = () => { if (state.phase !== 'ready' && Date.now() >= state.overlayDeadline) state.complete(true); };
  const watchdog = scope.timeout(() => state.complete(true), Math.max(0, state.overlayDeadline - Date.now()));
  window.HomeStartup = state; services.audio.homeLoading = true;
  context.cleanup(() => { state.disposed = true; watchdog(); if (window.HomeStartup === state) delete window.HomeStartup; });
  state.mountScene(); return state;
}

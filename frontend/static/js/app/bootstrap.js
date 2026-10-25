import { SharedResources } from './shared-resources.js';
import { AuthService } from './auth-service.js';
import { Router, routeDefinitions, resolveRoute } from './router.js';
import { AppHistory } from './history.js';
import { OverlayManager } from './overlay-manager.js';
import { AuthInteractions } from './auth-interactions.js';
import { createAudioService } from './audio-service.js';
import { DocumentLifecycle } from './lifecycle.js';
import { EntryExperience } from './entry-experience.js';

// A document owns shared services. Individual routes receive them through PageContext.
export async function start({ resources, root, overlayRoot, initialPage }) {
  if (window.AppShell) {
    if (window.AppShell.buildId !== resources.buildId) throw new Error('同一文档不能切换构建');
    return window.AppShell;
  }
  const shared = new SharedResources(resources);
  await Promise.all(['css/common.css', 'css/h5-theme.css', 'css/app-shell.css'].map(key => shared.style(key)));
  const shell = { buildId: resources.buildId, resources, shared, root, overlayRoot, services: { resources, shared } };
  window.AppShell = shell;
  let loginInput;
  const auth = new AuthService({ beforeChange: change => {
    const slot = shell.router?.current;
    loginInput = change.reason === 'login' && change.previous.principalId === null ? shell.router?.captureTransientInput() : undefined;
    if (slot && change.previous.principalId === change.principalId && change.reason !== 'logout') shell.services.history?.capture(slot);
  }, clearPrivate: () => {
    shell.services.history?.snapshots.clear();
    const slot = shell.router?.current;
    if (slot) { slot.context.scope.dispose('identity-change'); slot.root.replaceChildren(); }
  }, onChange: change => {
    // A 401 owns its rollback/navigation policy and must not race an automatic remount.
    if (shell.lifecycle?.frozen || !shell.router?.current || change.reason === 'unauthorized' || change.reason === 'login' && shell.router.current.route.name === 'login') return;
    return shell.router.navigate(location.href, { replace: true, force: true, reason: 'auth', safety: true, state: loginInput });
  } });
  shell.services.auth = auth;
  const history = new AppHistory({ buildId: resources.buildId, auth });
  const overlays = new OverlayManager({ history }); history.overlays = overlays;
  Object.assign(shell.services, { history, overlays });
  shell.router = new Router({ root, services: shell.services }); auth.router = shell.router;
  shell.services.ui = new AuthInteractions({ auth, router: shell.router, overlays, root: overlayRoot }); auth.ui = shell.services.ui;
  await shared.script('js/api.js');
  const forcedInitial = initialPage === 'login' ? 'login' : undefined;
  const initial = forcedInitial || resolveRoute(location.href, location.href)?.name || 'index';
  const hasPage = resources.resources.has(routeDefinitions[initial].module);
  shell.services.audio = await createAudioService({ shared, initialRoute: initial, entryPending: hasPage });
  shell.services.voice = shell.services.audio.callOwners;
  if (hasPage) shell.services.entry = new EntryExperience({ shell });
  shell.destroy = () => { shell.lifecycle?.dispose(); shell.services.entry?.destroy(); void shell.services.audio.destroy(); shell.services.ui.dispose(); shell.router.dispose(); history.dispose(); auth.dispose(); shared.dispose(); };
  root.dataset.build = resources.buildId;
  root.textContent = '页面准备中…';
  shell.initialURL = forcedInitial ? '/pages/login.html' : location.pathname === '/' ? '/pages/index.html' : location.href;
  // Entry may become interactive before a slow route import settles. The whole
  // document (including audio after entry) needs lifecycle ownership now.
  shell.lifecycle = new DocumentLifecycle({ shell });
  // During the staged, isolated migration a route is activated only when its real
  // module exists. Production entry activation remains a separate release operation.
  if (hasPage) {
    await shell.router.start({ initialPage: forcedInitial });
    if (shell.router.current && (shell.router.current.route.name !== 'index' || shell.router.current.phase === 'error')) shell.services.entry.prepared();
  }
  return shell;
}

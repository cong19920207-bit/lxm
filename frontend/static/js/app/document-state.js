const mobile = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
// Original page attributes. Per-page CSS is scoped separately to [data-app-page].
export const layouts = Object.freeze({
  index: { title: '林小梦', bodyClass: 'h5-skin home-scene-page', viewport: 'width=device-width, initial-scale=1.0, viewport-fit=cover', fullscreen: true, html: { 'data-home-scene-mode': 'dynamic' }, scroll: null },
  chat: { title: '林小梦 - 聊天', bodyClass: 'h5-skin chat-immersive', viewport: mobile, fullscreen: true, scroll: '#chat-messages' },
  feed: { title: '林小梦 - 朋友圈', bodyClass: 'h5-skin feed-page', viewport: mobile, scroll: 'document' },
  diary: { title: '林小梦 - 日记', bodyClass: 'h5-skin diary-page', viewport: mobile, scroll: 'document' },
  memory: { title: '林小梦 - 记忆星云', bodyClass: 'h5-skin memory-nebula-page', viewport: mobile + ', viewport-fit=cover', fullscreen: true, scroll: '.nebula-sheet-body' },
  relationship: { title: '林小梦 - 我们的关系', bodyClass: 'h5-skin relationship-page', viewport: mobile, scroll: 'document' },
  settings: { title: '林小梦 - 设置', bodyClass: 'h5-skin settings-soft-page', viewport: mobile, scroll: 'document' },
  login: { title: '林小梦 - 登录', bodyClass: 'h5-skin', viewport: mobile, scroll: 'document' }
});

export function installDocumentState(name, { doc = document } = {}) {
  const layout = layouts[name]; if (!layout) throw new Error('未知页面布局：' + name);
  const saved = { title: doc.title, html: {}, body: {} };
  for (const key of ['class', 'style', 'data-home-scene-mode', 'data-app-route']) saved.html[key] = doc.documentElement.getAttribute(key);
  for (const key of ['class', 'style']) saved.body[key] = doc.body.getAttribute(key);
  let viewport = doc.querySelector('meta[name="viewport"]'); const existed = !!viewport;
  if (!viewport) { viewport = doc.createElement('meta'); viewport.name = 'viewport'; doc.head.append(viewport); }
  saved.viewport = viewport.getAttribute('content'); doc.title = layout.title;
  doc.body.className = layout.bodyClass; doc.body.removeAttribute('style');
  doc.documentElement.removeAttribute('style'); doc.documentElement.removeAttribute('data-home-scene-mode');
  doc.documentElement.className = ''; doc.documentElement.dataset.appRoute = name;
  for (const [key, value] of Object.entries(layout.html || {})) doc.documentElement.setAttribute(key, value);
  if (layout.fullscreen) for (const element of [doc.documentElement, doc.body]) { element.style.height = '100%'; element.style.overflow = 'hidden'; }
  viewport.setAttribute('content', layout.viewport);
  let restored = false;
  return () => {
    if (restored) return; restored = true; doc.title = saved.title;
    for (const [target, attributes] of [[doc.documentElement, saved.html], [doc.body, saved.body]]) {
      for (const [key, value] of Object.entries(attributes)) value == null ? target.removeAttribute(key) : target.setAttribute(key, value);
    }
    if (!existed) viewport.remove();
    else if (saved.viewport == null) viewport.removeAttribute('content');
    else viewport.setAttribute('content', saved.viewport);
  };
}

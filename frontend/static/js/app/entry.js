// The shell pins this import-free bootstrap with SRI. Verify the manifest and loader before import.
async function checked(url, expected, type) {
  const response = await fetch(url, { credentials: 'same-origin', redirect: 'error' });
  if (!response.ok) throw new Error('构建资源不可用：' + response.status);
  const mime = (response.headers.get('content-type') || '').split(';')[0].trim();
  if (mime !== type && !(type === 'text/javascript' && mime === 'application/javascript')) throw new Error('构建资源类型错误');
  const bytes = await response.arrayBuffer();
  const actual = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
  if (actual !== expected) throw new Error('构建资源摘要不符');
  return bytes;
}

try {
  const config = JSON.parse(document.getElementById('app-build').textContent);
  if (!/^aps1-[a-f0-9]{24}$/.test(config.buildId) || config.baseURL !== `/static/app-builds/${config.buildId}/` ||
      config.manifestURL !== config.baseURL + 'manifest.json') throw new Error('非法构建描述');
  const manifest = JSON.parse(new TextDecoder().decode(await checked(config.manifestURL, config.manifestSHA256, 'application/json')));
  const loader = manifest.resources?.['js/app/resources.js'];
  if (manifest.buildId !== config.buildId || loader?.url !== config.baseURL + 'js/app/resources.js') throw new Error('构建依赖缺失');
  await checked(loader.url, loader.sha256, 'text/javascript');
  const { ResourceLoader } = await import(loader.url);
  const resources = new ResourceLoader(config, manifest);
  const { start } = await resources.module('js/app/bootstrap.js');
  const initialPage = document.querySelector('meta[name="lxm-initial-page"]')?.content;
  await start({ initialPage, resources, root: document.getElementById('app-root'), overlayRoot: document.getElementById('app-overlays') });
} catch (error) {
  window.AppShell?.services.entry?.destroy();
  const root = document.getElementById('app-root');
  root.replaceChildren();
  const message = document.createElement('p'); message.textContent = '页面资源加载失败，请重试。';
  const button = document.createElement('button'); button.textContent = '重新加载'; button.onclick = () => location.reload();
  root.append(message, button); console.error(error);
}

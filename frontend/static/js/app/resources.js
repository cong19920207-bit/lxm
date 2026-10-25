// No network or DOM work on import. One immutable manifest belongs to one document.
const hash = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
  .map(n => n.toString(16).padStart(2, '0')).join('');
const mimeType = value => (value || '').split(';')[0].trim().toLowerCase();
const compatible = (actual, expected) => actual === expected ||
  (expected === 'text/javascript' && actual === 'application/javascript');

export class ResourceLoader {
  constructor(config, manifest, { fetcher = globalThis.fetch.bind(globalThis), origin = location.origin } = {}) {
    if (config.schema !== 1 || manifest.schema !== 1 || manifest.buildId !== config.buildId ||
        manifest.baseURL !== config.baseURL || !/^aps1-[a-f0-9]{24}$/.test(config.buildId) ||
        config.baseURL !== `/static/app-builds/${config.buildId}/` || !manifest.resources) {
      throw new Error('构建描述不匹配');
    }
    this.buildId = config.buildId; this.baseURL = config.baseURL; this.origin = origin;
    this.fetcher = fetcher; this.pending = new Map(); this.resources = new Map();
    for (const [key, item] of Object.entries(manifest.resources)) {
      if (key.startsWith('/') || key.split('/').some(p => !p || p === '.' || p === '..') ||
          item.url !== this.baseURL + key || !/^[a-f0-9]{64}$/.test(item.sha256) ||
          !Array.isArray(item.dependencies) || !Number.isSafeInteger(item.bytes) || item.bytes < 0) {
        throw new Error('非法构建资源：' + key);
      }
      this.resources.set(key, Object.freeze({ ...item, dependencies: Object.freeze([...item.dependencies]) }));
    }
    for (const [key, item] of this.resources) for (const dep of item.dependencies) {
      if (!this.resources.has(dep)) throw new Error(`缺少构建依赖：${key} → ${dep}`);
    }
  }
  descriptor(key) {
    const item = this.resources.get(key);
    if (!item) throw new Error('构建中没有资源：' + key);
    return item;
  }
  url(key) { return new URL(this.descriptor(key).url, this.origin).href; }
  verify(key) {
    if (!this.pending.has(key)) {
      const task = this.read(key).catch(error => { this.pending.delete(key); throw error; });
      this.pending.set(key, task);
    }
    return this.pending.get(key);
  }
  async read(key) {
    const item = this.descriptor(key), url = this.url(key);
    const response = await this.fetcher(url, { credentials: 'same-origin', redirect: 'error' });
    if (!response.ok) throw new Error(`资源不可用 (${response.status})：${key}`);
    if (!compatible(mimeType(response.headers.get('content-type')), item.mime)) throw new Error('资源类型错误：' + key);
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength !== item.bytes || await hash(bytes) !== item.sha256) throw new Error('资源摘要不符：' + key);
    return bytes;
  }
  async graph(key, visited = new Set()) {
    if (visited.has(key)) return;
    visited.add(key);
    const item = this.descriptor(key);
    // Images/fonts stay build-locked and descriptor-validated, but their native
    // loading/error paths belong to the page (including image deadlines/fallback).
    // Awaiting every decorative dependency would defeat those contracts and lazy loading.
    const blocking = item.dependencies.filter(dep => !/^(?:image\/|font\/)/.test(this.descriptor(dep).mime));
    await Promise.all([this.verify(key), ...blocking.map(dep => this.graph(dep, visited))]);
  }
  async module(key) { await this.graph(key); return import(this.url(key)); }
  async text(key) { await this.graph(key); return new TextDecoder().decode(await this.verify(key)); }
  async script(key) {
    await this.graph(key);
    const script = document.createElement('script'); script.src = this.url(key); script.async = false;
    script.integrity = 'sha256-' + btoa(String.fromCharCode(...Uint8Array.from(this.descriptor(key).sha256.match(/../g), x => parseInt(x, 16))));
    script.crossOrigin = 'anonymous';
    await new Promise((resolve, reject) => {
      script.onload = resolve; script.onerror = () => reject(new Error('脚本装载失败：' + key));
      document.head.append(script);
    }).catch(error => { script.remove(); throw error; });
    return () => script.remove();
  }
  async style(key) {
    await this.graph(key);
    const link = document.createElement('link'); link.rel = 'stylesheet'; link.href = this.url(key);
    link.integrity = 'sha256-' + btoa(String.fromCharCode(...Uint8Array.from(this.descriptor(key).sha256.match(/../g), x => parseInt(x, 16))));
    link.crossOrigin = 'anonymous';
    await new Promise((resolve, reject) => {
      link.onload = resolve; link.onerror = () => reject(new Error('样式装载失败：' + key));
      document.head.append(link);
    }).catch(error => { link.remove(); throw error; });
    return () => link.remove();
  }
}

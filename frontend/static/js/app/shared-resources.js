// Global styles/classic compatibility libraries are service-owned, never page-owned.
export class SharedResources {
  constructor(resources) { this.resources = resources; this.tasks = new Map(); this.releases = []; this.closed = false; }
  once(kind, key) {
    if (this.closed) return Promise.reject(new Error('文档资源已释放'));
    const id = kind + ':' + key;
    if (!this.tasks.has(id)) this.tasks.set(id, this.resources[kind](key).then(release => {
      if (typeof release === 'function') this.closed ? release() : this.releases.push(release);
      return release;
    }).catch(error => { this.tasks.delete(id); throw error; }));
    return this.tasks.get(id);
  }
  style(key) { return this.once('style', key); }
  script(key) { return this.once('script', key); }
  dispose() { if (this.closed) return; this.closed = true; for (const release of this.releases.splice(0).reverse()) release(); }
}

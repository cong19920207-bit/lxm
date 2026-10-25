const fields = Object.freeze({
  index: ['scroll', 'focus', 'loaderDone', 'loaderStartedAt', 'deviceSelection'],
  chat: ['scroll', 'focus', 'draft', 'anchor', 'submissionKeys'],
  feed: ['scroll', 'focus', 'items', 'cursor', 'expandedIds'],
  diary: ['scroll', 'focus', 'items', 'cursor', 'expandedIds', 'readIds', 'hasMore'],
  memory: ['scroll', 'focus', 'view', 'selectedId'],
  relationship: ['scroll', 'focus', 'rightsCollapsed', 'cursor'],
  settings: ['scroll', 'focus', 'collapsed', 'deviceSelection'],
  login: ['scroll', 'remember', 'username']
});
const forbidden = /^(?:password|confirmPassword|oldPassword|newPassword|token|accessToken|refreshToken|apiKey|credential|authorization|secret|reader|controller|timer|socket|stream|renderer|texture|submitting|attempt|authAttempt)$/i;
function plain(value, depth = 0) {
  if (depth > 12) throw new TypeError('快照嵌套过深');
  if (value == null || typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.length <= 65536) return value;
  if (Array.isArray(value) && value.length <= 500) return value.map(item => plain(item, depth + 1));
  if (typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    const output = {};
    for (const [key, item] of Object.entries(value)) {
      if (forbidden.test(key.replace(/[_-]/g, '')) || key === '__proto__' || key === 'constructor' || key === 'prototype') throw new TypeError('快照包含敏感或运行字段');
      output[key] = plain(item, depth + 1);
    }
    return output;
  }
  throw new TypeError('快照只能包含有界普通JSON');
}

export class PageStateStore {
  constructor({ schema = 1, maxEntries = 16, maxBytes = 2 * 1024 * 1024, maxEntryBytes = 128 * 1024 } = {}) {
    this.schema = schema; this.maxEntries = maxEntries; this.maxBytes = maxBytes; this.maxEntryBytes = maxEntryBytes;
    this.entries = new Map(); this.bytes = 0;
  }
  key(entryId, principalId) { return JSON.stringify([this.schema, entryId, principalId]); }
  delete(key) { const item = this.entries.get(key); if (item) this.bytes -= item.bytes; this.entries.delete(key); }
  set(entryId, principalId, page, value) {
    if (!entryId || principalId === undefined || !fields[page]) return false;
    const key = this.key(entryId, principalId); this.delete(key);
    try {
      const selected = {};
      for (const field of fields[page]) if (value?.[field] !== undefined) selected[field] = plain(value[field]);
      if (page === 'login' && !selected.remember) delete selected.username;
      const json = JSON.stringify(selected), bytes = new TextEncoder().encode(json).byteLength;
      if (bytes > this.maxEntryBytes || bytes > this.maxBytes) return false;
      this.entries.set(key, { json, bytes, page }); this.bytes += bytes;
      while (this.entries.size > this.maxEntries || this.bytes > this.maxBytes) this.delete(this.entries.keys().next().value);
      return true;
    } catch (_) { return false; }
  }
  get(entryId, principalId, page, schema = this.schema) {
    if (schema !== this.schema || principalId === undefined) return undefined;
    const key = this.key(entryId, principalId), item = this.entries.get(key);
    if (!item || item.page !== page) return undefined;
    this.entries.delete(key); this.entries.set(key, item); return JSON.parse(item.json);
  }
  clear() { this.entries.clear(); this.bytes = 0; }
  inspect() { return { count: this.entries.size, bytes: this.bytes, schema: this.schema }; }
}

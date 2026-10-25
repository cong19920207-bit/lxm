// An original-request capability. No page, DOM, current-account token or new dial key.
// The existing create endpoint is the protocol's same-key lookup; never consume its ticket.
export function createCallVerification({ identity, attemptKey, apiBase = '', fetcher = (...args) => fetch(...args), now = () => Date.now() }) {
  let callId = null, payload = null, startedAt = null, inFlight = 0, evidence = null, allowConnectedEnd = false;
  const current = () => identity.current();
  const unknown = () => ({ status: 'unknown', callId });
  // These explicit failures occur after the server's same-key replay lookup and
  // before allocation. 401, banned, generic 4xx/5xx and missing bodies prove nothing.
  const preflightReasons = new Set(['browser_unsupported', 'microphone_denied', 'dial_cooldown', 'disabled',
    'maintenance', 'soft_stop', 'not_allowlisted', 'crisis_config_unavailable', 'quota_empty', 'provider_unavailable', 'user_busy']);
  function rejected(response, body) {
    if (current() && !callId && response.status !== 401 && !response.ok && body.code === response.status && preflightReasons.has(body.data?.block_reason)) {
      evidence = { kind: 'not-created', reason: body.data.block_reason }; return true;
    }
    return false;
  }
  async function request(path, options = {}) {
    if (!current()) throw new Error('Original request identity expired');
    const response = await fetcher(apiBase + path, { ...options, cache: 'no-store', headers: identity.headers({ 'Content-Type': 'application/json', ...options.headers }) });
    const body = await response.json();
    if (!current()) throw new Error('Original request identity expired');
    return { response, body };
  }
  function bind(id) {
    if (!id) return;
    if (callId && callId !== id) throw new Error('Original call ID cannot change');
    callId = id;
  }
  return Object.freeze({
    start(value) { if (!payload) { payload = JSON.stringify(value); startedAt = now(); } else if (payload !== JSON.stringify(value)) throw new Error('Original payload cannot change'); inFlight++; evidence = null; },
    settle() { inFlight = Math.max(0, inFlight - 1); },
    rejected,
    bind,
    authorizeEnd() { allowConnectedEnd = true; },
    ended(id) { if (!current()) return; bind(id); evidence = { kind: 'end', callId: id, cleanup_pending: false }; },
    async verify() {
      if (startedAt === null) return { status: 'complete', evidence: { kind: 'not-created' } };
      if (evidence) return { status: 'complete', callId, evidence };
      if (!current() || inFlight) return unknown();
      try {
        if (!callId) {
          // The server expires replay records after 24h. Never recreate an expired attempt.
          if (now() - startedAt >= 24 * 60 * 60 * 1000) return unknown();
          const result = await request('/api/voice/calls', { method: 'POST', headers: { 'Idempotency-Key': attemptKey }, body: payload });
          if (rejected(result.response, result.body)) return { status: 'complete', evidence };
          if (!result.response.ok || result.body.code !== 0 || !result.body.data?.call_id) return unknown();
          bind(result.body.data.call_id);
        }
        const result = await request('/api/voice/calls/' + encodeURIComponent(callId) + '/end' + (allowConnectedEnd ? '' : '?only_if_unconnected=true'), { method: 'POST' });
        if (!result.response.ok || result.body.code !== 0 || result.body.data?.cleanup_pending !== false) return unknown();
        evidence = { kind: 'end', callId, cleanup_pending: false };
        return { status: 'complete', callId, evidence };
      } catch (_) { return unknown(); }
    },
  });
}

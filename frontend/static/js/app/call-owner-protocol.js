// Internal handoff, never serialized to history/storage or sent as a new business API.
// Coordinator interface (implemented in STEP-009/011):
// accept(record), updateLocal(ownerId,result), adopt(ownerId,promise,dispose),
// subscribe(callback)->unsubscribe, verify(ownerId), release(ownerId,trustedEvidence).
export function createCallOwnerRecord({ ownerId, principalId, authEpoch, attemptKey,
  requestIdentity, callId = null, pendingResources = [], localClose = { status: 'pending' },
  remoteCleanup = { status: 'unknown', evidence: null }, verifyOriginal }) {
  if (!ownerId || !attemptKey || !Number.isSafeInteger(authEpoch) || !requestIdentity ||
      requestIdentity.principalId !== principalId || requestIdentity.authEpoch !== authEpoch ||
      typeof verifyOriginal !== 'function' || !Array.isArray(pendingResources)) {
    throw new TypeError('通话清理归属不完整');
  }
  for (const pending of pendingResources) if (!pending.promise?.then || typeof pending.dispose !== 'function') {
    throw new TypeError('迟到资源必须带原owner的实际释放函数');
  }
  return Object.freeze({ ownerId, principalId, authEpoch, attemptKey, callId,
    requestIdentity: Object.freeze({ ...requestIdentity }),
    pendingResources: Object.freeze(pendingResources.map(x => Object.freeze({ ...x }))),
    localClose: Object.freeze({ ...localClose }), remoteCleanup: Object.freeze({ ...remoteCleanup }), verifyOriginal });
}

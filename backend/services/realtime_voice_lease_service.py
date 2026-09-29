"""Call-owned Redis leases. All keys belong solely to the voice namespace."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID
from backend.services.realtime_voice_metric_service import VoiceMetrics

logger = logging.getLogger(__name__)

ACQUIRE = """
local t = redis.call('TIME'); local now = t[1]*1000+math.floor(t[2]/1000)
local expired = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', now)
for _, id in ipairs(expired) do redis.call('HDEL', KEYS[3], id) end
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
local owner = redis.call('GET', KEYS[1])
if owner and owner ~= ARGV[1] then return 'user_busy' end
if not owner and redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[3]) then return 'capacity_full' end
redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
redis.call('ZADD', KEYS[2], now+tonumber(ARGV[2]), ARGV[1])
redis.call('HSET', KEYS[3], ARGV[1], ARGV[4])
return 'acquired'
"""
RENEW = """
local t = redis.call('TIME'); local now = t[1]*1000+math.floor(t[2]/1000)
local expires = redis.call('ZSCORE', KEYS[2], ARGV[1])
if redis.call('GET', KEYS[1]) ~= ARGV[1] or not expires or tonumber(expires) <= now then return 0 end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
redis.call('ZADD', KEYS[2], now+tonumber(ARGV[2]), ARGV[1])
return 1
"""
RELEASE = """
if redis.call('HGET', KEYS[3], ARGV[1]) ~= ARGV[2] then return 0 end
if redis.call('GET', KEYS[1]) == ARGV[1] then redis.call('DEL', KEYS[1]) end
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('HDEL', KEYS[3], ARGV[1])
return 1
"""
PRUNE_EXPIRED = """
local t = redis.call('TIME'); local now = t[1]*1000+math.floor(t[2]/1000)
local expired = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', now)
for _, id in ipairs(expired) do redis.call('HDEL', KEYS[2], id) end
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
return #expired
"""
COOLDOWN = """
local t = redis.call('TIME'); local now = t[1]*1000+math.floor(t[2]/1000)
local remaining = math.min(3000, tonumber(ARGV[2])+3000-now)
if remaining <= 0 then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'PX', remaining, 'NX')
return redis.call('PTTL', KEYS[1])
"""


class VoiceLeaseService:
    active_key = 'voice:lease:active'
    owners_key = 'voice:lease:users'

    def __init__(self, cache, *, end_call, metric=None, metrics=None):
        self.cache = cache
        self.metrics=metrics if metrics is not None else VoiceMetrics(cache)
        # Required server cleanup callback: renewal failure must actively end.
        self.end_call = end_call
        self.metric = metric or (lambda name, value: logger.info('%s=%s', name, value))

    @staticmethod
    def user_key(user_id):
        if type(user_id) is not int or user_id < 1:
            raise ValueError('invalid_user_id')
        return f'voice:lease:user:{user_id}'

    @staticmethod
    def validate(call_id, ttl_ms):
        if str(UUID(call_id)) != call_id:
            raise ValueError('invalid_call_id')
        if type(ttl_ms) is not int or not 10000 <= ttl_ms <= 60000:
            raise ValueError('invalid_lease_ttl')

    async def acquire(self, *, user_id, call_id, ttl_ms, global_limit):
        self.validate(call_id, ttl_ms)
        if type(global_limit) is not int or global_limit < 1:
            raise ValueError('invalid_global_limit')
        try:
            result = await self.cache.eval(ACQUIRE, 3, self.user_key(user_id), self.active_key,
                                           self.owners_key, call_id, ttl_ms, global_limit, user_id)
        except Exception:
            await self.metrics.emit_many([('voice.lease.acquire',{'result':'failure'},1)])
            raise
        self.metric('voice.lease.acquire.'+result, 1)
        await self.metrics.emit_many([('voice.lease.acquire',{'result':result},1)])
        return result == 'acquired', result

    async def renew(self, *, user_id, call_id, ttl_ms):
        self.validate(call_id, ttl_ms)
        failed=False
        try:
            renewed = await self.cache.eval(RENEW, 2, self.user_key(user_id), self.active_key, call_id, ttl_ms)
        except Exception:
            renewed = False;failed=True
        events=[('voice.lease.renew',{'result':'renewed' if renewed else 'failure' if failed else 'owner_mismatch'},1)]
        if not renewed:
            if not failed:events.append(('voice.lease.owner_mismatch',{'operation':'renew'},1))
            self.metric('voice.lease.renew_failed', 1)
            # Keep termination ahead of best-effort metric I/O.
            try:await self.end_call(call_id=call_id, user_id=user_id, reason='system_error')
            finally:await self.metrics.emit_many(events)
        else:await self.metrics.emit_many(events)
        return bool(renewed)

    async def release(self, *, user_id, call_id):
        try:
            result = await self.cache.eval(RELEASE, 3, self.user_key(user_id), self.active_key, self.owners_key, call_id, user_id)
        except Exception:
            await self.metrics.emit_many([('voice.lease.release',{'result':'failure'},1)])
            raise
        events=[('voice.lease.release',{'result':'released' if result else 'owner_mismatch'},1)]
        if not result:
            self.metric('voice.lease.owner_mismatch', 1)
            events.append(('voice.lease.owner_mismatch',{'operation':'release'},1))
        await self.metrics.emit_many(events)
        return bool(result)

    async def after_end_commit(self, *, user_id, call_id, ended_at):
        if not isinstance(ended_at, datetime):
            raise ValueError('invalid_end_timestamp')
        # DB DateTime values are UTC-naive; accepting them does not use local TZ.
        ended_at = ended_at.replace(tzinfo=timezone.utc) if ended_at.tzinfo is None else ended_at
        return await self.cache.eval(COOLDOWN, 1, f'voice:cooldown:{user_id}', call_id,
                                     int(ended_at.timestamp()*1000))

    async def check_new_dial(self, user_id):
        self.user_key(user_id)
        return await self.cache.pttl(f'voice:cooldown:{user_id}') > 0

    async def owner_matches(self, *, user_id, call_id):
        matches=await self.cache.get(self.user_key(user_id)) == call_id
        if not matches:await self.metrics.emit_many([('voice.lease.owner_mismatch',{'operation':'check'},1)])
        return matches

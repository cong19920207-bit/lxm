"""Voice-only idempotent accounting into the existing UTC agent counter.

Uses the same key/day/TTL convention as increment_agent_count_for_future, while
leaving that existing non-idempotent text/Future path unchanged.
"""
from datetime import datetime,timezone
import hashlib
import re


COUNT_ONCE_LUA='''
local recorded = redis.call('GET', KEYS[2])
if recorded then
    if recorded ~= '1' then return redis.error_reply('voice_count_marker_invalid') end
    return 0
end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[1])
redis.call('SET', KEYS[2], '1', 'EX', ARGV[2])
return 1
'''


class VoiceFollowupCounter:
    def __init__(self,*,cache,clock=datetime.utcnow):
        self.cache,self.clock=cache,clock

    async def __call__(self,*,user_id,message_id,occurred_at,idempotency_key,dedupe_ttl_seconds):
        if (type(user_id) is not int or user_id<1 or type(message_id) is not int or message_id<1
                or type(dedupe_ttl_seconds) is not int or dedupe_ttl_seconds<1
                or not isinstance(occurred_at,datetime)
                or not isinstance(idempotency_key,str)
                or not re.fullmatch(r'voice-followup:[1-9]\d*:'+str(message_id),idempotency_key)):
            raise ValueError('invalid_voice_count_request')
        instant=occurred_at.astimezone(timezone.utc).replace(tzinfo=None) if occurred_at.tzinfo else occurred_at
        now=self.clock()
        if now.tzinfo:now=now.astimezone(timezone.utc).replace(tzinfo=None)
        counter=f'agent:count:{user_id}:{instant:%Y-%m-%d}'
        marker='voice:followup:count:'+hashlib.sha256(f'{user_id}:{idempotency_key}'.encode()).hexdigest()
        end=instant.replace(hour=23,minute=59,second=59,microsecond=0)
        ttl=max(int((end-now).total_seconds()),60)
        # Redis errors propagate: the sent job retains count_pending for recovery.
        result=await self.cache.eval(COUNT_ONCE_LUA,2,counter,marker,ttl,dedupe_ttl_seconds)
        if result not in (0,1):raise RuntimeError('voice_count_result_invalid')

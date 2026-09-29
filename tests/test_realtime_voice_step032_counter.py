"""Counter request projection; Lua atomicity is verified against real Redis."""
from datetime import datetime
import pytest


@pytest.mark.asyncio
async def test_counter_uses_original_utc_day_and_frozen_retention():
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    class Cache:
        async def eval(self,*args):self.args=args;return 1
    cache=Cache();counter=VoiceFollowupCounter(cache=cache,clock=lambda:datetime(2026,9,14,0,1))
    await counter(user_id=7,message_id=8,occurred_at=datetime(2026,9,13,23,59),
        idempotency_key='voice-followup:4:8',dedupe_ttl_seconds=90*86400)
    assert cache.args[1]==2 and cache.args[2]=='agent:count:7:2026-09-13'
    assert cache.args[3].startswith('voice:followup:count:')
    assert cache.args[4:]==(60,90*86400)


@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[{'user_id':0},{'message_id':0},{'dedupe_ttl_seconds':0},
    {'idempotency_key':'voice-followup:4:999'},{'occurred_at':'not a date'}])
async def test_invalid_count_request_does_not_call_redis(changes):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    class Cache:
        async def eval(self,*args):raise AssertionError('must not mutate Redis')
    args=dict(user_id=7,message_id=8,occurred_at=datetime(2026,9,13),
        idempotency_key='voice-followup:4:8',dedupe_ttl_seconds=90*86400)
    with pytest.raises(ValueError):await VoiceFollowupCounter(cache=Cache())(**(args|changes))

"""Real Redis atomic dedup and MySQL sent-job recovery using disposable stores."""
import asyncio
from datetime import datetime,timedelta
import hashlib
import os
import pytest
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceFollowupJob
from backend.models.agent_message import AgentMessage
from tests.test_realtime_voice_step032_dispatch_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step032_dispatch import dispatch_env,worker

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


def arguments(now):
    return dict(user_id=1,message_id=8,occurred_at=now,idempotency_key='voice-followup:4:8',dedupe_ttl_seconds=90*86400)


@pytest.mark.asyncio
async def test_redis_concurrent_dedup_increments_existing_agent_count_once(runtime):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    _,_,cache=runtime;now=datetime.utcnow();key=f'agent:count:1:{now:%Y-%m-%d}'
    await cache.set(key,'8')
    counter=VoiceFollowupCounter(cache=cache)
    await asyncio.gather(*(counter(**arguments(now)) for _ in range(12)))
    assert await cache.get(key)=='9'  # Accounting bypasses the old daily 8 gate.
    marker='voice:followup:count:'+hashlib.sha256(b'1:voice-followup:4:8').hexdigest()
    assert await cache.get(marker)=='1'
    assert 89*86400<await cache.ttl(marker)<=90*86400
    assert await cache.ttl(key)>0


@pytest.mark.asyncio
async def test_lost_redis_reply_can_retry_same_idempotency_key(runtime):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    _,_,cache=runtime;now=datetime.utcnow();key=f'agent:count:1:{now:%Y-%m-%d}'
    class LostReply:
        async def eval(self,*args):
            await cache.eval(*args)
            raise ConnectionError('controlled lost response after Redis executed Lua')
    with pytest.raises(ConnectionError):await VoiceFollowupCounter(cache=LostReply())(**arguments(now))
    assert await cache.get(key)=='1'
    await VoiceFollowupCounter(cache=cache)(**arguments(now))
    assert await cache.get(key)=='1'


@pytest.mark.asyncio
async def test_corrupt_counter_failure_does_not_mark_count_as_done(runtime):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    from redis.exceptions import ResponseError
    _,_,cache=runtime;now=datetime.utcnow();key=f'agent:count:1:{now:%Y-%m-%d}'
    await cache.set(key,'not-an-integer')
    counter=VoiceFollowupCounter(cache=cache)
    with pytest.raises(ResponseError):await counter(**arguments(now))
    marker='voice:followup:count:'+hashlib.sha256(b'1:voice-followup:4:8').hexdigest()
    assert await cache.get(marker) is None
    await cache.set(key,'4');await counter(**arguments(now))
    assert await cache.get(key)=='5'


@pytest.mark.asyncio
async def test_midnight_retry_keeps_original_day(runtime):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    _,_,cache=runtime
    original=datetime(2026,9,13,23,59,59);clock=[original]
    counter=VoiceFollowupCounter(cache=cache,clock=lambda:clock[0])
    await counter(**arguments(original));clock[0]+=timedelta(seconds=2)
    await counter(**arguments(original))
    assert await cache.get('agent:count:1:2026-09-13')=='1'
    assert await cache.get('agent:count:1:2026-09-14') is None


@pytest.mark.asyncio
async def test_sent_job_recovery_after_count_success_before_db_ack(dispatch_env,runtime,monkeypatch):
    from backend.services.realtime_voice_followup_counter_service import VoiceFollowupCounter
    factory,_,job_id,clock=dispatch_env;_,_,cache=runtime
    counter=VoiceFollowupCounter(cache=cache,clock=lambda:clock[0])
    service=worker(dispatch_env,count=counter)
    original=counter.__call__
    async def crash_after_count(**kw):
        await original(**kw)
        raise asyncio.CancelledError()
    service.count_sent=crash_after_count
    with pytest.raises(asyncio.CancelledError):await service.process(job_id=job_id)
    key=f'agent:count:1:{clock[0]:%Y-%m-%d}'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status=='sent' and job.fail_reason=='count_pending'
    assert await cache.get(key)=='1'
    clock[0]+=timedelta(seconds=31);service.count_sent=counter
    assert await service.poll()==['sent']
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status=='sent' and job.fail_reason is None
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==1
    assert await cache.get(key)=='1'

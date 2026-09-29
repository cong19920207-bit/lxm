"""Composed consumer with real MySQL/Redis and controlled DeepSeek transport."""
import json
import os
from datetime import timedelta
import pytest
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceCall,VoiceFollowupJob
from backend.models.agent_message import AgentMessage
from tests.test_realtime_voice_step032_dispatch_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step032_dispatch import dispatch_env

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict',[True,False,None])
async def test_composed_followup_consumes_model_and_counts_once(dispatch_env,runtime,monkeypatch,verdict):
    import backend.database as database
    import backend.redis_client as redis_module
    import backend.services.realtime_voice_summary_runtime as summary_runtime
    from backend.services.realtime_voice_followup_runtime import build_voice_followup_service
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory,_,job_id,clock=dispatch_env;_,_,cache=runtime
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer))
        call.connected_at=clock[0]-timedelta(minutes=1)
        await db.commit()
    await add_turn(factory,newer,user_text_final='今天吃了早餐',effective_text_expires_at=clock[0]+timedelta(days=1))
    calls=[];closed=[];checks=[]
    class Client:
        async def chat_sync(self,messages,**kwargs):
            calls.append((messages,kwargs))
            assert [m['role'] for m in messages]==['system','user']
            assert json.loads(messages[1]['content'])['later_user_texts']==['今天吃了早餐']
            return json.dumps({'continued':verdict})
        async def close(self):closed.append(True)
    async def redis_provider():return cache
    async def quota(**kw):checks.append(kw['job'].id);return True
    monkeypatch.setattr(database,'async_session_maker',factory)
    monkeypatch.setattr(redis_module,'get_redis',redis_provider)
    monkeypatch.setattr(summary_runtime,'DeepSeekClient',Client)
    service=await build_voice_followup_service(quota_available=quota,lease_seconds=30,
        retry_seconds=5,clock=lambda:clock[0])
    expected='cancelled' if verdict is True else 'sent' if verdict is False else 'pending'
    assert await service.poll()==[expected]
    assert await service.poll()==[]
    assert len(calls)==len(closed)==1
    assert checks==([job_id] if verdict is False else [])
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status==expected
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==(1 if verdict is False else 0)
        if verdict is False:assert job.agent_message_id and job.fail_reason is None
        if verdict is None:assert job.next_retry_at==clock[0]+timedelta(seconds=5)
    assert await cache.get(f'agent:count:1:{clock[0]:%Y-%m-%d}')==('1' if verdict is False else None)

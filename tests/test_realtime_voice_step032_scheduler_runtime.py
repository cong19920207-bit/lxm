"""Actual APScheduler callback and approved quota policy on isolated stores."""
import asyncio
import os
from datetime import timedelta
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceCall,VoiceFollowupJob
from backend.models.agent_message import AgentMessage
from backend.models.relationship import Relationship
from backend.models.conversation_log import ConversationLog
from tests.test_realtime_voice_step032_dispatch_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step032_dispatch import dispatch_env

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
@pytest.mark.parametrize('state',['eligible','user_chatted','deleted','window'])
async def test_registered_scheduler_bypasses_only_frequency_limits(dispatch_env,runtime,monkeypatch,state):
    import backend.database as database
    import backend.redis_client as redis_module
    from backend.tasks import scheduler as module
    from backend.services import realtime_voice_followup_runtime as composition
    factory,call_id,job_id,clock=dispatch_env;_,_,cache=runtime
    key=f'agent:count:1:{clock[0]:%Y-%m-%d}'
    await cache.set(key,'8')
    async with factory() as db:
        db.add(AgentMessage(user_id=1,content='先前的主动消息',trigger_type='TEST',
            action_score=0,sort_seq=1,created_at=clock[0]-timedelta(minutes=1)))
        db.add(Relationship(user_id=1,level=1,growth_value=0,last_interaction_at=clock[0],
            future_timestamp=1900000000,future_action='保留原Future事项',proactive_times=3))
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        if state=='deleted':call.deletion_fence_at=clock[0]
        if state=='user_chatted':db.add(ConversationLog(user_id=1,role='user',content='我又来聊天了',sort_seq=2,created_at=clock[0]))
        await db.commit()
    if state=='window':clock[0]=clock[0].replace(hour=13)
    async def redis_provider():return cache
    monkeypatch.setattr(database,'async_session_maker',factory)
    monkeypatch.setattr(redis_module,'get_redis',redis_provider)
    build=composition.build_voice_followup_service
    async def builder():return await build(clock=lambda:clock[0])
    monkeypatch.setattr(composition,'build_voice_followup_service',builder)
    real=AsyncIOScheduler();ticks=[];completed=asyncio.Event()
    from apscheduler.events import EVENT_JOB_EXECUTED,EVENT_JOB_ERROR
    def listener(event):
        ticks.append(event)
        if len(ticks)>=2:completed.set()
    real.add_listener(listener,EVENT_JOB_EXECUTED|EVENT_JOB_ERROR)
    class OnlyFollowup:
        running=False
        def add_job(self,callback,**kwargs):
            if kwargs['id']=='voice_followup_task':real.add_job(callback,**kwargs)
        def start(self):real.start()
        def get_jobs(self):return real.get_jobs()
    # Execute the registration emitted by production startup; suppress unrelated
    # business jobs in this isolated test process.
    monkeypatch.setattr(module,'scheduler',OnlyFollowup())
    try:
        module.start_scheduler()
        await asyncio.wait_for(completed.wait(),15)
    finally:
        if real.running:real.shutdown(wait=False)
        await asyncio.sleep(0)
    assert len(ticks)>=2 and not any(event.exception for event in ticks)
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status==('sent' if state=='eligible' else 'pending' if state=='window' else 'cancelled')
        assert job.attempt_count==1
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==(2 if state=='eligible' else 1)
        relationship=await db.scalar(select(Relationship).where(Relationship.user_id==1))
        assert (relationship.future_timestamp,relationship.future_action,relationship.proactive_times)==(1900000000,'保留原Future事项',3)
        if state=='eligible':assert job.agent_message_id and job.fail_reason is None
        if state=='window':assert job.next_retry_at==clock[0].replace(day=14,hour=2)
    assert await cache.get(key)==('9' if state=='eligible' else '8')

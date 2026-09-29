import asyncio
import os
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED,EVENT_JOB_ERROR
from backend.models.realtime_voice import VoiceCallTurn,VoiceCallCreateIdempotency
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step034_replay_retention import replay_env
from tests.test_realtime_voice_step034_content_retention import seed

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
async def test_registered_retention_cleans_real_stores_and_replay_ids(replay_env,runtime,monkeypatch):
    import backend.database as database
    import backend.redis_client as redis_module
    from backend.tasks import scheduler as module
    factory,call_id,_,replay_ids=replay_env;_,_,cache=runtime;now=datetime.utcnow()
    turn_id,_,_,_=await seed(factory,call_id,now,now-timedelta(seconds=1))
    key=f'voice:session_context:{call_id}';await cache.set(key,'private-context')
    async def redis_provider():return cache
    monkeypatch.setattr(database,'async_session_maker',factory)
    monkeypatch.setattr(redis_module,'get_redis',redis_provider)
    monkeypatch.setattr(module,'_voice_retention_cursors',{'contents':0,'replays':0})
    real=AsyncIOScheduler();done=asyncio.Event();events=[]
    def listener(event):events.append(event);done.set()
    real.add_listener(listener,EVENT_JOB_EXECUTED|EVENT_JOB_ERROR)
    class OnlyRetention:
        def add_job(self,callback,**kwargs):
            if kwargs['id']=='voice_retention_task':
                real.add_job(callback,**kwargs,next_run_time=datetime.now(timezone.utc)+timedelta(milliseconds=50))
        def start(self):real.start()
        def get_jobs(self):return real.get_jobs()
    monkeypatch.setattr(module,'scheduler',OnlyRetention())
    try:
        module.start_scheduler();await asyncio.wait_for(done.wait(),10)
    finally:
        if real.running:real.shutdown(wait=False)
        await asyncio.sleep(0)
    assert not events[0].exception
    async with factory() as db:
        row=await db.get(VoiceCallTurn,turn_id)
        assert row.user_text_final is None and row.assistant_text_generated is None
        assert list((await db.scalars(select(VoiceCallCreateIdempotency.id).where(VoiceCallCreateIdempotency.id.in_(replay_ids)))).all())==[]
    assert await cache.get(key) is None

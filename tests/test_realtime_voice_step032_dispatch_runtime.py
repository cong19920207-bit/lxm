"""MySQL dispatch transactions and concurrent workers; callbacks are controlled."""
import asyncio
import os
import pytest
import pytest_asyncio
from sqlalchemy import select,func
from backend.database import Base
from backend.models.realtime_voice import VoiceFollowupJob,VoicePostprocessJob
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.relationship import Relationship
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step032_dispatch import (
    dispatch_env,worker,test_dispatch_twice_single_message_and_count,
    test_pre_send_cancels_without_message,test_worker_crash_reclaims_expired_lease,
    test_message_transaction_failure_retries_without_partial_delivery,
    test_count_failure_keeps_sent_message_and_only_retries_accounting,
    test_existing_message_link_recovers_without_second_message,
    test_connected_followup_rechecks_effective_source,
    test_late_worker_uses_frozen_window_without_moving_due_snapshot,
    test_waiting_for_timeline_cannot_outlive_worker_lease,
    test_later_voice_requires_topic_recheck,
    test_changed_voice_during_model_wait_retries_before_delivery,
    test_expired_source_never_calls_topic_model,
    test_outside_window_with_later_voice_defers_without_topic_failure,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest_asyncio.fixture
async def card_env(runtime):
    factory,call_id,_=runtime
    tables=[m.__table__ for m in (Relationship,VoiceFollowupJob,VoicePostprocessJob,AgentMessage,ConversationLog)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try:yield factory,call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)


@pytest.mark.asyncio
async def test_two_workers_do_not_duplicate_delivery(dispatch_env):
    factory,_,job_id,_=dispatch_env;counted=[]
    async def count(**kw):counted.append(kw['idempotency_key'])
    a=worker(dispatch_env,count=count);b=worker(dispatch_env,count=count)
    results=await asyncio.gather(a.process(job_id=job_id),b.process(job_id=job_id))
    assert set(results)<={'sent','busy'} and 'sent' in results
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==1
        assert (await db.get(VoiceFollowupJob,job_id)).status=='sent'
    assert len(counted)==1


@pytest.mark.asyncio
async def test_chat_committed_after_initial_check_cancels_delivery(dispatch_env):
    from backend.services.timeline_seq_service import allocate_sort_seq
    from backend.models.user_timeline_seq import UserTimelineSeq
    factory,_,job_id,clock=dispatch_env
    async with factory() as db:
        db.add(UserTimelineSeq(user_id=1,next_seq=1));await db.commit()
    checked=asyncio.Event();resume=asyncio.Event()
    async def quota(**kw):checked.set();await resume.wait();return True
    task=asyncio.create_task(worker(dispatch_env,quota=quota).process(job_id=job_id))
    try:
        await asyncio.wait_for(checked.wait(),5)
        async with factory() as db:
            sequence=(await allocate_sort_seq(1,1,db))[0]
            db.add(ConversationLog(user_id=1,role='user',content='用户刚刚继续聊天',sort_seq=sequence,created_at=clock[0]))
            await asyncio.wait_for(db.commit(),5)
        resume.set()
        assert await asyncio.wait_for(task,5)=='cancelled'
        async with factory() as db:
            assert await db.scalar(select(AgentMessage)) is None
            assert (await db.get(VoiceFollowupJob,job_id)).cancel_reason=='user_chatted'
    finally:
        resume.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)


@pytest.mark.asyncio
async def test_topic_model_wait_does_not_hold_user_transaction_lock(dispatch_env):
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    from backend.models.realtime_voice import VoiceCall
    from backend.models.user import User
    from datetime import timedelta
    factory,_,job_id,clock=dispatch_env
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer))
        call.connected_at=clock[0]-timedelta(minutes=1);await db.commit()
    await add_turn(factory,newer,user_text_final='我今天早餐吃了面包',effective_text_expires_at=clock[0]+timedelta(days=1))
    entered=asyncio.Event();release=asyncio.Event()
    async def topic(**kw):entered.set();await release.wait();return False
    task=asyncio.create_task(worker(dispatch_env,topic=topic).process(job_id=job_id))
    try:
        await asyncio.wait_for(entered.wait(),5)
        async with factory() as db:
            await asyncio.wait_for(db.scalar(select(User.id).where(User.id==1).with_for_update()),5)
            await db.rollback()
        release.set()
        assert await asyncio.wait_for(task,5)=='sent'
    finally:
        release.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)

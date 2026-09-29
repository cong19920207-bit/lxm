"""Durable dispatch and recovery; quota/count policies supplied explicitly."""
import asyncio
from datetime import datetime,timedelta
import pytest
import pytest_asyncio
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceCall,VoiceFollowupJob
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage


@pytest_asyncio.fixture
async def dispatch_env(card_env):
    factory,call_id=card_env
    now=datetime(2026,9,13,2)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='missed';call.connected_at=None
        call.ended_at=now-timedelta(minutes=5)
        job=VoiceFollowupJob(call_id=call_id,user_id=call.user_id,content='晚一点我们再聊呀。',
            content_type='missed_explanation',status='pending',candidate_due_at=now,due_at=now,
            latest_due_at=now+timedelta(hours=24),relationship_stage_snapshot='stranger',
            schedule_config_version='1',timezone_snapshot='Asia/Shanghai',
            allowed_window_snapshot=[{'start':'10:00','end':'21:00'}],jitter_minutes=0)
        db.add(job);await db.commit();job_id=job.id
    return factory,call_id,job_id,[now]


def worker(env,*,quota=None,count=None,topic=None):
    from backend.services.realtime_voice_followup_job_service import VoiceFollowupJobService
    factory,_,_,clock=env
    async def yes(**kw):return True
    async def accounted(**kw):pass
    return VoiceFollowupJobService(session_factory=factory,quota_available=quota or yes,
        count_sent=count or accounted,topic_continued=topic,clock=lambda:clock[0],lease_seconds=30,retry_seconds=5)


@pytest.mark.asyncio
async def test_dispatch_twice_single_message_and_count(dispatch_env):
    factory,call_id,job_id,_=dispatch_env;counted=[]
    async def count(**kw):counted.append(kw)
    service=worker(dispatch_env,count=count)
    assert await service.poll()==['sent']
    assert await service.poll()==[]
    assert await service.process(job_id=job_id)=='sent'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id);message=await db.scalar(select(AgentMessage))
        assert job.status=='sent' and job.agent_message_id==message.id
        assert message.content=='晚一点我们再聊呀。' and message.sort_seq==1
        assert len(counted)==1 and counted[0]['message_id']==message.id
        assert counted[0]['idempotency_key']==f'voice-followup:{job_id}:{message.id}'
        assert job.attempt_count==1 and job.lease_owner is None


@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['user_chatted','quota_unavailable','source_deleted','source_expired','deadline_exceeded'])
async def test_pre_send_cancels_without_message(dispatch_env,reason):
    factory,_,job_id,clock=dispatch_env
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));job=await db.get(VoiceFollowupJob,job_id)
        if reason=='user_chatted':db.add(ConversationLog(user_id=1,role='user',content='继续聊',sort_seq=1,created_at=clock[0]))
        if reason=='source_deleted':call.deletion_fence_at=clock[0]
        if reason=='source_expired':call.transcript_expires_at=clock[0]
        if reason=='deadline_exceeded':job.latest_due_at=clock[0]
        await db.commit()
    if reason=='deadline_exceeded':clock[0]+=timedelta(microseconds=1)
    async def quota(**kw):return reason!='quota_unavailable'
    assert await worker(dispatch_env,quota=quota).process(job_id=job_id)=='cancelled'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.cancel_reason==reason and await db.scalar(select(AgentMessage)) is None


@pytest.mark.asyncio
async def test_worker_crash_reclaims_expired_lease(dispatch_env):
    factory,_,job_id,clock=dispatch_env
    async def crash(**kw):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):await worker(dispatch_env,quota=crash).process(job_id=job_id)
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status=='processing' and job.attempt_count==1
    assert await worker(dispatch_env).process(job_id=job_id)=='busy'
    clock[0]+=timedelta(seconds=31)
    assert await worker(dispatch_env).process(job_id=job_id)=='sent'
    async with factory() as db:
        assert (await db.get(VoiceFollowupJob,job_id)).attempt_count==2
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==1


@pytest.mark.asyncio
async def test_message_transaction_failure_retries_without_partial_delivery(dispatch_env,monkeypatch):
    factory,_,job_id,clock=dispatch_env;service=worker(dispatch_env)
    original=service._stage_message
    async def broken(*args,**kw):
        await original(*args,**kw)
        raise RuntimeError('controlled failure after message insert before job commit')
    monkeypatch.setattr(service,'_stage_message',broken)
    assert await service.process(job_id=job_id)=='pending'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.fail_reason=='dispatch_unavailable' and job.next_retry_at==clock[0]+timedelta(seconds=5)
        assert job.agent_message_id is None and await db.scalar(select(AgentMessage)) is None
    assert await service.poll()==[]
    clock[0]+=timedelta(seconds=5);monkeypatch.setattr(service,'_stage_message',original)
    assert await service.poll()==['sent']


@pytest.mark.asyncio
async def test_count_failure_keeps_sent_message_and_only_retries_accounting(dispatch_env):
    factory,_,job_id,clock=dispatch_env;attempts=[]
    async def count(**kw):
        attempts.append(kw)
        if len(attempts)==1:raise RuntimeError('counter temporarily unavailable')
    service=worker(dispatch_env,count=count)
    assert await service.process(job_id=job_id)=='sent'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.status=='sent' and job.fail_reason=='count_pending'
        call=await db.scalar(select(VoiceCall));call.deletion_fence_at=clock[0];await db.commit()
    clock[0]+=timedelta(seconds=5)
    assert await service.poll()==['sent']
    assert attempts[0]==attempts[1]
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.fail_reason is None and job.next_retry_at is None
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==1


@pytest.mark.asyncio
async def test_existing_message_link_recovers_without_second_message(dispatch_env):
    factory,_,job_id,clock=dispatch_env
    async with factory() as db:
        message=AgentMessage(user_id=1,content='已发送的追加内容',trigger_type='VOICE_FOLLOWUP',action_score=0,sort_seq=1,created_at=clock[0])
        db.add(message);await db.flush()
        job=await db.get(VoiceFollowupJob,job_id);job.agent_message_id=message.id
        job.status='processing';job.lease_owner='dead-worker';job.lease_expires_at=clock[0]-timedelta(seconds=1)
        await db.commit()
    assert await worker(dispatch_env).process(job_id=job_id)=='sent'
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(AgentMessage))==1
        assert (await db.scalar(select(AgentMessage))).content=='已发送的追加内容'


@pytest.mark.asyncio
@pytest.mark.parametrize('state',['good','expired','cleared','crisis','short','not_ready','configured_minimum'])
async def test_connected_followup_rechecks_effective_source(dispatch_env,state):
    from tests.test_realtime_voice_step028_jobs import add_turn
    from backend.models.realtime_voice import VoiceCallTurn
    factory,call_id,job_id,clock=dispatch_env
    await add_turn(factory,call_id)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ended';call.connected_at=call.ended_at-timedelta(seconds=20)
        call.duration_seconds=14 if state=='short' else 20
        call.summary_status='failed' if state=='not_ready' else 'ready'
        if state=='configured_minimum':call.config_snapshot={'resolved_config':{'followup':{'summary_min_effective_seconds':21}}}
        job=await db.get(VoiceFollowupJob,job_id);job.content_type='topic_continuation'
        turn=await db.scalar(select(VoiceCallTurn));turn.effective_text_expires_at=clock[0]+timedelta(days=1)
        if state=='expired':turn.effective_text_expires_at=clock[0]
        if state=='cleared':turn.effective_text_cleared_at=clock[0]
        if state=='crisis':turn.user_crisis_status='matched'
        await db.commit()
    assert await worker(dispatch_env).process(job_id=job_id)==('sent' if state=='good' else 'cancelled')


@pytest.mark.asyncio
async def test_late_worker_uses_frozen_window_without_moving_due_snapshot(dispatch_env):
    factory,_,job_id,clock=dispatch_env
    clock[0]=datetime(2026,9,13,13)  # Exact 21:00 right boundary, outside stranger window.
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id);frozen_due=job.due_at
        call=await db.scalar(select(VoiceCall));call.config_snapshot={'resolved_config':{'followup':{'schedule':{}}}}
        await db.commit()
    assert await worker(dispatch_env).process(job_id=job_id)=='pending'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.due_at==frozen_due and job.next_retry_at==datetime(2026,9,14,2)
    clock[0]=datetime(2026,9,14,2)  # Exactly candidate +24h remains eligible.
    assert await worker(dispatch_env).poll()==['sent']


@pytest.mark.asyncio
async def test_waiting_for_timeline_cannot_outlive_worker_lease(dispatch_env,monkeypatch):
    import backend.services.realtime_voice_followup_job_service as module
    factory,_,job_id,clock=dispatch_env
    allocate=module.allocate_sort_seq
    async def delayed(*args,**kw):
        result=await allocate(*args,**kw);clock[0]+=timedelta(seconds=31);return result
    monkeypatch.setattr(module,'allocate_sort_seq',delayed)
    assert await worker(dispatch_env).process(job_id=job_id)=='pending'
    async with factory() as db:
        assert await db.scalar(select(AgentMessage)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict',[True,False,None])
async def test_later_voice_requires_topic_recheck(dispatch_env,verdict):
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory,_,job_id,clock=dispatch_env
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer));call.connected_at=clock[0]-timedelta(minutes=1)
        await db.commit()
    await add_turn(factory,newer,user_text_final='京都行程已定为下周一，不用再问日期',
        effective_text_expires_at=clock[0]+timedelta(days=1))
    seen=[]
    async def topic(**kw):seen.append(kw);return verdict
    outcome=await worker(dispatch_env,topic=topic if verdict is not None else None).process(job_id=job_id)
    assert outcome==('cancelled' if verdict is True else 'sent' if verdict is False else 'pending')
    if verdict is not None:assert seen and '京都行程已定为下周一，不用再问日期' in seen[0]['later_user_texts']
    async with factory() as db:
        assert (await db.scalar(select(func.count()).select_from(AgentMessage)))==(1 if verdict is False else 0)


@pytest.mark.asyncio
async def test_changed_voice_during_model_wait_retries_before_delivery(dispatch_env):
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    from backend.models.realtime_voice import VoiceCallTurn
    factory,_,job_id,clock=dispatch_env
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer));call.connected_at=clock[0]-timedelta(minutes=1)
        await db.commit()
    await add_turn(factory,newer,user_text_final='我吃了早餐',effective_text_expires_at=clock[0]+timedelta(days=1))
    calls=[]
    async def topic(**kw):
        calls.append(kw['later_user_texts'])
        if len(calls)==1:
            async with factory() as db:
                turn=await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==newer))
                turn.user_text_final='京都日期已经定了，不用再问';await db.commit()
            return False
        return True
    service=worker(dispatch_env,topic=topic)
    assert await service.process(job_id=job_id)=='pending'
    async with factory() as db:
        assert await db.scalar(select(AgentMessage)) is None
    clock[0]+=timedelta(seconds=5)
    assert await service.poll()==['cancelled']
    assert calls==[['我吃了早餐'],['京都日期已经定了，不用再问']]


@pytest.mark.asyncio
@pytest.mark.parametrize('expired',['source','later'])
async def test_expired_source_never_calls_topic_model(dispatch_env,expired):
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory,source_id,job_id,clock=dispatch_env
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        source=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==source_id))
        if expired=='source':source.transcript_expires_at=clock[0]
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer));call.connected_at=clock[0]-timedelta(minutes=1)
        if expired=='later':call.transcript_expires_at=clock[0]
        await db.commit()
    await add_turn(factory,newer,user_text_final='后来继续聊过',effective_text_expires_at=clock[0]+timedelta(days=1))
    async def forbidden(**kw):raise AssertionError('expired source must not reach provider')
    assert await worker(dispatch_env,topic=forbidden).process(job_id=job_id)==('cancelled' if expired=='source' else 'sent')


@pytest.mark.asyncio
async def test_outside_window_with_later_voice_defers_without_topic_failure(dispatch_env):
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    factory,_,job_id,clock=dispatch_env
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer))
        call.connected_at=clock[0]-timedelta(minutes=1)
        await db.commit()
    await add_turn(factory,newer,user_text_final='京都行程已经确定',
        effective_text_expires_at=clock[0]+timedelta(days=2))
    clock[0]=datetime(2026,9,13,13)
    calls=[]
    async def topic(**kw):calls.append(kw);return True
    service=worker(dispatch_env,topic=topic)
    assert await service.process(job_id=job_id)=='pending'
    assert calls==[]
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.next_retry_at==datetime(2026,9,14,2)
        assert job.fail_reason is None
        assert await db.scalar(select(AgentMessage)) is None
    clock[0]=datetime(2026,9,14,2)
    assert await service.poll()==['cancelled']
    assert len(calls)==1


@pytest.mark.asyncio
async def test_consumer_uses_second_frozen_window_without_rewriting_job(dispatch_env):
    factory,_,job_id,clock=dispatch_env
    windows=[{'start':'10:00','end':'11:00'},{'start':'14:00','end':'15:00'}]
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id);job.allowed_window_snapshot=windows
        frozen=(job.due_at,job.candidate_due_at,job.latest_due_at,job.jitter_minutes,job.schedule_config_version)
        await db.commit()
    clock[0]=clock[0].replace(hour=3)  # 11:00 is outside the first window.
    service=worker(dispatch_env)
    assert await service.process(job_id=job_id)=='pending'
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        assert job.next_retry_at==clock[0].replace(hour=6)
        assert job.allowed_window_snapshot==windows
        assert (job.due_at,job.candidate_due_at,job.latest_due_at,job.jitter_minutes,job.schedule_config_version)==frozen
    clock[0]=clock[0].replace(hour=6)
    assert await service.poll()==['sent']
    assert await service.poll()==[]

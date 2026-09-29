import asyncio,json
from datetime import datetime,timedelta
import pytest
import pytest_asyncio
from sqlalchemy import select,func
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoicePostprocessJob,VoiceMemoryTrace
from backend.services.realtime_voice_card_service import stage_call_card
from backend.services.realtime_voice_summary_job_service import VoiceSummaryJobService
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step028_jobs import add_turn
from tests.test_realtime_voice_step031_summary import output

@pytest_asyncio.fixture
async def summary_env(card_env):
    factory,call=card_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoicePostprocessJob.__table__])
    await add_turn(factory,call)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ended';row.ended_at=datetime.utcnow();row.duration_seconds=20
        await stage_call_card(db,row);await db.commit()
    return factory,call


def service(factory,*,model=None,prepare=None,stage_followup=None):
    async def default_model(prompt):return json.dumps(output(should_send_followup=False))
    async def default_prepare(**kwargs):return {'status':'ok'}
    async def permits(**kwargs):return True
    return VoiceSummaryJobService(session_factory=factory,model=model or default_model,permits=permits,
        prepare=prepare or default_prepare,timeout_seconds=2,stage_followup=stage_followup)

@pytest.mark.asyncio
async def test_summary_transaction_fixed_card_reasoning_and_idempotency(summary_env):
    factory,call=summary_env;worker=service(factory)
    assert await worker.enqueue(call_id=call)=='pending'
    assert await worker.process(call_id=call)=='ready'
    assert await worker.enqueue(call_id=call)=='success'
    assert await worker.process(call_id=call)=='success'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));job=await db.scalar(select(VoicePostprocessJob))
        assert row.sort_seq==1 and row.summary_status=='ready' and row.user_emotion=='期待'
        assert row.summary_reasoning=='旅行话题没有展开'
        assert row.reasoning_expires_at==row.ended_at+timedelta(days=30)
        assert job.attempt_count==1 and job.lease_owner is None
        assert await db.scalar(select(func.count()).select_from(VoiceMemoryTrace))==0

@pytest.mark.asyncio
@pytest.mark.parametrize('status,seconds',[('ended',14),('missed',0),('failed',0),('cancelled',0)])
async def test_ineligible_matrix_does_not_call_model(summary_env,status,seconds):
    factory,call=summary_env
    async def model(prompt):raise AssertionError('must not call model')
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status=status;row.duration_seconds=seconds
        if status!='ended':row.connected_at=None
        await db.commit()
    worker=service(factory,model=model);await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='not_applicable'

@pytest.mark.asyncio
@pytest.mark.parametrize('raw',['broken-json',json.dumps(output(call_summary=''))])
async def test_invalid_model_output_preserves_static_card(summary_env,raw):
    factory,call=summary_env
    async def model(prompt):return raw
    worker=service(factory,model=model);await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='failed'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));assert row.sort_seq==1 and row.summary_status=='failed' and row.call_summary is None

@pytest.mark.asyncio
async def test_model_wait_releases_call_and_fence_rejects_late_result(summary_env):
    factory,call=summary_env;entered=asyncio.Event();release=asyncio.Event()
    async def model(prompt):entered.set();await release.wait();return json.dumps(output(should_send_followup=False))
    worker=service(factory,model=model);await worker.enqueue(call_id=call)
    task=asyncio.create_task(worker.process(call_id=call))
    try:
        await asyncio.wait_for(entered.wait(),1)
        assert await worker.process(call_id=call)=='processing'
        async with factory() as db:
            row=await db.scalar(select(VoiceCall));row.deletion_fence_at=datetime.utcnow();await db.commit()
        release.set();assert await task=='cancelled'
        async with factory() as db:
            row=await db.scalar(select(VoiceCall));assert row.call_summary is None and row.summary_reasoning is None
    finally:
        release.set();await task

@pytest.mark.asyncio
async def test_reasoning_expiry_clears_only_internal_content(summary_env):
    factory,call=summary_env;worker=service(factory)
    await worker.enqueue(call_id=call);assert await worker.process(call_id=call)=='ready'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.reasoning_expires_at=datetime.utcnow()-timedelta(seconds=1);await db.commit()
    assert await worker.purge_reasoning()==1
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));assert row.summary_reasoning is None and row.call_summary and row.sort_seq==1

@pytest.mark.asyncio
async def test_followup_storage_failure_rolls_back_summary_and_candidate(summary_env):
    factory,call=summary_env
    async def model(prompt):return json.dumps(output())
    async def sink(db,call,candidate):
        call.call_summary='不得部分提交';await db.flush();raise RuntimeError('controlled candidate failure')
    worker=service(factory,model=model,stage_followup=sink);await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='failed'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));assert row.call_summary is None and row.summary_status=='failed'

@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','observer','ops_admin','ai_trainer'])
async def test_reasoning_private_role_projection_and_each_read_audit(summary_env,role):
    from types import SimpleNamespace
    from backend.services.realtime_voice_summary_job_service import read_summary_reasoning
    from backend.services.realtime_voice_config_service import VoiceConfigError
    from backend.models.admin_operation_log import AdminOperationLog
    factory,call=summary_env;worker=service(factory)
    await worker.enqueue(call_id=call);await worker.process(call_id=call)
    async with factory() as db:
        admin=SimpleNamespace(id=1,username='operator',role=role)
        if role=='super_admin':
            for _ in range(2):assert (await read_summary_reasoning(db,call_id=call,admin=admin))['reasoning']
            assert await db.scalar(select(func.count()).select_from(AdminOperationLog))==2
        else:
            with pytest.raises(VoiceConfigError) as error:await read_summary_reasoning(db,call_id=call,admin=admin)
            assert error.value.status_code==403
            assert await db.scalar(select(func.count()).select_from(AdminOperationLog))==0

@pytest.mark.asyncio
async def test_expired_meaningful_turn_cannot_qualify_remaining_ack(summary_env):
    from backend.models.realtime_voice import VoiceCallTurn
    factory,call=summary_env
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn));row.effective_text_expires_at=datetime.utcnow()-timedelta(seconds=1);await db.commit()
    await add_turn(factory,call,2,user_text_final='嗯，好的。')
    async def model(prompt):raise AssertionError('expired meaning must not qualify')
    worker=service(factory,model=model);await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='not_applicable'

@pytest.mark.asyncio
async def test_source_expiry_during_model_cannot_leave_pending_card(summary_env,monkeypatch):
    import backend.services.realtime_voice_summary_job_service as module
    from backend.models.realtime_voice import VoiceCallTurn
    factory,call=summary_env;base=datetime.utcnow();clock=[base]
    class ControlledDatetime(datetime):
        @classmethod
        def utcnow(cls):return clock[0]
    monkeypatch.setattr(module,'datetime',ControlledDatetime)
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn));row.effective_text_expires_at=base+timedelta(milliseconds=500);await db.commit()
    async def model(prompt):
        clock[0]=base+timedelta(seconds=1)
        return json.dumps(output(should_send_followup=False))
    worker=service(factory,model=model);await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='cancelled'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));job=await db.scalar(select(VoicePostprocessJob))
        assert row.summary_status=='failed' and row.sort_seq==1 and row.call_summary is None
        assert job.status=='cancelled' and job.fail_reason=='source_unavailable'

@pytest.mark.asyncio
async def test_real_candidate_storage_shares_summary_commit_and_keeps_future_slot(summary_env):
    from backend.models.relationship import Relationship
    from backend.models.realtime_voice import VoiceFollowupJob
    from backend.services.realtime_voice_summary_followup_service import stage_summary_followup
    factory,call=summary_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceFollowupJob.__table__])
    async with factory() as db:
        db.add(Relationship(user_id=1,level=1,growth_value=20,future_timestamp=999,future_action='原先安排'))
        row=await db.scalar(select(VoiceCall));row.ended_at=datetime(2026,9,13,2)
        await db.commit()
    async def model(prompt):return json.dumps(output())
    worker=service(factory,model=model,stage_followup=stage_summary_followup)
    await worker.enqueue(call_id=call);assert await worker.process(call_id=call)=='ready'
    assert await worker.process(call_id=call)=='success'
    async with factory() as db:
        row=await db.scalar(select(VoiceFollowupJob));relation=await db.scalar(select(Relationship))
        assert row.status=='pending' and row.relationship_stage_snapshot=='friend'
        assert row.due_at==datetime(2026,9,13,3,30) and row.schedule_config_version=='code-default'
        assert (relation.future_timestamp,relation.future_action)==(999,'原先安排')
        assert await db.scalar(select(func.count()).select_from(VoiceFollowupJob))==1

@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','observer','ops_admin','ai_trainer'])
async def test_manual_summary_retry_roles_preserve_attempt_count(summary_env,role):
    from types import SimpleNamespace
    from backend.services.realtime_voice_summary_job_service import retry_summary_job
    from backend.services.realtime_voice_config_service import VoiceConfigError
    factory,call=summary_env
    async def model(prompt):return '{}'
    worker=service(factory,model=model);await worker.enqueue(call_id=call);await worker.process(call_id=call)
    async with factory() as db:
        job=await db.scalar(select(VoicePostprocessJob));admin=SimpleNamespace(id=1,username='operator',role=role)
        if role in {'super_admin','tech_ops'}:
            result=await retry_summary_job(db,job_id=job.id,admin=admin)
            assert result['status']=='pending' and result['attempt_count']==1
        else:
            with pytest.raises(VoiceConfigError) as error:await retry_summary_job(db,job_id=job.id,admin=admin)
            assert error.value.status_code==403

@pytest.mark.asyncio
async def test_followup_jitter_honors_nonzero_published_minimum(summary_env,monkeypatch):
    from copy import deepcopy
    from backend.constants.realtime_voice_config import DEFAULT_FOLLOWUP_SCHEDULE
    from backend.models.relationship import Relationship
    from backend.models.realtime_voice import VoiceFollowupJob
    import backend.services.realtime_voice_summary_followup_service as module
    factory,call=summary_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceFollowupJob.__table__])
    monkeypatch.setattr(module.secrets,'randbelow',lambda bound:0)
    async with factory() as db:
        db.add(Relationship(user_id=1,level=1,growth_value=20))
        row=await db.scalar(select(VoiceCall));row.ended_at=datetime(2026,9,13,0)
        schedule=deepcopy(DEFAULT_FOLLOWUP_SCHEDULE);schedule['jitter_min_minutes']=10;schedule['jitter_max_minutes']=20
        row.config_snapshot={**row.config_snapshot,'config_version':7,'resolved_config':{'followup':{'schedule':schedule}}}
        job=await module.stage_summary_followup(db,call=row,candidate={'delay_minutes':0,'content':'晚点继续聊','content_type':'topic_continuation'})
        await db.commit()
        assert job.jitter_minutes==10 and job.due_at==datetime(2026,9,13,1,40)
        assert job.schedule_config_version=='7'

@pytest.mark.asyncio
async def test_reasoning_assessment_timeout_keeps_ready_public_card(summary_env):
    factory,call=summary_env;worker=service(factory);worker.timeout=.1
    async def permits(call_id,text):
        if text=='旅行话题没有展开':await asyncio.sleep(2)
        return True
    worker.permits=permits
    await worker.enqueue(call_id=call)
    assert await worker.process(call_id=call)=='ready'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));assert row.call_summary and row.summary_reasoning is None

@pytest.mark.asyncio
async def test_scan_discovers_unqueued_card_and_stops_after_success_or_failure(summary_env):
    factory,call=summary_env;prepared=[]
    async def prepare(**kw):prepared.append(kw['call_id'])
    worker=service(factory,prepare=prepare)
    assert await worker.poll()==['ready']
    assert await worker.poll()==[]
    assert prepared==[call]
    async with factory() as db:
        job=await db.scalar(select(VoicePostprocessJob));job.status='failed';job.fail_reason='model_unavailable'
        row=await db.scalar(select(VoiceCall));row.summary_status='failed';await db.commit()
    assert await worker.poll()==[] # Only explicit manual retry can requeue a failed summary.

@pytest.mark.asyncio
async def test_production_composition_consumes_frozen_deepseek_prompt_and_compensates(summary_env,monkeypatch):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    import backend.services.realtime_voice_memory_service as memory_module
    import backend.services.realtime_voice_summary_runtime as runtime_module
    from backend.tasks.scheduler import _run_voice_summary
    from tests.test_realtime_voice_step028_jobs import Gate,Writer
    factory,call=summary_env;seen=[]
    async with factory() as db:
        row=await db.scalar(select(VoiceCall))
        row.config_snapshot={**row.config_snapshot,'resolved_config':{**row.config_snapshot['resolved_config'],'summary':{'model':'deepseek-chat'}},
            'resolved_script':{**row.config_snapshot['resolved_script'],'summary':{'prompt_template':'本通冻结的专用摘要提示词'}}}
        await db.commit()
    from tests.test_realtime_voice_step031_metrics import CounterCache
    metric_cache=CounterCache()
    async def memory_builder():
        gate=Gate();gate.cache=metric_cache
        return VoiceMemoryService(session_factory=factory,gate=gate,writer=Writer())
    class Client:
        async def chat_sync(self,messages,**kwargs):seen.append((messages,kwargs));return json.dumps(output(should_send_followup=False))
        async def close(self):pass
    monkeypatch.setattr(memory_module,'build_voice_memory_service',memory_builder)
    monkeypatch.setattr(runtime_module,'DeepSeekClient',Client)
    await _run_voice_summary()
    await _run_voice_summary()
    assert len(seen)==1 and seen[0][1]['model']=='deepseek-chat'
    assert ('voice.summary.result',{'result':'ready'},1) in [e for batch in metric_cache.batches for e in batch]
    assert '本通冻结的专用摘要提示词' in seen[0][0][0]['content']
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));assert row.summary_status=='ready' and row.sort_seq==1
        jobs=(await db.scalars(select(VoicePostprocessJob))).all()
        assert {job.job_type for job in jobs}=={'memory_compensation','call_summary'}

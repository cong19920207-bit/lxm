from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn,Gate,Writer
from tests.test_realtime_voice_step031_metrics import CounterCache


def events(sink):return [e for batch in sink.batches for e in batch]


@pytest.mark.asyncio
async def test_retry_exhaustion_claims_and_no_poll_inflation(memory_env):
    factory,call=memory_env;sink=CounterCache()
    async def model(_):raise RuntimeError('unavailable')
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,metrics=VoiceMetrics(sink))
    await svc.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob));job.created_at=datetime.utcnow()-timedelta(seconds=10)
        await db.commit()
    for attempt in range(1,4):
        assert await svc.process_next(call_id=call)=='failed'
        before=len(sink.batches)
        assert await svc.process_next(call_id=call)==('busy' if attempt<3 else 'idle')
        assert len(sink.batches)==before
        async with factory() as db:
            job=await db.scalar(select(VoiceMemoryJob))
            if attempt<3:job.next_retry_at=datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
    got=events(sink)
    assert got.count(('voice.memory_job.claim',{'phase':'first'},1))==1
    assert got.count(('voice.memory_job.claim',{'phase':'retry'},1))==2
    assert got.count(('voice.memory_job.retry',{'source':'automatic','reason':'extract_unavailable'},1))==2
    assert got.count(('voice.memory_job.drop',{'reason':'extract_unavailable'},1))==1
    durations=[e[2] for e in got if e[0]=='voice.memory_job.enqueue_to_claim_ms']
    assert len(durations)==3 and all(value>=10000 for value in durations)


@pytest.mark.asyncio
async def test_fence_counts_only_committed_cancellation(memory_env):
    factory,call=memory_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),metrics=metrics)
    await svc.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    sink.batches.clear()
    async with factory() as db:
        assert await svc.stage_deletion_fence(db,call_id=call)==1
        await db.rollback();await flush_voice_metrics(db,metrics)
    assert not sink.batches
    for expected in (1,0):
        async with factory() as db:
            assert await svc.stage_deletion_fence(db,call_id=call)==expected
            await db.commit();await flush_voice_metrics(db,metrics)
    assert events(sink).count(('voice.memory_job.fence_cancel',{},1))==1
    assert events(sink).count(('voice.memory_job.drop',{'reason':'deletion_fence'},1))==1


@pytest.mark.asyncio
async def test_compensation_reports_only_missing_jobs(memory_env):
    factory,call=memory_env;sink=CounterCache()
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),metrics=VoiceMetrics(sink))
    await add_turn(factory,call)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ended';await db.commit()
    assert len((await svc.compensate(call_id=call))['created'])==1
    assert (await svc.compensate(call_id=call))['created']==[]
    assert events(sink).count(('voice.memory_job.compensated_jobs',{},1))==1
    assert ('voice.memory_job.compensate',{'result':'no_change'},1) in events(sink)

from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step034_content_retention import seed,Cache
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step034_delete import ADMIN


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',[False,True])
async def test_delete_metrics_reflect_commit_not_rolled_back_changes(card_env,failure):
    factory,call_id=card_env;now=datetime.utcnow();sink=CounterCache()
    await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        for model in (VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob):
            job=await db.scalar(select(model));job.status='pending'
        await db.commit()
    class BrokenCache:
        async def delete(self,key):raise ConnectionError('private-cache-error')
    service=VoiceRetentionService(session_factory=factory,cache=BrokenCache() if failure else Cache(),metrics=VoiceMetrics(sink))
    if failure:
        with pytest.raises(ConnectionError):await service.delete_call(call_id=call_id,admin=ADMIN)
        assert [e for batch in sink.batches for e in batch]==[
            ('voice.retention.single_call_delete',{'result':'failure'},1),
            ('voice.retention.retry',{'reason':'delete_unavailable'},1)]
        async with factory() as db:assert (await db.scalar(select(VoiceCall))).deleted_at is None
    else:
        await service.delete_call(call_id=call_id,admin=ADMIN)
        await service.delete_call(call_id=call_id,admin=ADMIN)
        events=[e for batch in sink.batches for e in batch]
        for kind in ('memory','postprocess','followup'):
            assert events.count(('voice.retention.cancel',{'kind':kind,'reason':'deletion_fence'},1))==1
        assert events.count(('voice.memory_job.fence_cancel',{},1))==1
        assert events.count(('voice.memory_job.drop',{'reason':'deletion_fence'},1))==1
        assert events.count(('voice.followup.cancel',{'reason':'deletion_fence'},1))==1
        assert ('voice.retention.fence',{'result':'set'},1) in events
        assert ('voice.retention.fence',{'result':'existing'},1) in events
        assert ('voice.retention.single_call_delete',{'result':'deleted'},1) in events
        assert ('voice.retention.single_call_delete',{'result':'repeated'},1) in events
        assert not any(e[0]=='voice.summary.reasoning_expiry' for e in events)


@pytest.mark.asyncio
async def test_expiry_scan_counts_attempts_but_cancellation_only_once(card_env):
    factory,call_id=card_env;now=datetime.utcnow();sink=CounterCache()
    await seed(factory,call_id,now,now-timedelta(days=1))
    async with factory() as db:
        (await db.scalar(select(VoiceFollowupJob))).status='pending';await db.commit()
    service=VoiceRetentionService(session_factory=factory,cache=Cache(),metrics=VoiceMetrics(sink))
    await service.purge_contents(now=now);await service.purge_contents(now=now)
    events=[e for batch in sink.batches for e in batch]
    assert events.count(('voice.retention.expiry_scan',{'kind':'contents','result':'success'},1))==2
    assert events.count(('voice.followup.cancel',{'reason':'source_expired'},1))==1
    assert events.count(('voice.summary.reasoning_expiry',{},1))==1


@pytest.mark.asyncio
async def test_initial_delete_audit_failure_is_observed(card_env,monkeypatch):
    factory,call_id=card_env;sink=CounterCache()
    async def fail(*args,**kwargs):raise RuntimeError('private-audit-error')
    monkeypatch.setattr('backend.utils.admin_auth.log_operation',fail)
    service=VoiceRetentionService(session_factory=factory,cache=Cache(),metrics=VoiceMetrics(sink))
    with pytest.raises(RuntimeError):await service.delete_call(call_id=call_id,admin=ADMIN)
    assert [e for batch in sink.batches for e in batch]==[
        ('voice.retention.single_call_delete',{'result':'failure'},1),
        ('voice.retention.retry',{'reason':'delete_unavailable'},1)]
    async with factory() as db:assert (await db.scalar(select(VoiceCall))).deleted_at is None


@pytest.mark.asyncio
async def test_expiry_emits_memory_job_drop_after_commit(card_env):
    factory,call_id=card_env;now=datetime.utcnow();sink=CounterCache()
    await seed(factory,call_id,now,now-timedelta(seconds=1))
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob));job.status='pending';await db.commit()
    svc=VoiceRetentionService(session_factory=factory,cache=Cache(),metrics=VoiceMetrics(sink))
    await svc.purge_contents(now=now)
    await svc.purge_contents(now=now)
    events=[e for batch in sink.batches for e in batch]
    assert events.count(('voice.memory_job.drop',{'reason':'source_expired'},1))==1
    assert not any(e[0]=='voice.memory_job.fence_cancel' for e in events)

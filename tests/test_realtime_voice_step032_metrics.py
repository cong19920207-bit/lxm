from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall, VoiceFollowupJob
from backend.services.realtime_voice_metric_service import VoiceMetrics, flush_voice_metrics
from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
from backend.services.realtime_voice_state_service import transition_call
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step032_dispatch import dispatch_env,worker
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step031_jobs import summary_env,service as summary_service


@pytest.mark.asyncio
@pytest.mark.parametrize('case',['sent','deleted','retry','count_retry','window','lease'])
async def test_consumer_metrics_follow_committed_transitions(dispatch_env,case):
    factory,call_id,job_id,clock=dispatch_env;cache=CounterCache()
    async def quota(**kwargs):
        if case=='retry':raise RuntimeError('private-provider-error')
        return True
    async def count(**kwargs):
        if case=='count_retry':raise RuntimeError('private-counter-error')
    service=worker(dispatch_env,quota=quota,count=count);service.metrics=VoiceMetrics(cache)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));job=await db.get(VoiceFollowupJob,job_id)
        if case=='deleted':call.deletion_fence_at=clock[0]
        if case=='window':clock[0]=clock[0].replace(hour=13)
        if case=='lease':
            job.status='processing';job.lease_owner='old';job.lease_expires_at=clock[0]-timedelta(seconds=1)
        await db.commit()
    await service.process(job_id=job_id)
    events=[event for batch in cache.batches for event in batch]
    expected={
        'sent':[('voice.followup.send',{'result':'sent'},1)],
        'deleted':[('voice.followup.cancel',{'reason':'source_deleted'},1)],
        'retry':[('voice.followup.retry',{'reason':'dispatch_unavailable'},1)],
        'count_retry':[('voice.followup.send',{'result':'sent'},1),('voice.followup.retry',{'reason':'count_pending'},1)],
        'window':[('voice.followup.schedule',{'result':'window_deferred'},1)],
        'lease':[('voice.followup.retry',{'reason':'lease_expired'},1),('voice.followup.send',{'result':'sent'},1)]}
    assert events==expected[case]
    before=list(cache.batches);await service.process(job_id=job_id);assert cache.batches==before


@pytest.mark.asyncio
async def test_schedule_rollback_discards_events_and_replay_does_not_recount(card_env):
    factory,call_id=card_env;cache=CounterCache();metrics=VoiceMetrics(cache)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='missed';call.connected_at=None;call.ended_at=datetime(2026,9,19,2)
        await db.commit()
        await stage_missed_followup(db,call=call,jitter_minutes=0)
        assert cache.batches==[]
        await db.rollback();await flush_voice_metrics(db,metrics)
        assert cache.batches==[]
        call=await db.scalar(select(VoiceCall))
        await stage_missed_followup(db,call=call,jitter_minutes=0)
        await db.commit();await flush_voice_metrics(db,metrics)
        assert cache.batches==[[('voice.followup.branch',{'branch':'missed'},1),('voice.followup.schedule',{'result':'pending'},1)]]
        await stage_missed_followup(db,call=call,jitter_minutes=0)
        await db.commit();await flush_voice_metrics(db,metrics)
        assert len(cache.batches)==1


@pytest.mark.asyncio
async def test_missed_transition_owner_flushes_only_after_commit(card_env):
    factory,call_id=card_env;cache=CounterCache()
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ringing';call.connected_at=None;await db.commit()
        assert await transition_call(db,call_id=call_id,expected=('ringing',),target='missed',
            now=datetime(2026,9,19,2,tzinfo=timezone.utc),metrics=VoiceMetrics(cache))
    assert [e[0] for batch in cache.batches for e in batch]==['voice.timeline.insert','voice.followup.branch','voice.followup.schedule','voice.state.transition']


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback',[False,True])
async def test_summary_topic_candidate_events_share_summary_commit(summary_env,rollback):
    import json
    from backend.models.relationship import Relationship
    from backend.services.realtime_voice_summary_followup_service import stage_summary_followup
    from tests.test_realtime_voice_step031_summary import output
    factory,call_id=summary_env;cache=CounterCache()
    async with factory() as db:
        db.add(Relationship(user_id=1,level=1,growth_value=20));await db.commit()
    async def model(prompt):return json.dumps(output())
    async def candidate(db,**kwargs):
        await stage_summary_followup(db,**kwargs)
        if rollback:raise RuntimeError('private-failure')
    service=summary_service(factory,model=model,stage_followup=candidate);service.metrics=VoiceMetrics(cache)
    await service.enqueue(call_id=call_id)
    assert await service.process(call_id=call_id)==('failed' if rollback else 'ready')
    events=[e for batch in cache.batches for e in batch if e[0].startswith('voice.followup.')]
    assert events==([] if rollback else [('voice.followup.branch',{'branch':'topic'},1),('voice.followup.schedule',{'result':'pending'},1)])

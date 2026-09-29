import json
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall, VoicePostprocessJob
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step031_jobs import summary_env, service
from tests.test_realtime_voice_step021_cards import card_env, memory_env, storage
from tests.test_realtime_voice_step031_summary import output


class CounterCache:
    def __init__(self): self.batches = []; self.histograms = []
    async def eval(self, script, n, *args):
        batch = [(args[i].rsplit(':',1)[0], json.loads(args[n+2*i]), args[n+2*i+1]) for i in range(n)]
        self.histograms.extend(row for row in batch if row[0].startswith('voice.duration_histogram:'))
        self.batches.append([row for row in batch if not row[0].startswith('voice.duration_histogram:')])


@pytest.mark.asyncio
async def test_fenced_late_result_does_not_report_nonexistent_card_update(summary_env):
    factory,call_id=summary_env;cache=CounterCache()
    async def model(prompt):
        async with factory() as db:
            call=await db.scalar(select(VoiceCall));call.deletion_fence_at=datetime.utcnow();await db.commit()
        return json.dumps(output(should_send_followup=False))
    worker=service(factory,model=model);worker.metrics=VoiceMetrics(cache)
    await worker.enqueue(call_id=call_id)
    assert await worker.process(call_id=call_id)=='cancelled'
    assert [e for batch in cache.batches for e in batch]==[
        ('voice.summary.eligible',{'result':'eligible'},1),('voice.summary.result',{'result':'cancelled'},1)]


@pytest.mark.asyncio
async def test_retention_owner_reports_reasoning_expiry_without_double_count(summary_env):
    from backend.services.realtime_voice_retention_service import VoiceRetentionService
    factory,call_id=summary_env;worker=service(factory);cache=CounterCache()
    worker.metrics=VoiceMetrics(cache)
    await worker.enqueue(call_id=call_id);await worker.process(call_id=call_id)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.reasoning_expires_at=datetime.utcnow()-timedelta(days=1);await db.commit()
    retention=VoiceRetentionService(session_factory=factory,cache=cache,metrics=worker.metrics)
    await retention.purge_contents()
    assert await worker.purge_reasoning()==0
    assert [e for batch in cache.batches for e in batch if e[0]=='voice.summary.reasoning_expiry']==[('voice.summary.reasoning_expiry',{},1)]


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['ready','ineligible','invalid','model_error','configuration','commit_failure','source_expired','lease_expired'])
async def test_summary_transition_events_are_closed_and_not_replayed(summary_env, case):
    factory, call_id = summary_env
    cache = CounterCache()
    async def model(prompt):
        if case == 'invalid': return 'not-json-private-body'
        if case == 'model_error': raise ConnectionError('private-provider-secret')
        return json.dumps(output(should_send_followup=case=='commit_failure'))
    async def failing_candidate(*args, **kwargs): raise RuntimeError('private-storage-content')
    worker = service(factory, model=model, stage_followup=failing_candidate)
    worker.metrics = VoiceMetrics(cache)
    await worker.enqueue(call_id=call_id)
    async with factory() as db:
        call = await db.scalar(select(VoiceCall)); job = await db.scalar(select(VoicePostprocessJob))
        if case == 'ineligible': call.duration_seconds = 14
        if case == 'configuration': call.config_snapshot = {**call.config_snapshot,'resolved_config':{'summary':{'model':'invalid'}}}
        if case == 'source_expired': call.transcript_expires_at = datetime.utcnow()-timedelta(days=1)
        if case == 'lease_expired':
            job.status='processing'; job.lease_expires_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    expected = {'ready':'ready','ineligible':'not_applicable','source_expired':'cancelled'}.get(case,'failed')
    assert await worker.process(call_id=call_id) == expected
    events = [event for batch in cache.batches for event in batch]
    assert ('voice.summary.result', {'result':expected}, 1) in events
    if expected in {'ready','failed','not_applicable'}:
        assert ('voice.summary.card_update', {'status':expected}, 1) in events
        assert ('voice.timeline.update', {'status':expected}, 1) in events
    if case in {'ready','invalid','model_error','commit_failure'}:
        assert ('voice.summary.eligible', {'result':'eligible'}, 1) in events
    if expected == 'failed':
        reason={'invalid':'invalid_or_rejected_output','model_error':'model_unavailable',
            'configuration':'summary_configuration_invalid','commit_failure':'result_commit_failed',
            'lease_expired':'lease_expired'}[case]
        assert ('voice.summary.failure', {'reason':reason}, 1) in events
        assert ('voice.summary.static_fallback', {'reason':reason}, 1) in events
    before = list(cache.batches)
    await worker.process(call_id=call_id)
    assert cache.batches == before
    encoded = json.dumps(cache.batches)
    assert call_id not in encoded and 'private' not in encoded


@pytest.mark.asyncio
async def test_reasoning_expiry_counts_actual_clears_only(summary_env):
    factory, call_id=summary_env; worker=service(factory); cache=CounterCache();worker.metrics=VoiceMetrics(cache)
    await worker.enqueue(call_id=call_id);await worker.process(call_id=call_id)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.reasoning_expires_at=datetime.utcnow()-timedelta(days=1);await db.commit()
    assert await worker.purge_reasoning()==1
    assert await worker.purge_reasoning()==0
    assert [e for batch in cache.batches for e in batch if e[0]=='voice.summary.reasoning_expiry']==[('voice.summary.reasoning_expiry',{},1)]


@pytest.mark.asyncio
async def test_metric_failure_does_not_change_committed_summary(summary_env,caplog):
    class Unavailable:
        async def eval(self,*args):raise ConnectionError('private-body-or-key')
    factory,call_id=summary_env;worker=service(factory);worker.metrics=VoiceMetrics(Unavailable())
    await worker.enqueue(call_id=call_id)
    assert await worker.process(call_id=call_id)=='ready'
    assert 'private-body-or-key' not in caplog.text
    assert 'voice.metrics.emit_unavailable' in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('event',[
    ('voice.summary.result',{'result':'ready','call_id':'private'},1),
    ('voice.summary.result',{'result':'private-content'},1),
    ('llm_stats',{},1),('voice.summary.reasoning_expiry',{},float('nan')),
    ('voice.summary.reasoning_expiry',{},True),
])
async def test_metric_schema_rejects_sensitive_or_unbounded_inputs(event):
    cache=CounterCache()
    assert await VoiceMetrics(cache).emit_many([event]) is False
    assert cache.batches==[]

import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_ops_service import VoiceOpsService
from tests.test_realtime_voice_step018_ending import policy
from tests.test_realtime_voice_step009_ops import storage,StateCache,add_call
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
async def test_policy_trigger_counts_are_not_terminal_facts():
    p=policy();sink=CounterCache()
    for now in (0,6,12,22,30):p.tick(now=now,waiting=True,mic_ok=True,remaining=100)
    events=p.take_metrics()
    assert events==[('voice.finalizer.policy',{'kind':kind},1) for kind in ('silence_confirm','silence_goodbye','silence_timeout')]
    assert p.take_metrics()==[]
    p=policy()
    for now in (100,110,130,140):p.tick(now=now,waiting=False,mic_ok=False,remaining=0,grace_deadline=130)
    assert p.take_metrics()==[('voice.finalizer.policy',{'kind':kind},1) for kind in ('grace_started','time_low','quota_exhausted')]
    p=policy();p.tick(now=3600,waiting=False,mic_ok=False,remaining=100)
    events+=p.take_metrics()
    assert await VoiceMetrics(sink).emit_many(events)


@pytest.mark.asyncio
async def test_finalizer_commit_then_replay_does_not_change_reason(storage):
    sink=CounterCache();cache=StateCache();call_id=await add_call(storage,'connected',cache)
    ops=VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink))
    await ops.end_call(call_id=call_id,reason='hard_limit')
    await ops.end_call(call_id=call_id,reason='system_error')
    assert [e for b in sink.batches for e in b if e[0].startswith('voice.finalizer.')]==[
        ('voice.finalizer.end_reason',{'reason':'hard_limit'},1),('voice.finalizer.replay',{},1)]


@pytest.mark.asyncio
async def test_finalizer_commit_failure_emits_no_success(storage,monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    cache=StateCache();call_id=await add_call(storage,'connected',cache);sink=CounterCache()
    async def fail(self):raise RuntimeError('private-commit')
    monkeypatch.setattr(AsyncSession,'commit',fail)
    with pytest.raises(RuntimeError):await VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink)).end_call(call_id=call_id)
    assert not sink.batches

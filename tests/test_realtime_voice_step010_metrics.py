import pytest
from uuid import uuid4
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_create_service import VoicePreflightError
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step010_create import state,create,test_each_preflight_block_leaves_no_call_stub_account_ledger_or_lease as check_block


@pytest.mark.asyncio
@pytest.mark.parametrize('condition,reason',[
    ('db_ban','user_banned'),('redis_ban','user_banned'),('quota','quota_empty'),('allowlist','not_allowlisted'),
    ('soft_stop','soft_stop'),('maintenance','maintenance'),('disabled','disabled'),('cooldown','dial_cooldown'),
    ('browser','browser_unsupported'),('microphone','microphone_denied'),('capacity','capacity_full'),('provider','provider_unavailable')])
async def test_preflight_block_classification_and_no_residue(state,condition,reason):
    sink=CounterCache();state.service.metrics=VoiceMetrics(sink)
    await check_block(state,condition)
    assert [e for b in sink.batches for e in b]==[('voice.preflight.result',{'result':'blocked'},1),
        ('voice.preflight.block_reason',{'reason':reason},1)]


@pytest.mark.asyncio
async def test_preflight_commit_replay_conflict_and_existing_call(state):
    sink=CounterCache();state.service.metrics=VoiceMetrics(sink);key=str(uuid4())
    first=await create(state,key);assert await create(state,key)==first
    with pytest.raises(VoicePreflightError):await create(state,key,{**state.payload,'device_id':str(uuid4())})
    with pytest.raises(VoicePreflightError):await create(state)
    events=[e for b in sink.batches for e in b]
    assert events==[('voice.preflight.result',{'result':'created'},1),
        ('voice.preflight.result',{'result':'replay'},1),('voice.preflight.idempotency',{'result':'replay'},1),
        ('voice.preflight.result',{'result':'blocked'},1),('voice.preflight.block_reason',{'reason':'IDEMPOTENCY_KEY_REUSED'},1),
        ('voice.preflight.idempotency',{'result':'conflict'},1),('voice.preflight.result',{'result':'blocked'},1),
        ('voice.preflight.block_reason',{'reason':'user_busy'},1)]


@pytest.mark.asyncio
async def test_cancel_during_post_commit_metric_keeps_call_and_lease(state):
    import asyncio
    from sqlalchemy import select
    from backend.models.realtime_voice import VoiceCall
    entered=asyncio.Event()
    class BlockingMetrics:
        async def emit_many(self,events):
            assert events==[('voice.preflight.result',{'result':'created'},1)]
            entered.set();await asyncio.Future()
    state.service.metrics=BlockingMetrics()
    task=asyncio.create_task(create(state));await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    call=await state.db.scalar(select(VoiceCall))
    assert call.status=='deciding' and state.leases.owners[1]==call.call_id

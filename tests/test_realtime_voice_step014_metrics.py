from datetime import datetime,timezone
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_state_service import transition_call
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step009_ops import storage,StateCache,add_call
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
async def test_state_committed_transition_replay_and_invalid(storage):
    sink=CounterCache();cache=StateCache();call_id=await add_call(storage,'ringing',cache)
    async with storage() as db:
        assert await transition_call(db,call_id=call_id,expected=('ringing',),target='cancelled',
            now=datetime.now(timezone.utc),metrics=VoiceMetrics(sink))
        assert not await transition_call(db,call_id=call_id,expected=('ringing',),target='cancelled',
            now=datetime.now(timezone.utc),metrics=VoiceMetrics(sink))
        with pytest.raises(ValueError):await transition_call(db,call_id=call_id,expected=('ending',),target='ringing',
            now=datetime.now(timezone.utc),metrics=VoiceMetrics(sink))
    assert [e for b in sink.batches for e in b]==[
        ('voice.state.transition',{'from':'ringing','to':'cancelled','reason':'user_cancel'},1),
        ('voice.state.terminal_replay',{},1),('voice.state.invalid_transition',{},1)]


@pytest.mark.asyncio
async def test_state_failed_commit_never_emits_transition(storage,monkeypatch):
    sink=CounterCache();call_id=await add_call(storage,'ringing',StateCache())
    async with storage() as db:
        async def fail():raise RuntimeError('private-commit')
        monkeypatch.setattr(db,'commit',fail)
        with pytest.raises(RuntimeError):await transition_call(db,call_id=call_id,expected=('ringing',),target='cancelled',
            now=datetime.now(timezone.utc),metrics=VoiceMetrics(sink))
        await db.rollback()
    assert sink.batches==[]
    async with storage() as db:assert (await db.scalar(select(VoiceCall))).status=='ringing'


@pytest.mark.asyncio
async def test_ops_finalizer_emits_actual_state_once(storage):
    sink=CounterCache();cache=StateCache();call_id=await add_call(storage,'connected',cache)
    service=VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink))
    await service.end_call(call_id=call_id,reason='user_hangup');await service.end_call(call_id=call_id,reason='system_error')
    events=[e for b in sink.batches for e in b if e[0].startswith('voice.state.')]
    assert events==[('voice.state.transition',{'from':'connected','to':'ended','reason':'user_hangup'},1),
        ('voice.state.terminal_replay',{},1)]


@pytest.mark.asyncio
async def test_http_end_observation_wait_is_after_required_cleanup(storage,monkeypatch):
    import asyncio
    from uuid import UUID
    from backend.routers import realtime_voice as route
    cache=StateCache();call_id=await add_call(storage,'ringing',cache);entered=asyncio.Event()
    class Blocking:
        async def emit_many(self,events):
            assert ('voice:control:end',call_id) in cache.events
            entered.set();await asyncio.Future()
    async def redis():return cache
    monkeypatch.setattr(route,'get_redis',redis);monkeypatch.setattr(route,'async_session_maker',storage)
    monkeypatch.setattr(route,'ApplicationVoiceMetrics',Blocking)
    async with storage() as db:
        task=asyncio.create_task(route.end_call(UUID(call_id),user_id=1,db=db))
        await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    async with storage() as db:assert (await db.scalar(select(VoiceCall))).status=='cancelled'

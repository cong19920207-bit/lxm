"""Lifecycle contract: illegal rollback, anchored timing and terminal replay."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_decision_service import transition_call
from backend.services.realtime_voice_ops_service import VoiceOpsService
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache


@pytest.mark.asyncio
async def test_reconnect_keeps_first_connected_anchor_and_terminal_never_revives(storage):
    cache = StateCache()
    call_id = await add_call(storage, 'deciding', cache)
    start = datetime(2026, 9, 12, tzinfo=timezone.utc)
    async with storage() as db:
        for offset, before, after in [(0,'deciding','ringing'), (4,'ringing','connected'),
                                      (8,'connected','reconnecting'), (10,'reconnecting','connected'),
                                      (12,'connected','ending')]:
            assert await transition_call(db, call_id=call_id, expected=(before,), target=after,
                                         now=start+timedelta(seconds=offset))
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.connected_at == datetime(2026,9,12,0,0,4)
        with pytest.raises(ValueError):
            await transition_call(db, call_id=call_id, expected=('ending',), target='connected', now=start)


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['user_hangup','user_cancel','exit_intent','silence_timeout',
    'quota_exhausted','hard_limit','reconnect_timeout','provider_error','system_error'])
async def test_each_end_reason_settles_once_and_replay_preserves_first_reason(storage, reason):
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    ops = VoiceOpsService(cache=cache, session_factory=storage)
    assert (await ops.end_call(call_id=call_id, reason=reason))['changed']
    async with storage() as db:
        first = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        ended_at = first.ended_at
        assert first.end_reason == reason and first.free_seconds_used == 9
    assert not (await ops.end_call(call_id=call_id, reason='system_error'))['changed']
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert (row.status, row.end_reason, row.ended_at) == ('ended', reason, ended_at)
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('reason,target', [('user_cancel','cancelled'), ('provider_error','failed'), ('system_error','failed')])
async def test_preconnection_end_is_not_a_connected_call(storage, reason, target):
    cache = StateCache()
    call_id = await add_call(storage, 'ringing', cache)
    await VoiceOpsService(cache=cache, session_factory=storage).end_call(call_id=call_id, reason=reason)
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert (row.status,row.end_reason,row.connected_at,row.summary_status) == (target,reason,None,'not_applicable')
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('before,target', [('ended','connected'),('connected','ringing'),
    ('reconnecting','ringing'),('deciding','connected'),('missed','ending'),('failed','ringing'),('cancelled','ringing')])
async def test_illegal_transition_has_no_write(storage, before, target):
    cache = StateCache()
    call_id = await add_call(storage, before, cache)
    async with storage() as db:
        with pytest.raises(ValueError):
            await transition_call(db, call_id=call_id, expected=(before,), target=target, now=datetime.now(timezone.utc))
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == before


@pytest.mark.asyncio
async def test_cancelled_finalizer_finishes_settlement_before_propagating_cancel(storage):
    import asyncio
    from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
    from backend.services.realtime_voice_quota_service import ConnectedMeter
    import json
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    meter = ConnectedMeter(**json.loads(cache.data['voice:quota:'+call_id]))
    entered, release = asyncio.Event(), asyncio.Event()
    async def stop():
        entered.set()
        await release.wait()
    local_voice_calls[call_id] = LocalVoiceCall(meter, stop)
    task = asyncio.create_task(VoiceOpsService(cache=cache, session_factory=storage).end_call(call_id=call_id))
    try:
        await entered.wait()
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with storage() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert row.status == 'ended' and row.free_seconds_used == 9
        assert call_id not in local_voice_calls
    finally:
        local_voice_calls.pop(call_id, None)


@pytest.mark.asyncio
async def test_flush_failure_rolls_back_then_retry_commits_facts_and_charge_together(storage):
    import json
    from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
    from backend.services.realtime_voice_quota_service import ConnectedMeter
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    meter = ConnectedMeter(**json.loads(cache.data['voice:quota:'+call_id]))
    async def stop(): pass
    fail = [True]
    async def flush(db):
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        row.summary_status = 'not_applicable'
        if fail[0]:
            raise RuntimeError('flush failed')
    local_voice_calls[call_id] = LocalVoiceCall(meter, stop, final_flush=flush)
    ops = VoiceOpsService(cache=cache, session_factory=storage)
    try:
        with pytest.raises(RuntimeError, match='flush failed'):
            await ops.end_call(call_id=call_id)
        async with storage() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert (row.status, row.summary_status) == ('connected', 'pending')
            assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0
        assert not cache.events and call_id in local_voice_calls
        fail[0] = False
        await ops.end_call(call_id=call_id)
        async with storage() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert (row.status, row.summary_status, row.free_seconds_used) == ('ended','not_applicable',9)
        assert call_id not in local_voice_calls
    finally:
        local_voice_calls.pop(call_id, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['missed','failed','cancelled'])
async def test_reconcile_retries_resource_cleanup_for_all_terminal_kinds(storage, target):
    cache = StateCache()
    call_id = await add_call(storage, 'deciding', cache)
    async with storage() as db:
        await transition_call(db, call_id=call_id, expected=('deciding',), target=target, now=datetime.now(timezone.utc))
    await VoiceOpsService(cache=cache, session_factory=storage).reconcile()
    assert ('voice:control:end', call_id) in cache.events


@pytest.mark.asyncio
async def test_finalize_hooks_once_after_flush_before_committed_cleanup(storage):
    import json
    from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
    from backend.services.realtime_voice_quota_service import ConnectedMeter
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    meter = ConnectedMeter(**json.loads(cache.data['voice:quota:'+call_id]))
    effects = []
    async def stop(): effects.append('stop')
    async def flush(db):
        assert not cache.events
        effects.append('flush')
    async def finalize(db, row):
        assert row.status == 'ended' and row.free_seconds_used == 9
        assert not cache.events
        effects.append('jobs')
    local_voice_calls[call_id] = LocalVoiceCall(meter, stop, final_flush=flush, on_finalize=finalize)
    try:
        ops = VoiceOpsService(cache=cache, session_factory=storage)
        await ops.end_call(call_id=call_id)
        await ops.end_call(call_id=call_id)
        assert effects == ['stop','flush','jobs']
        assert cache.events
    finally:
        local_voice_calls.pop(call_id, None)

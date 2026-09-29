"""Rolled-back quota deadlocks retry without consuming pending final turn work."""
import json

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError

from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_quota_service import ConnectedMeter, VoiceQuotaService
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache


@pytest.mark.asyncio
@pytest.mark.parametrize('code,failures,expected_attempts', [(1213,2,3),(1213,5,4),(1205,1,1)])
async def test_quota_retry_rolls_back_before_final_flush(storage, monkeypatch, code, failures, expected_attempts):
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    meter = ConnectedMeter(**json.loads(cache.data['voice:quota:'+call_id]))
    settle = VoiceQuotaService.settle
    attempts, hooks, sessions = [], [], []
    async def flaky(self, db, current):
        sessions.append(db)
        attempts.append(1)
        await settle(self, db, current)
        if len(attempts) <= failures:
            raise OperationalError('synthetic quota write', {}, Exception(code, 'fixture transaction error'))
    monkeypatch.setattr(VoiceQuotaService, 'settle', flaky)
    async def stop():
        pass
    async def flush(db):
        hooks.append('flush')
    async def finalized(db, row):
        hooks.append('finalize')
    local_voice_calls[call_id] = LocalVoiceCall(meter, stop, final_flush=flush, on_finalize=finalized)
    try:
        service = VoiceOpsService(cache=cache, session_factory=storage)
        if failures >= expected_attempts:
            with pytest.raises(OperationalError) as caught:
                await service.end_call(call_id=call_id)
            assert caught.value.orig.args[0] == code
            assert hooks == [] and call_id in local_voice_calls and cache.events == []
        else:
            assert (await service.end_call(call_id=call_id))['changed']
            assert hooks == ['flush','finalize']
            assert not (await service.end_call(call_id=call_id))['changed']
            assert hooks == ['flush','finalize']
        assert len(attempts) == expected_attempts
        assert len({id(db) for db in sessions}) == expected_attempts
        async with storage() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            count = await db.scalar(select(func.count()).select_from(VoiceUsageLedger))
            success = failures < expected_attempts
            assert row.status == ('ended' if success else 'connected')
            assert row.free_seconds_used == (9 if success else 0)
            assert count == int(success)
    finally:
        local_voice_calls.pop(call_id,None)

import os
from datetime import datetime,timezone
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_state_service import transition_call
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_state_actual_transaction_and_independent_counters(runtime):
    factory,call_id,cache=runtime;metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ringing';call.connected_at=None;await db.commit()
        args=dict(call_id=call_id,expected=('ringing',),target='cancelled',now=datetime.now(timezone.utc),metrics=metrics)
        assert await transition_call(db,**args)
        assert not await transition_call(db,**args)
        with pytest.raises(ValueError):await transition_call(db,**{**args,'target':'ended'})
    keys=[key async for key in cache.scan_iter(match='voice.state.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.state.transition','voice.state.terminal_replay','voice.state.invalid_transition'}
    for key in keys:
        values=await cache.hgetall(key)
        assert set(values.values())=={'1'} and call_id not in str(values)
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

import os
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_ops_service import VoiceOpsService
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_finalizer_real_commit_and_counters(runtime,card_env):
    factory,call_id,cache=runtime
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ringing';row.connected_at=None;await db.commit()
    ops=VoiceOpsService(cache=cache,session_factory=factory,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await ops.end_call(call_id=call_id,reason='user_cancel');await ops.end_call(call_id=call_id)
    keys=[key async for key in cache.scan_iter(match='voice.finalizer.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.finalizer.end_reason','voice.finalizer.replay'}
    for key in keys:
        assert set((await cache.hgetall(key)).values())=={'1'}
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

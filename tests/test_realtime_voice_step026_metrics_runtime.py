import os
import pytest
from backend.services.realtime_voice_context_pack_service import context_pack_events
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step026_metrics import pack_for
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_compiler_actual_redis_crops_and_size(runtime):
    cache=runtime[2];pack,barrier=await pack_for()
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    events=context_pack_events(pack=pack,error=None,elapsed_ms=1,barrier_released=barrier.is_set())
    assert await VoiceMetrics(cache,deadline_seconds=1).emit_many(events)
    keys=[key async for key in cache.scan_iter(match='voice.context_pack.*')]
    assert len(keys)==5
    crop=next(key for key in keys if key.startswith('voice.context_pack.crop_count:'))
    assert await cache.hgetall(crop)=={'{}':'13'}
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

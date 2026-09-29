import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step019_metrics import exercise
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_recovery_actual_redis(runtime):
    cache=runtime[2]
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    for result in ('restored','timeout'):await exercise(VoiceMetrics(cache,deadline_seconds=1),result)
    keys=[key async for key in cache.scan_iter(match='voice.reconnect.*')]
    assert len(keys)>=7
    result_key=next(key for key in keys if key.startswith('voice.reconnect.result:'))
    assert await cache.hgetall(result_key)=={'{"result":"restored"}':'1','{"result":"timeout"}':'1'}
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

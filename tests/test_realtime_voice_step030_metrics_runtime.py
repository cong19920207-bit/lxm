import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step030_recall import service,recall,Adapter
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_recall_counters_actual_redis(runtime):
    cache=runtime[2]
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    s=service();s.metrics=VoiceMetrics(cache,deadline_seconds=1)
    assert (await recall(s,adapter=Adapter('next_turn'))).mode=='next_turn_cached'
    assert (await recall(s,turn_index=2)).mode=='current_turn_requested'
    keys=[key async for key in cache.scan_iter(match='voice.recall.*')]
    async def counter(name):return await cache.hgetall(next(k for k in keys if k.startswith('voice.recall.'+name+':')))
    assert await counter('mode')=={'{"mode":"next_turn_cached"}':'1','{"mode":"current_turn_requested"}':'1'}
    assert await counter('cache')=={'{"result":"stored"}':'1','{"result":"hit"}':'1'}
    assert await counter('not_measurable')=={'{"reason":"adoption"}':'1'}
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

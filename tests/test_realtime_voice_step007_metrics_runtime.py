import os
import pytest
from tests.test_realtime_voice_step033_runtime import containers,runtime
from tests.test_realtime_voice_step007_metrics import start
from backend.services.realtime_voice_metric_service import VoiceMetrics
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_provider_actual_redis_counters_no_shared_writes(runtime,monkeypatch):
    cache=runtime[2]
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    adapter,wire=await start(monkeypatch,VoiceMetrics(cache,deadline_seconds=1));await adapter.finish_session()
    keys=[key async for key in cache.scan_iter(match='voice.provider.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.provider.session','voice.provider.start','voice.provider.capability','voice.provider.usage'}
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        values=await cache.hgetall(key)
        assert adapter.call_id not in str(values) and 'private-' not in str(values)
        assert set(values.values())=={'1'}
    assert {key:await cache.get(key) for key in shared}==shared

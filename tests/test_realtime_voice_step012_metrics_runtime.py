import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_ws_metric_service import observed_stream
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_ws_actual_independent_counters_and_rejection(runtime):
    from backend.routers.realtime_voice import stream
    cache=runtime[2];metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async with observed_stream(metrics,'initial'):
        async with observed_stream(metrics,'reconnect'):pass
    async def close(**kwargs):pass
    socket=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(voice_metrics=metrics)),headers={},
        url=SimpleNamespace(query='',scheme='wss'),close=close)
    await stream(socket,str(uuid4()))
    keys=[key async for key in cache.scan_iter(match='voice.ws.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.ws.connection','voice.ws.concurrency','voice.ws.rejection'}
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        if key.startswith('voice.ws.connection:'):assert set((await cache.hgetall(key)).values())=={'1'}
    assert {key:await cache.get(key) for key in shared}==shared

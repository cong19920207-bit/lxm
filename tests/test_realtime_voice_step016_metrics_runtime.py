import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step016_playback import reply,client
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_playback_actual_redis(runtime):
    _,_,cache=runtime
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    engine,_,_=reply()
    engine.client(client('client_barge_in',1,played_audio_ms=0))
    assert await VoiceMetrics(cache,deadline_seconds=1).emit_many(engine.take_metrics())
    keys=[key async for key in cache.scan_iter(match='voice.effective_text.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.effective_text.evidence','voice.effective_text.event'}
    for key in keys:
        assert set((await cache.hgetall(key)).values())=={'1'}
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

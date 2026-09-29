import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_turn_service import VoiceTurnService
from tests.test_realtime_voice_step024_crisis import gate_for,SENTINEL
from tests.test_realtime_voice_step015_turns import event
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_crisis_actual_commit_alert_and_counters(runtime):
    factory,call_id,cache=runtime
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    await cache.set('banned_keywords','[]');await cache.set('active_config:crisis_keywords','["PRIVATE_CRISIS"]')
    signals=[];gate=gate_for(cache,signals)
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await service.consume(event(call_id,1,'asr_final',SENTINEL))
    assert len(signals)==1
    keys=[key async for key in cache.scan_iter(match='voice.crisis.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.crisis.hit','voice.crisis.assessment','voice.crisis.alert'}
    for key in keys:
        assert set((await cache.hgetall(key)).values())=={'1'}
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

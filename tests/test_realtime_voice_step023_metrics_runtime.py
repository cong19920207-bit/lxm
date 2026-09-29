import os
import pytest
from backend.services.realtime_voice_safety_service import VoiceSafetyGate
from backend.services.realtime_voice_turn_service import VoiceTurnService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step015_turns import event
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_safety_actual_gate_and_redis(runtime):
    factory,call_id,cache=runtime
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    await cache.set('banned_keywords','["blocked"]')
    gate=VoiceSafetyGate(cache=cache)
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await turns.consume(event(call_id,1,'asr_final','blocked private'))
    decision=await gate.assess(call_id=call_id,direction='user',text='blocked private')
    await gate.record(call_id=call_id,turn_index=1,direction='user',decision=decision)
    await turns.freeze()
    keys=[key async for key in cache.scan_iter(match='voice.content_safety.*') if '.seen:' not in key]
    assert len(keys)==4
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    result=next(key for key in keys if key.startswith('voice.content_safety.result:'))
    assert await cache.hgetall(result)=={'{"direction":"user","result":"matched"}':'2'}
    assert {key:await cache.get(key) for key in shared}==shared

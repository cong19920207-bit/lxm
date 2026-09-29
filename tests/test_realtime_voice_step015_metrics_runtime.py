import os
import pytest
import pytest_asyncio
from backend.services.realtime_voice_turn_service import VoiceTurnService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step015_turns import Gate,event
from tests.test_realtime_voice_step015_metrics import test_savepoint_discards_only_its_own_observations
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest_asyncio.fixture
async def turn_env(runtime):
    return runtime[:2]


@pytest.mark.asyncio
async def test_turn_real_storage_metrics(runtime):
    factory,call_id,cache=runtime;metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate(),metrics=metrics)
    await service.consume(event(call_id,1,'asr_interim','private-interim'))
    await service.consume(event(call_id,2,'asr_final','private-final'))
    await service.freeze()
    async with factory() as db:
        await service.final_flush(db);await db.commit();await flush_voice_metrics(db,metrics)
    keys=[key async for key in cache.scan_iter(match='voice.turn.*')]
    assert len(keys)==1
    values=await cache.hgetall(keys[0])
    assert values=={'{"kind":"interim"}':'1','{"kind":"final"}':'1','{"kind":"incomplete"}':'1'}
    assert 172790<=await cache.ttl(keys[0])<=172800
    assert {key:await cache.get(key) for key in shared}==shared

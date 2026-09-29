import os,json
import pytest
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step028_runtime import containers,runtime,memory_env
from tests.test_realtime_voice_step028_jobs import add_turn,Gate,Writer
from tests.test_realtime_voice_step028_metrics import atoms
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_extraction_actual_mysql_trace_and_redis(runtime,memory_env):
    factory,call_id=memory_env;cache=runtime[2];writer=Writer()
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async def model(_):return json.dumps({'memory_items':atoms()})
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=writer,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await svc.enqueue(call_id=call_id,turn_id=await add_turn(factory,call_id))
    assert await svc.process_next(call_id=call_id)=='success' and len(writer.calls)==5
    keys=[key async for key in cache.scan_iter(match='voice.memory_*')]
    result_key=next(key for key in keys if key.startswith('voice.memory_upsert.result:'))
    assert await cache.hgetall(result_key)=={'{"result":"written"}':'5'}
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

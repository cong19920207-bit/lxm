"""Isolated MySQL/Redis source observation; vector HTTP remains controlled."""
import json,os
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceMemoryTrace
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.utils.character_knowledge_validate import build_doc_id
from tests.test_realtime_voice_step028_runtime import containers,runtime,memory_env
from tests.test_realtime_voice_step028_jobs import add_turn,Gate

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores opt-in')


@pytest.mark.asyncio
async def test_source_observation_committed_trace_and_real_redis(memory_env,runtime,monkeypatch):
    from backend.utils import dashvector_client as vectors
    from backend.services.embedding_service import embedding_service
    factory,call=memory_env;cache=runtime[2];client=AsyncMock()
    client.upsert.return_value=True
    doc=build_doc_id('user','旅行-计划-日本',1)
    client.fetch_by_ids.return_value={doc:{'fields':{'last_write_source':'text'}}}
    monkeypatch.setattr(vectors,'dashvector_client',client)
    monkeypatch.setattr(embedding_service,'get_embedding',AsyncMock(return_value=[.1]))
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for k,v in shared.items():await cache.set(k,v)
    async def model(_):
        return json.dumps({'memory_items':[{'memory_type':'user','stable_key':'旅行-计划-日本','content':'下月去日本'}]})
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await svc.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    assert await svc.process_next(call_id=call)=='success'
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceMemoryTrace))==1
    assert client.upsert.await_args.kwargs['fields']['last_write_source']=='voice'
    keys=[k async for k in cache.scan_iter(match='voice.memory_upsert.source_observation:*')]
    assert len(keys)==1
    assert await cache.hgetall(keys[0])=={'{"boundary":"prewrite","current":"voice","previous":"text"}':'1'}
    assert 172790 <= await cache.ttl(keys[0]) <= 172800
    assert {k:await cache.get(k) for k in shared}==shared

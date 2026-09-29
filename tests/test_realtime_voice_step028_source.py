"""Real voice job/default writer composition with a controlled vector transport."""
import json
from unittest.mock import AsyncMock
import pytest
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.utils.character_knowledge_validate import build_doc_id
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn,Gate
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('previous',['text','voice','admin',None])
async def test_default_writer_metadata_trace_and_source_counter(memory_env,monkeypatch,previous):
    from backend.utils import dashvector_client as vectors
    from backend.services.embedding_service import embedding_service
    factory,call=memory_env;cache=CounterCache();client=AsyncMock()
    client.upsert.return_value=True
    doc=build_doc_id('user','旅行-计划-日本',1)
    client.fetch_by_ids.return_value={doc:{'fields':{'last_write_source':previous}}}
    monkeypatch.setattr(vectors,'dashvector_client',client)
    monkeypatch.setattr(embedding_service,'get_embedding',AsyncMock(return_value=[.1]))
    async def model(_):
        return json.dumps({'memory_items':[{'memory_type':'user','stable_key':'旅行-计划-日本','content':'下月去日本'}]})
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,metrics=VoiceMetrics(cache))
    await svc.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    assert await svc.process_next(call_id=call)=='success'
    assert client.upsert.await_args.kwargs['fields']['last_write_source']=='voice'
    events=[e for b in cache.batches for e in b]
    assert ('voice.memory_upsert.source_observation',{'previous':previous or 'unknown','current':'voice','boundary':'prewrite'},1) in events
    assert all('旅行' not in str(e) and call not in str(e) for e in events)

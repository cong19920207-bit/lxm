"""Last-writer metadata must follow content without changing embedding or IDs."""
from unittest.mock import AsyncMock
import pytest
from backend.services.vector_memory_write_service import upsert_user_memory
from backend.services import user_vector_memory_service as admin


@pytest.mark.asyncio
async def test_shared_writer_source_is_metadata_only():
    embed = AsyncMock(return_value=[.1, .2])
    client = AsyncMock()
    client.upsert.return_value = True
    first = await upsert_user_memory(memory_type='user', user_id=7, key='旅行-计划-日本',
        value='下月去日本', embed=embed, vector_client=client, last_write_source='voice')
    second = await upsert_user_memory(memory_type='user', user_id=7, key='旅行-计划-日本',
        value='下月去日本', embed=embed, vector_client=client, last_write_source='text')
    assert first == second
    assert [c.args for c in embed.await_args_list] == [('下月去日本',), ('下月去日本',)]
    a, b = [c.kwargs for c in client.upsert.await_args_list]
    assert a['fields'].pop('last_write_source') == 'voice'
    assert b['fields'].pop('last_write_source') == 'text'
    assert a == b


@pytest.mark.asyncio
async def test_admin_edits_replace_source_with_admin(monkeypatch):
    client = AsyncMock()
    client.fetch_by_ids.return_value = {'user_7_旅行-计划-日本': {
        'fields': {'stable_key':'旅行-计划-日本', 'last_write_source':'voice'}}}
    client.upsert.return_value = True
    monkeypatch.setattr(admin, 'dashvector_client', client)
    monkeypatch.setattr(admin.embedding_service, 'get_embedding', AsyncMock(return_value=[.1]))
    from backend.utils.character_knowledge_validate import build_doc_id
    doc = build_doc_id('user','旅行-计划-日本',7)
    client.fetch_by_ids.return_value = {doc:{'fields':{'stable_key':'旅行-计划-日本','last_write_source':'voice'}}}
    result = await admin.user_vector_memory_service.update_entry('user',7,doc,'明年去日本')
    assert 'data' in result
    assert client.upsert.await_args.kwargs['fields']['last_write_source'] == 'admin'


@pytest.mark.asyncio
async def test_text_two_user_routes_and_global_routes_unchanged(monkeypatch):
    from backend.services import memory_llm_service as text
    from tests.test_step6_vector_upsert import TestUpsertStep6Vectors
    client = AsyncMock(); client.upsert.return_value = True
    monkeypatch.setattr(text, 'dashvector_client', client)
    monkeypatch.setattr(text.embedding_service, 'get_embedding', AsyncMock(return_value=[.1]))
    output = TestUpsertStep6Vectors._make_output(**{name:'旅行-计划-日本：下月去日本' for name in (
        'UserSettings','CharacterPrivateSettings','CharacterPublicSettings','CharacterKnowledges')})
    counts = await text.upsert_step6_vectors(output,7)
    assert sum(counts.values()) == 4
    for call in client.upsert.await_args_list:
        fields=call.kwargs['fields']
        if call.kwargs['memory_type'] in {'user','character_private'}:
            assert fields['last_write_source']=='text'
        else:
            assert 'last_write_source' not in fields


@pytest.mark.asyncio
@pytest.mark.parametrize('old', ['voice','text','admin',None,'invalid',[]])
async def test_prewrite_observation_and_legacy_unknown(old):
    from backend.services.memory_write_source import collect_source_observations
    from backend.utils.character_knowledge_validate import build_doc_id
    doc=build_doc_id('user','旅行-计划-日本',7)
    client=AsyncMock(); client.upsert.return_value=True
    client.fetch_by_ids.return_value={doc:{'fields':{'last_write_source':old}}}
    with collect_source_observations() as observations:
        await upsert_user_memory(memory_type='user',user_id=7,key='旅行-计划-日本',value='下月去日本',
            embed=AsyncMock(return_value=[.1]),vector_client=client,last_write_source='voice')
    assert observations == [old if isinstance(old,str) and old in {'voice','text','admin'} else 'unknown']


@pytest.mark.asyncio
async def test_read_failure_does_not_fail_write_and_failed_write_has_no_observation():
    from backend.services.memory_write_source import collect_source_observations
    client=AsyncMock(); client.fetch_by_ids.side_effect=RuntimeError('offline');client.upsert.return_value=True
    kwargs=dict(memory_type='user',user_id=7,key='旅行-计划-日本',value='下月去日本',
        embed=AsyncMock(return_value=[.1]),vector_client=client,last_write_source='voice')
    with collect_source_observations() as observations:
        await upsert_user_memory(**kwargs)
    assert observations == ['unknown']
    client.upsert.return_value=False
    with collect_source_observations() as observations:
        with pytest.raises(RuntimeError,match='memory_vector_write_failed'):
            await upsert_user_memory(**kwargs)
    assert observations == []


@pytest.mark.asyncio
async def test_stalled_source_read_is_bounded_and_cancellation_propagates():
    import asyncio
    from backend.services.memory_write_source import collect_source_observations
    async def stalled(*a): await asyncio.Event().wait()
    client=AsyncMock(); client.fetch_by_ids.side_effect=stalled;client.upsert.return_value=True
    with collect_source_observations() as observations:
        await asyncio.wait_for(upsert_user_memory(memory_type='user',user_id=7,key='旅行-计划-日本',
            value='下月去日本',embed=AsyncMock(return_value=[.1]),vector_client=client),.8)
    assert observations == ['unknown']
    client.fetch_by_ids.side_effect=asyncio.CancelledError
    client.upsert.reset_mock()
    with collect_source_observations():
        with pytest.raises(asyncio.CancelledError):
            await upsert_user_memory(memory_type='user',user_id=7,key='旅行-计划-日本',value='下月去日本',
                embed=AsyncMock(return_value=[.1]),vector_client=client)
    client.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_observations_are_task_local():
    import asyncio
    from backend.services.memory_write_source import collect_source_observations
    from backend.utils.character_knowledge_validate import build_doc_id
    async def write(source):
        client=AsyncMock(); client.upsert.return_value=True
        doc=build_doc_id('user','旅行-计划-日本',7)
        async def fetch(ids):
            await asyncio.sleep(0)
            return {doc:{'fields':{'last_write_source':source}}}
        client.fetch_by_ids.side_effect=fetch
        with collect_source_observations() as observations:
            await upsert_user_memory(memory_type='user',user_id=7,key='旅行-计划-日本',value='下月去日本',
                embed=AsyncMock(return_value=[.1]),vector_client=client,last_write_source='voice')
        return observations
    assert await asyncio.gather(write('text'),write('admin')) == [['text'],['admin']]


def test_recall_rank_ignores_last_writer_metadata():
    from tests.test_realtime_voice_step030_recall import api
    rows=[dict(id='a',content='a',score=.8,fields={'quality':.9,'last_write_source':'voice'}),
          dict(id='b',content='b',score=.8,fields={'quality':.9,'last_write_source':'text'})]
    before=api().rank_results(rows,limit=3,threshold=.7)
    rows[0]['fields']['last_write_source']='text'
    rows[1]['fields']['last_write_source']='voice'
    assert api().rank_results(rows,limit=3,threshold=.7)==before


@pytest.mark.asyncio
async def test_source_roundtrip_on_actual_vector_client_transport(monkeypatch):
    import json,httpx
    from backend.utils import dashvector_client as module
    from backend.services.memory_write_source import collect_source_observations
    from backend.utils.character_knowledge_validate import build_doc_id
    doc=build_doc_id('user','旅行-计划-日本',7)
    docs={doc:{'id':doc,'fields':{'content':'旅行-计划-日本：原内容','last_write_source':'text'}}}
    def handle(request):
        if request.method=='GET':
            return httpx.Response(200,json={'code':0,'output':docs})
        assert request.url.path=='/v1/collections/test/docs/upsert'
        for row in json.loads(request.content)['docs']:docs[row['id']]=row
        return httpx.Response(200,json={'code':0,'message':'success'})
    monkeypatch.setattr(module,'get_dashvector_endpoint',lambda:'https://vector.test')
    monkeypatch.setattr(module,'get_dashvector_collection',lambda:'test')
    client=module.DashVectorClient()
    client._client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(client,'_build_headers',lambda:{})
    try:
        with collect_source_observations() as observations:
            await upsert_user_memory(memory_type='user',user_id=7,key='旅行-计划-日本',value='下月去日本',
                embed=AsyncMock(return_value=[.1]),vector_client=client,last_write_source='voice')
        fetched=await client.fetch_by_ids([doc])
        assert observations==['text']
        assert fetched[doc]['fields']['last_write_source']=='voice'
        assert fetched[doc]['content']=='旅行-计划-日本：下月去日本'
        assert len(docs)==1
    finally:
        await client.close()

"""VOICE-MEM input/output policy and shared full-upsert wire behavior."""
import asyncio
import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_shared_upsert_updates_same_stable_key_with_metadata_only_source(monkeypatch):
    from backend.services.vector_memory_write_service import upsert_user_memory
    from backend.utils.dashvector_client import DashVectorClient
    import backend.utils.dashvector_client as module
    monkeypatch.setattr(module, 'get_dashvector_endpoint', lambda: 'https://vector.test')
    monkeypatch.setattr(module, 'get_dashvector_collection', lambda: 'test')
    docs = {}
    def handle(request):
        assert request.url.path == '/v1/collections/test/docs/upsert'
        data = json.loads(request.content)
        for item in data['docs']:
            docs[item['id']] = item
        return httpx.Response(200, json={'code': 0, 'message': 'success'})
    vector = DashVectorClient()
    vector._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(vector, '_build_headers', lambda: {})
    async def embed(value):
        return [0.5, 0.5]
    try:
        first = await upsert_user_memory(memory_type='user', user_id=7, key='旅行-计划-日本',
                                        value='下周去日本', embed=embed, vector_client=vector)
        second = await upsert_user_memory(memory_type='user', user_id=7, key='旅行-计划-日本',
                                         value='下个月去日本', embed=embed, vector_client=vector)
        assert first == second and len(docs) == 1
        assert docs[first]['fields'] == {'content': '旅行-计划-日本：下个月去日本',
            'stable_key': '旅行-计划-日本', 'key_l1': '旅行', 'key_l2': '旅行-计划', 'user_id': 7, 'type': 'user', 'last_write_source': 'unknown'}
    finally:
        await vector.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,key,value', [('character_global','旅行-计划-日本','计划'),
    ('character_knowledge','旅行-计划-日本','计划'), ('user','只有-两段','计划'),
    ('user','旅行-计划-日本','汉'*101), ('user','旅行-计划-日本', '')])
async def test_invalid_atom_never_reaches_embedding_or_vector(kind, key, value):
    from backend.services.vector_memory_write_service import upsert_user_memory
    async def forbidden(*args, **kwargs):
        pytest.fail('invalid atom reached external sink')
    with pytest.raises(ValueError):
        await upsert_user_memory(memory_type=kind, user_id=7, key=key, value=value, embed=forbidden)


def test_output_validation_dedupes_and_drops_invalid_without_retry():
    from backend.services.realtime_voice_memory_service import parse_memory_items
    raw = json.dumps({'memory_items': [
        {'memory_type':'user', 'stable_key':'旅行-计划-日本', 'content':'下月去日本'},
        {'memory_type':'character_private', 'stable_key':'后续话题-日本-行程', 'content':'下次问准备情况'},
        {'memory_type':'user', 'stable_key':'旅行-计划-日本', 'content':'重复主题'},
        {'memory_type':'character_global', 'stable_key':'全局-设定-性格', 'content':'非法'},
        {'memory_type':'user', 'stable_key':'少了-一段', 'content':'非法'}]})
    items, dropped = parse_memory_items(raw, max_items=5)
    assert len(items) == 2 and dropped == 3
    assert items[0]['content'] == '下月去日本'


def test_output_count_and_schema_are_bounded():
    from backend.services.realtime_voice_memory_service import parse_memory_items
    raw = json.dumps({'memory_items': [{'memory_type':'user', 'stable_key':f'旅行-计划-{i}',
        'content':'计划'} for i in range(8)]})
    items, dropped = parse_memory_items(raw, max_items=5)
    assert len(items) == 5 and dropped == 3
    for invalid in ('[]', '{}', '{"memory_items":{}}', 'not json'):
        with pytest.raises(ValueError):
            parse_memory_items(invalid, max_items=5)


def test_nonstring_type_drops_only_invalid_items():
    from backend.services.realtime_voice_memory_service import parse_memory_items
    raw=json.dumps({'memory_items':[{'memory_type':kind,'stable_key':'旅行-计划-日本','content':'计划'}
        for kind in ([],{},'user')]})
    items,dropped=parse_memory_items(raw,max_items=5)
    assert len(items)==1 and dropped==2


@pytest.mark.asyncio
async def test_extractor_uses_effective_facts_and_preserves_input_boundaries():
    from types import SimpleNamespace
    from backend.services.realtime_voice_memory_service import extract_memory
    received = []
    async def model(prompt):
        received.append(prompt)
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    turn = SimpleNamespace(call_id='call1', turn_index=3, user_text_final='下月去日本',
        assistant_text_effective='到时候看看京都', assistant_text_generated='UNPLAYED_SENTINEL',
        turn_status='finalized', effective_text_evidence='full',
        user_content_safety_status='passed', assistant_content_safety_status='passed',
        user_crisis_status='passed', assistant_crisis_status='passed')
    result = await extract_memory(turn=turn, model=model,
        script={'prompt_template':'只保存长期事实', 'max_items_per_turn':5},
        previous_turn_summary='上轮谈旅行', relationship_context={'level':'friend'})
    assert result.status == 'ready' and len(result.items) == 1
    assert len(received) == 1 and 'UNPLAYED_SENTINEL' not in received[0]
    assert '上轮谈旅行' in received[0] and 'origin_channel' in received[0]


@pytest.mark.asyncio
async def test_extractor_allows_a_model_response_after_the_old_15_second_limit(monkeypatch):
    from types import SimpleNamespace
    import backend.services.realtime_voice_memory_service as memory
    import backend.utils.llm_client as llm

    request_timeouts = []

    class SlowLLMClient:
        async def chat_sync(self, prompt, timeout_sec=None):
            request_timeouts.append(timeout_sec)
            await asyncio.sleep(0.2)  # 20 seconds on the scaled extraction clock.
            return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'

        async def close(self):
            pass

    real_wait_for = asyncio.wait_for

    async def scaled_wait_for(awaitable, timeout):
        return await real_wait_for(awaitable, timeout=timeout / 100)

    monkeypatch.setattr(llm, 'LLMClient', SlowLLMClient)
    monkeypatch.setattr(memory, 'asyncio', SimpleNamespace(wait_for=scaled_wait_for))
    turn = SimpleNamespace(call_id='call1', turn_index=3, user_text_final='下月去日本',
        assistant_text_effective='到时候看看京都', turn_status='finalized',
        effective_text_evidence='full', user_content_safety_status='passed',
        assistant_content_safety_status='passed', user_crisis_status='passed',
        assistant_crisis_status='passed')

    result = await memory.extract_memory(turn=turn,
        script={'prompt_template':'只保存长期事实', 'max_items_per_turn':5})

    assert request_timeouts == [45]
    assert result.status == 'ready'
    assert result.items[0]['content'] == '下月去日本'


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [dict(user_content_safety_status='matched'),
    dict(assistant_content_safety_status='error_allowed'), dict(user_crisis_status='suspected'),
    dict(assistant_crisis_status='matched'), dict(effective_text_evidence='none'),
    dict(user_text_final='嗯，哈哈'), dict(assistant_text_effective=''), dict(turn_status='collecting')])
async def test_nonmeaningful_or_risk_turn_never_calls_extractor(change):
    from types import SimpleNamespace
    from backend.services.realtime_voice_memory_service import extract_memory
    data=dict(call_id='call1', turn_index=3, user_text_final='下月去日本',
        assistant_text_effective='到时候看看京都', turn_status='finalized', effective_text_evidence='full',
        user_content_safety_status='passed', assistant_content_safety_status='passed',
        user_crisis_status='passed', assistant_crisis_status='passed')
    async def model(prompt):
        pytest.fail('unsafe or meaningless turn sent to extraction model')
    result=await extract_memory(turn=SimpleNamespace(**{**data, **change}),         model=model, script={'prompt_template':'facts','max_items_per_turn':5})
    assert result.status == 'skipped' and not result.items


@pytest.mark.parametrize('confidence,expected', [(None,True), (.49,False), (.5,True), (1.,True),
    (float('nan'),False), (float('inf'),False), (-1,False), (1.01,False)])
def test_confirmed_confidence_boundary(confidence, expected):
    from types import SimpleNamespace
    from backend.services.realtime_voice_memory_service import eligible_turn
    turn=SimpleNamespace(user_text_final='下月去日本', assistant_text_effective='好好准备',
        turn_status='finalized', effective_text_evidence='full', user_asr_confidence=confidence,
        user_content_safety_status='passed', assistant_content_safety_status='passed',
        user_crisis_status='passed', assistant_crisis_status='passed')
    assert eligible_turn(turn) is expected


@pytest.mark.asyncio
async def test_adapter_preserves_optional_asr_confidence_without_inventing_it(monkeypatch):
    from tests.test_realtime_voice_step007_provider import connected, response
    adapter, wire = await connected(monkeypatch)
    try:
        await wire.incoming.put(response(450, adapter.session_id, {'question_id':'q1'}))
        await wire.incoming.put(response(451, adapter.session_id, {'question_id':'q1',
            'results':[{'text':'去日本','is_interim':False,'confidence':.49}]}))
        events=[await adapter.receive_event() for _ in range(3)]
        final=next(e for e in events if e.kind=='asr_final')
        assert final.asr_confidence == .49
        assert 'asr_confidence' not in final.public_metadata()
    finally:
        await adapter.finish_session()

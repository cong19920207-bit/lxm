"""Voice memory prompt examples and the actual LLM input/output boundary."""
import json

import httpx
import pytest

from backend.models.realtime_voice import VoiceCallTurn
from backend.services.realtime_voice_memory_service import (
    MEMORY_RULES,
    extract_memory,
    parse_memory_items,
)


def test_voice_output_example_is_valid_for_voice_memory_parser():
    _, heading, section = MEMORY_RULES.partition('【输出示例】')
    assert heading
    explanation, json_start, json_body = section.partition('\n{')
    assert json_start
    assert '仅示范格式' in explanation
    assert '不能当作当前用户的事实' in explanation
    raw_example = '{' + json_body.strip()
    example = json.loads(raw_example)
    assert set(example) == {'memory_items'}
    assert isinstance(example['memory_items'], list)
    assert len(example['memory_items']) <= 5
    assert all(isinstance(item, dict) and
               set(item) == {'memory_type', 'stable_key', 'content'} and
               item['memory_type'] in {'user', 'character_private'}
               for item in example['memory_items'])
    items, dropped = parse_memory_items(raw_example)
    assert items == example['memory_items']
    assert dropped == 0
    with pytest.raises(ValueError, match='voice_memory_schema_invalid'):
        parse_memory_items(section.strip())


@pytest.mark.asyncio
@pytest.mark.parametrize('with_context', [False, True])
async def test_prompt_inputs_and_llm_response_use_the_existing_wire_fields(monkeypatch, with_context):
    import backend.utils.llm_client as llm

    turn = VoiceCallTurn(
        call_id='prompt-test', turn_index=3, user_text_final='我更喜欢先听问题。',
        assistant_text_effective='好，以后每次聊天，我都会先问你现在需要什么。',
        assistant_text_generated='UNPLAYED_SENTINEL', turn_status='interrupted',
        effective_text_evidence='exact_played', user_content_safety_status='passed',
        assistant_content_safety_status='passed', user_crisis_status='passed',
        assistant_crisis_status='passed',
    )
    context = dict(previous_turn_summary='之前总是直接给建议。',
                   relationship_context={'level': 1, 'description': '熟悉的朋友'},
                   short_term_candidates=['先询问我的需要。']) if with_context else {}
    expected_input = {
        'call_id': 'prompt-test', 'turn_index': 3, 'user_text': '我更喜欢先听问题。',
        'assistant_text_effective': '好，以后每次聊天，我都会先问你现在需要什么。',
        'previous_turn_summary': '之前总是直接给建议。' if with_context else '',
        'relationship_context': {'level': 1, 'description': '熟悉的朋友'} if with_context else {},
        'short_term_candidates': ['先询问我的需要。'] if with_context else [],
        'origin_channel': 'voice_call',
    }
    response_items = [
        {'memory_type': 'user', 'stable_key': '沟通-偏好-询问', 'content': '希望先被询问需要。'},
        {'memory_type': 'character_private', 'stable_key': '交流-约定-方式', 'content': '答应以后每次聊天先询问对方需要。'},
    ]
    requests = []

    def handle(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body['stream'] is False
        assert len(body['messages']) == 1
        prompt = body['messages'][0]['content']
        rules, marker, raw_input = prompt.partition('\nINPUT_JSON:\n')
        assert marker
        assert rules == MEMORY_RULES + '\n补充记忆说明'
        assert json.loads(raw_input) == expected_input
        assert 'UNPLAYED_SENTINEL' not in prompt
        return httpx.Response(200, json={
            'choices': [{'message': {'role': 'assistant', 'content': json.dumps(
                {'memory_items': response_items}, ensure_ascii=False)}}],
        })

    client = llm.LLMClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(client, '_build_headers', lambda: {})
    monkeypatch.setattr(llm, 'get_volc_endpoint', lambda: 'https://llm.test')
    monkeypatch.setattr(llm, 'get_volc_model', lambda: 'test-model')
    monkeypatch.setattr(llm, 'LLMClient', lambda: client)
    try:
        result = await extract_memory(
            turn=turn, script={'prompt_template': '补充记忆说明', 'max_items_per_turn': 5},
            **context,
        )
        assert len(requests) == 1
        assert result.status == 'ready'
        assert list(result.items) == response_items
        assert result.dropped == 0
    finally:
        await client.close()

"""Read-only voice prompt access and runtime template compatibility."""
import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

KEYS = ['call_answer', 'recall', 'memory', 'summary', 'time_low',
        'silence_confirm', 'goodbye', 'silence_fallback', 'closing_review', 'followup_review']


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin', 'ai_trainer', 'observer', 'tech_ops', 'ops_admin'])
async def test_prompt_views_enforce_the_existing_prompt_read_roles(monkeypatch, role):
    from backend.main import app
    from backend.utils.admin_auth import get_current_admin

    monkeypatch.setitem(app.dependency_overrides, get_current_admin,
                        lambda: SimpleNamespace(id=1, username='reader', role=role))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/admin/voice/prompt-view')
        assert response.status_code == (200 if role in {'super_admin', 'ai_trainer', 'observer'} else 403)
        if response.status_code != 200:
            return
        catalog = response.json()['data']
        assert catalog['readonly'] is True
        assert len(catalog['groups']) == 7
        assert [item['key'] for group in catalog['groups'] for item in group['items']] == KEYS
        for key in KEYS:
            result = await client.get('/api/admin/voice/prompt-view/' + key)
            assert result.status_code == 200
            data = result.json()['data']
            assert data['prompt_key'] == key and data['readonly'] is True
            assert data['content'].strip() and data['source_files']
        assert (await client.get('/api/admin/voice/prompt-view/explicit_exit')).status_code == 404
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            assert (await client.request(method, '/api/admin/voice/prompt-view/memory', json={})).status_code == 405


@pytest.mark.asyncio
async def test_prompt_views_require_admin_authentication():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/api/admin/voice/prompt-view')).status_code == 401
        assert (await client.get('/api/admin/voice/prompt-view/memory')).status_code == 401


def test_views_include_all_runtime_parts_with_placeholders():
    from backend.services.realtime_voice_prompt_view_service import get_prompt_view
    from backend.services.realtime_voice_memory_service import MEMORY_RULES
    from backend.services.realtime_voice_recall_service import RECALL_RULES
    from backend.services.realtime_voice_summary_service import SUMMARY_RULES
    from backend.services.realtime_voice_followup_topic_service import TOPIC_CHECK_PROMPT

    for key, rules in [('memory', MEMORY_RULES), ('recall', RECALL_RULES),
                       ('summary', SUMMARY_RULES), ('followup_review', TOPIC_CHECK_PROMPT)]:
        content = get_prompt_view(key)['content']
        assert content.startswith(rules + '\n')
        inputs = json.loads(content.split('\nINPUT_JSON:\n')[1])
        assert inputs
    assert '{{memory.prompt_template}}' in get_prompt_view('memory')['content']
    assert '作息-惯性-熬夜' in get_prompt_view('memory')['content']
    assert '{{call_answer.prompt_template}}' in get_prompt_view('call_answer')['content']
    assert '{{summary.prompt_template}}' in get_prompt_view('summary')['content']
    memory_inputs = json.loads(get_prompt_view('memory')['content'].split('\nINPUT_JSON:\n')[1])
    assert set(memory_inputs) == {'call_id', 'turn_index', 'user_text', 'assistant_text_effective',
                                 'previous_turn_summary', 'relationship_context', 'short_term_candidates', 'origin_channel'}


def test_extracted_control_and_decision_templates_preserve_wire_text():
    from backend.services.realtime_voice_prompt_templates import build_control_prompt, build_decision_prompt
    assert build_decision_prompt('接听规则', {'is_first_call': True}) == (
        '接听规则\n只返回JSON：answer为布尔值，delay_seconds为0到12的整数，opening_text最多200字。'
        '\n输入资料：{"is_first_call": true}')
    assert build_control_prompt('time_low') == 'time_low：剩余通话时长有限，只完成当前表达与简短告别，不得开启新话题或新的提问。'
    assert build_control_prompt('silence_confirm') == '请仅简短确认用户是否还在听，不要开启新话题。'
    assert build_control_prompt('goodbye', '我们下次聊') == '请只说一次简短告别，不得开启新话题。可采用：我们下次聊'
    assert build_control_prompt('silence_fallback', '我们下次聊') == 'Speak only this exact text, without additions: 我们下次聊'


@pytest.mark.asyncio
async def test_closing_view_matches_the_prompt_sent_by_the_runtime():
    from backend.services.realtime_voice_ending_service import ClosingSemanticGate
    from backend.services.realtime_voice_prompt_view_service import get_prompt_view

    seen = []
    async def model(prompt):
        seen.append(prompt)
        return '{"allowed": true}'
    assert await ClosingSemanticGate(model=model).allow_reply('{{current_topic}}', '{{candidate_reply}}')
    assert seen == [get_prompt_view('closing_review')['content']]

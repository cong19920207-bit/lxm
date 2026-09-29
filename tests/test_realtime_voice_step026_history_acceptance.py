"""AC8: automatic first-turn history selection and privacy exclusions."""
import asyncio
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest

from tests.test_realtime_voice_step026_sources import factory, NOW
from backend.models.admin_config import AdminConfig
from backend.models.relationship import Relationship
from backend.models.realtime_voice import VoiceCall
from backend.constants.realtime_voice_config import get_default_voice_call_config, get_default_voice_call_script
from backend.services.realtime_voice_context_source_service import DatabaseVoiceContextSource, prepare_voice_context
from backend.utils.character_knowledge_validate import build_doc_id


@pytest.mark.asyncio
async def test_first_context_selects_latest_eligible_history_and_dynamic_memory(factory):
    raw = json.dumps({'background': '稳定人格'}, ensure_ascii=False)
    ref = {'config_key': 'persona', 'version': 1,
           'content_sha256': 'sha256:' + hashlib.sha256(raw.encode()).hexdigest()}
    snapshot = {'resolved_config': get_default_voice_call_config(ref),
                'resolved_script': get_default_voice_call_script()}
    now = NOW.replace(tzinfo=None)

    def history(summary, age, **overrides):
        values = dict(call_id=str(uuid4()), user_id=1, initiated_by='user', status='ended',
                      summary_status='ready', call_summary=summary, ended_at=now-timedelta(minutes=age),
                      config_snapshot=snapshot, capability_snapshot={}, transcript_retention_days=30,
                      generated_retention_days=30, generated_text_expires_at=now+timedelta(days=1))
        values.update(overrides)
        return VoiceCall(**values)

    async with factory() as db:
        db.add_all([
            AdminConfig(config_key='persona', version=1, config_value=raw, is_active=True, is_draft=False),
            Relationship(user_id=1, level=1, growth_value=0, user_hobby_name='小林', relation_description='朋友'),
            history('更旧的摘要', 20), history('上次约好周末去海边', 10),
            history('EXCLUDED_FOREIGN', 1, user_id=2),
            history('EXCLUDED_DELETED', 2, deleted_at=now),
            history('EXCLUDED_FENCED', 3, deletion_fence_at=now),
            history('EXCLUDED_EXPIRED', 4, generated_text_expires_at=now),
            history('EXCLUDED_PENDING', 5, summary_status='pending'),
            history('EXCLUDED_FAILED', 6, status='failed'),
        ])
        await db.commit()

    doc_id = build_doc_id('user', '偏好-旅行-地点', 1)
    calls = []

    async def search(query, user_id):
        calls.append((query, user_id))
        return [('user', {'id': doc_id, 'score': .95, 'fields': {
            'user_id': 1, 'content': '喜欢安静的海边', 'quality': .9,
            'updated_at': NOW.isoformat()}})]

    call = VoiceCall(call_id=str(uuid4()), user_id=1, config_snapshot=snapshot)
    barrier = asyncio.Event()
    pack = await prepare_voice_context(call=call, session_factory=factory, now=NOW, barrier=barrier,
        source=DatabaseVoiceContextSource(factory, memory_search=search))
    assert barrier.is_set() and not pack.degraded
    assert all(text in pack.dynamic for text in ('小林', '上次约好周末去海边', '喜欢安静的海边'))
    assert 'EXCLUDED_' not in pack.dynamic and '更旧的摘要' not in pack.dynamic
    assert len(pack.dynamic) <= 2000 and pack.metadata['memory_count'] == 1
    assert len(calls) == 1 and calls[0][1] == 1 and doc_id not in calls[0][0]

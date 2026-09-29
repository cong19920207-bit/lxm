"""STEP020 C15: production finalization cannot become a text-chat fallback."""
import asyncio
import json
from collections import Counter
from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.database import Base
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_presentation_service import call_presentation
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache


async def rows(factory, model):
    async with factory() as db:
        values = (await db.execute(select(model.__table__))).mappings().all()
        return Counter(json.dumps(dict(row), sort_keys=True, default=str) for row in values)


@pytest.mark.asyncio
@pytest.mark.parametrize('connected', [False, True])
@pytest.mark.parametrize('reason', ['provider_error', 'system_error'])
async def test_error_finalization_preserves_text_rows_and_generation_tasks(storage, monkeypatch, connected, reason):
    from backend.services import chat_service, chat_queue_service
    from backend.services.llm_service import LLMService

    async with storage.kw['bind'].begin() as connection:
        await connection.run_sync(Base.metadata.create_all,
                                  tables=[ConversationLog.__table__, AgentMessage.__table__])
    async with storage() as db:
        # Include existing user/assistant rows and repeated content, not just an empty count.
        db.add_all([ConversationLog(user_id=1, role=role, content='已有文字', sort_seq=i,
                                   round_id='existing-round')
                    for i, role in enumerate(('user', 'assistant', 'user'), 1)])
        db.add(AgentMessage(user_id=1, trigger_type='P0', content='已有主动消息', action_score=7, sort_seq=4))
        await db.commit()
    pending = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(chat_service, '_generation_futures', {'existing': pending})
    monkeypatch.setattr(chat_service, '_generation_results', {'ready': {'messages': ['已有结果']}})
    monkeypatch.setattr(chat_queue_service, '_debounce_tasks', {1: pending})
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append('text-generation')
        raise AssertionError('voice failure must not invoke text generation')

    for name in ('enqueue_send', 'enqueue_resend', 'new_generation_for_user', 'schedule_recovery_bundle'):
        monkeypatch.setattr(chat_service, name, forbidden)
    for name in ('schedule_debounced', 'redis_set_generation'):
        monkeypatch.setattr(chat_queue_service, name, forbidden)
    for name in ('chat', 'chat_with_parse', 'chat_with_step5_parse', 'generate_with_fallback'):
        monkeypatch.setattr(LLMService, name, forbidden)
    before = {model: await rows(storage, model) for model in (ConversationLog, AgentMessage)}
    results = deepcopy(chat_service._generation_results)
    cache = StateCache()
    call_id = await add_call(storage, 'connected' if connected else 'ringing', cache)
    ops = VoiceOpsService(cache=cache, session_factory=storage)
    assert (await ops.end_call(call_id=call_id, reason=reason))['changed']
    terminal = await rows(storage, VoiceCall)
    assert not (await ops.end_call(call_id=call_id, reason=reason))['changed']
    assert await rows(storage, VoiceCall) == terminal
    for model, snapshot in before.items():
        assert await rows(storage, model) == snapshot
    assert chat_service._generation_futures == {'existing': pending}
    assert chat_service._generation_results == results
    assert chat_queue_service._debounce_tasks == {1: pending}
    assert not pending.done() and calls == []
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.end_reason == reason
        assert row.status == ('ended' if connected else 'failed')
        assert call_presentation(row)['end_message'] == ('通话暂时中断，请稍后再试' if connected else '暂时无法接通')


@pytest.mark.asyncio
async def test_preconnection_repeated_cancel_preserves_quota_ledger_and_card(storage):
    cache = StateCache()
    call_id = await add_call(storage, 'ringing', cache)
    before = {model: await rows(storage, model) for model in (VoiceQuotaAccount, VoiceUsageLedger)}
    ops = VoiceOpsService(cache=cache, session_factory=storage)
    assert (await ops.end_call(call_id=call_id, reason='user_cancel'))['changed']
    terminal = await rows(storage, VoiceCall)
    for _ in range(3):
        assert not (await ops.end_call(call_id=call_id, reason='user_cancel'))['changed']
    assert await rows(storage, VoiceCall) == terminal
    for model, snapshot in before.items():
        assert await rows(storage, model) == snapshot
    async with storage() as db:
        row = await db.scalar(select(VoiceCall))
        assert row.status == 'cancelled' and row.connected_at is None and row.sort_seq is None
        assert row.duration_seconds == 0 and row.free_seconds_used == 0 and row.extra_seconds_used == 0
        assert call_presentation(row)['show_end_page'] is False

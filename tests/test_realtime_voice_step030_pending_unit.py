"""Focused STEP-030 next-turn tests with controlled storage and Provider transport."""
import asyncio
import gzip
import hashlib
import json

import pytest

from backend.services.realtime_voice_recall_service import VoiceRecallCoordinator
from backend.services.realtime_voice_session_context_service import ContextResult, VoiceSessionContext
from tests.test_realtime_voice_step007_provider import connected, verified_capability
from tests.test_realtime_voice_step030_recall import Adapter, Context, recall, service


def pending_row(*, topic='trip', content='计划去京都', turn=1, legacy=False):
    row = dict(kind='recall_result', id=topic,
               text=json.dumps([{'id': topic, 'content': content}], ensure_ascii=False),
               turn_index=turn, visible_from=turn + 1)
    if not legacy:
        row['delivery_pending'] = True
    return row


class PendingContext(Context):
    def __init__(self, rows=(), *, receipt_status='ok'):
        super().__init__()
        self.items = list(rows)
        self.receipt_status = receipt_status
        self.receipts = []

    async def mark_recall_delivered(self, *, items, **kwargs):
        self.receipts.append(items)
        if self.receipt_status == 'ok':
            for row in self.items:
                if any(all(row[key] == sent[key] for key in ('id', 'text', 'turn_index', 'visible_from'))
                       for sent in items):
                    row['delivery_pending'] = False
        return ContextResult(self.receipt_status)


async def no_retrieval(*args, **kwargs):
    raise AssertionError('pending facts must not perform a fresh model or vector search')


async def deliver(recall_service, adapter, *, question='q2', turn=2, text='再说说刚才的事'):
    return await recall_service.deliver_pending(call_id='call', user_id=1,
        question_id=question, turn_index=turn, user_text=text, adapter=adapter)


@pytest.mark.asyncio
async def test_next_turn_submits_legacy_pending_without_new_retrieval_and_consumes_once():
    context = PendingContext([pending_row(legacy=True)])
    recall_service = service(context, no_retrieval, no_retrieval, no_retrieval)
    adapter = Adapter()
    result = await deliver(recall_service, adapter)
    assert result.status == 'ready' and result.mode == 'current_turn_requested'
    assert result.source == 'topic_cache'
    assert len(adapter.calls) == 1 and adapter.calls[0][0] == 'q2'
    assert '计划去京都' in adapter.calls[0][1]
    assert len(context.receipts) == 1 and context.items[0]['delivery_pending'] is False
    assert (await deliver(recall_service, adapter, question='q3', turn=3)).status == 'empty'
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_reply_started_keeps_pending_until_later_question(monkeypatch):
    context = PendingContext([pending_row()])
    recall_service = service(context, no_retrieval, no_retrieval, no_retrieval)
    adapter, wire = await connected(monkeypatch)
    adapter._capabilities['supports_current_turn_rag_gate'] = verified_capability()
    adapter._question = 'q2'
    adapter._text_started.add('q2')
    before = len(wire.sent)
    missed = await deliver(recall_service, adapter)
    assert missed.mode == 'next_turn_cached' and not context.receipts
    assert len(wire.sent) == before and context.items[0]['delivery_pending'] is True
    adapter._question = 'q3'
    sent = await deliver(recall_service, adapter, question='q3', turn=3)
    assert sent.mode == 'current_turn_requested'
    frames = [raw for raw in wire.sent[before:] if int.from_bytes(raw[4:8], 'big') == 502]
    assert len(frames) == 1
    n = int.from_bytes(frames[0][8:12], 'big')
    data = json.loads(gzip.decompress(frames[0][16+n:]))
    assert '计划去京都' in json.loads(data['external_rag'])[0]['content']
    assert context.items[0]['delivery_pending'] is False
    await adapter.finish_session()


@pytest.mark.asyncio
async def test_send_failure_retains_pending_and_receipt_failure_does_not_repeat():
    context = PendingContext([pending_row()])
    recall_service = service(context)
    failed = Adapter('next_turn')
    assert (await deliver(recall_service, failed)).mode == 'next_turn_cached'
    assert context.items[0]['delivery_pending'] is True and context.receipts == []
    context.receipt_status = 'unavailable'
    accepted = Adapter()
    assert (await deliver(recall_service, accepted, question='q3', turn=3)).mode == 'current_turn_requested'
    assert len(context.receipts) == 1 and context.items[0]['delivery_pending'] is True
    assert (await deliver(recall_service, accepted, question='q4', turn=4)).status == 'empty'
    assert len(accepted.calls) == 1


@pytest.mark.asyncio
async def test_unsafe_or_replaced_pending_never_reaches_adapter():
    unsafe = PendingContext([pending_row(content='UNSAFE')])
    adapter = Adapter()
    assert (await deliver(service(unsafe), adapter)).status == 'empty'
    assert adapter.calls == [] and unsafe.receipts == []

    class ReplacedContext(PendingContext):
        def __init__(self):
            super().__init__([pending_row()])
            self.reads = 0

        async def query(self, **kwargs):
            self.reads += 1
            if self.reads == 2:
                self.items = [pending_row(content='更新后的资料')]
            return await super().query(**kwargs)

    replaced = ReplacedContext()
    assert (await deliver(service(replaced), adapter)).status == 'context_unavailable'
    assert adapter.calls == [] and replaced.receipts == []


@pytest.mark.asyncio
async def test_coordinator_prioritizes_pending_and_skips_second_search():
    context = PendingContext([pending_row()])
    recall_service = service(context, no_retrieval, no_retrieval, no_retrieval)
    adapter = Adapter()
    coordinator = VoiceRecallCoordinator(call_id='call', user_id=1, session_factory=None,
        service=recall_service, adapter=adapter, script={})

    async def committed_final(question_id):
        assert question_id == 'q2'
        return '下一个问题', 2

    coordinator._load_final = committed_final
    coordinator.submit('q2')
    await asyncio.gather(*list(coordinator.tasks.values()))
    assert len(adapter.calls) == 1 and len(context.receipts) == 1
    await coordinator.close()


@pytest.mark.asyncio
async def test_context_receipt_requires_exact_cached_version():
    context = object.__new__(VoiceSessionContext)
    calls = []

    async def capture(**kwargs):
        calls.append(kwargs)
        return ContextResult('ok')

    context._execute = capture
    row = pending_row()
    assert (await context.mark_recall_delivered(call_id='call', user_id=1, items=[row])).status == 'ok'
    assert calls[0]['operation'] == 'recall_delivered'
    assert calls[0]['item'] == [{key: row[key] for key in ('id', 'text', 'turn_index', 'visible_from')}]
    assert (await context.mark_recall_delivered(call_id='call', user_id=1,
        items=[{**row, 'visible_from': True}])).status == 'invalid'
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_ordinary_topic_cache_send_also_clears_pending_receipt():
    topic = hashlib.sha256('京都旅行'.encode()).hexdigest()
    context = PendingContext([pending_row(topic=topic)])
    adapter = Adapter()
    result = await recall(service(context), question_id='q2', turn_index=2, adapter=adapter)
    assert result.source == 'topic_cache' and result.mode == 'current_turn_requested'
    assert len(adapter.calls) == 1 and len(context.receipts) == 1
    assert context.items[0]['delivery_pending'] is False

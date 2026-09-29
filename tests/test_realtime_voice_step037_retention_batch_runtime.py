"""Multiple production-size retention pages with interleaved live objects."""
import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall, VoiceCallTurn, VoiceCallCreateIdempotency
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step037_provider_fault_runtime import containers, runtime, full_runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated multi-page retention')


@pytest.mark.asyncio
async def test_retention_multiple_full_pages_preserve_unexpired_exact_objects(full_runtime, record_property):
    factory, _, cache = full_runtime
    now = datetime.utcnow().replace(microsecond=0)
    calls, turns, replays, expired_calls = [], [], [], set()
    async with factory() as db:
        for index in range(305):
            call_id = str(uuid4())
            expiry = now + timedelta(days=1) if index % 3 == 0 else now - timedelta(seconds=1)
            if expiry <= now:
                expired_calls.add(call_id)
            call = VoiceCall(call_id=call_id, user_id=1, initiated_by='user', status='ended',
                summary_status='ready', call_summary='retained summary', config_snapshot={}, capability_snapshot={},
                transcript_retention_days=180, generated_retention_days=30, transcript_expires_at=expiry)
            turn = VoiceCallTurn(call_id=call_id, turn_index=1, user_text_final='synthetic private text',
                assistant_text_effective='synthetic played text', assistant_text_generated='synthetic generated',
                effective_text_evidence='full', turn_status='finalized', memory_status='success',
                user_content_safety_status='passed', assistant_content_safety_status='passed',
                user_crisis_status='passed', assistant_crisis_status='passed', started_at=now-timedelta(days=2),
                effective_text_expires_at=expiry, generated_text_expires_at=expiry)
            replay = VoiceCallCreateIdempotency(user_id=1, idempotency_key=str(uuid4()),
                call_id=call_id, request_payload_sha256='a'*64, replay_expires_at=expiry)
            db.add_all([call, turn, replay])
            calls.append(call); turns.append(turn); replays.append(replay)
        await db.commit()
    for call in calls:
        await cache.set('voice:session_context:' + call.call_id, 'synthetic context')
    def values(row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
    expired_turn_ids = {turn.id for turn in turns if turn.call_id in expired_calls}
    expired_replay_ids = {row.id for row in replays if row.call_id in expired_calls}
    async with factory() as db:
        all_call_ids = set(await db.scalars(select(VoiceCall.id)))
        # Compare persisted state on both sides, including every timestamp column.
        persisted_turns = list(await db.scalars(select(VoiceCallTurn)))
        live_turns = {row.id: values(row) for row in persisted_turns if row.call_id not in expired_calls}
        live_replays = {row.id: values(row) for row in await db.scalars(select(VoiceCallCreateIdempotency))
            if row.call_id not in expired_calls}
        before_storage = {row.id: values(row) for row in turns}
        roundtrip_fields = sorted({key for row in persisted_turns for key, value in values(row).items()
            if value != before_storage[row.id][key]})
        record_property('insert_roundtrip_changed_fields', ','.join(roundtrip_fields))
    service = VoiceRetentionService(session_factory=factory, cache=cache)

    async def sweep(method):
        cursor, candidates, reports = 0, [], []
        for _ in range(10):
            report = await method(now=now, after_id=cursor, limit=100)
            assert len(report['candidate_ids']) <= 100
            assert all(identity > cursor for identity in report['candidate_ids'])
            candidates.extend(report['candidate_ids']); reports.append(report)
            if report['next_cursor'] is None:
                break
            assert report['next_cursor'] > cursor
            cursor = report['next_cursor']
        else:
            pytest.fail('bounded sweep did not terminate')
        assert len(candidates) == len(set(candidates))
        return set(candidates), reports

    contents, content_pages = await sweep(service.purge_contents)
    assert contents == all_call_ids
    assert [len(page['candidate_ids']) for page in content_pages] == [100, 100, 100, 6, 0]
    changed_turns = {obj['id'] for page in content_pages for report in page['reports']
        for obj in report['changed'] if obj['table'] == VoiceCallTurn.__tablename__}
    assert changed_turns == expired_turn_ids
    candidates, replay_pages = await sweep(service.purge_replays)
    assert candidates == expired_replay_ids
    assert {identity for page in replay_pages for identity in page['deleted_ids']} == expired_replay_ids
    assert [len(page['candidate_ids']) for page in replay_pages] == [100, 100, 3, 0]
    async with factory() as db:
        rows = list(await db.scalars(select(VoiceCallTurn)))
        assert {row.id: values(row) for row in rows if row.id in live_turns} == live_turns
        for row in rows:
            if row.id in expired_turn_ids:
                assert row.user_text_final is row.assistant_text_effective is row.assistant_text_generated is None
        assert {row.id: values(row) for row in await db.scalars(select(VoiceCallCreateIdempotency))} == live_replays
        assert set(await db.scalars(select(VoiceCall.id))) == all_call_ids
    for call in calls:
        assert await cache.get('voice:session_context:' + call.call_id) == (None if call.call_id in expired_calls else 'synthetic context')
    _, repeated = await sweep(service.purge_contents)
    assert all(not report['changed'] for page in repeated for report in page['reports'])
    assert (await service.purge_replays(now=now))['deleted_ids'] == []

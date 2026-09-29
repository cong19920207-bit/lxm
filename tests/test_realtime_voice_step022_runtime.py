"""STEP-022 isolated MySQL/Redis transactions; no business data or model calls."""
import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.database import Base
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.relationship_level_history import RelationshipLevelHistory
from backend.services.relationship_service import RelationshipService
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step022_growth import (
    growth_env, test_voice_growth_rounding_upgrade_and_replay,
    test_voice_daily_cap_partial_and_old_log_unchanged, test_end_transaction_settles_once,
)

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME') != '1', reason='isolated runtime opt-in')


@pytest.mark.asyncio
async def test_complete_end_preserves_old_growth_and_three_emotion_domains(growth_env, runtime):
    import json
    from dataclasses import asdict
    from datetime import datetime, timezone, timedelta
    from backend.models.conversation_log import ConversationLog
    from backend.models.emotion_log import EmotionLog
    from backend.models.user_short_term_emotion import UserShortTermEmotion
    from backend.models.realtime_voice import VoiceCall
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    from backend.services.realtime_voice_quota_service import ConnectedMeter, VoiceQuotaService
    factory, call_id = growth_env
    cache = runtime[2]
    tables = [ConversationLog.__table__, EmotionLog.__table__, UserShortTermEmotion.__table__]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    try:
        async with factory() as db:
            conv = ConversationLog(user_id=1, role='user', content='旧文字', sort_seq=100)
            db.add(conv)
            await db.flush()
            db.add(EmotionLog(user_id=1, emotion_label='平静', confidence=.8, conversation_id=conv.id))
            db.add(UserShortTermEmotion(user_id=1, emotion_label='开心', confidence=.9, payload='旧画像'))
            db.add(RelationshipGrowthLog(user_id=1, action_type='dialog', points=2))
            call = await db.scalar(select(VoiceCall))
            call.status, call.ended_at = 'connected', None
            await db.commit()
        await cache.set('ai_emotion:1', '旧情绪')
        await cache.set('ai_emotion:other', '另一用户情绪')
        async def snapshot():
            async with factory() as db:
                values = {model.__tablename__: [tuple(row) for row in (await db.execute(
                    select(model.__table__).order_by(model.id))).all()]
                    for model in (EmotionLog, UserShortTermEmotion)}
                values['old_growth'] = [tuple(row) for row in (await db.execute(
                    select(RelationshipGrowthLog.__table__).where(RelationshipGrowthLog.source_type.is_(None))
                    .order_by(RelationshipGrowthLog.id))).all()]
            keys = sorted([key async for key in cache.scan_iter('ai_emotion:*')])
            values['redis'] = [(key, await cache.get(key)) for key in keys]
            return values
        before = await snapshot()
        meter = ConnectedMeter(call_id, 1, 300, 30)
        async with factory() as db:
            now = datetime.now(timezone.utc)
            await VoiceQuotaService().observe(db, meter, connected=True, monotonic=0, now=now)
            await VoiceQuotaService().observe(db, meter, connected=False, monotonic=65, now=now+timedelta(seconds=65))
        await cache.set('voice:quota:' + call_id, json.dumps(asdict(meter)))
        ops = VoiceOpsService(cache=cache, session_factory=factory)
        await ops.end_call(call_id=call_id, reason='user_hangup')
        await ops.end_call(call_id=call_id, reason='system_error')
        assert await snapshot() == before
        async with factory() as db:
            call = await db.scalar(select(VoiceCall))
            assert call.growth_points == 10 and call.growth_eligible_seconds == 65
            assert call.status == 'ended' and call.sort_seq is not None
            new = (await db.scalars(select(RelationshipGrowthLog).where(
                RelationshipGrowthLog.source_type == 'voice_call'))).all()
            assert len(new) == 1 and new[0].source_id == call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=tables)


@pytest_asyncio.fixture
async def memory_env(runtime):
    factory, call_id, _ = runtime
    tables = [m.__table__ for m in (Relationship, RelationshipGrowthLog, RelationshipLevelHistory)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    try:
        yield factory, call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=tables)


@pytest.mark.asyncio
@pytest.mark.parametrize('first_kind', ['text', 'voice'])
async def test_mysql_text_voice_concurrency_with_stale_identity_map(growth_env, runtime, monkeypatch, first_kind):
    factory, call_id = growth_env
    async def redis():
        return runtime[2]
    monkeypatch.setattr('backend.services.relationship_service.get_redis', redis)
    locked, release, second_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async with factory() as stale_db:
        stale = await stale_db.scalar(select(Relationship))
        assert stale.growth_value == 195
        async def work(kind, first=False):
            async with factory() as fresh_db:
                db = fresh_db if first else stale_db
                service = RelationshipService(db)
                if first:
                    original = service._get_or_create_relationship
                    async def held(user_id):
                        rel = await original(user_id)
                        locked.set()
                        await release.wait()
                        return rel
                    service._get_or_create_relationship = held
                else:
                    second_started.set()
                result = (await service.add_growth(1, 'dialog') if kind == 'text'
                          else await service.add_voice_growth(1, 65, call_id))
                await db.commit()
                return result
        first = asyncio.create_task(work(first_kind, True))
        second = None
        try:
            await asyncio.wait_for(locked.wait(), 5)
            second = asyncio.create_task(work('voice' if first_kind == 'text' else 'text'))
            await second_started.wait()
            await asyncio.sleep(.05)
            assert not second.done()
            release.set()
            await asyncio.wait_for(asyncio.gather(first, second), 10)
        finally:
            release.set()
            await asyncio.gather(first, *([second] if second else []), return_exceptions=True)
    async with factory() as db:
        assert (await db.scalar(select(Relationship))).growth_value == 207
        logs = (await db.scalars(select(RelationshipGrowthLog))).all()
        assert sorted(log.points for log in logs) == [2, 10]


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('RUN_VOICE_DIARY_LIVE') != '1', reason='synthetic live diary opt-in')
@pytest.mark.parametrize('summary_status', ['ready', 'failed'])
async def test_live_next_day_voice_only_diary(growth_env, monkeypatch, summary_status):
    import json
    from pathlib import Path
    from datetime import datetime, timedelta, timezone
    from backend.models.ai_diary import AiDiary
    from backend.models.conversation_log import ConversationLog
    from backend.models.emotion_log import EmotionLog
    from backend.models.realtime_voice import VoiceCall
    from backend.services.diary_service import DiaryService, compute_shanghai_diary_batch_window
    from backend.services.diary_rules_loader import resolve_diary_rules_dict
    from backend.utils.llm_client import LLMClient
    factory, _ = growth_env
    tables = [ConversationLog.__table__, EmotionLog.__table__, AiDiary.__table__]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    async def rules(**kwargs):
        return resolve_diary_rules_dict(None)
    monkeypatch.setattr('backend.services.diary_service.get_resolved_diary_rules', rules)
    client = LLMClient()
    prompts = []
    original = client.chat_sync
    async def capture(prompt):
        prompts.append(prompt)
        return await original(prompt)
    client.chat_sync = capture
    monkeypatch.setattr('backend.services.diary_service.llm_client', client)
    try:
        _, covers, start, end = compute_shanghai_diary_batch_window(datetime.now(timezone.utc))
        async with factory() as db:
            rel = await db.scalar(select(Relationship))
            rel.level, rel.growth_value = 2, 800
            call = await db.scalar(select(VoiceCall))
            call.connected_at = start + timedelta(hours=8)
            call.ended_at = call.connected_at + timedelta(seconds=65)
            call.summary_status = summary_status
            call.call_summary = '聊了下个月去日本的计划，还没决定去哪些城市。' if summary_status == 'ready' else None
            await db.commit()
            assert await DiaryService(db).generate_diary_for_user(1,
                covers_beijing_date=covers, conv_start_naive_utc=start, conv_end_naive_utc=end)
            await db.commit()
            diary = await db.scalar(select(AiDiary))
            assert diary.relationship_level_at_creation == 2 and diary.content.strip()
            assert prompts and all('用户没有来找你聊天' not in p for p in prompts)
            assert all(('日本' in p if summary_status == 'ready' else '有过语音通话' in p) for p in prompts)
            assert '今天没联系' not in diary.content
            Path(f'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step022-diary-{summary_status}.json').write_text(
                json.dumps({'status': 'passed', 'input': 'synthetic only', 'prompt': prompts,
                    'diary': diary.content, 'covers_date': str(covers)}, ensure_ascii=False, indent=2)+'\n')
    finally:
        await client.close()
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=tables)

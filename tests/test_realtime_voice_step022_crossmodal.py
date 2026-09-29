from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.database import Base
from backend.models.emotion_log import EmotionLog
from backend.models.realtime_voice import VoiceCall
from backend.services.agent_service import AgentService
from backend.services.diary_service import DiaryService
from tests.test_realtime_voice_step021_cards import card_env, memory_env, storage


@pytest.mark.asyncio
@pytest.mark.parametrize('summary_status,expired,deleted', [
    ('ready', False, False), ('failed', False, False),
    ('pending', False, False), ('ready', True, False), ('ready', False, True),
])
async def test_voice_only_diary_has_nonempty_safe_summary(card_env, summary_status, expired, deleted):
    factory, _ = card_env
    now = datetime.utcnow()
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.connected_at = now - timedelta(hours=1)
        call.status = 'ended'
        call.summary_status = summary_status
        call.call_summary = '聊了下个月去日本的计划'
        call.transcript_expires_at = now + timedelta(days=-1 if expired else 1)
        if deleted:
            call.deletion_fence_at = now
            call.deleted_at = now
        await db.commit()
        active, summary = await DiaryService(db)._get_conversation_summary_in_window(
            1, now - timedelta(days=1), now)
        assert active and summary.strip()
        assert ('日本' in summary) == (summary_status == 'ready' and not expired and not deleted)
        assert '今天没联系' not in summary
        assert await DiaryService(db)._get_conversation_summary_in_window(
            1, now, now + timedelta(days=1)) == (False, '')


@pytest.mark.asyncio
async def test_unanswered_call_is_not_diary_interaction(card_env):
    factory, _ = card_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.connected_at = None
        call.status = 'missed'
        await db.commit()
        now = datetime.utcnow()
        assert await DiaryService(db)._get_conversation_summary_in_window(
            1, now - timedelta(days=1), now) == (False, '')


@pytest.mark.asyncio
async def test_recent_connected_call_suppresses_p0(card_env):
    factory, _ = card_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[EmotionLog.__table__])
    async with factory() as db:
        db.add(EmotionLog(user_id=1, emotion_label='悲伤', confidence=.9,
            conversation_id=1, created_at=datetime.utcnow() - timedelta(days=2)))
        await db.commit()
        assert await AgentService()._check_p0(1, db) is False
        call = await db.scalar(select(VoiceCall))
        call.connected_at = datetime.utcnow() - timedelta(days=2)
        await db.commit()
        assert await AgentService()._check_p0(1, db) is True

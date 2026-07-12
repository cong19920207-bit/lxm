# -*- coding: utf-8 -*-
# STEP-019 单元测试：agent_aware_service（点赞/已读感知排队消费基建）
# 覆盖 steps.md STEP-019 单测要求表：入队 / 未到期不消费 / 到期消费 / 并发消费 / 失败隔离。

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.agent_aware_queue import AgentAwareQueue
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.services import agent_aware_service as aas_mod
from backend.services.agent_aware_service import agent_aware_service

_USER = 1


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        await conn.run_sync(Relationship.__table__.create)
        await conn.run_sync(FeedPost.__table__.create)
        await conn.run_sync(AgentMessage.__table__.create)
        await conn.run_sync(AgentAwareQueue.__table__.create)
        await conn.run_sync(UserTimelineSeq.__table__.create)
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(aas_mod, "async_session_maker", m)
    async with m() as db:
        db.add(User(id=_USER, username="u1", password_hash="x", created_at=datetime.utcnow()))
        db.add(Relationship(user_id=_USER, level=1, growth_value=0))
        db.add(FeedPost(
            id=1, scene_id="s1", scheduled_publish_time=datetime.utcnow(),
            generation_status="ready", content_text="帖子", hashtags=[],
            image_reference_url="r", emotion="平静", city="杭州", season="夏",
            base_likes=1, like_multiplier=1, real_likes=0, is_visible=1, dedup_hash="h"))
        await db.commit()
    yield m
    await engine.dispose()


class TestEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_like_aware(self, maker):
        qid = await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=30, relationship_stage="friend",
            extra_context={"is_special": False})
        async with maker() as db:
            row = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == qid))).scalars().first()
        assert row.status == "pending"
        assert row.trigger_type == TriggerType.LIKE_AWARE
        assert row.prompt_key == "prompt_p07"
        # due_at 约等于 now+30s
        delta = (row.due_at - datetime.utcnow()).total_seconds()
        assert 20 < delta <= 31


class TestConsume:
    @pytest.mark.asyncio
    async def test_not_due_skip(self, maker):
        await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=300, relationship_stage="friend")
        n = await agent_aware_service.consume_pending()
        assert n == 0

    @pytest.mark.asyncio
    async def test_due_consume_success(self, maker, monkeypatch):
        from backend.services.like_aware_service import like_aware_service
        monkeypatch.setattr(like_aware_service, "generate_and_send",
                            AsyncMock(return_value="小梦的私信"))
        qid = await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=0, relationship_stage="friend")
        n = await agent_aware_service.consume_pending()
        assert n == 1
        async with maker() as db:
            row = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == qid))).scalars().first()
            msg = (await db.execute(
                select(AgentMessage).where(AgentMessage.id == row.agent_message_id))).scalars().first()
        assert row.status == "sent"
        assert msg is not None
        assert msg.content == "小梦的私信"
        assert msg.action_score == 0.0
        assert msg.trigger_type == TriggerType.LIKE_AWARE
        assert msg.sort_seq >= 1

    @pytest.mark.asyncio
    async def test_concurrent_claim_only_one(self, maker):
        qid = await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=0, relationship_stage="friend")
        # 模拟另一 worker 抢先置 generating
        async with maker() as db:
            row = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == qid))).scalars().first()
            row.status = "generating"
            await db.commit()
        ok = await agent_aware_service.consume_record(qid)
        assert ok is False

    @pytest.mark.asyncio
    async def test_failure_isolated(self, maker, monkeypatch):
        from backend.services.like_aware_service import like_aware_service
        monkeypatch.setattr(like_aware_service, "generate_and_send",
                            AsyncMock(return_value=None))  # 生成失败
        qfail = await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=0, relationship_stage="friend")
        # 另一条未到期的记录，验证互不影响
        qok = await agent_aware_service.enqueue(
            user_id=_USER, aware_type=TriggerType.LIKE_AWARE, related_post_id=1,
            prompt_key="prompt_p07", delay_seconds=300, relationship_stage="friend")
        await agent_aware_service.consume_pending()
        async with maker() as db:
            rf = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == qfail))).scalars().first()
            ro = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == qok))).scalars().first()
        assert rf.status == "failed"
        assert rf.fail_reason
        assert ro.status == "pending"

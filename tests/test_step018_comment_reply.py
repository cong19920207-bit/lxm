# -*- coding: utf-8 -*-
# STEP-018 单元测试：comment_reply_service（LLM-05 评论回复延迟消费）
# 覆盖 steps.md STEP-018 单测要求表。

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.feed_comment import FeedComment
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.services import comment_reply_service as crs_mod
from backend.services.comment_reply_service import comment_reply_service

_USER = 1


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Relationship.__table__.create)
        await conn.run_sync(FeedPost.__table__.create)
        await conn.run_sync(FeedComment.__table__.create)
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(crs_mod, "async_session_maker", m)
    monkeypatch.setattr(crs_mod, "render_prompt", AsyncMock(return_value="P"))
    monkeypatch.setattr(crs_mod.content_safety_service, "check_content",
                        AsyncMock(return_value={"is_safe": True, "reason": ""}))
    async with m() as db:
        db.add(FeedPost(
            id=1, scene_id="s1", scheduled_publish_time=datetime.utcnow(),
            generation_status="ready", content_text="帖子", hashtags=[],
            image_reference_url="r", emotion="平静", city="杭州", season="夏",
            base_likes=1, like_multiplier=1, real_likes=0, is_visible=1, dedup_hash="h"))
        db.add(Relationship(user_id=_USER, level=3, growth_value=0))
        await db.commit()
    yield m
    await engine.dispose()


async def _add_comment(maker, due_offset_sec, status="pending"):
    async with maker() as db:
        c = FeedComment(post_id=1, user_id=_USER, content="用户评论",
                        gen_status=status,
                        due_at=datetime.utcnow() + timedelta(seconds=due_offset_sec))
        db.add(c)
        await db.commit()
        await db.refresh(c)
        return c.id


class TestPollAndConsume:
    @pytest.mark.asyncio
    async def test_no_pending(self, maker):
        n = await comment_reply_service.poll_and_consume()
        assert n == 0

    @pytest.mark.asyncio
    async def test_not_due(self, maker):
        await _add_comment(maker, due_offset_sec=300)  # 未来到期
        with patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="回复"):
            n = await comment_reply_service.poll_and_consume()
        assert n == 0

    @pytest.mark.asyncio
    async def test_due_success(self, maker):
        cid = await _add_comment(maker, due_offset_sec=-10)
        with patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="小梦的回复"):
            n = await comment_reply_service.poll_and_consume()
        assert n == 1
        async with maker() as db:
            c = (await db.execute(
                select(FeedComment).where(FeedComment.id == cid))).scalars().first()
        assert c.gen_status == "ready"
        assert c.lxm_reply == "小梦的回复"
        assert c.lxm_reply_at is not None


class TestConsumeOne:
    @pytest.mark.asyncio
    async def test_three_timeouts_failed(self, maker):
        cid = await _add_comment(maker, due_offset_sec=-10)
        with patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, side_effect=TimeoutError("timeout")):
            ok = await comment_reply_service.consume_one(cid)
        assert ok is False
        async with maker() as db:
            c = (await db.execute(
                select(FeedComment).where(FeedComment.id == cid))).scalars().first()
        assert c.gen_status == "failed"

    @pytest.mark.asyncio
    async def test_content_violation_failed(self, maker, monkeypatch):
        cid = await _add_comment(maker, due_offset_sec=-10)
        monkeypatch.setattr(crs_mod.content_safety_service, "check_content",
                            AsyncMock(return_value={"is_safe": False, "reason": "违规"}))
        with patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="违规回复"):
            ok = await comment_reply_service.consume_one(cid)
        assert ok is False
        async with maker() as db:
            c = (await db.execute(
                select(FeedComment).where(FeedComment.id == cid))).scalars().first()
        assert c.gen_status == "failed"

    @pytest.mark.asyncio
    async def test_concurrent_claim_only_one(self, maker):
        cid = await _add_comment(maker, due_offset_sec=-10)
        # 先手动置为 generating（模拟另一 worker 抢先）
        async with maker() as db:
            c = (await db.execute(
                select(FeedComment).where(FeedComment.id == cid))).scalars().first()
            c.gen_status = "generating"
            await db.commit()
        with patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="回复"):
            ok = await comment_reply_service.consume_one(cid)
        assert ok is False  # 已被抢占，claim 失败

    @pytest.mark.asyncio
    async def test_soulmate_stage_zh(self, maker):
        cid = await _add_comment(maker, due_offset_sec=-10)
        captured = {}

        async def _fake_render(key, variables=None, optional=None):
            if key == "prompt_p06_user":
                captured["vars"] = variables
                captured["opt"] = optional
            return "P"

        with patch.object(crs_mod, "render_prompt", side_effect=_fake_render), \
             patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="回复"):
            await comment_reply_service.consume_one(cid)
        assert captured["vars"]["relationship_stage"] == "知己"

    @pytest.mark.asyncio
    async def test_no_call_segment_off(self, maker):
        cid = await _add_comment(maker, due_offset_sec=-10)
        captured = {}

        async def _fake_render(key, variables=None, optional=None):
            if key == "prompt_p06_user":
                captured["opt"] = optional
            return "P"

        with patch.object(crs_mod, "render_prompt", side_effect=_fake_render), \
             patch.object(crs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value="回复"):
            await comment_reply_service.consume_one(cid)
        assert captured["opt"]["称呼"] is False  # hobby+real 皆空

# -*- coding: utf-8 -*-
# STEP-020 单元测试：like_aware_service.on_like_hook（LLM-06 点赞感知入队判定）
# 覆盖 steps.md STEP-020 单测要求表：特殊档/特殊已满/常规命中/常规未中/同帖去重。

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
from backend.services import like_aware_service as las_mod
from backend.services.like_aware_service import like_aware_service

_USER = 1

_CFG = {
    "like_aware_special_window_hours": 48,
    "like_aware_special_max_count": 1,
    "like_aware_special_delay_sec": 30,
    "like_regular_delay_friend_min": 10,
    "like_regular_delay_friend_max": 20,
}


async def _fake_cfg(key, default=None):
    return _CFG.get(key, default)


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
    monkeypatch.setattr(las_mod, "async_session_maker", m)
    monkeypatch.setattr(aas_mod, "async_session_maker", m)
    monkeypatch.setattr(las_mod, "get_life_feed_config", _fake_cfg)
    yield m
    await engine.dispose()


async def _seed(maker, created_hours_ago, level=1, used=0):
    async with maker() as db:
        db.add(User(id=_USER, username="u1", password_hash="x",
                    created_at=datetime.utcnow() - timedelta(hours=created_hours_ago)))
        db.add(Relationship(user_id=_USER, level=level, growth_value=0,
                            like_aware_special_used_count=used))
        db.add(FeedPost(
            id=1, scene_id="s1", scheduled_publish_time=datetime.utcnow(),
            generation_status="ready", content_text="帖子", hashtags=[],
            image_reference_url="r", emotion="平静", city="杭州", season="夏",
            base_likes=1, like_multiplier=1, real_likes=0, is_visible=1, dedup_hash="h"))
        await db.commit()


async def _queue_rows(maker):
    async with maker() as db:
        return (await db.execute(select(AgentAwareQueue))).scalars().all()


@pytest.mark.asyncio
async def test_special_window_hit(maker):
    await _seed(maker, created_hours_ago=2, level=1, used=0)
    await like_aware_service.on_like_hook(_USER, 1)
    rows = await _queue_rows(maker)
    assert len(rows) == 1
    assert rows[0].trigger_type == TriggerType.LIKE_AWARE
    assert rows[0].prompt_key == "prompt_p07"
    assert rows[0].extra_context.get("is_special") is True
    async with maker() as db:
        rel = (await db.execute(
            select(Relationship).where(Relationship.user_id == _USER))).scalars().first()
    assert rel.like_aware_special_used_count == 1


@pytest.mark.asyncio
async def test_special_used_max_falls_to_regular(maker, monkeypatch):
    await _seed(maker, created_hours_ago=2, level=1, used=1)  # 已用满
    monkeypatch.setattr(las_mod.random, "random", lambda: 0.1)  # 常规命中
    monkeypatch.setattr(las_mod.random, "randint", lambda a, b: a)
    await like_aware_service.on_like_hook(_USER, 1)
    rows = await _queue_rows(maker)
    assert len(rows) == 1
    assert rows[0].extra_context.get("is_special") is False


@pytest.mark.asyncio
async def test_regular_hit(maker, monkeypatch):
    await _seed(maker, created_hours_ago=100, level=1, used=0)  # 窗口外
    monkeypatch.setattr(las_mod.random, "random", lambda: 0.1)  # <0.3 命中
    monkeypatch.setattr(las_mod.random, "randint", lambda a, b: a)
    await like_aware_service.on_like_hook(_USER, 1)
    rows = await _queue_rows(maker)
    assert len(rows) == 1
    assert rows[0].extra_context.get("is_special") is False


@pytest.mark.asyncio
async def test_regular_miss(maker, monkeypatch):
    await _seed(maker, created_hours_ago=100, level=1, used=0)
    monkeypatch.setattr(las_mod.random, "random", lambda: 0.9)  # >=0.3 未中
    await like_aware_service.on_like_hook(_USER, 1)
    rows = await _queue_rows(maker)
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_same_post_dedup(maker):
    await _seed(maker, created_hours_ago=2, level=1, used=0)
    # 预置一条同帖 pending LIKE_AWARE
    async with maker() as db:
        db.add(AgentAwareQueue(
            user_id=_USER, trigger_type=TriggerType.LIKE_AWARE, post_id=1,
            relationship_stage="friend", due_at=datetime.utcnow(), status="pending",
            prompt_key="prompt_p07"))
        await db.commit()
    await like_aware_service.on_like_hook(_USER, 1)
    rows = await _queue_rows(maker)
    assert len(rows) == 1  # 未新增

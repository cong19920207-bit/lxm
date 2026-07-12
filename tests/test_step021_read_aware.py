# -*- coding: utf-8 -*-
# STEP-021 单元测试：read_aware_service.on_feed_read（LLM-07 已读感知入队判定）
# 覆盖 steps.md STEP-021 单测要求表：特殊档 P-14 / 陌生 P-08 / 知己 P-11 /
# 6h 点赞互斥 / 同帖去重 / 多帖取最近。

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
from backend.services import read_aware_service as ras_mod
from backend.services.read_aware_service import read_aware_service

_USER = 1

_CFG = {
    "read_aware_special_window_hours": 48,
    "read_aware_special_max_count": 1,
    "read_aware_special_delay_sec": 60,
    "read_suppress_after_like_im_hours": 6,
    "read_aware_user_cooldown_hours": 6,
    "read_regular_delay_stranger_min": 10, "read_regular_delay_stranger_max": 20,
    "read_regular_delay_friend_min": 10, "read_regular_delay_friend_max": 20,
    "read_regular_delay_intimate_min": 10, "read_regular_delay_intimate_max": 20,
    "read_regular_delay_soulmate_min": 10, "read_regular_delay_soulmate_max": 20,
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
    monkeypatch.setattr(ras_mod, "async_session_maker", m)
    monkeypatch.setattr(aas_mod, "async_session_maker", m)
    monkeypatch.setattr(ras_mod, "get_life_feed_config", _fake_cfg)
    monkeypatch.setattr(ras_mod.random, "randint", lambda a, b: a)
    yield m
    await engine.dispose()


async def _seed(maker, created_hours_ago, level=1, used=0, posts=((1, 0),)):
    """posts: [(post_id, publish_offset_min)]，offset 越大发布越晚。"""
    async with maker() as db:
        db.add(User(id=_USER, username="u1", password_hash="x",
                    created_at=datetime.utcnow() - timedelta(hours=created_hours_ago)))
        db.add(Relationship(user_id=_USER, level=level, growth_value=0,
                            read_aware_special_used_count=used))
        for pid, off in posts:
            db.add(FeedPost(
                id=pid, scene_id="s%d" % pid,
                scheduled_publish_time=datetime.utcnow() + timedelta(minutes=off),
                generation_status="ready", content_text="帖子%d" % pid, hashtags=[],
                image_reference_url="r", emotion="平静", city="杭州", season="夏",
                base_likes=1, like_multiplier=1, real_likes=0, is_visible=1,
                dedup_hash="h%d" % pid))
        await db.commit()


async def _rows(maker):
    async with maker() as db:
        return (await db.execute(select(AgentAwareQueue))).scalars().all()


@pytest.mark.asyncio
async def test_special_uses_p14(maker):
    await _seed(maker, created_hours_ago=1, level=0, used=0)
    await read_aware_service.on_feed_read(_USER, 1)
    rows = await _rows(maker)
    assert len(rows) == 1
    assert rows[0].prompt_key == "prompt_p14"
    assert rows[0].extra_context.get("is_special") is True
    async with maker() as db:
        rel = (await db.execute(
            select(Relationship).where(Relationship.user_id == _USER))).scalars().first()
    assert rel.read_aware_special_used_count == 1


@pytest.mark.asyncio
async def test_regular_stranger_p08(maker):
    await _seed(maker, created_hours_ago=100, level=0, used=0)  # 窗口外 → 常规
    await read_aware_service.on_feed_read(_USER, 1)
    rows = await _rows(maker)
    assert len(rows) == 1
    assert rows[0].prompt_key == "prompt_p08"


@pytest.mark.asyncio
async def test_regular_soulmate_p11(maker):
    await _seed(maker, created_hours_ago=100, level=3, used=0)
    await read_aware_service.on_feed_read(_USER, 1)
    rows = await _rows(maker)
    assert len(rows) == 1
    assert rows[0].prompt_key == "prompt_p11"


@pytest.mark.asyncio
async def test_like_im_suppress_6h(maker):
    await _seed(maker, created_hours_ago=100, level=1, used=0)
    async with maker() as db:  # 6h 内已有 LIKE_AWARE(sent)
        db.add(AgentAwareQueue(
            user_id=_USER, trigger_type=TriggerType.LIKE_AWARE, post_id=2,
            relationship_stage="friend", due_at=datetime.utcnow(), status="sent",
            prompt_key="prompt_p07", created_at=datetime.utcnow() - timedelta(hours=1)))
        await db.commit()
    await read_aware_service.on_feed_read(_USER, 1)
    rows = [r for r in await _rows(maker) if r.trigger_type == TriggerType.READ_AWARE]
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_same_post_dedup(maker):
    await _seed(maker, created_hours_ago=100, level=1, used=0)
    async with maker() as db:
        db.add(AgentAwareQueue(
            user_id=_USER, trigger_type=TriggerType.READ_AWARE, post_id=1,
            relationship_stage="friend", due_at=datetime.utcnow(), status="pending",
            prompt_key="prompt_p09"))
        await db.commit()
    await read_aware_service.on_feed_read(_USER, 1)
    rows = await _rows(maker)
    assert len(rows) == 1  # 未新增


@pytest.mark.asyncio
async def test_user_cooldown_blocks_second_post(maker):
    """滚动冷却窗口内已有 READ_AWARE → 另一帖也不再入队。"""
    await _seed(maker, created_hours_ago=100, level=1, used=0, posts=((1, 0), (2, 60)))
    await read_aware_service.on_feed_read(_USER, 1)
    await read_aware_service.on_feed_read(_USER, 2)
    rows = [r for r in await _rows(maker) if r.trigger_type == TriggerType.READ_AWARE]
    assert len(rows) == 1
    assert rows[0].post_id == 1


@pytest.mark.asyncio
async def test_user_cooldown_expires(maker):
    """冷却窗外的旧 READ_AWARE 不阻断新入队。"""
    await _seed(maker, created_hours_ago=100, level=1, used=0, posts=((1, 0), (2, 60)))
    async with maker() as db:
        db.add(AgentAwareQueue(
            user_id=_USER, trigger_type=TriggerType.READ_AWARE, post_id=1,
            relationship_stage="friend", due_at=datetime.utcnow(), status="sent",
            prompt_key="prompt_p09",
            created_at=datetime.utcnow() - timedelta(hours=7)))
        await db.commit()
    await read_aware_service.on_feed_read(_USER, 2)
    rows = [r for r in await _rows(maker) if r.trigger_type == TriggerType.READ_AWARE]
    assert len(rows) == 2
    assert any(r.post_id == 2 for r in rows)


@pytest.mark.asyncio
async def test_multi_post_picks_latest(maker):
    # post 1 发布早，post 2 发布晚 → anchor 应为 2
    # 冷却关掉，避免 batch 以外的「用户级 1 条」干扰本断言
    _CFG["read_aware_user_cooldown_hours"] = 0
    try:
        await _seed(maker, created_hours_ago=100, level=1, used=0,
                    posts=((1, 0), (2, 60)))
        await read_aware_service.on_feed_read_batch(_USER, [1, 2])
        rows = await _rows(maker)
        assert len(rows) == 1
        assert rows[0].post_id == 2
    finally:
        _CFG["read_aware_user_cooldown_hours"] = 6
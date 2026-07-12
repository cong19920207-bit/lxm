# -*- coding: utf-8 -*-
# STEP-026 单元测试：feed_sse_service 注册表 + feed_new_broadcast_task 广播调度去重。
# 覆盖 steps.md STEP-026 单测要求：单用户注册 / 广播 / 同帖二次扫描不再广播 / 断开清理。

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.feed_post import FeedPost
from backend.services.feed_sse_service import FeedSSEService


class TestRegistry:
    def test_register_and_online_count(self):
        svc = FeedSSEService()
        q = svc.register(1)
        assert svc.online_user_count() == 1
        assert q is not None

    def test_broadcast_delivers_event(self):
        svc = FeedSSEService()
        q = svc.register(1)
        delivered = svc.broadcast_new_feed([10, 11, 12])
        assert delivered == 1
        event = q.get_nowait()
        assert event == {"type": "feed_new", "delta": 3}

    def test_broadcast_empty_noop(self):
        svc = FeedSSEService()
        svc.register(1)
        assert svc.broadcast_new_feed([]) == 0

    def test_unregister_cleans(self):
        svc = FeedSSEService()
        q = svc.register(1)
        svc.unregister(1, q)
        assert svc.online_user_count() == 0


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(FeedPost.__table__.create)
    m = async_sessionmaker(engine, expire_on_commit=False)
    import backend.tasks.feed_new_broadcast_task as task_mod
    monkeypatch.setattr(task_mod, "async_session_maker", m)
    yield m, task_mod
    await engine.dispose()


async def _add_post(maker, pid, offset_min, status="ready", visible=1, broadcasted=0):
    async with maker() as db:
        db.add(FeedPost(
            id=pid, scene_id="s%d" % pid,
            scheduled_publish_time=datetime.utcnow() + timedelta(minutes=offset_min),
            generation_status=status, content_text="帖子", hashtags=[],
            image_reference_url="r", emotion="平静", city="杭州", season="夏",
            base_likes=1, like_multiplier=1, real_likes=0, is_visible=visible,
            dedup_hash="h%d" % pid, sse_broadcasted=broadcasted))
        await db.commit()


class TestBroadcastTask:
    @pytest.mark.asyncio
    async def test_broadcast_and_mark(self, maker, monkeypatch):
        m, task_mod = maker
        await _add_post(m, 1, offset_min=-1)  # 已到点
        captured = {}
        monkeypatch.setattr(task_mod.feed_sse_service, "broadcast_new_feed",
                            lambda ids: captured.setdefault("ids", ids) or len(ids))
        await task_mod.feed_new_broadcast_task()
        assert captured.get("ids") == [1]
        async with m() as db:
            p = (await db.execute(select(FeedPost).where(FeedPost.id == 1))).scalars().first()
        assert p.sse_broadcasted == 1

    @pytest.mark.asyncio
    async def test_second_scan_no_rebroadcast(self, maker, monkeypatch):
        m, task_mod = maker
        await _add_post(m, 1, offset_min=-1, broadcasted=1)  # 已广播
        calls = []
        monkeypatch.setattr(task_mod.feed_sse_service, "broadcast_new_feed",
                            lambda ids: calls.append(ids) or len(ids))
        await task_mod.feed_new_broadcast_task()
        assert calls == []  # 未再广播

    @pytest.mark.asyncio
    async def test_future_post_not_broadcast(self, maker, monkeypatch):
        m, task_mod = maker
        await _add_post(m, 1, offset_min=60)  # 未到点
        calls = []
        monkeypatch.setattr(task_mod.feed_sse_service, "broadcast_new_feed",
                            lambda ids: calls.append(ids) or len(ids))
        await task_mod.feed_new_broadcast_task()
        assert calls == []

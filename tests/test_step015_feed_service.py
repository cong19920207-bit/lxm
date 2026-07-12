# -*- coding: utf-8 -*-
# STEP-015/016/017 单元测试：feed_service（列表/enter/badge、点赞、评论）
# 直接对服务层跑内存 SQLite，覆盖 steps.md 三个 STEP 的单测要求表。

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.constants import (
    ERR_COMMENT_EMPTY,
    ERR_COMMENT_RATE_LIMIT,
    ERR_COMMENT_TOO_LONG,
    ERR_CONTENT_SAFETY_VIOLATION,
    ERR_FEED_POST_NOT_FOUND,
)
from backend.models.feed_comment import FeedComment
from backend.models.feed_like import FeedLike
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services import feed_service as fs_mod
from backend.services.feed_service import FeedError, feed_service

_USER = 1
_OTHER = 2


@pytest_asyncio.fixture
async def db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        await conn.run_sync(Relationship.__table__.create)
        await conn.run_sync(FeedPost.__table__.create)
        await conn.run_sync(FeedComment.__table__.create)
        await conn.run_sync(FeedLike.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(fs_mod, "get_life_feed_config",
                        AsyncMock(side_effect=lambda k, d=None: d))
    monkeypatch.setattr(fs_mod.content_safety_service, "check_content",
                        AsyncMock(return_value={"is_safe": True, "reason": ""}))
    monkeypatch.setattr(fs_mod.like_aware_service, "on_like_hook", AsyncMock())
    async with maker() as session:
        session.add(User(id=_USER, username="u1", password_hash="x"))
        session.add(User(id=_OTHER, username="u2", password_hash="x"))
        session.add(Relationship(user_id=_USER, level=2, growth_value=0,
                                 has_ever_commented_feed=0))
        await session.commit()
        yield session
    await engine.dispose()


def _post(pid, minutes_ago=10, visible=1, status="ready", base=5, mul=2, real=0,
          base_comments=0, comment_multiplier=1):
    """构造测试帖。评论假数默认 0×1（历史帖口径）；新帖场景显式传 base_comments/comment_multiplier。"""
    now = datetime.utcnow()
    return FeedPost(
        id=pid, scene_id=f"s{pid}",
        scheduled_publish_time=now - timedelta(minutes=minutes_ago),
        actual_publish_time=None, generation_status=status,
        content_text=f"帖子{pid}", hashtags=["#t"], image_urls=None,
        image_reference_url="ref", image_type=None, emotion="平静",
        city="杭州", season="夏", base_likes=base, like_multiplier=mul,
        real_likes=real,
        base_comments=base_comments, comment_multiplier=comment_multiplier,
        is_visible=visible, dedup_hash=f"h{pid}",
    )


# ============ STEP-015 列表/enter/badge ============

class TestListFeed:
    @pytest.mark.asyncio
    async def test_empty(self, db):
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"] == []
        assert r["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_pagination(self, db):
        for i in range(1, 31):
            db.add(_post(i, minutes_ago=i))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert len(r["posts"]) == 20
        assert r["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_hidden_excluded(self, db):
        db.add(_post(1, visible=0))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"] == []

    @pytest.mark.asyncio
    async def test_not_to_point_excluded(self, db):
        db.add(_post(1, minutes_ago=-60))  # 未来
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"] == []

    @pytest.mark.asyncio
    async def test_lazy_writeback(self, db):
        db.add(_post(1))
        await db.commit()
        await feed_service.list_feed(db, _USER, None, 20)
        p = (await db.execute(select(FeedPost).where(FeedPost.id == 1))).scalars().first()
        first_ts = p.actual_publish_time
        assert first_ts is not None
        await feed_service.list_feed(db, _USER, None, 20)
        p2 = (await db.execute(select(FeedPost).where(FeedPost.id == 1))).scalars().first()
        assert p2.actual_publish_time == first_ts

    @pytest.mark.asyncio
    async def test_private_comment(self, db):
        db.add(_post(1))
        await db.commit()
        db.add(FeedComment(post_id=1, user_id=_OTHER, content="别人评论",
                           gen_status="pending"))
        db.add(FeedComment(post_id=1, user_id=_USER, content="我的评论",
                           gen_status="pending"))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        comments = r["posts"][0]["comments"]
        assert len(comments) == 1
        assert comments[0]["content"] == "我的评论"

    @pytest.mark.asyncio
    async def test_visible_range_7d(self, db, monkeypatch):
        monkeypatch.setattr(fs_mod, "get_life_feed_config",
                            AsyncMock(side_effect=lambda k, d=None: "7d"))
        db.add(_post(1, minutes_ago=8 * 24 * 60))  # 8 天前
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"] == []

    @pytest.mark.asyncio
    async def test_user_liked_flag(self, db):
        db.add(_post(1))
        await db.commit()
        db.add(FeedLike(user_id=_USER, post_id=1))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"][0]["user_liked"] is True
        assert r["posts"][0]["display_likes"] == 5 * 2 + 0


class TestDisplayComments:
    """评论角标假数：display_comments = base_comments × comment_multiplier + 真实可见条数"""

    @pytest.mark.asyncio
    async def test_history_default_zero_base(self, db):
        """历史帖默认 0×1：无评论时展示 0（不回填假数）"""
        db.add(_post(1))  # base_comments=0, comment_multiplier=1
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"][0]["display_comments"] == 0

    @pytest.mark.asyncio
    async def test_formula_without_real(self, db):
        """新帖假数：5×2 + 0 = 10"""
        db.add(_post(1, base_comments=5, comment_multiplier=2))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert r["posts"][0]["display_comments"] == 5 * 2 + 0

    @pytest.mark.asyncio
    async def test_formula_plus_own_comments_only(self, db):
        """真实条数只计当前用户可见评论；他人评论不计入 display_comments"""
        db.add(_post(1, base_comments=5, comment_multiplier=2))
        await db.commit()
        db.add(FeedComment(post_id=1, user_id=_OTHER, content="别人", gen_status="pending"))
        db.add(FeedComment(post_id=1, user_id=_USER, content="我的1", gen_status="pending"))
        db.add(FeedComment(post_id=1, user_id=_USER, content="我的2", gen_status="pending"))
        await db.commit()
        r = await feed_service.list_feed(db, _USER, None, 20)
        assert len(r["posts"][0]["comments"]) == 2
        assert r["posts"][0]["display_comments"] == 5 * 2 + 2

    @pytest.mark.asyncio
    async def test_create_comment_bumps_display(self, db):
        """发评后再次 list：展示数在假数底上 +1"""
        db.add(_post(1, base_comments=3, comment_multiplier=2))
        await db.commit()
        r0 = await feed_service.list_feed(db, _USER, None, 20)
        assert r0["posts"][0]["display_comments"] == 3 * 2 + 0
        await feed_service.create_comment(db, _USER, 1, "一条评论")
        await db.commit()
        r1 = await feed_service.list_feed(db, _USER, None, 20)
        assert r1["posts"][0]["display_comments"] == 3 * 2 + 1


class TestEnterBadge:
    @pytest.mark.asyncio
    async def test_enter_no_unread(self, db):
        r = await feed_service.enter_feed(db, _USER)
        assert r["anchor_comment_id"] is None

    @pytest.mark.asyncio
    async def test_enter_with_unread(self, db):
        db.add(_post(1))
        await db.commit()
        db.add(FeedComment(post_id=1, user_id=_USER, content="c", gen_status="ready",
                           lxm_reply="回复", lxm_reply_at=datetime.utcnow(),
                           lxm_reply_read_at=None))
        await db.commit()
        r = await feed_service.enter_feed(db, _USER)
        assert r["anchor_comment_id"] is not None

    @pytest.mark.asyncio
    async def test_badge_two_fields(self, db):
        db.add(_post(1))
        await db.commit()
        db.add(FeedComment(post_id=1, user_id=_USER, content="c", gen_status="ready",
                           lxm_reply="回复", lxm_reply_at=datetime.utcnow(),
                           lxm_reply_read_at=None))
        await db.commit()
        r = await feed_service.get_badge(db, _USER)
        assert r["has_new"] is True
        assert r["new_post_count"] == 0  # 从未 enter：不暴露全量 N
        assert r["unread_reply_count"] == 1

    @pytest.mark.asyncio
    async def test_badge_new_post_count_after_enter(self, db):
        """进入后再出现新帖：new_post_count 为相对 last_feed_entered_at 的条数。"""
        now = fs_mod.feed_now()
        user = (await db.execute(select(User).where(User.id == _USER))).scalars().first()
        user.last_feed_entered_at = now - timedelta(hours=2)
        db.add(FeedPost(
            id=2, scene_id="s2",
            scheduled_publish_time=now - timedelta(minutes=30),
            actual_publish_time=None, generation_status="ready",
            content_text="新帖", hashtags=[], image_urls=None,
            image_reference_url="ref", image_type=None, emotion="平静",
            city="杭州", season="夏", base_likes=5, like_multiplier=2,
            real_likes=0, base_comments=0, comment_multiplier=1,
            is_visible=1, dedup_hash="h2",
        ))
        await db.commit()
        r = await feed_service.get_badge(db, _USER)
        assert r["has_new"] is True
        assert r["new_post_count"] == 1
        assert r["unread_reply_count"] == 0


# ============ STEP-016 点赞 ============

class TestLike:
    @pytest.mark.asyncio
    async def test_first_like(self, db):
        db.add(_post(1, real=0))
        await db.commit()
        r = await feed_service.like_post(db, _USER, 1)
        assert r["user_liked"] is True
        assert r["display_likes"] == 5 * 2 + 1

    @pytest.mark.asyncio
    async def test_duplicate_like_idempotent(self, db):
        db.add(_post(1, real=0))
        await db.commit()
        await feed_service.like_post(db, _USER, 1)
        r = await feed_service.like_post(db, _USER, 1)
        assert r["display_likes"] == 5 * 2 + 1  # 不重复加

    @pytest.mark.asyncio
    async def test_unlike(self, db):
        db.add(_post(1, real=0))
        await db.commit()
        await feed_service.like_post(db, _USER, 1)
        r = await feed_service.unlike_post(db, _USER, 1)
        assert r["user_liked"] is False
        assert r["display_likes"] == 5 * 2 + 0

    @pytest.mark.asyncio
    async def test_unlike_not_liked(self, db):
        db.add(_post(1, real=0))
        await db.commit()
        r = await feed_service.unlike_post(db, _USER, 1)
        assert r["display_likes"] == 5 * 2 + 0  # 保持 >=0

    @pytest.mark.asyncio
    async def test_like_hidden_404(self, db):
        db.add(_post(1, visible=0))
        await db.commit()
        with pytest.raises(FeedError) as ei:
            await feed_service.like_post(db, _USER, 1)
        assert ei.value.code == ERR_FEED_POST_NOT_FOUND

    @pytest.mark.asyncio
    async def test_like_not_to_point_404(self, db):
        db.add(_post(1, minutes_ago=-60))
        await db.commit()
        with pytest.raises(FeedError) as ei:
            await feed_service.like_post(db, _USER, 1)
        assert ei.value.code == ERR_FEED_POST_NOT_FOUND


# ============ STEP-017 评论 ============

class TestComment:
    @pytest.mark.asyncio
    async def test_empty(self, db):
        db.add(_post(1))
        await db.commit()
        with pytest.raises(FeedError) as ei:
            await feed_service.create_comment(db, _USER, 1, "   ")
        assert ei.value.code == ERR_COMMENT_EMPTY

    @pytest.mark.asyncio
    async def test_too_long(self, db):
        db.add(_post(1))
        await db.commit()
        with pytest.raises(FeedError) as ei:
            await feed_service.create_comment(db, _USER, 1, "x" * 201)
        assert ei.value.code == ERR_COMMENT_TOO_LONG

    @pytest.mark.asyncio
    async def test_rate_limit(self, db):
        db.add(_post(1))
        await db.commit()
        await feed_service.create_comment(db, _USER, 1, "第一条")
        with pytest.raises(FeedError) as ei:
            await feed_service.create_comment(db, _USER, 1, "第二条")
        assert ei.value.code == ERR_COMMENT_RATE_LIMIT

    @pytest.mark.asyncio
    async def test_content_safety(self, db, monkeypatch):
        db.add(_post(1))
        await db.commit()
        monkeypatch.setattr(fs_mod.content_safety_service, "check_content",
                            AsyncMock(return_value={"is_safe": False, "reason": "违规"}))
        with pytest.raises(FeedError) as ei:
            await feed_service.create_comment(db, _USER, 1, "违规内容")
        assert ei.value.code == ERR_CONTENT_SAFETY_VIOLATION

    @pytest.mark.asyncio
    async def test_first_comment_override(self, db):
        db.add(_post(1))
        await db.commit()
        before = datetime.utcnow()
        r = await feed_service.create_comment(db, _USER, 1, "首评")
        c = (await db.execute(
            select(FeedComment).where(FeedComment.id == r["comment_id"]))).scalars().first()
        delta = (c.due_at - before).total_seconds()
        assert 28 <= delta <= 33  # ≈ +30s
        rel = (await db.execute(
            select(Relationship).where(Relationship.user_id == _USER))).scalars().first()
        assert rel.has_ever_commented_feed == 1

    @pytest.mark.asyncio
    async def test_non_first_comment_delay(self, db):
        # 已发过评论 → intimate 档 60~180s
        rel = (await db.execute(
            select(Relationship).where(Relationship.user_id == _USER))).scalars().first()
        rel.has_ever_commented_feed = 1
        db.add(_post(1))
        await db.commit()
        before = datetime.utcnow()
        r = await feed_service.create_comment(db, _USER, 1, "非首评")
        c = (await db.execute(
            select(FeedComment).where(FeedComment.id == r["comment_id"]))).scalars().first()
        delta = (c.due_at - before).total_seconds()
        assert 58 <= delta <= 182  # intimate 60~180s

    @pytest.mark.asyncio
    async def test_hidden_404(self, db):
        db.add(_post(1, visible=0))
        await db.commit()
        with pytest.raises(FeedError) as ei:
            await feed_service.create_comment(db, _USER, 1, "评论")
        assert ei.value.code == ERR_FEED_POST_NOT_FOUND

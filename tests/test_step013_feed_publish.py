# -*- coding: utf-8 -*-
# STEP-013 单元测试：每日发布整合 feed_publish_service.run_daily_publish
# 覆盖场景（对应 steps.md STEP-013 单测要求表）：
#   - 无 life_plan → skip
#   - 自动开关 False → skip
#   - 抽 3 条但可用 2 场景 → 发布 2 条
#   - dedup 命中 1 条 → 发布 count-1 条
#   - 图片全失败 → 该条纯文字发布
#   - 快照 generating → 视同 failed 降级（非 ready 路径）
#   - season 南半球 → 冬
#   - scheduled_publish_time → 分别落在 3 个窗口内

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.feed_post import FeedPost
from backend.models.life_plan import LifePlan
from backend.models.worldview_snapshot import WorldviewSnapshot
from backend.services import feed_publish_service as fps_mod
from backend.services.feed_content_service import DedupHitException
from backend.services.feed_publish_service import feed_publish_service
from backend.utils.season_utils import compute_season

_PLAN_DATE = date(2026, 6, 15)


def _scene(seq, time_range, city="杭州", category="工作", venue="咖啡馆"):
    return {
        "scene_id": f"scene_{seq}", "time_range": time_range,
        "city": city, "category": category, "venue_type": venue,
        "description": "描" * 200,
    }


def _draft(emotion="平静", dh="hash1"):
    return {"post_text": "今天在咖啡馆坐了很久", "hashtags": ["#日常"],
            "emotion": emotion, "dedup_hash": dh, "travel_stage": None}


@pytest_asyncio.fixture
async def sqlite_maker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(LifePlan.__table__.create)
        await conn.run_sync(WorldviewSnapshot.__table__.create)
        await conn.run_sync(FeedPost.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(fps_mod, "async_session_maker", maker)
    yield maker
    await engine.dispose()


async def _seed_plan(maker, scenes, gen_status="ready"):
    async with maker() as db:
        db.add(LifePlan(plan_date=_PLAN_DATE, scenes=scenes, gen_status=gen_status))
        await db.commit()


def _cfg(w2=0, w3=100, auto=True):
    """count 权重 + 自动开关，其余走 default。"""
    async def _side(key, default=None):
        if key == "feed_daily_post_count_2_weight":
            return w2
        if key == "feed_daily_post_count_3_weight":
            return w3
        if key == "feed_auto_publish_enabled":
            return auto
        return default
    return AsyncMock(side_effect=_side)


def _patches(gen_side, img_return, cfg):
    return (
        patch.object(fps_mod, "get_life_feed_config", cfg),
        patch.object(fps_mod.feed_content_service, "generate_post_text", gen_side),
        patch.object(fps_mod.feed_image_service, "generate_images",
                     new_callable=AsyncMock, side_effect=img_return),
        patch.object(fps_mod, "get_feed_image_reference_public_url",
                     return_value="https://x/base.png"),
    )


# ============ 季节工具 ============

class TestSeason:
    def test_northern_summer(self):
        assert compute_season("杭州", date(2026, 6, 15)) == "夏"

    def test_southern_winter(self):
        assert compute_season("悉尼", date(2026, 6, 15)) == "冬"

    def test_southern_summer_december(self):
        assert compute_season("墨尔本", date(2026, 12, 20)) == "夏"


# ============ run_daily_publish ============

class TestRunDailyPublish:
    @pytest.mark.asyncio
    async def test_no_plan_skip(self, sqlite_maker):
        cfg = _cfg()
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["status"] == "skipped_no_plan"

    @pytest.mark.asyncio
    async def test_auto_disabled_skip(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [_scene(1, "09:00-10:00")])
        cfg = _cfg(auto=False)
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["status"] == "skipped_disabled"

    @pytest.mark.asyncio
    async def test_target3_only2_scenes(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [
            _scene(1, "09:00-10:00"), _scene(2, "14:00-15:00"),
        ])
        cfg = _cfg(w2=0, w3=100)  # target=3
        gen = AsyncMock(return_value=_draft())

        async def _img(ctx):
            ctx["image_type"] = "daily"
            return ["https://cdn/a.webp"]

        for p in _patches(gen, _img, cfg):
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["success"] == 2
        async with sqlite_maker() as db:
            posts = (await db.execute(select(FeedPost))).scalars().all()
        assert len(posts) == 2
        assert all(p.generation_status == "ready" for p in posts)

    @pytest.mark.asyncio
    async def test_dedup_hit_reduces_one(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [
            _scene(1, "09:00-10:00"), _scene(2, "14:00-15:00"), _scene(3, "19:00-20:00"),
        ])
        cfg = _cfg(w2=0, w3=100)  # target=3
        gen = AsyncMock(side_effect=[
            DedupHitException("dup", 999), _draft(), _draft(),
        ])
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["success"] == 2
        assert r["skipped"] == 1

    @pytest.mark.asyncio
    async def test_all_images_fail_text_only(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [_scene(1, "09:00-10:00")])
        cfg = _cfg(w2=100, w3=0)  # target=2 → min(2,1)=1
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):  # 图片返回 []
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["success"] == 1
        async with sqlite_maker() as db:
            post = (await db.execute(select(FeedPost))).scalars().first()
        assert post.image_urls is None
        assert post.generation_status == "ready"

    @pytest.mark.asyncio
    async def test_snapshot_generating_degraded(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [_scene(1, "09:00-10:00")])
        async with sqlite_maker() as db:
            db.add(WorldviewSnapshot(
                plan_date=_PLAN_DATE, scene_id="scene_1", gen_status="generating"))
            await db.commit()
        cfg = _cfg(w2=100, w3=0)
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            r = await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        assert r["success"] == 1
        # 传入的快照 gen_status=generating（feed_content 自行走非 ready 路径）
        snap_arg = gen.await_args.args[1]
        assert snap_arg.gen_status == "generating"

    @pytest.mark.asyncio
    async def test_season_written_southern(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [_scene(1, "09:00-10:00", city="悉尼")])
        cfg = _cfg(w2=100, w3=0)
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        async with sqlite_maker() as db:
            post = (await db.execute(select(FeedPost))).scalars().first()
        assert post.season == "冬"  # 悉尼 6 月

    @pytest.mark.asyncio
    async def test_scheduled_time_in_windows(self, sqlite_maker):
        await _seed_plan(sqlite_maker, [
            _scene(1, "09:00-10:00"), _scene(2, "14:00-15:00"), _scene(3, "19:00-20:00"),
        ])
        cfg = _cfg(w2=0, w3=100)  # target=3
        gen = AsyncMock(return_value=_draft())
        for p in _patches(gen, lambda ctx: [], cfg):
            p.start()
        try:
            await feed_publish_service.run_daily_publish(_PLAN_DATE)
        finally:
            patch.stopall()
        async with sqlite_maker() as db:
            posts = (await db.execute(
                select(FeedPost).order_by(FeedPost.id))).scalars().all()
        assert len(posts) == 3
        # 窗口：10-12 / 15-20 / 20-23
        assert 10 <= posts[0].scheduled_publish_time.hour < 12
        assert 15 <= posts[1].scheduled_publish_time.hour < 20
        assert 20 <= posts[2].scheduled_publish_time.hour < 23

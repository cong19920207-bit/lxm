# -*- coding: utf-8 -*-
# STEP-007 单元测试：LLM-02 日场景生成 generate_daily_scenes
# 覆盖场景（对应 steps.md STEP-007 单测要求表）：
#   - 无大纲 → 跳过
#   - 场景数<2 → gen_status=failed
#   - city 不符 → 校验失败（failed）
#   - time_range 越界 → 校验失败（failed）
#   - scene_id 编号 001/002/003
#   - 已 ready 时二次执行 → 跳过

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.life_plan import LifePlan
from backend.models.life_plan_outline import LifePlanOutline
from backend.services import life_planner_service as lps_mod
from backend.services.life_planner_service import life_planner_service

_PLAN_DATE = date(2026, 6, 2)
_CITY = "杭州"


def _scene(cat="工作", city=_CITY, time_range="09:00-10:30", desc_len=250):
    return {
        "scene_id": "scene_001",
        "time_range": time_range,
        "city": city,
        "category": cat,
        "venue_type": "咖啡馆",
        "description": "描" * desc_len,
    }


def _scenes_payload(scenes):
    return json.dumps({"plan_date": _PLAN_DATE.isoformat(), "scenes": scenes})


@pytest_asyncio.fixture
async def sqlite_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(LifePlanOutline.__table__.create)
        await conn.run_sync(LifePlan.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(lps_mod, "async_session_maker", maker)
    yield maker
    await engine.dispose()


async def _seed_outline(maker, categories="工作\n旅游"):
    async with maker() as db:
        db.add(LifePlanOutline(
            week_start_date=date(2026, 6, 1), plan_date=_PLAN_DATE,
            city=_CITY, categories=categories, gen_status="auto",
        ))
        await db.commit()


def _patch(llm_return):
    return (
        patch.object(lps_mod, "get_life_feed_config", new_callable=AsyncMock,
                     side_effect=lambda key, default=None: default),
        patch.object(lps_mod, "render_prompt", new_callable=AsyncMock, return_value="p"),
        patch.object(lps_mod.deepseek_llm_service, "call_llm",
                     new_callable=AsyncMock, return_value=llm_return),
    )


class TestGenerateDailyScenes:
    @pytest.mark.asyncio
    async def test_no_outline_skips(self, sqlite_session):
        # 未种大纲
        llm = AsyncMock()
        with patch.object(lps_mod.deepseek_llm_service, "call_llm", llm):
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "skipped_no_outline"
        llm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_normal_scene_ids(self, sqlite_session):
        await _seed_outline(sqlite_session)
        payload = _scenes_payload([_scene(), _scene(), _scene()])
        p_cfg, p_render, p_llm = _patch(payload)
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "ready"
        assert result["scenes"] == 3

        async with sqlite_session() as db:
            row = (await db.execute(select(LifePlan))).scalars().first()
        assert row.gen_status == "ready"
        ids = [s["scene_id"] for s in row.scenes]
        assert ids[0].endswith("_001")
        assert ids[1].endswith("_002")
        assert ids[2].endswith("_003")

    @pytest.mark.asyncio
    async def test_less_than_two_failed(self, sqlite_session):
        await _seed_outline(sqlite_session)
        p_cfg, p_render, p_llm = _patch(_scenes_payload([_scene()]))
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "failed"
        async with sqlite_session() as db:
            row = (await db.execute(select(LifePlan))).scalars().first()
        assert row.gen_status == "failed"

    @pytest.mark.asyncio
    async def test_city_mismatch_failed(self, sqlite_session):
        await _seed_outline(sqlite_session)
        bad = [_scene(city="上海"), _scene()]
        p_cfg, p_render, p_llm = _patch(_scenes_payload(bad))
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_time_range_out_of_bound_failed(self, sqlite_session):
        await _seed_outline(sqlite_session)
        bad = [_scene(time_range="05:00-06:00"), _scene()]
        p_cfg, p_render, p_llm = _patch(_scenes_payload(bad))
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_category_out_of_outline_failed(self, sqlite_session):
        await _seed_outline(sqlite_session, categories="工作")
        bad = [_scene(cat="旅游"), _scene(cat="工作")]
        p_cfg, p_render, p_llm = _patch(_scenes_payload(bad))
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_already_ready_skips(self, sqlite_session):
        await _seed_outline(sqlite_session)
        async with sqlite_session() as db:
            db.add(LifePlan(plan_date=_PLAN_DATE, scenes=[_scene(), _scene()], gen_status="ready"))
            await db.commit()

        llm = AsyncMock(return_value=_scenes_payload([_scene(), _scene()]))
        with patch.object(lps_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=lambda key, default=None: default), \
             patch.object(lps_mod, "render_prompt", new_callable=AsyncMock, return_value="p"), \
             patch.object(lps_mod.deepseek_llm_service, "call_llm", llm):
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "skipped_ready"
        llm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_then_retry_success_upsert(self, sqlite_session):
        """先 failed 落库，再成功 → 同一行 upsert 为 ready。"""
        await _seed_outline(sqlite_session)
        p_cfg, p_render, p_llm = _patch(_scenes_payload([_scene()]))
        with p_cfg, p_render, p_llm:
            await life_planner_service.generate_daily_scenes(_PLAN_DATE)

        p_cfg2, p_render2, p_llm2 = _patch(_scenes_payload([_scene(), _scene()]))
        with p_cfg2, p_render2, p_llm2:
            result = await life_planner_service.generate_daily_scenes(_PLAN_DATE)
        assert result["status"] == "ready"

        async with sqlite_session() as db:
            rows = (await db.execute(select(LifePlan))).scalars().all()
        assert len(rows) == 1  # upsert，未重复插入
        assert rows[0].gen_status == "ready"

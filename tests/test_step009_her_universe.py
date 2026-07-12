# -*- coding: utf-8 -*-
# STEP-009 单元测试：LLM-03 她的宇宙 daily_her_universe_task / generate_for_scene
# 覆盖场景（对应 steps.md STEP-009 单测要求表）：
#   - 无 ready 计划 → skip
#   - 3 场景全成功 → 3 快照 + 3 事件（name 不重）
#   - 单条 3 次失败 → 该 snapshot=failed，其余正常
#   - event_name 已存在 → INSERT IGNORE 跳过
#   - core_attitude 非法 → 校验失败重试

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.life_plan import LifePlan
from backend.models.worldview_event import WorldviewEvent
from backend.models.worldview_snapshot import WorldviewSnapshot
from backend.services import her_universe_service as hus_mod
from backend.services.her_universe_service import HerUniverseError, her_universe_service

_PLAN_DATE = date(2026, 6, 2)


def _scene(scene_id, category="工作", city="杭州"):
    return {
        "scene_id": scene_id, "time_range": "09:00-10:30",
        "city": city, "category": category, "venue_type": "咖啡馆",
        "description": "描" * 250,
    }


def _llm_payload(event_name="在人多景区的感受与应对方式", attitude_in_view=True):
    view = ("我对这个话题" + ("喜欢" if attitude_in_view else "喜爱") + "，" + "详" * 120)
    return json.dumps({
        "snapshot": {
            "feeling_text": "今天挺好的",
            "emotion_value": "平静",
            "focus_tag": "安于当下",
            "worldview_trigger": "慢生活",
        },
        "worldview_event": {"event_name": event_name, "event_view": view},
    })


@pytest_asyncio.fixture
async def sqlite_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(LifePlan.__table__.create)
        await conn.run_sync(WorldviewSnapshot.__table__.create)
        await conn.run_sync(WorldviewEvent.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(hus_mod, "async_session_maker", maker)
    yield maker
    await engine.dispose()


async def _seed_plan(maker, scenes, gen_status="ready"):
    async with maker() as db:
        db.add(LifePlan(plan_date=_PLAN_DATE, scenes=scenes, gen_status=gen_status))
        await db.commit()


def _base_patches():
    return (
        patch.object(hus_mod, "get_life_feed_config", new_callable=AsyncMock,
                     side_effect=lambda key, default=None: default),
        patch.object(hus_mod, "render_prompt", new_callable=AsyncMock, return_value="p"),
    )


class TestDailyHerUniverse:
    @pytest.mark.asyncio
    async def test_no_ready_plan_skips(self, sqlite_session):
        await _seed_plan(sqlite_session, [_scene("s1")], gen_status="failed")
        result = await her_universe_service.daily_her_universe_task(_PLAN_DATE)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_three_scenes_all_success(self, sqlite_session):
        scenes = [_scene("scene_2026-06-02_001"),
                  _scene("scene_2026-06-02_002"),
                  _scene("scene_2026-06-02_003")]
        await _seed_plan(sqlite_session, scenes)
        p_cfg, p_render = _base_patches()
        # 三次返回不同 event_name，保证事件不重
        returns = [_llm_payload(f"关于某类事物的固定看法与做法{i}") for i in range(3)]
        with p_cfg, p_render, patch.object(
            hus_mod.deepseek_llm_service, "call_llm",
            new_callable=AsyncMock, side_effect=returns,
        ):
            result = await her_universe_service.daily_her_universe_task(_PLAN_DATE)
        assert result["success"] == 3
        assert result["failed"] == 0
        assert result["events_new"] == 3

        async with sqlite_session() as db:
            snaps = (await db.execute(select(WorldviewSnapshot))).scalars().all()
            events = (await db.execute(select(WorldviewEvent))).scalars().all()
        assert len(snaps) == 3
        assert all(s.gen_status == "ready" for s in snaps)
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_single_scene_three_failures(self, sqlite_session):
        scenes = [_scene("s_fail"), _scene("s_ok")]
        await _seed_plan(sqlite_session, scenes)
        p_cfg, p_render = _base_patches()
        # s_fail 三次超时，s_ok 一次成功
        side = [TimeoutError("t"), TimeoutError("t"), TimeoutError("t"),
                _llm_payload("正常的一个话题固定看法描述")]
        with p_cfg, p_render, patch.object(
            hus_mod.deepseek_llm_service, "call_llm",
            new_callable=AsyncMock, side_effect=side,
        ):
            result = await her_universe_service.daily_her_universe_task(_PLAN_DATE)
        assert result["success"] == 1
        assert result["failed"] == 1

        async with sqlite_session() as db:
            snaps = {s.scene_id: s for s in
                     (await db.execute(select(WorldviewSnapshot))).scalars().all()}
        assert snaps["s_fail"].gen_status == "failed"
        assert snaps["s_ok"].gen_status == "ready"

    @pytest.mark.asyncio
    async def test_duplicate_event_name_ignored(self, sqlite_session):
        scenes = [_scene("s1"), _scene("s2")]
        await _seed_plan(sqlite_session, scenes)
        p_cfg, p_render = _base_patches()
        # 两条同 event_name
        same = _llm_payload("同一个话题的固定看法描述短语")
        with p_cfg, p_render, patch.object(
            hus_mod.deepseek_llm_service, "call_llm",
            new_callable=AsyncMock, side_effect=[same, same],
        ):
            result = await her_universe_service.daily_her_universe_task(_PLAN_DATE)
        assert result["success"] == 2
        assert result["events_new"] == 1  # 第二条 INSERT IGNORE 跳过

        async with sqlite_session() as db:
            events = (await db.execute(select(WorldviewEvent))).scalars().all()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_core_attitude_invalid_retries_then_fail(self, sqlite_session):
        scenes = [_scene("s1")]
        await _seed_plan(sqlite_session, scenes)
        p_cfg, p_render = _base_patches()
        # 显式 core_attitude 非法 "喜爱"，三次都非法 → 最终失败
        bad = json.loads(_llm_payload())
        bad["worldview_event"]["core_attitude"] = "喜爱"
        # 去掉 view 里的态度词，确保只走显式字段判定
        bad["worldview_event"]["event_view"] = "描" * 120
        bad_str = json.dumps(bad)
        call = AsyncMock(side_effect=[bad_str, bad_str, bad_str])
        with p_cfg, p_render, patch.object(
            hus_mod.deepseek_llm_service, "call_llm", call,
        ):
            result = await her_universe_service.daily_her_universe_task(_PLAN_DATE)
        assert result["failed"] == 1
        assert call.await_count == 3  # 3 次立即重试


class TestGenerateForSceneValidation:
    @pytest.mark.asyncio
    async def test_attitude_in_view_ok(self, sqlite_session):
        p_cfg, p_render = _base_patches()
        with p_cfg, p_render, patch.object(
            hus_mod.deepseek_llm_service, "call_llm",
            new_callable=AsyncMock, return_value=_llm_payload(),
        ):
            snap, event = await her_universe_service.generate_for_scene(
                _scene("s1"), _PLAN_DATE
            )
        assert snap["emotion_value"] == "平静"
        assert event["event_name"]

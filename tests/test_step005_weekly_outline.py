# -*- coding: utf-8 -*-
# STEP-005 单元测试：LLM-01 周大纲生成 generate_week_outline
# 覆盖场景（对应 steps.md STEP-005 单测要求表）：
#   - Mock LLM 正常返回 days_count=7 → 7 条落库
#   - LLM 返回条数不符（6 条）→ 校验失败抛错
#   - categories 词表外 → 校验失败抛错
#   - 已有落库 → 跳过（不调用 LLM）
#   - markdown 代码块剥离 → 正确解析
#   + _classify_month_days 纯逻辑

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.life_plan_outline import LifePlanOutline
from backend.services import life_planner_service as lps_mod
from backend.services.life_planner_service import (
    LifePlannerError,
    _classify_month_days,
    _strip_markdown_fence,
    life_planner_service,
)

_VOCAB = ["工作", "学习", "旅游", "购物逛街", "探店美食",
          "户外散步", "休闲在家", "看展文化", "运动健身", "社交"]
_MONDAY = date(2026, 6, 1)  # 2026-06-01 为周一


def _make_days(count: int, start: date = _MONDAY, bad_category: bool = False) -> dict:
    days = []
    for i in range(count):
        d = start + timedelta(days=i)
        cat = "外星探索" if (bad_category and i == 0) else "工作"
        days.append({"date": d.isoformat(), "city": "杭州", "categories": cat})
    return {"plan_start_date": start.isoformat(), "days": days}


@pytest_asyncio.fixture
async def sqlite_session(monkeypatch):
    """用 aiosqlite 内存库替换 life_planner_service.async_session_maker。"""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(LifePlanOutline.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(lps_mod, "async_session_maker", maker)
    yield maker
    await engine.dispose()


def _patch_deps(llm_return: str):
    """统一打桩 config / render_prompt / call_llm。"""
    return (
        patch.object(lps_mod, "get_life_feed_config", new_callable=AsyncMock,
                     side_effect=lambda key, default=None: {
                         "home_city": "杭州",
                         "categories_vocab": _VOCAB,
                     }.get(key, default)),
        patch.object(lps_mod, "render_prompt", new_callable=AsyncMock,
                     return_value="dummy prompt"),
        patch.object(lps_mod.deepseek_llm_service, "call_llm",
                     new_callable=AsyncMock, return_value=llm_return),
    )


# ============ 纯逻辑 ============

class TestPureHelpers:
    def test_strip_markdown_fence(self):
        raw = "```json\n{\"a\": 1}\n```"
        assert _strip_markdown_fence(raw) == '{"a": 1}'

    def test_strip_plain(self):
        assert _strip_markdown_fence('{"a":1}') == '{"a":1}'

    def test_classify_month_days_local_short_long(self):
        # 本地3天 + 单天短途1天 + 连续3天长途
        rows = []
        base = date(2026, 6, 1)
        cities = ["杭州", "杭州", "苏州", "杭州", "北京", "北京", "北京"]
        for i, c in enumerate(cities):
            r = LifePlanOutline(
                week_start_date=base, plan_date=base + timedelta(days=i),
                city=c, categories="工作", gen_status="auto",
            )
            rows.append(r)
        stats = _classify_month_days(rows, "杭州")
        assert stats["local"] == 3
        assert stats["short"] == 1   # 苏州单天
        assert stats["long"] == 3    # 北京连续3天


# ============ generate_week_outline ============

class TestGenerateWeekOutline:
    @pytest.mark.asyncio
    async def test_normal_7_days_persisted(self, sqlite_session):
        p_cfg, p_render, p_llm = _patch_deps(json.dumps(_make_days(7)))
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_week_outline(7, _MONDAY)
        assert result["status"] == "success"
        assert result["days"] == 7

        async with sqlite_session() as db:
            rows = (await db.execute(select(LifePlanOutline))).scalars().all()
        assert len(rows) == 7
        assert all(r.gen_status == "auto" for r in rows)

    @pytest.mark.asyncio
    async def test_count_mismatch_raises(self, sqlite_session):
        p_cfg, p_render, p_llm = _patch_deps(json.dumps(_make_days(6)))
        with p_cfg, p_render, p_llm:
            with pytest.raises(LifePlannerError):
                await life_planner_service.generate_week_outline(7, _MONDAY)

    @pytest.mark.asyncio
    async def test_category_out_of_vocab_raises(self, sqlite_session):
        p_cfg, p_render, p_llm = _patch_deps(json.dumps(_make_days(7, bad_category=True)))
        with p_cfg, p_render, p_llm:
            with pytest.raises(LifePlannerError):
                await life_planner_service.generate_week_outline(7, _MONDAY)

    @pytest.mark.asyncio
    async def test_already_generated_skips_without_llm(self, sqlite_session):
        # 预置该周 1 天落库
        async with sqlite_session() as db:
            db.add(LifePlanOutline(
                week_start_date=_MONDAY, plan_date=_MONDAY, city="杭州",
                categories="工作", gen_status="auto",
            ))
            await db.commit()

        llm_mock = AsyncMock(return_value=json.dumps(_make_days(7)))
        with patch.object(lps_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=lambda key, default=None: {
                              "home_city": "杭州", "categories_vocab": _VOCAB,
                          }.get(key, default)), \
             patch.object(lps_mod, "render_prompt", new_callable=AsyncMock,
                          return_value="dummy"), \
             patch.object(lps_mod.deepseek_llm_service, "call_llm", llm_mock):
            result = await life_planner_service.generate_week_outline(7, _MONDAY)
        assert result["status"] == "skipped"
        llm_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_markdown_fence_parsed(self, sqlite_session):
        wrapped = "```json\n" + json.dumps(_make_days(7)) + "\n```"
        p_cfg, p_render, p_llm = _patch_deps(wrapped)
        with p_cfg, p_render, p_llm:
            result = await life_planner_service.generate_week_outline(7, _MONDAY)
        assert result["status"] == "success"
        assert result["days"] == 7

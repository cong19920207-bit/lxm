# -*- coding: utf-8 -*-
# STEP-011 单元测试：LLM-04 文案生成 feed_content_service
# 覆盖场景（对应 steps.md STEP-011 单测要求表）：
#   - 快照 ready → emotion 直接复制
#   - 快照 failed → emotion 取自 LLM 输出
#   - dedup 命中 → DedupHitException
#   - 相似度 0.8+ → SimilarityHitException
#   - 主场城市 → 不注入旅游段
#   - 返程日 → travel_stage='return' 且注入 P-05-return
#   - 内容安全违规 → ContentSafetyException
#   - hashtags 抽签 0（权重 100/0/0/0）→ 提示不生成话题

import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.feed_post import FeedPost
from backend.models.life_plan_outline import LifePlanOutline
from backend.services import feed_content_service as fcs_mod
from backend.services.feed_content_service import (
    ContentSafetyException,
    DedupHitException,
    SimilarityHitException,
    bi_gram_set,
    feed_content_service,
    jaccard,
)
from backend.utils.hash_utils import compute_dedup_hash

_PLAN_DATE = date(2026, 6, 3)  # 周三


def _scene(city="杭州", scene_id="scene_2026-06-03_001"):
    return {
        "scene_id": scene_id, "time_range": "09:00-10:30", "city": city,
        "category": "工作", "venue_type": "咖啡馆", "description": "描" * 250,
    }


def _ready_snapshot(emotion="慵懒"):
    return SimpleNamespace(
        gen_status="ready", emotion_value=emotion,
        focus_tag="安于当下", feeling_text="挺好的",
    )


def _failed_snapshot():
    return SimpleNamespace(gen_status="failed", emotion_value=None,
                           focus_tag=None, feeling_text=None)


@pytest_asyncio.fixture
async def sqlite_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(FeedPost.__table__.create)
        await conn.run_sync(LifePlanOutline.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(fcs_mod, "async_session_maker", maker)
    yield maker
    await engine.dispose()


async def _add_feed_post(maker, content_text, dedup_hash, status="ready"):
    async with maker() as db:
        db.add(FeedPost(
            scene_id="old", scheduled_publish_time=datetime(2026, 6, 1, 10, 0),
            generation_status=status, content_text=content_text,
            emotion="平静", city="杭州", season="夏", base_likes=3,
            like_multiplier=2, real_likes=0, is_visible=1,
            dedup_hash=dedup_hash, created_at=datetime.utcnow(),
        ))
        await db.commit()


async def _add_week_outline(maker):
    cities = {date(2026, 6, 1): "杭州", date(2026, 6, 2): "苏州",
              date(2026, 6, 3): "苏州", date(2026, 6, 4): "杭州"}
    async with maker() as db:
        for d, c in cities.items():
            db.add(LifePlanOutline(
                week_start_date=date(2026, 6, 1), plan_date=d, city=c,
                categories="工作", gen_status="auto",
            ))
        await db.commit()


def _patches(llm_return, cfg_overrides=None, safe=True):
    overrides = cfg_overrides or {}

    async def _cfg(key, default=None):
        return overrides.get(key, default)

    return (
        patch.object(fcs_mod, "get_life_feed_config", side_effect=_cfg),
        patch.object(fcs_mod, "render_prompt", new_callable=AsyncMock, return_value="P"),
        patch.object(fcs_mod.deepseek_llm_service, "call_llm",
                     new_callable=AsyncMock, return_value=llm_return),
        patch.object(fcs_mod, "check_content", new_callable=AsyncMock,
                     return_value={"is_safe": safe, "reason": "" if safe else "命中违规词: xx"}),
    )


# ============ 纯函数 ============

class TestSimilarityHelpers:
    def test_bi_gram(self):
        assert bi_gram_set("abcd") == {"ab", "bc", "cd"}

    def test_jaccard_identical(self):
        assert jaccard("今天天气很好啊", "今天天气很好啊") == 1.0

    def test_jaccard_disjoint(self):
        assert jaccard("abcd", "wxyz") == 0.0


# ============ emotion 双路径 ============

class TestEmotionDualPath:
    @pytest.mark.asyncio
    async def test_snapshot_ready_copies_emotion(self, sqlite_session):
        llm = json.dumps({"post_text": "今天喝了杯咖啡，很舒服", "hashtags": ["咖啡"]})
        p1, p2, p3, p4 = _patches(llm)
        with p1, p2, p3, p4:
            draft = await feed_content_service.generate_post_text(
                _scene(), _ready_snapshot("慵懒"), _PLAN_DATE
            )
        assert draft["emotion"] == "慵懒"
        assert draft["hashtags"] == ["咖啡"]

    @pytest.mark.asyncio
    async def test_snapshot_failed_uses_llm_emotion(self, sqlite_session):
        llm = json.dumps({"post_text": "随便写写今天", "hashtags": [], "emotion": "平静"})
        p1, p2, p3, p4 = _patches(llm)
        with p1, p2, p3, p4:
            draft = await feed_content_service.generate_post_text(
                _scene(), _failed_snapshot(), _PLAN_DATE
            )
        assert draft["emotion"] == "平静"


# ============ 去重 / 相似度 / 内容安全 ============

class TestFilters:
    @pytest.mark.asyncio
    async def test_dedup_hit(self, sqlite_session):
        dh = compute_dedup_hash("咖啡馆", "工作", "杭州")
        await _add_feed_post(sqlite_session, "旧文案", dh, status="ready")
        llm = json.dumps({"post_text": "新文案", "hashtags": [], "emotion": "平静"})
        p1, p2, p3, p4 = _patches(llm)
        with p1, p2, p3, p4:
            with pytest.raises(DedupHitException):
                await feed_content_service.generate_post_text(
                    _scene(), _failed_snapshot(), _PLAN_DATE
                )

    @pytest.mark.asyncio
    async def test_similarity_hit(self, sqlite_session):
        # 不同 dedup_hash（避免先触发去重），content 与生成文案完全相同
        text = "今天在河边散步，看到夕阳特别温柔啊"
        await _add_feed_post(sqlite_session, text, "other_hash_123", status="ready")
        llm = json.dumps({"post_text": text, "hashtags": [], "emotion": "平静"})
        p1, p2, p3, p4 = _patches(llm)
        with p1, p2, p3, p4:
            with pytest.raises(SimilarityHitException):
                await feed_content_service.generate_post_text(
                    _scene(), _failed_snapshot(), _PLAN_DATE
                )

    @pytest.mark.asyncio
    async def test_content_safety_violation(self, sqlite_session):
        llm = json.dumps({"post_text": "违规内容", "hashtags": [], "emotion": "平静"})
        p1, p2, p3, p4 = _patches(llm, safe=False)
        with p1, p2, p3, p4:
            with pytest.raises(ContentSafetyException):
                await feed_content_service.generate_post_text(
                    _scene(), _failed_snapshot(), _PLAN_DATE
                )


# ============ 旅游叙事 ============

class TestTravelNarrative:
    @pytest.mark.asyncio
    async def test_home_city_no_travel(self, sqlite_session):
        await _add_week_outline(sqlite_session)
        llm = json.dumps({"post_text": "在家待着", "hashtags": [], "emotion": "平静"})
        p1, p2, p3, p4 = _patches(llm)
        with p1, p2, p3, p4:
            draft = await feed_content_service.generate_post_text(
                _scene(city="杭州"), _failed_snapshot(), _PLAN_DATE
            )
        assert draft["travel_stage"] is None

    @pytest.mark.asyncio
    async def test_return_day_injects_p05_return(self, sqlite_session):
        await _add_week_outline(sqlite_session)
        llm = json.dumps({"post_text": "又回到熟悉的街道", "hashtags": [], "emotion": "平静"})
        render_mock = AsyncMock(return_value="P")

        async def _cfg(key, default=None):
            return default

        with patch.object(fcs_mod, "get_life_feed_config", side_effect=_cfg), \
             patch.object(fcs_mod, "render_prompt", render_mock), \
             patch.object(fcs_mod.deepseek_llm_service, "call_llm",
                          new_callable=AsyncMock, return_value=llm), \
             patch.object(fcs_mod, "check_content", new_callable=AsyncMock,
                          return_value={"is_safe": True, "reason": ""}):
            draft = await feed_content_service.generate_post_text(
                _scene(city="苏州"), _failed_snapshot(), _PLAN_DATE
            )
        assert draft["travel_stage"] == "return"
        rendered_keys = [c.args[0] for c in render_mock.call_args_list]
        assert "prompt_p05_return" in rendered_keys


# ============ hashtag 抽签 ============

class TestHashtagDraw:
    @pytest.mark.asyncio
    async def test_zero_weight_hint(self, sqlite_session):
        overrides = {
            "feed_hashtag_count_0_weight": 100,
            "feed_hashtag_count_1_weight": 0,
            "feed_hashtag_count_2_weight": 0,
            "feed_hashtag_count_3_weight": 0,
        }
        count = 0
        for _ in range(20):
            with patch.object(fcs_mod, "get_life_feed_config",
                              side_effect=lambda k, d=None: overrides.get(k, d)):
                count = await feed_content_service._draw_hashtag_count()
                assert count == 0
        hint = feed_content_service._hashtag_hint(0)
        assert "不生成" in hint

    def test_hint_positive(self):
        assert "2" in feed_content_service._hashtag_hint(2)

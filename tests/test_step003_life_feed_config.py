# -*- coding: utf-8 -*-
# STEP-003 单元测试：生活流全局 admin_config 配置项与热加载
# 覆盖场景（对应 steps.md STEP-003 单测要求表）：
#   - 种子脚本幂等：二次执行不产生重复行
#   - level_to_stage(2) == "intimate"
#   - get_life_feed_config 命中默认值：key 不存在返回传入 default
#   - 缓存失效：invalidate 后走库取新值（通过 mock 验证 redis.delete 调用）
#   + 默认值与 PRD 一致性抽查（词汇表条数 / 关系档延迟单位秒）

from unittest.mock import AsyncMock, patch

import sqlalchemy as sa
import pytest

from backend.constants.life_feed_config import (
    DEFAULT_CATEGORIES_VOCAB,
    DEFAULT_EMOTION_VOCAB,
    RELATIONSHIP_STAGE_MAP,
    RELATIONSHIP_STAGE_ZH,
    build_seed_config_items,
    comment_reply_delay_key,
    level_to_stage,
)
from backend.scripts.seed_life_feed_config import seed


# ============ 关系档映射 ============

class TestRelationshipStageMap:
    def test_level_to_stage_intimate(self):
        assert level_to_stage(2) == "intimate"

    def test_all_levels(self):
        assert level_to_stage(0) == "stranger"
        assert level_to_stage(1) == "friend"
        assert level_to_stage(3) == "soulmate"

    def test_out_of_range_clamps(self):
        assert level_to_stage(-1) == "stranger"
        assert level_to_stage(99) == "soulmate"

    def test_map_and_zh_consistent(self):
        assert set(RELATIONSHIP_STAGE_MAP.values()) == set(RELATIONSHIP_STAGE_ZH.keys())


# ============ 默认值与 PRD 一致性 ============

class TestSeedDefaults:
    def test_categories_vocab_10_items(self):
        assert len(DEFAULT_CATEGORIES_VOCAB) == 10

    def test_emotion_vocab_14_items(self):
        assert len(DEFAULT_EMOTION_VOCAB) == 14

    def test_seed_items_unique_keys(self):
        items = build_seed_config_items()
        keys = [i["config_key"] for i in items]
        assert len(keys) == len(set(keys)), "种子 config_key 不允许重复"

    def test_comment_reply_delay_seconds_present(self):
        items = {i["config_key"]: i["config_value"] for i in build_seed_config_items()}
        # 陌生档评论回复 5-10 分钟 = 300-600 秒
        assert items[comment_reply_delay_key("stranger", "min")] == 300
        assert items[comment_reply_delay_key("stranger", "max")] == 600
        # 知己档 30 秒 - 1 分钟
        assert items[comment_reply_delay_key("soulmate", "min")] == 30
        assert items[comment_reply_delay_key("soulmate", "max")] == 60


# ============ 种子脚本幂等（SQLite 内存库）============

def _make_sqlite_engine_with_admin_config():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE admin_config ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "config_key VARCHAR(100) NOT NULL, "
            "config_value TEXT, "
            "version INTEGER DEFAULT 1, "
            "is_active BOOLEAN DEFAULT 1, "
            "is_draft BOOLEAN DEFAULT 0, "
            "updated_by VARCHAR(50), "
            "updated_at DATETIME)"
        ))
    return engine


class TestSeedIdempotent:
    def test_second_run_no_duplicate(self):
        engine = _make_sqlite_engine_with_admin_config()

        first = seed(engine)
        expected = len(build_seed_config_items())
        assert first["inserted"] == expected
        assert first["skipped"] == 0

        # 二次执行：全部跳过，无新增
        second = seed(engine)
        assert second["inserted"] == 0
        assert second["skipped"] == expected

        # 库中每个 key 只有一条生效版本
        with engine.begin() as conn:
            total = conn.execute(sa.text("SELECT COUNT(*) FROM admin_config")).scalar()
        assert total == expected


# ============ get_life_feed_config 与缓存失效 ============

class TestGetLifeFeedConfig:
    @pytest.mark.asyncio
    async def test_returns_default_when_missing(self):
        from backend.services import life_feed_config_service as svc

        with patch.object(
            svc.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value=None,
        ):
            result = await svc.get_life_feed_config("not_exist_key", default="兜底")
        assert result == "兜底"

    @pytest.mark.asyncio
    async def test_returns_value_when_present(self):
        from backend.services import life_feed_config_service as svc

        with patch.object(
            svc.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value=["工作", "旅游"],
        ):
            result = await svc.get_life_feed_config("categories_vocab", default=[])
        assert result == ["工作", "旅游"]

    @pytest.mark.asyncio
    async def test_invalidate_deletes_cache_key(self):
        from backend.services import life_feed_config_service as svc

        fake_redis = AsyncMock()
        with patch.object(
            svc, "get_redis", new_callable=AsyncMock, return_value=fake_redis,
        ):
            await svc.invalidate_life_feed_config_cache("home_city")

        fake_redis.delete.assert_awaited_once_with("active_config:home_city")

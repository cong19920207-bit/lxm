# -*- coding: utf-8 -*-
# STEP-004 单元测试：life_prompt_service.render_prompt + Prompt 种子
# 覆盖场景（对应 steps.md STEP-004 单测要求表）：
#   - 简单变量替换
#   - 可选段保留 / 删除
#   - persona 注入（从 active_config:persona 读取）
#   - 变量遗漏 → PromptRenderError
#   - 种子幂等（二次执行不重复、不覆盖）
#   + 全部 config_key 齐全性抽查

from unittest.mock import AsyncMock, patch

import sqlalchemy as sa
import pytest

from backend.constants.life_feed_prompts import (
    IMAGE_MAP_SEED,
    PROMPT_SEED,
    build_prompt_seed_items,
)
from backend.services import life_prompt_service as lps
from backend.services.life_prompt_service import PromptRenderError, _render_text
from backend.scripts.seed_life_feed_prompts import seed


# ============ render_prompt 纯逻辑 ============

class TestRenderText:
    @pytest.mark.asyncio
    async def test_simple_variable(self):
        out = await _render_text("你好 {{name}}", {"name": "小梦"})
        assert out == "你好 小梦"

    @pytest.mark.asyncio
    async def test_optional_segment_keep(self):
        out = await _render_text(
            "a[可选段·记忆]b[/可选段]c", {}, {"记忆": True}
        )
        assert out == "abc"

    @pytest.mark.asyncio
    async def test_optional_segment_drop(self):
        out = await _render_text(
            "a[可选段·记忆]b[/可选段]c", {}, {"记忆": False}
        )
        assert out == "ac"

    @pytest.mark.asyncio
    async def test_optional_segment_default_drop(self):
        # 未提供该可选段 → 默认删除
        out = await _render_text("a[可选段·记忆]b[/可选段]c", {})
        assert out == "ac"

    @pytest.mark.asyncio
    async def test_missing_variable_raises(self):
        with pytest.raises(PromptRenderError):
            await _render_text("剩余 {{unknown}}", {"name": "x"})

    @pytest.mark.asyncio
    async def test_persona_injection(self):
        with patch.object(
            lps.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value="我是林小梦，温柔细腻",
        ):
            out = await _render_text("人设：{{lxm_base_persona}}", {})
        assert out == "人设：我是林小梦，温柔细腻"

    @pytest.mark.asyncio
    async def test_persona_dict_joined(self):
        persona = {"bg": "来自2149", "trait": "温柔", "empty": ""}
        with patch.object(
            lps.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value=persona,
        ):
            out = await _render_text("{{lxm_base_persona}}", {})
        assert out == "来自2149\n温柔"


# ============ render_prompt 读模板 ============

class TestRenderPrompt:
    @pytest.mark.asyncio
    async def test_reads_template_by_key(self):
        with patch.object(
            lps.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value="你好 {{name}}",
        ):
            out = await lps.render_prompt("prompt_p01_system", {"name": "小梦"})
        assert out == "你好 小梦"

    @pytest.mark.asyncio
    async def test_missing_template_raises(self):
        with patch.object(
            lps.admin_config_service, "get_active_config",
            new_callable=AsyncMock, return_value=None,
        ):
            with pytest.raises(PromptRenderError):
                await lps.render_prompt("not_exist", {})


# ============ 种子齐全性 ============

class TestPromptSeedCompleteness:
    def test_all_prompt_keys_present(self):
        expected = {
            "prompt_p01_system", "prompt_p01_user",
            "prompt_p02_system", "prompt_p02_user",
            "prompt_p03_system", "prompt_p03_user",
            "prompt_p04_system", "prompt_p04_user",
            "prompt_p05_departure", "prompt_p05_transit",
            "prompt_p05_return", "prompt_p05_oneday",
            "prompt_p06_system", "prompt_p06_user",
            "prompt_p07_system", "prompt_p07_user",
            "prompt_p08_system", "prompt_p08_user",
            "prompt_p09_system", "prompt_p09_user",
            "prompt_p10_system", "prompt_p10_user",
            "prompt_p11_system", "prompt_p11_user",
            "prompt_p12_pos", "prompt_p12_neg",
            "prompt_p13a_pos", "prompt_p13a_neg",
            "prompt_p13b_pos", "prompt_p13b_neg",
            "prompt_p13c_pos", "prompt_p13c_neg",
            "prompt_p14_system", "prompt_p14_user",
        }
        assert set(PROMPT_SEED.keys()) == expected

    def test_six_image_maps(self):
        assert set(IMAGE_MAP_SEED.keys()) == {
            "venue_type_img_keyword", "category_img_keyword",
            "emotion_img_keyword", "emotion_atmosphere_desc",
            "emotion_fallback_img_keyword", "emotion_fallback_atmosphere_desc",
        }

    def test_category_img_keyword_full_coverage(self):
        # category_img_keyword 必须 100% 覆盖 10 项分类
        assert len(IMAGE_MAP_SEED["category_img_keyword"]) == 10

    def test_emotion_maps_cover_14(self):
        assert len(IMAGE_MAP_SEED["emotion_img_keyword"]) == 14
        assert len(IMAGE_MAP_SEED["emotion_atmosphere_desc"]) == 14

    def test_seed_items_unique_keys(self):
        keys = [i["config_key"] for i in build_prompt_seed_items()]
        assert len(keys) == len(set(keys))


# ============ 种子幂等 ============

def _make_sqlite_engine_with_admin_config():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE admin_config ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "config_key VARCHAR(100) NOT NULL, config_value TEXT, "
            "version INTEGER DEFAULT 1, is_active BOOLEAN DEFAULT 1, "
            "is_draft BOOLEAN DEFAULT 0, updated_by VARCHAR(50), updated_at DATETIME)"
        ))
    return engine


class TestPromptSeedIdempotent:
    def test_second_run_no_duplicate(self):
        engine = _make_sqlite_engine_with_admin_config()
        expected = len(build_prompt_seed_items())

        first = seed(engine)
        assert first["inserted"] == expected
        assert first["skipped"] == 0

        second = seed(engine)
        assert second["inserted"] == 0
        assert second["skipped"] == expected

        with engine.begin() as conn:
            total = conn.execute(sa.text("SELECT COUNT(*) FROM admin_config")).scalar()
        assert total == expected

    def test_no_overwrite_existing(self):
        engine = _make_sqlite_engine_with_admin_config()
        # 预置一条被运营手改的 P-01-S 生效版本
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO admin_config "
                "(config_key, config_value, version, is_active, is_draft, updated_by, updated_at) "
                "VALUES ('prompt_p01_system', '运营手改内容', 3, 1, 0, 'admin', :now)"
            ), {"now": "2026-01-01 00:00:00"})

        seed(engine)

        with engine.begin() as conn:
            val = conn.execute(sa.text(
                "SELECT config_value FROM admin_config "
                "WHERE config_key='prompt_p01_system' AND is_active=1 AND is_draft=0"
            )).scalar()
        assert val == "运营手改内容"

# -*- coding: utf-8 -*-
# STEP-018 单元测试：Step1 并行装载扩展 — round_context 构建与注入

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


# ============ 辅助工厂 ============


def _make_relationship(**overrides):
    """构造模拟 Relationship 对象（含 9 个扩展字段）"""
    defaults = {
        "id": 1,
        "user_id": 1,
        "level": 1,
        "growth_value": 300,
        "last_interaction_at": datetime.utcnow(),
        "consecutive_login_days": 5,
        "relation_description": None,
        "user_real_name": None,
        "user_hobby_name": None,
        "user_description": None,
        "character_purpose": None,
        "character_attitude": None,
        "future_timestamp": None,
        "future_action": None,
        "proactive_times": 0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ============ 测试场景1：扩展字段有值 → round_context 包含正确数据 ============


class TestBuildRoundContextWithValues:
    """relationship 扩展字段有值 → round_context 正确映射"""

    def test_all_fields_populated(self):
        from backend.routers.chat import _build_round_context

        rel = _make_relationship(
            level=2,
            relation_description="我们是亲密的朋友",
            user_real_name="张三",
            user_hobby_name="小三三",
            user_description="热爱运动，性格开朗",
            character_purpose="陪伴用户度过每一天",
            character_attitude="温柔体贴",
        )

        ctx = _build_round_context(
            relationship_info=rel,
            time_description="现在是周三下午15点00分",
            activity_description="她在写代码",
        )

        assert ctx["time_description"] == "现在是周三下午15点00分"
        assert ctx["activity_description"] == "她在写代码"
        assert ctx["relation_description"] == "我们是亲密的朋友"
        assert ctx["user_real_name"] == "张三"
        assert ctx["user_hobby_name"] == "小三三"
        assert ctx["user_description"] == "热爱运动，性格开朗"
        assert ctx["character_purpose"] == "陪伴用户度过每一天"
        assert ctx["character_attitude"] == "温柔体贴"
        assert ctx["level"] == 2
        assert ctx["level_name"] == "亲密"

    def test_silence_days_calculated(self):
        """silence_days 从 last_interaction_at 正确计算"""
        from backend.routers.chat import _build_round_context

        rel = _make_relationship(
            last_interaction_at=datetime.utcnow() - timedelta(days=10),
        )

        ctx = _build_round_context(
            relationship_info=rel,
            time_description="现在是周一早上9点00分",
            activity_description="",
        )

        assert ctx["silence_days"] == 10


# ============ 测试场景2：扩展字段全 NULL → 使用占位文案 ============


class TestBuildRoundContextNullFields:
    """扩展字段全 NULL → 使用占位文案"""

    def test_all_null_fields_use_fallback(self):
        from backend.routers.chat import _build_round_context

        rel = _make_relationship(
            relation_description=None,
            user_real_name=None,
            user_hobby_name=None,
            user_description=None,
            character_purpose=None,
            character_attitude=None,
        )

        ctx = _build_round_context(
            relationship_info=rel,
            time_description="现在是周一早上9点00分",
            activity_description="",
        )

        assert ctx["relation_description"] == "暂无，初次互动"
        assert ctx["user_real_name"] == ""
        assert ctx["user_hobby_name"] == ""
        assert ctx["user_description"] == ""
        assert ctx["character_purpose"] == ""
        assert ctx["character_attitude"] == ""


# ============ 测试场景3：时间描述串 + 活动描述串正确注入上下文 ============


class TestTimeActivityInjection:
    """时间/活动描述正确写入 round_context"""

    def test_time_and_activity_present(self):
        from backend.routers.chat import _build_round_context

        ctx = _build_round_context(
            relationship_info=_make_relationship(),
            time_description="现在是周五晚上21点30分",
            activity_description="她在看书",
        )

        assert ctx["time_description"] == "现在是周五晚上21点30分"
        assert ctx["activity_description"] == "她在看书"

    def test_empty_activity(self):
        """活动描述为空串时保留空串"""
        from backend.routers.chat import _build_round_context

        ctx = _build_round_context(
            relationship_info=_make_relationship(),
            time_description="现在是周一上午10点00分",
            activity_description="",
        )

        assert ctx["time_description"] == "现在是周一上午10点00分"
        assert ctx["activity_description"] == ""

    @pytest.mark.asyncio
    async def test_round_context_passed_to_build_time_prompt(self):
        """round_context 传入 build_chat_prompt 后，_build_time_prompt 使用预计算值"""
        from backend.services.prompt_builder import PromptBuilder

        mock_db = AsyncMock()
        builder = PromptBuilder(db=mock_db)

        round_ctx = {
            "time_description": "现在是周六中午12点00分",
            "activity_description": "她在吃午饭",
        }

        prompt = await builder._build_time_prompt(round_context=round_ctx)

        assert "现在是周六中午12点00分" in prompt
        assert "她在吃午饭" in prompt

    @pytest.mark.asyncio
    async def test_build_time_prompt_no_round_context_fallback(self):
        """round_context 为 None 时回退到自行生成"""
        from backend.services.prompt_builder import PromptBuilder

        mock_db = AsyncMock()
        builder = PromptBuilder(db=mock_db)

        with patch(
            "backend.services.prompt_builder.get_activity_description",
            new_callable=AsyncMock,
            return_value="",
        ):
            prompt = await builder._build_time_prompt(round_context=None)

        assert "【当前时间】" in prompt
        assert "现在是" in prompt


# ============ 边界测试：新用户无 relationship 行 ============


class TestNewUserNoRelationship:
    """relationship_info 为 None → get_or_create 后扩展字段为空的等价场景"""

    def test_none_relationship_info(self):
        from backend.routers.chat import _build_round_context

        ctx = _build_round_context(
            relationship_info=None,
            time_description="现在是周日凌晨3点00分",
            activity_description="",
        )

        assert ctx["level"] == 0
        assert ctx["level_name"] == "陌生"
        assert ctx["silence_days"] == 999
        assert ctx["relation_description"] == "暂无，初次互动"
        assert ctx["user_real_name"] == ""
        assert ctx["user_hobby_name"] == ""
        assert ctx["user_description"] == ""
        assert ctx["character_purpose"] == ""
        assert ctx["character_attitude"] == ""
        assert ctx["time_description"] == "现在是周日凌晨3点00分"
        assert ctx["activity_description"] == ""


# ============ R-L1L3-01：chat_send gather 不再读取 relationship ============


class TestChatSendGatherNoRelationship:
    """验证 chat_send 的 gather 中已不包含 _get_relationship"""

    def test_get_relationship_not_in_gather(self):
        """静态检查：chat_send 源码 gather 调用中不含 _get_relationship"""
        import inspect
        from backend.routers.chat import chat_send

        source = inspect.getsource(chat_send)
        gather_start = source.index("asyncio.gather")
        gather_end = source.index(")", gather_start)
        gather_block = source[gather_start:gather_end]
        assert "_get_relationship" not in gather_block


# ============ R-L1L3-06：Step5.5 / Step6 共用同一份 round_context ============


class TestRoundContextSharedBySteps:
    """round_context 在 _execute_llm_bundle 内只构建一次，Step5.5 和 Step6 共用"""

    def test_round_context_keys_complete(self):
        """round_context 包含 Step5.5 / Step6 所需的所有字段"""
        from backend.routers.chat import _build_round_context

        rel = _make_relationship(
            level=3,
            relation_description="知己",
            user_real_name="李四",
            user_hobby_name="四儿",
            user_description="安静内敛",
            character_purpose="成为最好的陪伴",
            character_attitude="永远支持",
        )

        ctx = _build_round_context(
            relationship_info=rel,
            time_description="t",
            activity_description="a",
        )

        required_keys = {
            "time_description", "activity_description",
            "relation_description", "user_real_name", "user_hobby_name",
            "user_description", "character_purpose", "character_attitude",
            "level", "level_name", "silence_days",
        }
        assert required_keys.issubset(ctx.keys())
